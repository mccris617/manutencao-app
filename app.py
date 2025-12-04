# app.py — Sistema de Manutenção Preventiva (com sistema de múltiplas tabelas - COMPLETO)
import streamlit as st
from datetime import datetime, timedelta
from supabase_client import get_supabase_client
from fpdf import FPDF
import os
import re
import uuid
import json
from streamlit_drawable_canvas import st_canvas
from streamlit_calendar import calendar
from math import floor
import tempfile
import shutil

supabase = get_supabase_client()

# Estados da sessão
if "show_new_form" not in st.session_state:
    st.session_state["show_new_form"] = False
if "show_history" not in st.session_state:
    st.session_state["show_history"] = False
if "selected_task" not in st.session_state:
    st.session_state["selected_task"] = None
if "view_mode" not in st.session_state:
    st.session_state["view_mode"] = "list"
if "show_clone_form" not in st.session_state:
    st.session_state["show_clone_form"] = False
if "cloning_task_id" not in st.session_state:
    st.session_state["cloning_task_id"] = None
if "clone_form_data" not in st.session_state:
    st.session_state["clone_form_data"] = {}
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = {}
if "expanded_groups" not in st.session_state:
    st.session_state["expanded_groups"] = {
        "scheduled": True,
        "in_progress": True,
        "completed": True,
        "overdue": True
    }
if "checklist_expanded" not in st.session_state:
    st.session_state["checklist_expanded"] = {}
if "checklist_states" not in st.session_state:
    st.session_state["checklist_states"] = {}
if "editing_task_id" not in st.session_state:
    st.session_state["editing_task_id"] = None
if "editing_field" not in st.session_state:
    st.session_state["editing_field"] = None
if "show_edit_form" not in st.session_state:
    st.session_state["show_edit_form"] = False
if "editing_task_data" not in st.session_state:
    st.session_state["editing_task_data"] = {}

# NOVO: Estado para MÚLTIPLAS tabelas de materiais
if "materials_tables" not in st.session_state:
    st.session_state["materials_tables"] = [
        {
            "id": str(uuid.uuid4()),
            "name": "Tabela de Materiais 1",
            "rows": 3,
            "cols": 4,
            "data": [
                ["", "", "", ""],
                ["", "", "", ""],
                ["", "", "", ""]
            ],
            "headers": ["Material", "Quantidade", "Unidade", "Observações"],
            "show_editor": False,
            "has_data": False
        }
    ]

# NOVO: Estado para gerenciador de tabelas
if "show_tables_manager" not in st.session_state:
    st.session_state["show_tables_manager"] = False

status_labels = {
    "scheduled": "📅 Agendada",
    "in_progress": "🛠️ Em Execução",
    "completed": "✅ Concluída",
    "overdue": "❗ Atrasada",
    "unscheduled": "⏳ Não Programada"
}

COLORS = {
    "Refrigeração": "#e3f2fd",
    "Elétrica": "#fff8e1",
    "Hidráulica": "#f3e5f5",
    "Mecânica": "#e8f5e9",
    "Outra": "#eeeeee"
}

PRIORITIES = {
    "missao_critica": {"label": "MISSÃO CRÍTICA", "color": "#ff4444", "pdf_label": "MISSÃO CRÍTICA"},
    "alta": {"label": "ALTA", "color": "#ff6b6b", "pdf_label": "ALTA"},
    "media": {"label": "MÉDIA", "color": "#ffd93d", "pdf_label": "MÉDIA"},
    "baixa": {"label": "BAIXA", "color": "#6bcf7f", "pdf_label": "BAIXA"}
}
PRIORITIES_WITH_EMOJIS = {
    "missao_critica": {"label": "🚨 Missão Crítica", "color": "#ff4444"},
    "alta": {"label": "🔴 Alta", "color": "#ff6b6b"},
    "media": {"label": "🟡 Média", "color": "#ffd93d"},
    "baixa": {"label": "🟢 Baixa", "color": "#6bcf7f"}
}

st.markdown("""
<style>
.card { border: 1px solid #e0e0e0; border-radius: 12px; padding: 12px; margin-bottom: 10px; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.card:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.15); }
.priority-badge { padding: 4px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; display: inline-block; }
.checklist-item-completed { text-decoration: line-through; color: #888; }
.unscheduled-card { background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border: 2px dashed #dee2e6; }
.editing-field { background-color: #fff3cd; border: 2px solid #ffc107; border-radius: 4px; padding: 4px; }
.multi-select-info { background: #e7f3ff; padding: 8px; border-radius: 6px; margin: 8px 0; }
.multi-tech-info { background: #fff3cd; padding: 8px; border-radius: 6px; margin: 8px 0; }
.materials-table-view { border-collapse: collapse; width: 100%; margin: 10px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.materials-table-view th { background-color: #4CAF50; color: white; padding: 12px; text-align: left; border: 1px solid #ddd; }
.materials-table-view td { border: 1px solid #ddd; padding: 8px; }
.materials-table-view tr:nth-child(even) { background-color: #f2f2f2; }
.notes-with-table { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #4CAF50; }
.table-tab { margin: 5px; }
.table-editor-section { border: 2px solid #4CAF50; border-radius: 8px; padding: 15px; margin: 10px 0; background-color: #f8f9fa; }
.table-preview-section { border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; }
.stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ----------- Funções Auxiliares -----------
def load_technicians():
    res = supabase.table("technicians").select("*").execute()
    return {t["id"]: t for t in res.data} if res.data else {}

def load_locations():
    res = supabase.table("locations").select("*").execute()
    return {l["id"]: l["name"] for l in res.data} if res.data else {}

def get_technician_name(tech_id, tech_dict):
    if not tech_id:
        return "Não atribuído"
    return tech_dict.get(str(tech_id), {}).get("name", "Não atribuído")

def get_location_name(loc_id, loc_dict):
    return loc_dict.get(str(loc_id), "—")

def get_specialties_list():
    res = supabase.table("technicians").select("specialty").execute()
    specialties = {r["specialty"] for r in res.data if r.get("specialty")}
    return sorted(specialties) if specialties else ["Refrigeração", "Elétrica", "Hidráulica", "Mecânica"]

def load_checklist(task_id):
    try:
        res = supabase.table("checklists").select("*").eq("task_id", task_id).execute()
        return [{"id": item["id"], "item": item["item"], "is_completed": item["is_completed"]} for item in res.data] if res.data else []
    except Exception as e:
        st.error(f"Erro ao carregar checklist: {str(e)}")
        return []

def get_priority_badge(priority):
    priority_info = PRIORITIES_WITH_EMOJIS.get(priority, PRIORITIES_WITH_EMOJIS["media"])
    return f'<span class="priority-badge" style="background-color: {priority_info["color"]}20; color: {priority_info["color"]}; border: 1px solid {priority_info["color"]};">{priority_info["label"]}</span>'

def sanitize_filename(filename):
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    unique_id = str(uuid.uuid4())[:8]
    return f"{name}_{unique_id}{ext}"

def handle_file_upload(task_id, uploaded_file):
    try:
        upload_key = f"{task_id}_{uploaded_file.name}_{uploaded_file.size}"
        if upload_key in st.session_state.uploaded_files:
            st.warning("📎 Este arquivo já foi enviado.")
            return
        safe_filename = sanitize_filename(uploaded_file.name)
        file_path = f"{task_id}/{safe_filename}"
        supabase.storage.from_("task-attachments").upload(file_path, uploaded_file.getvalue(), file_options={"content-type": uploaded_file.type})
        st.session_state.uploaded_files[upload_key] = True
        st.toast("✅ Imagem anexada!", icon="🖼️")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao enviar: {str(e)}")

def load_attachments(task_id):
    try:
        return supabase.storage.from_("task-attachments").list(task_id) or []
    except:
        return []

def get_attachment_url(task_id, filename):
    try:
        return supabase.storage.from_("task-attachments").get_public_url(f"{task_id}/{filename}")
    except:
        return None

def is_image_file(filepath):
    return filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'))

def download_attachments_to_temp(task_id, attachments):
    if not attachments:
        return [], None
    temp_dir = tempfile.mkdtemp()
    image_paths = []
    for att in attachments:
        if not is_image_file(att['name']):
            continue
        try:
            file_path = f"{task_id}/{att['name']}"
            file_data = supabase.storage.from_("task-attachments").download(file_path)
            local_path = os.path.join(temp_dir, att['name'])
            with open(local_path, 'wb') as f:
                f.write(file_data)
            image_paths.append(local_path)
        except:
            pass
    return image_paths, temp_dir

# ----------- Recorrência e Status Automático -----------
def get_next_due_date(due_date, recurrence):
    if recurrence == "daily": return due_date + timedelta(days=1)
    elif recurrence == "weekly": return due_date + timedelta(weeks=1)
    elif recurrence == "monthly":
        if due_date.month == 12:
            return due_date.replace(year=due_date.year + 1, month=1)
        else:
            return due_date.replace(month=due_date.month + 1)
    return None

def archive_task(task, checklist_items):
    try:
        archive_data = {
            "task_id": task["id"],
            "title": task["title"],
            "description": task.get("description"),
            "specialty": task.get("specialty"),
            "technician_id": task.get("technician_id"),
            "location_id": task.get("location_id"),
            "due_date": task["due_date"],
            "completed_at": datetime.now().isoformat(),
            "checklist": [{"item": i["text"], "is_completed": i["checked"]} for i in checklist_items],
            "recurrence": task.get("recurrence"),
            "notes": task.get("notes", "")
        }
        supabase.table("task_history").insert(archive_data).execute()
    except Exception as e:
        st.toast(f"⚠️ Erro ao arquivar: {str(e)}", icon="⚠️")

def create_recurring_task(original_task):
    recurrence = original_task.get("recurrence")
    if not recurrence: return
    try:
        current_due = datetime.fromisoformat(original_task["due_date"])
        next_due = get_next_due_date(current_due, recurrence)
        if not next_due: return

        new_task = {
            "title": original_task["title"],
            "description": original_task.get("description"),
            "specialty": original_task.get("specialty"),
            "technician_id": original_task.get("technician_id"),
            "location_id": original_task.get("location_id"),
            "due_date": next_due.isoformat(),
            "recurrence": recurrence,
            "status": "scheduled",
            "notes": original_task.get("notes", ""),
            "priority": original_task.get("priority", "media")
        }
        res = supabase.table("maintenance_tasks").insert(new_task).execute()
        new_task_id = res.data[0]["id"] if res.data else None

        if not new_task_id: return

        checklist_data = load_checklist(original_task["id"])
        if checklist_data:
            for item in checklist_data:
                supabase.table("checklists").insert({
                    "task_id": new_task_id,
                    "item": item["item"],
                    "is_completed": False
                }).execute()

        next_date_str = next_due.strftime('%d/%m/%Y')
        st.toast(f"🔁 Tarefa recorrente agendada para {next_date_str}", icon="🔁")

    except Exception as e:
        st.toast(f"⚠️ Erro na recorrência: {str(e)}", icon="⚠️")

def update_overdue_tasks():
    """Atualiza status de tarefas agendadas que estão atrasadas"""
    now = datetime.now()
    
    try:
        scheduled_tasks = supabase.table("maintenance_tasks").select("*").eq("status", "scheduled").execute()
        
        overdue_count = 0
        for task in scheduled_tasks.data:
            if task.get("due_date"):
                try:
                    due_date = datetime.fromisoformat(task["due_date"])
                    if due_date < now:
                        supabase.table("maintenance_tasks").update({"status": "overdue"}).eq("id", task["id"]).execute()
                        overdue_count += 1
                except Exception as e:
                    print(f"Erro ao processar data da tarefa {task['id']}: {e}")
        
        if overdue_count > 0:
            st.toast(f"❗ {overdue_count} tarefa(s) marcada(s) como atrasada(s)", icon="❗")
            
    except Exception as e:
        print(f"Erro ao atualizar tarefas atrasadas: {e}")

def determine_task_status(due_datetime, is_scheduled=True):
    """Determina o status correto da tarefa baseado na data"""
    if not is_scheduled or not due_datetime:
        # IMPORTANTE: O banco de dados não aceita "unscheduled" como status válido
        # Mapeamos para "scheduled" quando não há data
        return "scheduled"
    
    try:
        if isinstance(due_datetime, str):
            due_date = datetime.fromisoformat(due_datetime)
        else:
            due_date = due_datetime
        
        now = datetime.now()
        
        if due_date > now:
            return "scheduled"
        else:
            return "overdue"
            
    except Exception as e:
        print(f"Erro ao determinar status: {e}")
        return "scheduled"

# ----------- FUNÇÕES PARA MÚLTIPLAS TABELAS DE MATERIAIS -----------

def show_materials_table_editor(table_idx=None):
    """Mostra o editor de tabela de materiais para uma tabela específica"""
    if table_idx is None:
        return
    
    table = st.session_state["materials_tables"][table_idx]
    
    st.markdown(f"#### 📊 {table['name']}")
    
    with st.container(border=True):
        # Configurações da tabela
        col1, col2, col3 = st.columns(3)
        with col1:
            rows = st.number_input("Número de linhas", min_value=1, max_value=20, 
                                  value=table["rows"], 
                                  key=f"mat_rows_{table_idx}")
        with col2:
            cols = st.number_input("Número de colunas", min_value=2, max_value=6, 
                                  value=table["cols"], 
                                  key=f"mat_cols_{table_idx}")
        with col3:
            table_name = st.text_input("Nome da tabela", 
                                      value=table["name"],
                                      key=f"table_name_{table_idx}")
        
        # Botão para atualizar configuração
        if st.button("🔄 Atualizar Configuração", 
                    key=f"update_config_{table_idx}",
                    use_container_width=True):
            st.session_state["materials_tables"][table_idx]["rows"] = rows
            st.session_state["materials_tables"][table_idx]["cols"] = cols
            st.session_state["materials_tables"][table_idx]["name"] = table_name
            st.rerun()
        
        st.divider()
        
        # Definir cabeçalhos personalizáveis
        st.markdown("**Cabeçalhos das colunas:**")
        header_cols = st.columns(cols)
        for i in range(cols):
            with header_cols[i]:
                if i < len(table["headers"]):
                    default_header = table["headers"][i]
                elif i == 0:
                    default_header = "Material"
                elif i == 1:
                    default_header = "Quantidade"
                elif i == 2:
                    default_header = "Unidade"
                elif i == 3:
                    default_header = "Observações"
                else:
                    default_header = f"Coluna {i+1}"
                    
                header = st.text_input(f"Coluna {i+1}", value=default_header, 
                                     key=f"header_{table_idx}_{i}")
                if header != table["headers"][i] if i < len(table["headers"]) else True:
                    # Atualizar cabeçalho se necessário
                    if i >= len(table["headers"]):
                        table["headers"].append(header)
                    else:
                        table["headers"][i] = header
        
        st.divider()
        
        # Exibir tabela editável - INTERATIVA (sem botão de salvar por linha)
        st.markdown("**Preencha os dados da tabela (edite diretamente):**")
        
        # Garantir que os dados têm o tamanho correto
        if len(table["data"]) != rows or (table["data"] and len(table["data"][0]) != cols):
            # Redimensionar dados
            new_data = []
            for r in range(rows):
                row = []
                for c in range(cols):
                    if r < len(table["data"]) and c < len(table["data"][0]):
                        row.append(table["data"][r][c])
                    else:
                        row.append("")
                new_data.append(row)
            table["data"] = new_data
        
        # Renderizar tabela editável
        for r in range(rows):
            row_cols = st.columns(cols)
            for c in range(cols):
                with row_cols[c]:
                    # Campo de entrada interativo
                    current_value = table["data"][r][c]
                    new_value = st.text_input(
                        f"",
                        value=current_value,
                        key=f"cell_{table_idx}_{r}_{c}",
                        label_visibility="collapsed",
                        placeholder=f"Linha {r+1}, Coluna {c+1}"
                    )
                    # Atualizar automaticamente (não precisa de botão de salvar)
                    if new_value != current_value:
                        table["data"][r][c] = new_value
                        # Verificar se há dados
                        has_any_data = any(
                            any(cell.strip() for cell in row) 
                            for row in table["data"]
                        )
                        table["has_data"] = has_any_data
        
        st.divider()
        
        # Botões de ação
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("➕ Adicionar Linha", key=f"add_row_{table_idx}", use_container_width=True):
                new_row = ["" for _ in range(cols)]
                table["data"].append(new_row)
                table["rows"] += 1
                st.rerun()
        with col2:
            if st.button("🗑️ Limpar Tabela", key=f"clear_table_{table_idx}", use_container_width=True):
                table["data"] = [["" for _ in range(cols)] for _ in range(rows)]
                table["has_data"] = False
                st.rerun()
        with col3:
            if st.button("❌ Remover Tabela", key=f"remove_table_{table_idx}", use_container_width=True, type="secondary"):
                if len(st.session_state["materials_tables"]) > 1:
                    st.session_state["materials_tables"].pop(table_idx)
                    st.rerun()
                else:
                    st.warning("Não é possível remover a última tabela")

def materials_tables_to_text():
    """Converte todas as tabelas de materiais para formato de texto"""
    if not any(table["has_data"] for table in st.session_state["materials_tables"]):
        return ""
    
    text = "\n\n📋 **LISTA DE MATERIAIS:**\n\n"
    
    for table_idx, table in enumerate(st.session_state["materials_tables"]):
        if table["has_data"]:
            # Adicionar nome da tabela
            text += f"**{table['name']}**\n\n"
            
            # Criar tabela formatada
            headers = table["headers"]
            data = table["data"]
            
            # Adicionar cabeçalhos
            header_line = "| " + " | ".join(headers) + " |"
            separator = "|" + "|".join(["---" for _ in headers]) + "|"
            text += header_line + "\n" + separator + "\n"
            
            # Adicionar dados
            for row in data:
                if any(cell.strip() for cell in row):
                    row_line = "| " + " | ".join([cell if cell.strip() else "—" for cell in row]) + " |"
                    text += row_line + "\n"
            
            text += "\n\n"
    
    return text

def materials_tables_to_html():
    """Converte todas as tabelas de materiais para HTML (para PDF)"""
    html_tables = []
    
    for table in st.session_state["materials_tables"]:
        if table["has_data"]:
            headers = table["headers"]
            data = table["data"]
            
            html = f"""
            <div style="margin: 20px 0;">
            <h4 style="color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 5px;">{table['name']}</h4>
            <table style="border-collapse: collapse; width: 100%; margin-top: 10px; font-family: Arial, sans-serif;">
            <thead>
            <tr style="background-color: #4CAF50; color: white;">
            """
            
            for header in headers:
                html += f'<th style="border: 1px solid #ddd; padding: 8px; text-align: left; font-weight: bold;">{header}</th>'
            
            html += "</tr></thead><tbody>"
            
            for row in data:
                if any(cell.strip() for cell in row):
                    html += "<tr>"
                    for cell in row:
                        html += f'<td style="border: 1px solid #ddd; padding: 6px;">{cell if cell.strip() else "—"}</td>'
                    html += "</tr>"
            
            html += "</tbody></table></div>"
            html_tables.append(html)
    
    return "\n".join(html_tables)

def combine_notes_with_tables(original_notes, tables_text):
    """Combina observações originais com tabelas de materiais"""
    if not tables_text:
        return original_notes
    
    # Se já existem tabelas nas observações, substituir
    if "📋 **LISTA DE MATERIAIS:**" in original_notes:
        parts = original_notes.split("📋 **LISTA DE MATERIAIS:**")
        if len(parts) > 1:
            # Manter apenas a parte antes das tabelas
            clean_notes = parts[0].strip()
        else:
            clean_notes = original_notes
    else:
        clean_notes = original_notes.strip()
    
    # Combinar observações com novas tabelas
    if clean_notes:
        return clean_notes + tables_text
    else:
        return tables_text

def show_materials_tables_manager():
    """Mostra o gerenciador de múltiplas tabelas"""
    st.markdown("#### 📋 Gerenciador de Tabelas de Materiais")
    
    # Criar tabs para cada tabela
    tab_titles = [f"{table['name']}" for table in st.session_state["materials_tables"]]
    tab_titles.append("➕ Nova Tabela")
    
    tabs = st.tabs(tab_titles)
    
    # Tabs para cada tabela existente
    for i, tab in enumerate(tabs[:-1]):  # Excluir a última tab (nova tabela)
        with tab:
            show_materials_table_editor(i)
    
    # Última tab para adicionar nova tabela
    with tabs[-1]:
        st.markdown("#### ➕ Criar Nova Tabela de Materiais")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            new_name = st.text_input("Nome da nova tabela", value=f"Tabela de Materiais {len(st.session_state['materials_tables']) + 1}")
        with col2:
            new_rows = st.number_input("Linhas", min_value=1, max_value=20, value=3)
        with col3:
            new_cols = st.number_input("Colunas", min_value=2, max_value=6, value=4)
        
        if st.button("✅ Criar Nova Tabela", use_container_width=True, type="primary"):
            new_table = {
                "id": str(uuid.uuid4()),
                "name": new_name,
                "rows": new_rows,
                "cols": new_cols,
                "data": [["" for _ in range(new_cols)] for _ in range(new_rows)],
                "headers": ["Material", "Quantidade", "Unidade", "Observações"][:new_cols],
                "show_editor": False,
                "has_data": False
            }
            st.session_state["materials_tables"].append(new_table)
            st.success(f"✅ Nova tabela '{new_name}' criada!")
            st.rerun()
    
    # Visualização consolidada
    st.divider()
    st.markdown("#### 👁️ Visualização Consolidada")
    
    has_any_data = any(table["has_data"] for table in st.session_state["materials_tables"])
    
    if has_any_data:
        for table in st.session_state["materials_tables"]:
            if table["has_data"]:
                st.markdown(f"**{table['name']}**")
                
                table_html = '<table class="materials-table-view"><thead><tr>'
                
                for header in table["headers"]:
                    table_html += f"<th>{header}</th>"
                table_html += "</tr></thead><tbody>"
                
                for row in table["data"]:
                    if any(cell.strip() for cell in row):
                        table_html += "<tr>"
                        for cell in row:
                            table_html += f"<td>{cell if cell.strip() else '—'}</td>"
                        table_html += "</tr>"
                
                table_html += "</tbody></table>"
                st.markdown(table_html, unsafe_allow_html=True)
                
                # Contar itens
                item_count = sum(1 for row in table["data"] if any(cell.strip() for cell in row))
                st.caption(f"Total de itens nesta tabela: {item_count}")
                st.divider()
    else:
        st.info("Nenhuma tabela contém dados. Preencha as tabelas acima.")

# ----------- PDF -----------
def clean_text_for_pdf(text):
    if text is None: return ""
    text = str(text)
    replacements = {'á':'a', 'à':'a', 'ã':'a', 'â':'a', 'ä':'a', 'é':'e', 'è':'e', 'ê':'e', 'ë':'e',
                    'í':'i', 'ì':'i', 'î':'i', 'ï':'i', 'ó':'o', 'ò':'o', 'õ':'o', 'ô':'o', 'ö':'o',
                    'ú':'u', 'ù':'u', 'û':'u', 'ü':'u', 'ç':'c', 'Á':'A', 'À':'A', 'Ã':'A', 'Â':'A',
                    'É':'E', 'È':'E', 'Í':'I', 'Ì':'I', 'Ó':'O', 'Ò':'O', 'Ú':'U', 'Ù':'U', 'Ç':'C', 'ñ':'n', 'Ñ':'N'}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode('ascii', 'ignore').decode('ascii')

def generate_pdf(task, technician_name, location_name, checklist_items, image_paths=None):
    if image_paths is None: image_paths = []
    image_paths = [p for p in image_paths if is_image_file(p) and os.path.isfile(p)]
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "RELATORIO DE MANUTENCAO PREVENTIVA", ln=True, align='C')
    pdf.ln(10)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "INFORMACOES DA ATIVIDADE", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 6, "Titulo:", 0)
    pdf.set_font("Arial", "", 10)
    title_clean = clean_text_for_pdf(task['title'])
    pdf.multi_cell(0, 6, title_clean)
    pdf.ln(2)
    if task.get('description'):
        pdf.set_font("Arial", "B", 10)
        pdf.cell(40, 6, "Descricao:", 0)
        pdf.set_font("Arial", "", 10)
        desc_clean = clean_text_for_pdf(task['description'])
        pdf.multi_cell(0, 6, desc_clean)
        pdf.ln(2)
    col_width = 95
    y_start = pdf.get_y()
    pdf.set_x(10)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(30, 6, "Especialidade:", 0)
    pdf.set_font("Arial", "", 10)
    specialty_clean = clean_text_for_pdf(task.get('specialty', '-'))
    pdf.cell(0, 6, specialty_clean, ln=True)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(30, 6, "Tecnico:", 0)
    pdf.set_font("Arial", "", 10)
    tech_clean = clean_text_for_pdf(technician_name)
    pdf.cell(0, 6, tech_clean, ln=True)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(30, 6, "Local:", 0)
    pdf.set_font("Arial", "", 10)
    loc_clean = clean_text_for_pdf(location_name)
    pdf.cell(0, 6, loc_clean, ln=True)
    pdf.set_xy(10 + col_width, y_start)
    due_date = task['due_date'][:10] if task['due_date'] else "Não programada"
    due_time = task['due_date'][11:16] if task['due_date'] else "—"
    pdf.set_font("Arial", "B", 10)
    pdf.cell(25, 6, "Data:", 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, due_date, ln=True)
    pdf.set_x(10 + col_width)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(25, 6, "Hora:", 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, due_time, ln=True)
    pdf.set_x(10 + col_width)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(25, 6, "Prioridade:", 0)
    pdf.set_font("Arial", "", 10)
    priority_info = PRIORITIES.get(task.get('priority', 'media'), PRIORITIES['media'])
    pdf.cell(0, 6, priority_info['pdf_label'], ln=True)
    pdf.set_x(10 + col_width)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(25, 6, "Status:", 0)
    pdf.set_font("Arial", "", 10)
    status_map = {"scheduled": "AGENDADA", "in_progress": "EM EXECUCAO", "completed": "CONCLUIDA", "overdue": "ATRASADA"}
    status_text = status_map.get(task["status"], task["status"].upper())
    pdf.cell(0, 6, status_text, ln=True)
    pdf.ln(10)
    
    # Adicionar tabelas de materiais se existirem
    materials_html = materials_tables_to_html()
    if materials_html:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "LISTA DE MATERIAIS", ln=True)
        pdf.ln(5)
        
        # Converter HTML para PDF manualmente
        for table in st.session_state["materials_tables"]:
            if table["has_data"]:
                # Nome da tabela
                pdf.set_font("Arial", "B", 10)
                pdf.cell(0, 8, clean_text_for_pdf(table['name']), ln=True)
                pdf.ln(2)
                
                headers = table["headers"]
                data = table["data"]
                
                # Calcular larguras das colunas
                col_widths = [40, 30, 25, 95]
                if len(headers) == 4:
                    col_widths = [50, 30, 25, 85]
                elif len(headers) == 5:
                    col_widths = [40, 30, 25, 30, 65]
                elif len(headers) == 6:
                    col_widths = [35, 25, 20, 25, 30, 45]
                
                # Cabeçalho da tabela
                pdf.set_fill_color(79, 175, 80)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", "B", 9)
                
                for i, header in enumerate(headers):
                    if i < len(col_widths):
                        pdf.cell(col_widths[i], 8, clean_text_for_pdf(header), 1, 0, 'C', True)
                pdf.ln()
                
                # Conteúdo da tabela
                pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Arial", "", 9)
                
                for row in data:
                    if any(cell.strip() for cell in row):
                        for i, cell in enumerate(row):
                            if i < len(col_widths):
                                cell_text = clean_text_for_pdf(cell) if cell.strip() else "—"
                                if i == 0:
                                    pdf.set_font("Arial", "B", 9)
                                    pdf.cell(col_widths[i], 8, cell_text, 1)
                                    pdf.set_font("Arial", "", 9)
                                else:
                                    pdf.cell(col_widths[i], 8, cell_text, 1)
                        pdf.ln()
                
                pdf.ln(5)
    
    if checklist_items:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "CHECKLIST", ln=True)
        pdf.ln(5)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(15, 8, "#", 1, 0, 'C', True)
        pdf.cell(15, 8, "Status", 1, 0, 'C', True)
        pdf.cell(0, 8, "Item", 1, 1, 'C', True)
        pdf.set_font("Arial", "", 10)
        for i, item in enumerate(checklist_items, 1):
            pdf.cell(15, 8, str(i), 1, 0, 'C')
            status = "X" if item.get("checked", False) else "-"
            pdf.cell(15, 8, status, 1, 0, 'C')
            item_text = clean_text_for_pdf(item['text'])
            if pdf.get_string_width(item_text) > 160:
                words = item_text.split(' ')
                current_line = ""
                lines = []
                for word in words:
                    test_line = current_line + word + " "
                    if pdf.get_string_width(test_line) < 160:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line.strip())
                        current_line = word + " "
                if current_line:
                    lines.append(current_line.strip())
                pdf.cell(0, 8, lines[0], 1, 1)
                for line in lines[1:]:
                    pdf.cell(30, 8, "", 0, 0)
                    pdf.cell(0, 8, line, 1, 1)
            else:
                pdf.cell(0, 8, item_text, 1, 1)
        pdf.ln(10)
    if task.get('notes'):
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "OBSERVACOES TECNICAS", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "", 10)
        notes_clean = clean_text_for_pdf(task['notes'])
        pdf.multi_cell(0, 6, notes_clean)
        pdf.ln(8)
    if image_paths:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "REGISTROS FOTOGRÁFICOS", ln=True)
        pdf.ln(5)
        margin = 10
        spacing = 5
        thumb_width = 90
        max_height = 70
        cols = 2
        for idx, img_path in enumerate(image_paths):
            if idx % cols == 0:
                if idx > 0:
                    pdf.ln(max_height + 12)
                x_start = margin
            else:
                x_start = margin + thumb_width + spacing
            y_start = pdf.get_y()
            try:
                pdf.image(img_path, x=x_start, y=y_start, w=thumb_width)
                img_height = pdf.get_y() - y_start
                new_y = y_start + max(img_height, max_height) + 10
                pdf.set_y(new_y)
            except:
                pdf.set_xy(x_start, y_start)
                pdf.set_font("Arial", "I", 8)
                pdf.set_text_color(200, 0, 0)
                pdf.cell(thumb_width, max_height, "Imagem indisponível", align='C', border=1)
                pdf.set_text_color(0, 0, 0)
                pdf.set_y(y_start + max_height + 10)
        pdf.ln(10)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 8, "ASSINATURAS", ln=True)
    pdf.ln(8)
    pdf.cell(80, 6, "Tecnico: _________________________", 0, 0)
    pdf.cell(50, 6, "", 0, 0)
    pdf.cell(0, 6, "Data: ___/___/_______", 0, 1)
    pdf.ln(15)
    pdf.cell(80, 6, "Supervisor: _________________________", 0, 0)
    pdf.cell(50, 6, "", 0, 0) 
    pdf.cell(0, 6, "Data: ___/___/_______", 0, 1)
    pdf.ln(20)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 6, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 0, 'C')
    return bytes(pdf.output(dest='S'))

# ----------- Formulário de Edição Completa -----------
def show_edit_form(task_id):
    """Mostra formulário de edição completa de uma tarefa com tabelas de materiais"""
    st.subheader("✏️ Editar Atividade")
    
    # Carregar dados da tarefa
    task_res = supabase.table("maintenance_tasks").select("*").eq("id", task_id).execute()
    if not task_res.data:
        st.error("❌ Tarefa não encontrada")
        if st.button("Fechar", use_container_width=True):
            st.session_state["show_edit_form"] = False
            st.rerun()
        return
    
    task = task_res.data[0]
    checklist_data = load_checklist(task_id)
    
    # Botão para abrir gerenciador de tabelas (FORA do formulário)
    if st.button("📊 Gerenciador de Tabelas de Materiais", use_container_width=True, 
                key="open_mat_manager_edit"):
        st.session_state["show_tables_manager"] = not st.session_state.get("show_tables_manager", False)
        st.rerun()
    
    # Mostrar gerenciador se solicitado (FORA do formulário)
    if st.session_state.get("show_tables_manager", False):
        show_materials_tables_manager()
        st.markdown("---")
    
    with st.form("edit_activity_form"):
        st.markdown("#### 📝 Informações Básicas")
        title = st.text_input("Título *", value=task.get("title", ""))
        description = st.text_area("Descrição", value=task.get("description", ""))
        
        col1, col2 = st.columns(2)
        with col1:
            specialty = st.selectbox("Especialidade *", get_specialties_list(),
                index=get_specialties_list().index(task.get("specialty")) if task.get("specialty") in get_specialties_list() else 0)
            
            technicians = load_technicians()
            if technicians:
                opts = list(technicians.keys())
                curr = task.get("technician_id")
                idx = opts.index(curr) + 1 if curr in opts else 0
                technician_id = st.selectbox("Técnico Responsável", options=[None] + opts, index=idx,
                    format_func=lambda x: "Não atribuído" if x is None else f"{technicians[x]['name']} ({technicians[x].get('specialty', 'N/A')})")
            else:
                technician_id = None
                
        with col2:
            locations = load_locations()
            loc_id = task.get("location_id")
            loc_idx = list(locations.keys()).index(loc_id) if loc_id in locations else 0
            location_id = st.selectbox("Localidade *", options=list(locations.keys()), index=loc_idx, format_func=lambda x: locations[x])
            
            # Data
            col_date, col_time = st.columns(2)
            with col_date:
                if task['due_date']:
                    try:
                        dt = datetime.fromisoformat(task['due_date'])
                        current_date = dt.date()
                        current_time = dt.time()
                    except:
                        current_date = datetime.now().date()
                        current_time = datetime.now().time()
                else:
                    current_date = datetime.now().date()
                    current_time = datetime.now().time()
                
                due_date = st.date_input("Data *", value=current_date)
            with col_time:
                due_time = st.time_input("Hora *", value=current_time)
        
        st.markdown("#### ⚙️ Configurações")
        priority = st.selectbox("Prioridade", options=list(PRIORITIES_WITH_EMOJIS.keys()),
            index=list(PRIORITIES_WITH_EMOJIS.keys()).index(task.get("priority", "media")),
            format_func=lambda x: PRIORITIES_WITH_EMOJIS[x]["label"])
        
        recurrence_map = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
        reverse_recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
        current_recurrence = recurrence_map.get(task.get("recurrence"), "Nenhuma")
        recurrence = st.selectbox("Recorrência", options=["Nenhuma", "Diária", "Semanal", "Mensal"],
            index=["Nenhuma", "Diária", "Semanal", "Mensal"].index(current_recurrence))
        
        # Status: agora determinamos automaticamente baseado na data
        due_datetime = datetime.combine(due_date, due_time)
        auto_status = determine_task_status(due_datetime, True)
        
        # Exibir o status que será aplicado
        status_display = status_labels.get(auto_status, auto_status)
        st.markdown(f"**Status:** {status_display} *(determinado automaticamente pela data)*")
        
        # Campo de observações (COM tabelas de materiais se houver)
        st.markdown("#### 📝 Observações Técnicas")
        notes = st.text_area("Observações Técnicas", 
                           value=task.get('notes', ''), 
                           height=150,
                           placeholder="Descreva as observações técnicas aqui...",
                           key="notes_edit_field")
        
        st.markdown("#### 📋 Checklist")
        checklist_text = st.text_area("Itens do checklist (um por linha)", 
            value="\n".join([item["item"] for item in checklist_data]),
            placeholder="Item 1\nItem 2\nItem 3",
            key="checklist_edit_field")
        
        submitted = st.form_submit_button("💾 Salvar Alterações", type="primary")
        
        if submitted:
            if not title or not specialty or not location_id:
                st.error("Preencha os campos obrigatórios (*)")
            else:
                try:
                    # Converter data para string ISO
                    due_datetime = datetime.combine(due_date, due_time)
                    due_datetime_iso = due_datetime.isoformat()
                    
                    # Determinar status baseado na data
                    status = determine_task_status(due_datetime, True)
                    
                    # Combinar observações com tabelas de materiais
                    combined_notes = notes
                    tables_text = materials_tables_to_text()
                    if tables_text:
                        combined_notes = combine_notes_with_tables(notes, tables_text)
                    
                    # Atualizar tarefa
                    updated_task = {
                        "title": title,
                        "description": description,
                        "specialty": specialty,
                        "technician_id": technician_id,
                        "location_id": location_id,
                        "due_date": due_datetime_iso,
                        "priority": priority,
                        "recurrence": reverse_recurrence_map[recurrence],
                        "notes": combined_notes,
                        "status": status
                    }
                    
                    supabase.table("maintenance_tasks").update(updated_task).eq("id", task_id).execute()
                    
                    # Atualizar checklist se houve alterações
                    if checklist_text.strip():
                        # Primeiro, excluir checklist antigo
                        supabase.table("checklists").delete().eq("task_id", task_id).execute()
                        
                        # Inserir novo checklist
                        items = [item.strip() for item in checklist_text.split("\n") if item.strip()]
                        for item in items:
                            supabase.table("checklists").insert({
                                "task_id": task_id,
                                "item": item,
                                "is_completed": False
                            }).execute()
                    
                    st.success("✅ Atividade atualizada com sucesso!")
                    st.toast("✅ Atividade atualizada com sucesso!", icon="💾")
                    st.session_state["show_edit_form"] = False
                    
                    # Limpar tabelas após salvar
                    st.session_state["materials_tables"] = [
                        {
                            "id": str(uuid.uuid4()),
                            "name": "Tabela de Materiais 1",
                            "rows": 3,
                            "cols": 4,
                            "data": [
                                ["", "", "", ""],
                                ["", "", "", ""],
                                ["", "", "", ""]
                            ],
                            "headers": ["Material", "Quantidade", "Unidade", "Observações"],
                            "show_editor": False,
                            "has_data": False
                        }
                    ]
                    st.session_state["show_tables_manager"] = False
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar: {str(e)}")
    
    if st.button("Fechar", use_container_width=True, key="close_edit_form_btn"):
        st.session_state["show_edit_form"] = False
        # Limpar tabelas
        st.session_state["materials_tables"] = [
            {
                "id": str(uuid.uuid4()),
                "name": "Tabela de Materiais 1",
                "rows": 3,
                "cols": 4,
                "data": [
                    ["", "", "", ""],
                    ["", "", "", ""],
                    ["", "", "", ""]
                ],
                "headers": ["Material", "Quantidade", "Unidade", "Observações"],
                "show_editor": False,
                "has_data": False
            }
        ]
        st.session_state["show_tables_manager"] = False
        st.rerun()

# ----------- Modais -----------
def show_new_activity_form():
    st.subheader("➕ Nova Atividade")
    
    # Botão para abrir gerenciador de tabelas (FORA do formulário)
    if st.button("📊 Gerenciador de Tabelas de Materiais", use_container_width=True, 
                key="open_mat_manager_new"):
        st.session_state["show_tables_manager"] = not st.session_state.get("show_tables_manager", False)
        st.rerun()
    
    # Mostrar gerenciador se solicitado (FORA do formulário)
    if st.session_state.get("show_tables_manager", False):
        show_materials_tables_manager()
        st.markdown("---")
    
    with st.form("new_activity", clear_on_submit=True):
        title = st.text_input("Título *")
        description = st.text_area("Descrição")
        col1, col2 = st.columns(2)
        with col1:
            specialty = st.selectbox("Especialidade *", get_specialties_list())
            technicians = load_technicians()
            technician_id = None
            if technicians:
                technician_options = list(technicians.keys())
                technician_id = st.selectbox("Técnico", options=[None] + technician_options,
                    format_func=lambda x: "Não atribuído" if x is None else f"{technicians[x]['name']} ({technicians[x].get('specialty', 'N/A')})")
        with col2:
            locations = load_locations()
            location_id = st.selectbox("Localidade *", options=list(locations.keys()), format_func=lambda x: locations[x])
            
            # Data opcional
            col_date, col_time = st.columns(2)
            with col_date:
                schedule_now = st.checkbox("Programar agora?", value=True, help="Se não marcar, a atividade ficará como não programada")
                if schedule_now:
                    due_date = st.date_input("Data *", value=datetime.now())
                else:
                    due_date = None
            with col_time:
                if schedule_now:
                    due_time = st.time_input("Hora *", value=datetime.now().time())
                else:
                    due_time = None
                    
        priority = st.selectbox("Prioridade", options=list(PRIORITIES_WITH_EMOJIS.keys()), 
                               format_func=lambda x: PRIORITIES_WITH_EMOJIS[x]["label"], index=2)
        recurrence = st.selectbox("Recorrência", options=["Nenhuma", "Diária", "Semanal", "Mensal"])
        recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
        
        # Campo de observações (SEM tabelas por padrão - serão combinadas)
        st.markdown("#### 📝 Observações Técnicas")
        notes = st.text_area("Observações Técnicas", 
                           height=150,
                           placeholder="Descreva as observações técnicas aqui...",
                           key="notes_new_field")
        
        checklist_items = st.text_area("Itens do checklist (um por linha)", 
                                      placeholder="Item 1\nItem 2\nItem 3...",
                                      key="checklist_new_field")
        
        submitted = st.form_submit_button("Salvar", type="primary")
        
        if submitted:
            if not title or not specialty or not location_id:
                st.error("Preencha os campos obrigatórios (*)")
            else:
                # Lógica de data flexível
                if schedule_now and due_date and due_time:
                    due_datetime = datetime.combine(due_date, due_time)
                    due_datetime_iso = due_datetime.isoformat()
                    # Determinar status baseado na data
                    status = determine_task_status(due_datetime, True)
                else:
                    due_datetime_iso = None
                    # IMPORTANTE: "unscheduled" não é aceito pelo banco
                    # Mapeamos para "scheduled" quando não há data
                    status = "scheduled"
                    
                try:
                    # Combinar observações com tabelas de materiais
                    combined_notes = notes
                    tables_text = materials_tables_to_text()
                    if tables_text:
                        combined_notes = combine_notes_with_tables(notes, tables_text)
                    
                    new_task = {
                        "title": title,
                        "description": description,
                        "specialty": specialty,
                        "technician_id": technician_id,
                        "location_id": location_id,
                        "due_date": due_datetime_iso,
                        "priority": priority,
                        "recurrence": recurrence_map[recurrence],
                        "notes": combined_notes,
                        "status": status
                    }
                    
                    res = supabase.table("maintenance_tasks").insert(new_task).execute()
                    new_task_id = res.data[0]["id"] if res.data else None
                    
                    if checklist_items:
                        items = [item.strip() for item in checklist_items.split("\n") if item.strip()]
                        for item in items:
                            supabase.table("checklists").insert({
                                "task_id": new_task_id, 
                                "item": item, 
                                "is_completed": False
                            }).execute()
                    
                    st.success("✅ Atividade criada com sucesso!")
                    st.toast("✅ Atividade criada com sucesso!", icon="✅")
                    st.session_state["show_new_form"] = False
                    
                    # Limpar tabelas após salvar
                    st.session_state["materials_tables"] = [
                        {
                            "id": str(uuid.uuid4()),
                            "name": "Tabela de Materiais 1",
                            "rows": 3,
                            "cols": 4,
                            "data": [
                                ["", "", "", ""],
                                ["", "", "", ""],
                                ["", "", "", ""]
                            ],
                            "headers": ["Material", "Quantidade", "Unidade", "Observações"],
                            "show_editor": False,
                            "has_data": False
                        }
                    ]
                    st.session_state["show_tables_manager"] = False
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao criar: {str(e)}")
    
    if st.button("Fechar", use_container_width=True, key="close_new_form_btn"):
        st.session_state["show_new_form"] = False
        # Limpar tabelas
        st.session_state["materials_tables"] = [
            {
                "id": str(uuid.uuid4()),
                "name": "Tabela de Materiais 1",
                "rows": 3,
                "cols": 4,
                "data": [
                    ["", "", "", ""],
                    ["", "", "", ""],
                    ["", "", "", ""]
                ],
                "headers": ["Material", "Quantidade", "Unidade", "Observações"],
                "show_editor": False,
                "has_data": False
            }
        ]
        st.session_state["show_tables_manager"] = False
        st.rerun()

def show_task_modal(task):
    # Validação da tarefa
    if not isinstance(task, dict) or "id" not in task:
        st.error("❌ Tarefa inválida")
        if st.button("Fechar", use_container_width=True):
            st.session_state["selected_task"] = None
            st.rerun()
        return
    
    # Carregar dados atualizados
    try:
        task_res = supabase.table("maintenance_tasks").select("*").eq("id", task["id"]).execute()
        if not task_res.data:
            st.error("❌ Tarefa não encontrada")
            if st.button("Fechar", use_container_width=True):
                st.session_state["selected_task"] = None
                st.rerun()
            return
        task = task_res.data[0]
    except Exception as e:
        st.error(f"❌ Erro ao carregar tarefa: {str(e)}")
        if st.button("Fechar", use_container_width=True):
            st.session_state["selected_task"] = None
            st.rerun()
        return

    st.subheader(f"🔍 {task['title']}")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Título:** {task['title']}")
            st.markdown(f"**Descrição:** {task.get('description', '—')}")
            st.markdown(f"**Especialidade:** {task.get('specialty', '—')}")
            st.markdown(f"**Técnico:** {get_technician_name(task['technician_id'], load_technicians())}")
            st.markdown(f"**Local:** {get_location_name(task['location_id'], load_locations())}")
        with col2:
            # Exibição condicional da data
            if task['due_date']:
                st.markdown(f"**Data:** {task['due_date'][:10]}")
                st.markdown(f"**Hora:** {task['due_date'][11:16]}")
            else:
                st.markdown("**Data:** ⏳ Não programada")
                st.markdown("**Hora:** —")
                
            st.markdown(f"**Prioridade:** {PRIORITIES_WITH_EMOJIS.get(task.get('priority', 'media'), PRIORITIES_WITH_EMOJIS['media'])['label']}")
            st.markdown(f"**Status:** {status_labels.get(task['status'], task['status'])}")
            recurrence_map = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
            st.markdown(f"**Recorrência:** {recurrence_map.get(task.get('recurrence'), 'Nenhuma')}")

    # CHECKLIST INTERATIVO
    st.markdown("### 📋 Checklist")
    
    # Carregar checklist atual
    checklist_data = load_checklist(task["id"])
    
    # Inicializar estado do checklist se necessário
    checklist_key = f"checklist_{task['id']}"
    if checklist_key not in st.session_state:
        st.session_state[checklist_key] = checklist_data
    
    # Atualizar progresso
    total_items = len(st.session_state[checklist_key])
    completed_items = sum(1 for item in st.session_state[checklist_key] if item.get("is_completed", False))
    progress = completed_items / total_items if total_items > 0 else 0
    
    # Barra de progresso
    st.progress(progress)
    st.caption(f"Progresso: {completed_items}/{total_items} ({progress:.0%})")
    
    # Formulário interativo do checklist
    with st.form(f"checklist_form_{task['id']}"):
        st.markdown("**Marque os itens concluídos:**")
        
        updated_checklist = []
        for i, item in enumerate(st.session_state[checklist_key]):
            col1, col2 = st.columns([1, 20])
            with col1:
                is_checked = st.checkbox(
                    "", 
                    value=item.get("is_completed", False),
                    key=f"check_{task['id']}_{i}"
                )
            with col2:
                item_text = item["item"]
                if is_checked:
                    st.markdown(f"<div class='checklist-item-completed'>{item_text} ✅</div>", unsafe_allow_html=True)
                else:
                    st.markdown(item_text)
            
            updated_checklist.append({
                "id": item["id"],
                "item": item_text,
                "is_completed": is_checked
            })
        
        # Botões de ação do checklist
        col1, col2, col3 = st.columns(3)
        with col1:
            save_checklist = st.form_submit_button("💾 Salvar Checklist", use_container_width=True)
        with col2:
            reset_checklist = st.form_submit_button("🔄 Reiniciar", use_container_width=True, type="secondary")
        with col3:
            add_new_item = st.form_submit_button("➕ Novo Item", use_container_width=True)
        
        if save_checklist:
            try:
                # Atualizar cada item no banco
                for item in updated_checklist:
                    supabase.table("checklists").update({
                        "is_completed": item["is_completed"]
                    }).eq("id", item["id"]).execute()
                
                # Atualizar estado da sessão
                st.session_state[checklist_key] = updated_checklist
                st.toast("✅ Checklist salvo com sucesso!", icon="💾")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erro ao salvar checklist: {str(e)}")
        
        if reset_checklist:
            try:
                # Resetar todos os itens para não concluídos
                for item in st.session_state[checklist_key]:
                    supabase.table("checklists").update({
                        "is_completed": False
                    }).eq("id", item["id"]).execute()
                
                # Atualizar estado da sessão
                reset_data = [{"id": item["id"], "item": item["item"], "is_completed": False} for item in st.session_state[checklist_key]]
                st.session_state[checklist_key] = reset_data
                st.toast("🔄 Checklist reiniciado!", icon="🔄")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erro ao reiniciar checklist: {str(e)}")
    
    # Formulário para adicionar novo item (fora do formulário principal)
    if add_new_item:
        with st.form(f"new_item_form_{task['id']}"):
            new_item = st.text_input("Novo item do checklist:", placeholder="Digite o novo item...")
            col1, col2 = st.columns(2)
            with col1:
                submit_new = st.form_submit_button("✅ Adicionar", use_container_width=True)
            with col2:
                cancel_new = st.form_submit_button("❌ Cancelar", use_container_width=True)
            
            if submit_new and new_item.strip():
                try:
                    # Inserir novo item no banco
                    res = supabase.table("checklists").insert({
                        "task_id": task["id"],
                        "item": new_item.strip(),
                        "is_completed": False
                    }).execute()
                    
                    if res.data:
                        # Recarregar checklist completo
                        refreshed_checklist = load_checklist(task["id"])
                        st.session_state[checklist_key] = refreshed_checklist
                        st.toast("✅ Novo item adicionado!", icon="➕")
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erro ao adicionar item: {str(e)}")

    # Anexos
    st.markdown("### 📎 Anexos")
    uploaded_files = st.file_uploader("Adicionar imagens", type=['png', '.jpg', '.jpeg'], accept_multiple_files=True, key=f"upload_{task['id']}")
    if uploaded_files:
        for f in uploaded_files:
            handle_file_upload(task["id"], f)
    
    attachments = load_attachments(task["id"])
    if attachments:
        cols = st.columns(3)
        for i, att in enumerate(attachments):
            with cols[i % 3]:
                url = get_attachment_url(task["id"], att['name'])
                if url and is_image_file(att['name']):
                    st.image(url, caption=att['name'], use_column_width=True)
    else:
        st.caption("📷 Nenhuma imagem anexada.")

    # Observações técnicas (COM tabelas de materiais se houver)
    st.markdown("### 📝 Observações Técnicas")
    notes = (task.get('notes') or '').strip()
    
    if notes:
        st.markdown('<div class="notes-with-table">', unsafe_allow_html=True)
        
        # Separar observações das tabelas se houver
        if "📋 **LISTA DE MATERIAIS:**" in notes:
            parts = notes.split("📋 **LISTA DE MATERIAIS:**")
            if parts[0].strip():
                st.markdown("**Observações:**")
                st.text(parts[0].strip())
            
            # Mostrar tabelas se existirem
            if len(parts) > 1:
                st.markdown("**Lista de Materiais:**")
                tables_text = "📋 **LISTA DE MATERIAIS:**" + parts[1]
                st.markdown(tables_text)
        else:
            st.text(notes)
            
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.caption("_Nenhuma observação._")

    # Ações
    st.markdown("### 🛠️ Ações")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if task["status"] in ["scheduled", "overdue", "unscheduled"]:
            if st.button("▶️ Iniciar", use_container_width=True, key=f"start_{task['id']}"):
                supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task["id"]).execute()
                st.toast("▶️ Tarefa iniciada!", icon="▶️")
                st.rerun()
        elif task["status"] == "in_progress":
            if st.button("✅ Concluir", use_container_width=True, key=f"complete_{task['id']}"):
                supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task["id"]).execute()
                checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in st.session_state[checklist_key]]
                archive_task(task, checklist_items)
                if task.get("recurrence"):
                    create_recurring_task(task)
                st.toast("✅ Tarefa concluída e arquivada!", icon="✅")
                st.rerun()
    
    with col2:
        if st.button("📋 Clonar", use_container_width=True, key=f"clone_{task['id']}"):
            st.session_state["cloning_task_id"] = task["id"]
            st.session_state["show_clone_form"] = True
            st.toast("📋 Preparando clonagem...", icon="📋")
            st.rerun()
    
    with col3:
        if st.button("✏️ Editar", use_container_width=True, key=f"edit_{task['id']}"):
            st.session_state["show_edit_form"] = True
            st.session_state["editing_task_data"] = {"id": task["id"]}
            st.rerun()
    
    with col4:
        try:
            checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in st.session_state[checklist_key]]
            attachments = load_attachments(task["id"])
            image_paths, temp_dir = download_attachments_to_temp(task["id"], attachments) if attachments else ([], None)
            pdf_bytes = generate_pdf(task, get_technician_name(task['technician_id'], load_technicians()), get_location_name(task['location_id'], load_locations()), checklist_items, image_paths)
            st.download_button("📄 PDF", data=pdf_bytes, file_name=f"atividade_{task['id']}.pdf", mime="application/pdf", use_container_width=True, key=f"pdf_{task['id']}")
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            st.error(f"❌ Erro ao gerar PDF: {str(e)}")
    
    # Botão excluir em nova linha
    if st.button("🗑️ Excluir", type="secondary", use_container_width=True, key=f"delete_{task['id']}"):
        supabase.table("checklists").delete().eq("task_id", task["id"]).execute()
        supabase.table("maintenance_tasks").delete().eq("id", task["id"]).execute()
        st.session_state["selected_task"] = None
        st.toast("🗑️ Tarefa excluída!", icon="🗑️")
        st.rerun()
    
    if st.button("Fechar", use_container_width=True, key=f"close_{task['id']}"):
        st.session_state["selected_task"] = None
        st.rerun()

def show_clone_form():
    st.subheader("📋 Clonar Tarefa")
    
    LEGACY_LABEL_TO_KEY = {
        "Alta": "alta", "Média": "media", "Baixa": "baixa", "Missão Crítica": "missao_critica",
        "🔴 Alta": "alta", "🟡 Média": "media", "🟢 Baixa": "baixa", "🚨 Missão Crítica": "missao_critica",
        "alta": "alta", "media": "media", "baixa": "baixa", "missao_critica": "missao_critica"
    }
    raw_priority = st.session_state["clone_form_data"].get("priority", "media")
    priority_key = LEGACY_LABEL_TO_KEY.get(str(raw_priority).strip(), "media")
    
    # Botão para abrir gerenciador de tabelas (FORA do formulário)
    if st.button("📊 Gerenciador de Tabelas de Materiais", use_container_width=True, 
                key="open_mat_manager_clone"):
        st.session_state["show_tables_manager"] = not st.session_state.get("show_tables_manager", False)
        st.rerun()
    
    # Mostrar gerenciador se solicitado (FORA do formulário)
    if st.session_state.get("show_tables_manager", False):
        show_materials_tables_manager()
        st.markdown("---")
    
    with st.form("clone_form"):
        st.markdown("#### 📝 Informações Básicas")
        title = st.text_input("Título *", value=st.session_state["clone_form_data"].get("title", ""))
        description = st.text_area("Descrição", value=st.session_state["clone_form_data"].get("description", ""))
        
        col1, col2 = st.columns(2)
        with col1:
            specialty = st.selectbox("Especialidade *", get_specialties_list(),
                index=get_specialties_list().index(st.session_state["clone_form_data"].get("specialty")) if st.session_state["clone_form_data"].get("specialty") in get_specialties_list() else 0)
            
            # Múltiplos técnicos para UMA atividade
            technicians = load_technicians()
            if technicians:
                st.markdown("#### 👥 Técnicos para Atividade (Equipe)")
                st.info("📝 **Múltiplos técnicos = 1 atividade com equipe**")
                
                tech_options = list(technicians.keys())
                tech_names = [f"{technicians[t]['name']} ({technicians[t].get('specialty', 'N/A')})" for t in tech_options]
                
                # Técnico original da tarefa clonada
                original_tech_id = st.session_state["clone_form_data"].get("technician_id")
                original_tech_name = f"{technicians[original_tech_id]['name']} ({technicians[original_tech_id].get('specialty', 'N/A')})" if original_tech_id in technicians else ""
                
                selected_tech_names = st.multiselect(
                    "Técnicos (equipe)",
                    options=tech_names,
                    default=[original_tech_name] if original_tech_name in tech_names else [],
                    help="Selecione um ou mais técnicos para formar a equipe da atividade"
                )
                
                # Mapear nomes selecionados de volta para IDs
                name_to_tech_id = {f"{technicians[t]['name']} ({technicians[t].get('specialty', 'N/A')})": t for t in tech_options}
                selected_technician_ids = [name_to_tech_id[name] for name in selected_tech_names if name in name_to_tech_id]
                
                # Se houver múltiplos técnicos, vamos armazenar como string separada por vírgulas
                if len(selected_technician_ids) > 1:
                    st.markdown(f'<div class="multi-tech-info">', unsafe_allow_html=True)
                    st.markdown(f"**Equipe selecionada ({len(selected_technician_ids)} técnicos):**")
                    for i, tech_id in enumerate(selected_technician_ids):
                        tech_name = technicians[tech_id]['name']
                        st.markdown(f"{i+1}. {tech_name}")
                    st.markdown('</div>', unsafe_allow_html=True)
                elif len(selected_technician_ids) == 1:
                    st.info(f"👤 **Técnico único:** {technicians[selected_technician_ids[0]]['name']}")
                else:
                    st.info("👤 **Nenhum técnico selecionado:** atividade ficará sem técnico atribuído")
            else:
                selected_technician_ids = []
                st.info("Nenhum técnico cadastrado.")
                    
        with col2:
            # Múltiplas localidades = MÚLTIPLAS atividades
            st.markdown("#### 🏢 Localidades para Atividades")
            st.info("📍 **Múltiplas localidades = múltiplas atividades (uma para cada)**")
            
            all_locations = load_locations()
            location_names = list(all_locations.values())
            location_ids = list(all_locations.keys())
            
            # Mapear nomes para IDs
            name_to_id = {name: loc_id for loc_id, name in all_locations.items()}
            
            # Localidade original da tarefa clonada
            original_location_id = st.session_state["clone_form_data"].get("location_id")
            original_location_name = all_locations.get(original_location_id, "")
            
            selected_location_names = st.multiselect(
                "Localidades *",
                options=location_names,
                default=[original_location_name] if original_location_name in location_names else [],
                help="Selecione uma ou mais localidades para criar atividades separadas"
            )
            
            # Converter nomes selecionados de volta para IDs
            selected_location_ids = [name_to_id[name] for name in selected_location_names if name in name_to_id]
            
            # Data opcional na clonagem
            col_date, col_time = st.columns(2)
            with col_date:
                schedule_now = st.checkbox("Programar agora?", value=True, help="Se não marcar, as atividades ficarão como não programadas")
                if schedule_now:
                    due_date = st.date_input("Data *", value=datetime.now())
                else:
                    due_date = None
            with col_time:
                if schedule_now:
                    due_time = st.time_input("Hora *", value=datetime.now().time())
                else:
                    due_time = None
        
        st.markdown("#### ⚙️ Configurações Adicionais")
        priority = st.selectbox("Prioridade", options=list(PRIORITIES_WITH_EMOJIS.keys()),
            index=list(PRIORITIES_WITH_EMOJIS.keys()).index(priority_key),
            format_func=lambda x: PRIORITIES_WITH_EMOJIS[x]["label"])
        recurrence = st.selectbox("Recorrência", options=["Nenhuma", "Diária", "Semanal", "Mensal"],
            index=["Nenhuma", "Diária", "Semanal", "Mensal"].index(st.session_state["clone_form_data"].get("recurrence", "Nenhuma")))
        recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
        
        # Campo de observações (COM tabelas de materiais se houver)
        st.markdown("#### 📝 Observações Técnicas")
        notes = st.text_area("Observações Técnicas", 
                           value=st.session_state["clone_form_data"].get("notes", ""), 
                           height=150,
                           placeholder="Observações técnicas...",
                           key="notes_clone_field")
        
        checklist_items = st.text_area("Checklist", 
                                      value="\n".join(st.session_state["clone_form_data"].get("checklist", [])), 
                                      placeholder="...",
                                      key="checklist_clone_field")
        
        # Resumo da clonagem
        if selected_location_names:
            total_tasks = len(selected_location_ids)
            
            st.markdown(f'<div class="multi-select-info">', unsafe_allow_html=True)
            st.markdown(f"**📋 Resumo da Clonagem:**")
            
            if len(selected_location_names) > 1:
                st.markdown(f"- **Localidades selecionadas:** {len(selected_location_names)} → **{total_tasks} atividades**")
                for i, location_name in enumerate(selected_location_names[:3]):
                    st.markdown(f"  {i+1}. {location_name}")
                if len(selected_location_names) > 3:
                    st.markdown(f"  ... e mais {len(selected_location_names) - 3}")
            else:
                st.markdown(f"- **Localidade:** {selected_location_names[0]} → **1 atividade**")
            
            if selected_technician_ids:
                if len(selected_technician_ids) > 1:
                    st.markdown(f'- **Equipe de técnicos:** {len(selected_technician_ids)} técnicos em cada atividade')
                    for i, tech_id in enumerate(selected_technician_ids[:3]):
                        tech_name = technicians.get(tech_id, {}).get('name', 'N/A')
                        st.markdown(f"  {i+1}. {tech_name}")
                    if len(selected_technician_ids) > 3:
                        st.markdown(f"  ... e mais {len(selected_technician_ids) - 3}")
                else:
                    tech_name = technicians.get(selected_technician_ids[0], {}).get('name', 'N/A')
                    st.markdown(f"- **Técnico:** {tech_name}")
            else:
                st.markdown("- **Técnicos:** Não atribuído")
            
            st.markdown(f"- **Total de atividades a criar:** {total_tasks}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        submitted = st.form_submit_button(f"🚀 Criar {len(selected_location_ids)} Atividades" if selected_location_ids else "Criar Cópias", type="primary")
        
        if submitted:
            if not title or not selected_location_ids or not specialty:
                st.error("Preencha os campos obrigatórios (*)")
            else:
                # Lógica de data flexível na clonagem
                if schedule_now and due_date and due_time:
                    due_datetime = datetime.combine(due_date, due_time)
                    due_datetime_iso = due_datetime.isoformat()
                    # Determinar status baseado na data
                    status = determine_task_status(due_datetime, True)
                else:
                    due_datetime_iso = None
                    status = "scheduled"
                    
                try:
                    created_count = 0
                    
                    # Se houver múltiplos técnicos, vamos armazenar como string
                    if selected_technician_ids:
                        if len(selected_technician_ids) == 1:
                            technician_id_for_task = selected_technician_ids[0]
                            technician_team = None
                        else:
                            technician_id_for_task = None
                            technician_team = ",".join(selected_technician_ids)
                    else:
                        technician_id_for_task = None
                        technician_team = None
                    
                    # Combinar observações com tabelas de materiais
                    combined_notes = notes
                    tables_text = materials_tables_to_text()
                    if tables_text:
                        combined_notes = combine_notes_with_tables(notes, tables_text)
                    
                    # Criar uma atividade para CADA localidade
                    for location_id in selected_location_ids:
                        location_name = all_locations.get(location_id, "")
                        
                        # Definir título apropriado
                        if len(selected_location_names) > 1:
                            task_title = f"{title} - {location_name}"
                        else:
                            task_title = title
                        
                        # Adicionar observações sobre equipe se houver múltiplos técnicos
                        task_notes = combined_notes
                        if technician_team and len(selected_technician_ids) > 1:
                            team_names = []
                            for tech_id in selected_technician_ids:
                                if tech_id in technicians:
                                    team_names.append(technicians[tech_id]['name'])
                            
                            if task_notes:
                                task_notes += f"\n\n👥 **Equipe de trabalho:** {', '.join(team_names)}"
                            else:
                                task_notes = f"👥 **Equipe de trabalho:** {', '.join(team_names)}"
                        
                        new_task = {
                            "title": task_title,
                            "description": description,
                            "specialty": specialty,
                            "technician_id": technician_id_for_task,
                            "location_id": location_id,
                            "due_date": due_datetime_iso,
                            "priority": priority,
                            "recurrence": recurrence_map[recurrence],
                            "notes": task_notes,
                            "status": status
                        }
                        
                        # Se houver equipe, adicionar campo extra
                        if technician_team:
                            new_task["technician_team"] = technician_team
                        
                        res = supabase.table("maintenance_tasks").insert(new_task).execute()
                        new_task_id = res.data[0]["id"] if res.data else None
                        
                        if new_task_id and checklist_items:
                            items = [item.strip() for item in checklist_items.split("\n") if item.strip()]
                            for item in items:
                                supabase.table("checklists").insert({"task_id": new_task_id, "item": item, "is_completed": False}).execute()
                        
                        created_count += 1
                    
                    location_count = len(selected_location_names)
                    tech_count = len(selected_technician_ids) if selected_technician_ids else 0
                    
                    if tech_count > 1:
                        message = f"✅ {created_count} atividades criadas com sucesso para {location_count} localidades, cada uma com equipe de {tech_count} técnicos!"
                    elif tech_count == 1:
                        message = f"✅ {created_count} atividades criadas com sucesso para {location_count} localidades!"
                    else:
                        message = f"✅ {created_count} atividades criadas com sucesso para {location_count} localidades!"
                    
                    st.success(message)
                    st.toast(message, icon="✅")
                    st.session_state.update({"show_clone_form": False, "cloning_task_id": None, "clone_form_data": {}})
                    
                    # Limpar tabelas após salvar
                    st.session_state["materials_tables"] = [
                        {
                            "id": str(uuid.uuid4()),
                            "name": "Tabela de Materiais 1",
                            "rows": 3,
                            "cols": 4,
                            "data": [
                                ["", "", "", ""],
                                ["", "", "", ""],
                                ["", "", "", ""]
                            ],
                            "headers": ["Material", "Quantidade", "Unidade", "Observações"],
                            "show_editor": False,
                            "has_data": False
                        }
                    ]
                    st.session_state["show_tables_manager"] = False
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erro ao criar atividades: {str(e)}")
    
    if st.button("Fechar", use_container_width=True, key="close_clone_form_btn"):
        st.session_state.update({"show_clone_form": False, "cloning_task_id": None, "clone_form_data": {}})
        # Limpar tabelas
        st.session_state["materials_tables"] = [
            {
                "id": str(uuid.uuid4()),
                "name": "Tabela de Materiais 1",
                "rows": 3,
                "cols": 4,
                "data": [
                    ["", "", "", ""],
                    ["", "", "", ""],
                    ["", "", "", ""]
                ],
                "headers": ["Material", "Quantidade", "Unidade", "Observações"],
                "show_editor": False,
                "has_data": False
            }
        ]
        st.session_state["show_tables_manager"] = False
        st.rerun()

# ----------- Funções para Renderização -----------
def render_kanban_checklist(task):
    """Renderiza um checklist simplificado nos cards do Kanban"""
    checklist_data = load_checklist(task["id"])
    if not checklist_data:
        return
    
    total = len(checklist_data)
    completed = sum(1 for item in checklist_data if item["is_completed"])
    
    # Barra de progresso compacta
    if total > 0:
        progress = completed / total
        st.progress(progress)
        st.caption(f"Checklist: {completed}/{total} ({progress:.0%})")
        
        # Mostrar alguns itens principais
        for i, item in enumerate(checklist_data[:3]):
            status = "✅" if item["is_completed"] else "⏳"
            st.markdown(f"{status} {item['item'][:30]}{'...' if len(item['item']) > 30 else ''}")
        
        if total > 3:
            st.caption(f"... e mais {total - 3} itens")

def render_task_row(task, techs, locs):
    """Renderiza uma linha de tarefa na visualização de lista"""
    is_unscheduled = task["status"] == "unscheduled"
    
    # Aplicar estilo diferente para tarefas não programadas
    card_class = "unscheduled-card" if is_unscheduled else ""
    
    with st.container():
        st.markdown(f'<div class="card {card_class}">', unsafe_allow_html=True)
        
        col1, col2, col3, col4, col5, col6, col7 = st.columns([3, 2, 2, 1, 1, 1, 1])
        
        with col1:
            st.markdown(f"**{task['title']}**")
            if task.get("notes"):
                preview = (task["notes"][:50] + "...") if len(task["notes"]) > 50 else task["notes"]
                st.caption(f"📝 {preview}")
                
        with col2:
            st.caption(f"📍 {get_location_name(task['location_id'], locs)}")
            st.caption(f"👷 {get_technician_name(task['technician_id'], techs)}")
            
        with col3:
            st.markdown(get_priority_badge(task.get('priority', 'media')), unsafe_allow_html=True)
            st.caption(f"**{task.get('specialty', '—')}**")
            
        with col4:
            if task['due_date']:
                st.caption(f"📅 {task['due_date'][:10]}")
                st.caption(f"🕒 {task['due_date'][11:16]}")
            else:
                st.caption("⏳ Não programada")
                st.caption("—")
                        
        with col5:
            status_display = status_labels.get(task["status"], task["status"])
            if is_unscheduled:
                st.caption(f"⏳ {status_display}")
            else:
                st.caption(status_display)
                
        with col6:
            if st.button("✏️", key=f"edit_{task['id']}", help="Editar atividade"):
                st.session_state["show_edit_form"] = True
                st.session_state["editing_task_data"] = {"id": task["id"]}
                st.rerun()
                
        with col7:
            if st.button("🔍", key=f"open_{task['id']}", help="Detalhes"):
                st.session_state["selected_task"] = task
                st.rerun()
                
        st.markdown('</div>', unsafe_allow_html=True)

def render_list_view(tasks_all, techs, locs):
    """Renderiza a visualização em lista"""
    grouped = {}
    for t in tasks_all:
        grouped.setdefault(t["status"], []).append(t)
    
    # Ordem de exibição: Não programadas primeiro, depois as outras
    status_order = ["unscheduled", "overdue", "scheduled", "in_progress", "completed"]
    
    for status in status_order:
        if status not in grouped: 
            continue
            
        tasks = grouped[status]
        with st.expander(f"{status_labels[status]} ({len(tasks)})", expanded=st.session_state["expanded_groups"].get(status, True)):
            for task in tasks:
                render_task_row(task, techs, locs)

# ----------- Página Principal -----------
st.set_page_config(page_title="🔧 Manutenção Preventiva", layout="wide")

# Atualização automática de status
update_overdue_tasks()

st.title("🔧 Sistema de Manutenção Preventiva")

# Sidebar
with st.sidebar:
    st.header("📁 Cadastros")
    with st.expander("👷 Técnicos"):
        with st.form("add_technician"):
            name = st.text_input("Nome")
            specialty = st.selectbox("Especialidade", get_specialties_list() + ["Outra"])
            if specialty == "Outra":
                specialty = st.text_input("Nova especialidade")
            if st.form_submit_button("Salvar") and name and specialty:
                supabase.table("technicians").insert({"name": name, "specialty": specialty}).execute()
                st.toast("✅ Técnico salvo!", icon="👷")
                st.rerun()
    with st.expander("📍 Localidades"):
        with st.form("add_location"):
            name = st.text_input("Nome")
            if st.form_submit_button("Salvar") and name:
                supabase.table("locations").insert({"name": name}).execute()
                st.toast("✅ Localidade salva!", icon="📍")
                st.rerun()
    if st.button("📋 Histórico"):
        st.session_state["show_history"] = True
        st.rerun()

# Filtros e Modo
st.markdown("### 🖼️ Modo de Visualização")
mode = st.radio("Modo", ["📋 Lista", "📊 Kanban"], horizontal=True, key="view_mode_radio")
st.session_state["view_mode"] = "list" if mode == "📋 Lista" else "kanban"

col1, col2, col3, col4 = st.columns(4)
with col1: 
    selected_speciality = st.selectbox("Especialidade", ["Todas"] + get_specialties_list(), key="specialty_filter")
with col2: 
    selected_loc = st.selectbox("Localidade", ["Todas"] + list(load_locations().values()), key="location_filter")
with col3: 
    filter_date = st.date_input("Data", value=None, key="date_filter")
with col4: 
    priority_filter = st.selectbox("Prioridade", ["Todas"] + [v["label"] for v in PRIORITIES_WITH_EMOJIS.values()], key="priority_filter")

st.divider()

if st.button("➕ Nova Atividade", type="primary", key="new_activity_btn"):
    st.session_state["show_new_form"] = True

# ----------- EXIBIÇÃO DE MODAIS -----------
if st.session_state["show_new_form"]:
    show_new_activity_form()

if st.session_state["show_edit_form"] and st.session_state.get("editing_task_data"):
    show_edit_form(st.session_state["editing_task_data"]["id"])

if st.session_state["show_clone_form"] and st.session_state["cloning_task_id"]:
    task_res = supabase.table("maintenance_tasks").select("*").eq("id", st.session_state["cloning_task_id"]).execute()
    if task_res.data:
        task = task_res.data[0]
        checklist_data = load_checklist(task["id"])
        st.session_state["clone_form_data"] = {
            "title": task["title"],
            "description": task.get("description", ""),
            "specialty": task.get("specialty", ""),
            "technician_id": task.get("technician_id"),
            "location_id": task.get("location_id"),
            "due_date": datetime.fromisoformat(task["due_date"]).date() if task["due_date"] else None,
            "priority": task.get("priority", "media"),
            "recurrence": "Nenhuma" if not task.get("recurrence") else {"daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}.get(task.get("recurrence"), "Nenhuma"),
            "checklist": [item["item"] for item in checklist_data],
            "notes": task.get("notes", "")
        }
    show_clone_form()

# Modal de detalhes da tarefa
selected_task = st.session_state.get("selected_task")
if selected_task and isinstance(selected_task, dict) and "id" in selected_task:
    show_task_modal(selected_task)

# Conteúdo principal (só aparece se nenhum modal estiver aberto)
if not any([st.session_state.get("show_new_form"), st.session_state.get("show_clone_form"), 
            st.session_state.get("selected_task"), st.session_state.get("show_edit_form")]):
    techs = load_technicians()
    locs = load_locations()
    
    def get_filtered_tasks(status_list):
        query = supabase.table("maintenance_tasks").select("*").in_("status", status_list).eq("is_template", False).order("due_date")
        if selected_speciality != "Todas":
            query = query.eq("specialty", selected_speciality)
        if selected_loc != "Todas":
            loc_id = next((k for k, v in locs.items() if v == selected_loc), None)
            if loc_id:
                query = query.eq("location_id", loc_id)
        if filter_date:
            start = datetime.combine(filter_date, datetime.min.time()).isoformat()
            end = datetime.combine(filter_date, datetime.max.time()).isoformat()
            query = query.gte("due_date", start).lte("due_date", end)
        if priority_filter != "Todas":
            key = next((k for k, v in PRIORITIES_WITH_EMOJIS.items() if v["label"] == priority_filter), None)
            if key:
                query = query.eq("priority", key)
        return query.execute().data or []
    
    # Incluir tarefas não programadas na consulta
    tasks_all = get_filtered_tasks(["scheduled", "in_progress", "completed", "overdue", "unscheduled"])
    
    if st.session_state["view_mode"] == "list":
        render_list_view(tasks_all, techs, locs)
    else:
        st.subheader("📊 Quadro Kanban")
        cols = st.columns(3)
        for i, (status, label) in enumerate([("unscheduled", "⏳ Não Programadas"), ("scheduled", "📅 Agendadas"), ("in_progress", "🛠️ Em Andamento"), ("completed", "✅ Concluídas")]):
            if i < 3:  # Distribuir em 3 colunas
                with cols[i]:
                    st.markdown(f"### {label}")
                    tasks = get_filtered_tasks([status])
                    for task in tasks:
                        is_unscheduled = task["status"] == "unscheduled"
                        card_class = "unscheduled-card" if is_unscheduled else ""
                        
                        with st.container(border=True):
                            st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
                            st.markdown(f"**{task['title']}**")
                            if task.get("notes"):
                                st.caption(f"📝 {task['notes'][:50]}...")
                            st.markdown(get_priority_badge(task.get('priority', 'media')), unsafe_allow_html=True)
                            st.caption(f"📍 {get_location_name(task['location_id'], locs)}")
                            st.caption(f"👷 {get_technician_name(task['technician_id'], techs)}")
                            
                            # Exibição de data no Kanban
                            if task['due_date']:
                                st.caption(f"📅 {task['due_date'][:16].replace('T', ' ')}")
                            else:
                                st.caption("⏳ Não programada")
                            
                            # Botão para editar atividade completa
                            if st.button("✏️ Editar", key=f"edit_kanban_{task['id']}", use_container_width=True):
                                st.session_state["show_edit_form"] = True
                                st.session_state["editing_task_data"] = {"id": task["id"]}
                                st.rerun()
                            
                            # CHECKLIST NO KANBAN
                            render_kanban_checklist(task)
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                if task["status"] in ["scheduled", "overdue", "unscheduled"]:
                                    if st.button("▶️ Iniciar", key=f"done_{task['id']}", use_container_width=True):
                                        supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task["id"]).execute()
                                        st.toast("▶️ Tarefa iniciada!", icon="▶️")
                                        st.rerun()
                                elif task["status"] == "in_progress":
                                    if st.button("✅ Concluir", key=f"complete_{task['id']}", use_container_width=True):
                                        supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task["id"]).execute()
                                        checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in load_checklist(task["id"])]
                                        archive_task(task, checklist_items)
                                        if task.get("recurrence"):
                                            create_recurring_task(task)
                                        st.toast("✅ Tarefa concluída!", icon="✅")
                                        st.rerun()
                            with col2:
                                if st.button("📋 Clonar", key=f"clone_k_{task['id']}", use_container_width=True):
                                    checklist_data = load_checklist(task["id"])
                                    st.session_state["clone_form_data"] = {
                                        "title": task["title"],
                                        "description": task.get("description", ""),
                                        "specialty": task.get("specialty", ""),
                                        "technician_id": task.get("technician_id"),
                                        "location_id": task.get("location_id"),
                                        "due_date": datetime.fromisoformat(task["due_date"]).date() if task["due_date"] else None,
                                        "priority": task.get("priority", "media"),
                                        "recurrence": "Nenhuma" if not task.get("recurrence") else {"daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}.get(task.get("recurrence"), "Nenhuma"),
                                        "checklist": [item["item"] for item in checklist_data],
                                        "notes": task.get("notes", "")
                                    }
                                    st.session_state["cloning_task_id"] = task["id"]
                                    st.session_state["show_clone_form"] = True
                                    st.rerun()
                            with col3:
                                if st.button("🔍 Detalhes", key=f"det_k_{task['id']}", use_container_width=True):
                                    st.session_state["selected_task"] = task
                                    st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)

# Histórico
if st.session_state.get("show_history"):
    st.markdown("## 📋 Histórico")
    start = st.date_input("Início", value=datetime.now() - timedelta(days=30), key="hist_start")
    end = st.date_input("Fim", value=datetime.now(), key="hist_end")
    res = supabase.table("task_history").select("*").gte("completed_at", str(start)).lte("completed_at", str(end)).order("completed_at", desc=True).execute()
    for h in res.data or []:
        with st.expander(f"✅ {h['title']} — {h['completed_at'][:10]}"):
            st.write(f"**Técnico:** {get_technician_name(h['technician_id'], load_technicians())}")
            st.write(f"**Local:** {get_location_name(h['location_id'], load_locations())}")
            st.write(f"**Concluído em:** {h['completed_at'][:16].replace('T', ' ')}")
            if h.get("notes"):
                st.write(f"📝 **Observações:** {h['notes']}")
    if st.button("Voltar", key="back_from_history"):
        st.session_state["show_history"] = False
        st.rerun()