# app.py — Sistema de Manutenção Preventiva (com sistema de tabelas persistente + Relatórios HTML)
import streamlit as st
from datetime import datetime, timedelta
from supabase_client import get_supabase_client
import os
import re
import uuid
import json
from streamlit_drawable_canvas import st_canvas
from streamlit_calendar import calendar
from math import floor
import tempfile
import shutil
import pandas as pd

supabase = get_supabase_client()

# ----------- ESTADOS DA SESSÃO COM PERSISTÊNCIA -----------
def init_session_state():
    """Inicializa todos os estados da sessão com valores padrão"""
    defaults = {
        "show_new_form": False,
        "show_history": False,
        "selected_task": None,
        "view_mode": "list",
        "show_clone_form": False,
        "cloning_task_id": None,
        "clone_form_data": {},
        "uploaded_files": {},
        "expanded_groups": {
            "scheduled": True,
            "in_progress": True,
            "completed": True,
            "overdue": True
        },
        "checklist_expanded": {},
        "checklist_states": {},
        "editing_task_id": None,
        "editing_field": None,
        "show_edit_form": False,
        "editing_task_data": {},
        "materials_tables": {},
        "show_tables_manager": False,
        "task_materials_loaded": set(),
        "active_materials_editor": None,
        "last_modified_task": None,
        "table_editor_states": {},
        "current_editing_table": None,
        "table_tab_selection": {},
        "generated_report_html": None,
        "show_report": False,
        "initialized": True
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

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

# ----------- FUNÇÃO DE RELATÓRIO HTML -----------
def generate_html_report(task, checklist_items, materials_tables, attachments, technicians, locations):
    """Gera HTML estruturado para impressão."""
    title = task.get("title", "—")
    description = task.get("description", "")
    specialty = task.get("specialty", "—")
    technician_id = task.get("technician_id")
    location_id = task.get("location_id")
    due_date_str = task.get("due_date")
    priority = task.get("priority", "media")
    status = task.get("status", "scheduled")
    notes = task.get("notes", "")

    # Formatação de datas
    if due_date_str:
        try:
            dt = datetime.fromisoformat(due_date_str)
            formatted_date = dt.strftime("%d/%m/%Y")
            formatted_time = dt.strftime("%H:%M")
        except:
            formatted_date = "—"
            formatted_time = "—"
    else:
        formatted_date = "—"
        formatted_time = "—"

    tech_name = get_technician_name(technician_id, technicians)
    loc_name = get_location_name(location_id, locations)
    priority_label = PRIORITIES.get(priority, PRIORITIES["media"])["label"]
    status_label = status_labels.get(status, status)

    # Checklist
    checklist_html = ""
    if checklist_items:
        checklist_html += "<ul style='list-style: none; padding-left: 0;'>"
        for item in checklist_items:
            symbol = "✓" if item.get("is_completed") else "○"
            color = "#28a745" if item.get("is_completed") else "#6c757d"
            checklist_html += f"<li><span style='color:{color}; font-size:16px; margin-right:8px;'>{symbol}</span> {item['item']}</li>"
        checklist_html += "</ul>"
    else:
        checklist_html = "<p><em>Nenhum item no checklist.</em></p>"

    # Tabelas de materiais
    materials_html = ""
    has_materials = False
    for table in materials_tables:
        if not table.get("has_data"):
            continue
        has_materials = True
        headers = table.get("headers", [])
        data = table.get("data", [])
        materials_html += f"<h4 style='color:#2c3e50;'>{table['name']}</h4>"
        materials_html += "<table style='width:100%; border-collapse:collapse; margin:10px 0;'>"
        materials_html += "<thead><tr>"
        for h in headers:
            materials_html += f"<th style='background:#4CAF50; color:white; padding:8px; border:1px solid #ddd;'>{h}</th>"
        materials_html += "</tr></thead><tbody>"
        for row in data:
            if not any(cell.strip() for cell in row):
                continue
            materials_html += "<tr>"
            for cell in row:
                materials_html += f"<td style='border:1px solid #ddd; padding:8px;'>{cell}</td>"
            materials_html += "</tr>"
        materials_html += "</tbody></table>"

    if not has_materials:
        materials_html = "<p><em>Nenhuma tabela com dados.</em></p>"

    # Anexos
    attachments_html = ""
    if attachments:
        attachments_html += "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(120px,1fr)); gap:10px; margin-top:10px;'>"
        for att in attachments:
            if is_image_file(att["name"]):
                url = get_attachment_url(task["id"], att["name"])
                if url:
                    attachments_html += f'<img src="{url}" style="width:100%; height:auto; border:1px solid #ddd; border-radius:4px;" alt="{att["name"]}">'
        attachments_html += "</div>"
    else:
        attachments_html = "<p><em>Nenhuma imagem anexada.</em></p>"

    # HTML completo
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Relatório - {title}</title>
        <style>
            @media print {{
                @page {{ margin: 15mm; }}
                body {{ -webkit-print-color-adjust: exact; }}
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: white;
            }}
            header {{
                text-align: center;
                margin-bottom: 25px;
                padding-bottom: 15px;
                border-bottom: 2px solid #4CAF50;
            }}
            .logo-placeholder {{
                height: 60px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 10px;
                background-color: #f8f9fa;
                border: 1px dashed #ccc;
                border-radius: 4px;
                color: #666;
                font-size: 14px;
            }}
            h1 {{
                color: #2c3e50;
                font-size: 22px;
                margin: 10px 0;
            }}
            h2, h3, h4 {{
                color: #2c3e50;
                margin-top: 1.5em;
            }}
            .info-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 12px;
                margin: 15px 0;
            }}
            .info-item {{
                padding: 6px 0;
            }}
            .info-label {{
                font-weight: bold;
                color: #555;
            }}
            .notes {{
                background-color: #f8f9fa;
                padding: 12px;
                border-left: 4px solid #4CAF50;
                border-radius: 4px;
                margin: 15px 0;
            }}
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ padding: 0; }}
            }}
        </style>
    </head>
    <body>
        <div class="report-container">
            <header>
                <div class="logo-placeholder">[LOGO DA EMPRESA]</div>
                <h1>Relatório de Atividade de Manutenção</h1>
            </header>

            <div>
                <h2>{title}</h2>
                <p><strong>Descrição:</strong> {description or '—'}</p>
                <div class="info-grid">
                    <div class="info-item"><span class="info-label">Local:</span> {loc_name}</div>
                    <div class="info-item"><span class="info-label">Técnico:</span> {tech_name}</div>
                    <div class="info-item"><span class="info-label">Especialidade:</span> {specialty}</div>
                    <div class="info-item"><span class="info-label">Data:</span> {formatted_date}</div>
                    <div class="info-item"><span class="info-label">Hora:</span> {formatted_time}</div>
                    <div class="info-item"><span class="info-label">Prioridade:</span> {priority_label}</div>
                    <div class="info-item"><span class="info-label">Status:</span> {status_label}</div>
                </div>
            </div>

            <div>
                <h3>✅ Checklist</h3>
                {checklist_html}
            </div>

            <div>
                <h3>📋 Lista de Materiais</h3>
                {materials_html}
            </div>

                        <div class="section">
                <h3>📝 Observações Técnicas</h3>
                <div class="notes">{
                    notes.replace('\n', '<br>') if notes else '<em>Nenhuma observação.</em>'
                }</div>
            </div>

            <div>
                <h3>📎 Anexos</h3>
                {attachments_html}
            </div>
        </div>

        <div class="no-print" style="text-align: center; margin-top: 30px;">
            <button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; background: #4CAF50; color: white; border: none; border-radius: 6px; cursor: pointer;">
                🖨️ Imprimir Relatório
            </button>
        </div>
    </body>
    </html>
    """
    return html

# ----------- ESTILOS CSS (sem alterações) -----------
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
.editable-cell { background-color: #fff; border: 1px solid #ddd; padding: 4px; border-radius: 3px; }
.editable-cell:focus { border-color: #4CAF50; outline: none; }
.materials-section { border: 2px solid #4CAF50; border-radius: 8px; padding: 15px; margin: 15px 0; }
.materials-header { background-color: #4CAF50; color: white; padding: 10px; border-radius: 6px; margin-bottom: 10px; }
.inline-edit-btn { padding: 2px 8px; font-size: 0.8em; margin: 0 2px; }
</style>
""", unsafe_allow_html=True)


# ----------- FUNÇÕES AUXILIARES -----------
def load_technicians():
    try:
        res = supabase.table("technicians").select("*").execute()
        return {t["id"]: t for t in res.data} if res.data else {}
    except Exception as e:
        st.error(f"Erro ao carregar técnicos: {str(e)}")
        return {}

def load_locations():
    try:
        res = supabase.table("locations").select("*").execute()
        return {l["id"]: l["name"] for l in res.data} if res.data else {}
    except Exception as e:
        st.error(f"Erro ao carregar localidades: {str(e)}")
        return {}

def get_technician_name(tech_id, tech_dict):
    if not tech_id:
        return "Não atribuído"
    return tech_dict.get(str(tech_id), {}).get("name", "Não atribuído")

def get_location_name(loc_id, loc_dict):
    return loc_dict.get(str(loc_id), "—")

def get_specialties_list():
    try:
        res = supabase.table("technicians").select("specialty").execute()
        specialties = {r["specialty"] for r in res.data if r.get("specialty")}
        return sorted(specialties) if specialties else ["Refrigeração", "Elétrica", "Hidráulica", "Mecânica"]
    except:
        return ["Refrigeração", "Elétrica", "Hidráulica", "Mecânica"]

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
        supabase.storage.from_("task-attachments").upload(
            file_path, 
            uploaded_file.getvalue(), 
            file_options={"content-type": uploaded_file.type}
        )
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

# ----------- GERENCIAMENTO DE TABELAS DE MATERIAIS -----------
def load_task_materials_tables(task_id, force_reload=False):
    if not force_reload and task_id in st.session_state["task_materials_loaded"]:
        return st.session_state["materials_tables"].get(task_id, [])
    try:
        res = supabase.table("task_materials").select("*").eq("task_id", task_id).execute()
        tables = []
        if res.data:
            for table_data in res.data:
                try:
                    data_json = json.loads(table_data["table_data"])
                    if not isinstance(data_json, dict):
                        data_json = {}
                    name = data_json.get("name", "Tabela de Materiais")
                    headers = data_json.get("headers", ["Material", "Quantidade", "Unidade", "Observações"])
                    data = data_json.get("data", [])
                    if not isinstance(headers, list):
                        headers = ["Material", "Quantidade", "Unidade", "Observações"]
                    if not isinstance(data, list):
                        data = []
                    else:
                        data = [row if isinstance(row, list) else [] for row in data]
                    tables.append({
                        "id": table_data["id"],
                        "name": name,
                        "rows": len(data),
                        "cols": len(headers),
                        "data": data,
                        "headers": headers,
                        "has_data": any(
                            any(cell.strip() for cell in row) 
                            for row in data
                        )
                    })
                except Exception as e:
                    print(f"Erro ao processar tabela: {e}")
                    tables.append(create_default_table())
        else:
            tables = [create_default_table()]
        st.session_state["materials_tables"][task_id] = tables
        st.session_state["task_materials_loaded"].add(task_id)
        if task_id not in st.session_state["table_editor_states"]:
            st.session_state["table_editor_states"][task_id] = {}
        return tables
    except Exception as e:
        st.error(f"Erro ao carregar tabelas de materiais: {str(e)}")
        default_tables = [create_default_table()]
        st.session_state["materials_tables"][task_id] = default_tables
        return default_tables

def save_task_materials_tables(task_id, tables):
    try:
        supabase.table("task_materials").delete().eq("task_id", task_id).execute()
        for table in tables:
            table_data = {
                "name": table.get("name", "Tabela de Materiais"),
                "headers": table.get("headers", ["Material", "Quantidade", "Unidade", "Observações"]),
                "data": table.get("data", [])
            }
            supabase.table("task_materials").insert({
                "task_id": task_id,
                "table_data": json.dumps(table_data, ensure_ascii=False)
            }).execute()
        st.session_state["materials_tables"][task_id] = tables
        st.session_state["task_materials_loaded"].add(task_id)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar tabelas de materiais: {str(e)}")
        return False

def create_default_table():
    return {
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
        "has_data": False
    }

def get_table_editor_state(task_id, table_idx):
    if task_id not in st.session_state["table_editor_states"]:
        st.session_state["table_editor_states"][task_id] = {}
    table_key = f"table_{table_idx}"
    if table_key not in st.session_state["table_editor_states"][task_id]:
        tables = load_task_materials_tables(task_id)
        if table_idx < len(tables):
            table = tables[table_idx]
            st.session_state["table_editor_states"][task_id][table_key] = {
                "name": table.get("name", f"Tabela {table_idx + 1}"),
                "rows": table.get("rows", 3),
                "cols": table.get("cols", 4),
                "headers": table.get("headers", ["Material", "Quantidade", "Unidade", "Observações"]).copy(),
                "data": [row.copy() for row in table.get("data", [])],
                "has_data": table.get("has_data", False)
            }
    return st.session_state["table_editor_states"][task_id].get(table_key, None)

def update_table_editor_state(task_id, table_idx, updates):
    table_key = f"table_{table_idx}"
    if task_id in st.session_state["table_editor_states"] and table_key in st.session_state["table_editor_states"][task_id]:
        st.session_state["table_editor_states"][task_id][table_key].update(updates)
        return True
    return False

def show_materials_table_editor(task_id, table_idx):
    if task_id not in st.session_state["materials_tables"]:
        st.session_state["materials_tables"][task_id] = load_task_materials_tables(task_id)
    tables = st.session_state["materials_tables"][task_id]
    if table_idx >= len(tables):
        st.error("Índice de tabela inválido")
        return
    table = tables[table_idx]
    editor_state = get_table_editor_state(task_id, table_idx)
    if editor_state is None:
        editor_state = {
            "name": table.get("name", f"Tabela {table_idx + 1}"),
            "rows": table.get("rows", 3),
            "cols": table.get("cols", 4),
            "headers": table.get("headers", ["Material", "Quantidade", "Unidade", "Observações"]).copy(),
            "data": [row.copy() for row in table.get("data", [])],
            "has_data": table.get("has_data", False)
        }
        update_table_editor_state(task_id, table_idx, editor_state)
    st.markdown(f"#### 📊 {editor_state['name']}")
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_rows = st.number_input(
                "Linhas", 
                min_value=1, 
                max_value=50, 
                value=editor_state["rows"],
                key=f"rows_{task_id}_{table_idx}_{editor_state['name']}"
            )
        with col2:
            new_cols = st.number_input(
                "Colunas", 
                min_value=2, 
                max_value=10, 
                value=editor_state["cols"],
                key=f"cols_{task_id}_{table_idx}_{editor_state['name']}"
            )
        with col3:
            new_name = st.text_input(
                "Nome", 
                value=editor_state["name"],
                key=f"name_{task_id}_{table_idx}_{editor_state['name']}"
            )
        with col4:
            st.write("")
            st.write("")
            if st.button("🔄 Atualizar Tamanho", 
                        key=f"update_size_{task_id}_{table_idx}_{editor_state['name']}",
                        use_container_width=True):
                editor_state["rows"] = new_rows
                editor_state["cols"] = new_cols
                editor_state["name"] = new_name
                current_data = editor_state["data"]
                adjusted_data = []
                for r in range(new_rows):
                    if r < len(current_data):
                        row = current_data[r]
                        if new_cols > len(row):
                            row = row + [""] * (new_cols - len(row))
                        elif new_cols < len(row):
                            row = row[:new_cols]
                    else:
                        row = [""] * new_cols
                    adjusted_data.append(row)
                editor_state["data"] = adjusted_data
                current_headers = editor_state["headers"]
                if new_cols > len(current_headers):
                    for i in range(len(current_headers), new_cols):
                        current_headers.append(f"Coluna {i+1}")
                elif new_cols < len(current_headers):
                    current_headers = current_headers[:new_cols]
                editor_state["headers"] = current_headers
                update_table_editor_state(task_id, table_idx, editor_state)
                st.rerun()
        st.divider()
        st.markdown("**Cabeçalhos das colunas:**")
        header_cols = st.columns(new_cols)
        new_headers = []
        for i in range(new_cols):
            with header_cols[i]:
                default_header = editor_state["headers"][i] if i < len(editor_state["headers"]) else f"Coluna {i+1}"
                header = st.text_input(
                    f"Coluna {i+1}", 
                    value=default_header,
                    key=f"header_{task_id}_{table_idx}_{i}_{editor_state['name']}",
                    label_visibility="collapsed"
                )
                new_headers.append(header)
        if new_headers != editor_state["headers"]:
            editor_state["headers"] = new_headers
            update_table_editor_state(task_id, table_idx, {"headers": new_headers})
        st.divider()
        st.markdown("**Preencha os dados da tabela:**")
        data = editor_state["data"]
        if len(data) < new_rows:
            for _ in range(new_rows - len(data)):
                data.append([""] * new_cols)
        cell_updates = {}
        for r in range(new_rows):
            row_cols = st.columns(new_cols)
            for c in range(new_cols):
                with row_cols[c]:
                    if r < len(data):
                        if c < len(data[r]):
                            cell_value = data[r][c]
                        else:
                            data[r].append("")
                            cell_value = ""
                    else:
                        data.append([""] * new_cols)
                        cell_value = ""
                    new_value = st.text_input(
                        "",
                        value=cell_value,
                        key=f"cell_{task_id}_{table_idx}_{r}_{c}_{editor_state['name']}",
                        label_visibility="collapsed",
                        placeholder=f"Linha {r+1}, Coluna {c+1}"
                    )
                    if new_value != cell_value:
                        cell_updates[(r, c)] = new_value
        if cell_updates:
            for (r, c), value in cell_updates.items():
                if r < len(data):
                    if c < len(data[r]):
                        data[r][c] = value
                    else:
                        while len(data[r]) <= c:
                            data[r].append("")
                        data[r][c] = value
                else:
                    new_row = [""] * new_cols
                    new_row[c] = value
                    data.append(new_row)
            editor_state["data"] = data
            update_table_editor_state(task_id, table_idx, {"data": data})
        editor_state["has_data"] = any(
            any(cell.strip() for cell in row) 
            for row in editor_state["data"]
        )
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("💾 Salvar Tabela", 
                        key=f"save_table_{task_id}_{table_idx}_{editor_state['name']}",
                        use_container_width=True,
                        type="primary"):
                updated_table = {
                    "id": table.get("id", str(uuid.uuid4())),
                    "name": editor_state["name"],
                    "rows": editor_state["rows"],
                    "cols": editor_state["cols"],
                    "data": editor_state["data"],
                    "headers": editor_state["headers"],
                    "has_data": editor_state["has_data"]
                }
                if table_idx < len(tables):
                    tables[table_idx] = updated_table
                    st.session_state["materials_tables"][task_id] = tables
                if save_task_materials_tables(task_id, tables):
                    st.success("✅ Tabela salva com sucesso!")
                    st.rerun()
        with col2:
            if st.button("➕ Adicionar Linha", 
                        key=f"add_row_{task_id}_{table_idx}_{editor_state['name']}",
                        use_container_width=True):
                editor_state["data"].append([""] * editor_state["cols"])
                editor_state["rows"] += 1
                update_table_editor_state(task_id, table_idx, {
                    "data": editor_state["data"],
                    "rows": editor_state["rows"]
                })
                st.rerun()
        with col3:
            if st.button("🗑️ Limpar Tabela", 
                        key=f"clear_table_{task_id}_{table_idx}_{editor_state['name']}",
                        use_container_width=True):
                editor_state["data"] = [["" for _ in range(editor_state["cols"])] for _ in range(editor_state["rows"])]
                editor_state["has_data"] = False
                update_table_editor_state(task_id, table_idx, {
                    "data": editor_state["data"],
                    "has_data": editor_state["has_data"]
                })
                st.rerun()
        with col4:
            if len(tables) > 1:
                if st.button("❌ Remover Tabela", 
                            key=f"remove_table_{task_id}_{table_idx}_{editor_state['name']}",
                            use_container_width=True,
                            type="secondary"):
                    tables.pop(table_idx)
                    st.session_state["materials_tables"][task_id] = tables
                    table_key = f"table_{table_idx}"
                    if task_id in st.session_state["table_editor_states"] and table_key in st.session_state["table_editor_states"][task_id]:
                        del st.session_state["table_editor_states"][task_id][table_key]
                    if save_task_materials_tables(task_id, tables):
                        st.success("✅ Tabela removida!")
                        st.rerun()
            else:
                st.button("❌ Remover Tabela", 
                         disabled=True, 
                         help="Não é possível remover a última tabela",
                         use_container_width=True)

def show_materials_tables_manager(task_id, tables=None):
    if tables is None:
        tables = load_task_materials_tables(task_id)
    st.markdown("#### 📋 Gerenciador de Tabelas de Materiais")
    tab_options = [f"📊 {table['name']}" for table in tables]
    tab_options.append("➕ Nova Tabela")
    tab_key = f"tab_selection_{task_id}"
    if tab_key not in st.session_state:
        st.session_state[tab_key] = 0
    selected_tab_index = st.radio(
        "Selecione uma tabela:",
        options=list(range(len(tab_options))),
        format_func=lambda i: tab_options[i],
        horizontal=True,
        key=f"tab_radio_{task_id}",
        label_visibility="collapsed"
    )
    st.divider()
    if selected_tab_index == len(tables):
        st.markdown("#### ➕ Criar Nova Tabela de Materiais")
        col1, col2, col3 = st.columns(3)
        with col1:
            new_name = st.text_input(
                "Nome da nova tabela", 
                value=f"Tabela de Materiais {len(tables) + 1}",
                key=f"new_table_name_{task_id}"
            )
        with col2:
            new_rows = st.number_input(
                "Linhas", 
                min_value=1, 
                max_value=50, 
                value=3,
                key=f"new_table_rows_{task_id}"
            )
        with col3:
            new_cols = st.number_input(
                "Colunas", 
                min_value=2, 
                max_value=10, 
                value=4,
                key=f"new_table_cols_{task_id}"
            )
        if st.button(
            "✅ Criar Nova Tabela", 
            use_container_width=True, 
            type="primary",
            key=f"create_table_btn_{task_id}"
        ):
            new_table = create_default_table()
            new_table["name"] = new_name
            new_table["rows"] = new_rows
            new_table["cols"] = new_cols
            new_table["data"] = [["" for _ in range(new_cols)] for _ in range(new_rows)]
            new_table["headers"] = ["Material", "Quantidade", "Unidade", "Observações"][:new_cols]
            if task_id not in st.session_state["materials_tables"]:
                st.session_state["materials_tables"][task_id] = []
            st.session_state["materials_tables"][task_id].append(new_table)
            save_task_materials_tables(task_id, st.session_state["materials_tables"][task_id])
            st.success(f"✅ Nova tabela '{new_name}' criada!")
            st.rerun()
    else:
        show_materials_table_editor(task_id, selected_tab_index)
    st.divider()
    st.markdown("#### 👁️ Visualização Consolidada")
    has_any_data = any(table.get("has_data", False) for table in tables)
    if has_any_data:
        for table_idx, table in enumerate(tables):
            if table.get("has_data"):
                st.markdown(f"**{table['name']}**")
                df_data = []
                headers = table.get("headers", [])
                for row in table.get("data", []):
                    if any(cell.strip() for cell in row):
                        if len(row) != len(headers):
                            if len(row) < len(headers):
                                row = row + [""] * (len(headers) - len(row))
                            else:
                                row = row[:len(headers)]
                        df_data.append(row)
                if df_data:
                    try:
                        df = pd.DataFrame(df_data, columns=headers)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        item_count = len(df_data)
                        st.caption(f"Total de itens nesta tabela: {item_count}")
                    except Exception as e:
                        st.error(f"Erro ao exibir tabela: {str(e)}")
                        st.write("Dados da tabela:")
                        for i, row in enumerate(df_data, 1):
                            st.write(f"Linha {i}: {row}")
                st.divider()
    else:
        st.info("ℹ️ Nenhuma tabela contém dados. Preencha as tabelas acima.")

# ----------- FUNÇÕES PARA VISUALIZAÇÃO DE TABELAS -----------
def render_materials_tables(task_id):
    tables = load_task_materials_tables(task_id)
    if not any(table.get("has_data", False) for table in tables):
        return False
    st.markdown("### 📋 Lista de Materiais")
    for table_idx, table in enumerate(tables):
        if table.get("has_data", False):
            st.markdown(f"**{table['name']}**")
            data_with_content = []
            headers = table.get("headers", [])
            for row in table.get("data", []):
                if any(cell.strip() for cell in row):
                    if len(row) != len(headers):
                        if len(row) < len(headers):
                            row = row + [""] * (len(headers) - len(row))
                        else:
                            row = row[:len(headers)]
                    data_with_content.append(row)
            if data_with_content:
                try:
                    valid_rows = []
                    for row in data_with_content:
                        if len(row) != len(headers):
                            if len(row) < len(headers):
                                row = row + [""] * (len(headers) - len(row))
                            else:
                                row = row[:len(headers)]
                        valid_rows.append(row)
                    df = pd.DataFrame(valid_rows, columns=headers)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(
                            "✏️ Editar Tabela", 
                            key=f"edit_table_{task_id}_{table_idx}",
                            use_container_width=True
                        ):
                            st.session_state["active_materials_editor"] = task_id
                            st.rerun()
                    with col2:
                        try:
                            csv = df.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(
                                "📥 Exportar CSV",
                                data=csv,
                                file_name=f"materiais_{table['name'].replace(' ', '_')}.csv",
                                mime="text/csv",
                                key=f"export_{task_id}_{table_idx}",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error(f"Erro ao exportar: {str(e)}")
                    st.divider()
                except Exception as e:
                    st.error(f"❌ Erro ao exibir tabela '{table['name']}': {str(e)}")
                    st.write("**Dados da tabela (modo de emergência):**")
                    for i, row in enumerate(data_with_content, 1):
                        st.write(f"**Linha {i}:** {row}")
                    st.divider()
    return True

def materials_tables_to_dataframes(task_id):
    tables = load_task_materials_tables(task_id)
    dataframes = []
    for table in tables:
        if table.get("has_data", False):
            data_with_content = []
            headers = table.get("headers", [])
            for row in table.get("data", []):
                if any(cell.strip() for cell in row):
                    if len(row) != len(headers):
                        if len(row) < len(headers):
                            row = row + [""] * (len(headers) - len(row))
                        else:
                            row = row[:len(headers)]
                    data_with_content.append(row)
            if data_with_content:
                try:
                    valid_rows = []
                    for row in data_with_content:
                        if len(row) != len(headers):
                            if len(row) < len(headers):
                                row = row + [""] * (len(headers) - len(row))
                            else:
                                row = row[:len(headers)]
                        valid_rows.append(row)
                    df = pd.DataFrame(valid_rows, columns=headers)
                    dataframes.append((table["name"], df))
                except Exception as e:
                    print(f"Erro ao converter tabela '{table['name']}' para DataFrame: {e}")
    return dataframes

# ----------- FUNÇÕES DE RECORRÊNCIA E STATUS -----------
def get_next_due_date(due_date, recurrence):
    if recurrence == "daily": 
        return due_date + timedelta(days=1)
    elif recurrence == "weekly": 
        return due_date + timedelta(weeks=1)
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
            "checklist": [{"item": i["item"], "is_completed": i["is_completed"]} for i in checklist_items],
            "recurrence": task.get("recurrence"),
            "notes": task.get("notes", "")
        }
        supabase.table("task_history").insert(archive_data).execute()
    except Exception as e:
        st.toast(f"⚠️ Erro ao arquivar: {str(e)}", icon="⚠️")

def create_recurring_task(original_task):
    recurrence = original_task.get("recurrence")
    if not recurrence: 
        return
    try:
        current_due = datetime.fromisoformat(original_task["due_date"])
        next_due = get_next_due_date(current_due, recurrence)
        if not next_due: 
            return
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
        if not new_task_id: 
            return
        checklist_data = load_checklist(original_task["id"])
        if checklist_data:
            for item in checklist_data:
                supabase.table("checklists").insert({
                    "task_id": new_task_id,
                    "item": item["item"],
                    "is_completed": False
                }).execute()
        tables = load_task_materials_tables(original_task["id"])
        save_task_materials_tables(new_task_id, tables)
        next_date_str = next_due.strftime('%d/%m/%Y')
        st.toast(f"🔁 Tarefa recorrente agendada para {next_date_str}", icon="🔁")
    except Exception as e:
        st.toast(f"⚠️ Erro na recorrência: {str(e)}", icon="⚠️")

def update_overdue_tasks():
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
    if not is_scheduled or not due_datetime:
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

# ----------- FORMULÁRIO DE EDIÇÃO COMPLETA -----------
def show_edit_form(task_id):
    st.subheader("✏️ Editar Atividade")
    task_res = supabase.table("maintenance_tasks").select("*").eq("id", task_id).execute()
    if not task_res.data:
        st.error("❌ Tarefa não encontrada")
        if st.button("Fechar", use_container_width=True):
            st.session_state["show_edit_form"] = False
            st.rerun()
        return
    task = task_res.data[0]
    checklist_data = load_checklist(task_id)
    if task_id not in st.session_state["materials_tables"]:
        load_task_materials_tables(task_id)
    current_title = task.get("title", "")
    current_description = task.get("description", "")
    current_specialty = task.get("specialty", "")
    current_technician = task.get("technician_id")
    current_location = task.get("location_id")
    current_priority = task.get("priority", "media")
    current_recurrence = task.get("recurrence")
    current_notes = task.get("notes", "")
    current_due_date = None
    current_due_time = None
    if task.get("due_date"):
        try:
            dt = datetime.fromisoformat(task["due_date"])
            current_due_date = dt.date()
            current_due_time = dt.time()
        except:
            current_due_date = datetime.now().date()
            current_due_time = datetime.now().time()
    tab1, tab2, tab3 = st.tabs(["📝 Informações Básicas", "📋 Tabelas de Materiais", "✅ Checklist"])
    with tab1:
        with st.form("edit_activity_form"):
            st.markdown("#### 📝 Informações da Atividade")
            title = st.text_input("Título *", value=current_title)
            description = st.text_area("Descrição", value=current_description, height=100)
            col1, col2 = st.columns(2)
            with col1:
                specialties = get_specialties_list()
                specialty_index = specialties.index(current_specialty) if current_specialty in specialties else 0
                specialty = st.selectbox("Especialidade *", specialties, index=specialty_index)
                technicians = load_technicians()
                technician_id = None
                if technicians:
                    tech_options = list(technicians.keys())
                    tech_index = tech_options.index(current_technician) + 1 if current_technician in tech_options else 0
                    technician_id = st.selectbox("Técnico", options=[None] + tech_options, 
                                               index=tech_index,
                                               format_func=lambda x: "Não atribuído" if x is None else f"{technicians[x]['name']} ({technicians[x].get('specialty', 'N/A')})")
            with col2:
                locations = load_locations()
                loc_options = list(locations.keys())
                loc_index = loc_options.index(current_location) if current_location in loc_options else 0
                location_id = st.selectbox("Localidade *", options=loc_options, 
                                         index=loc_index, 
                                         format_func=lambda x: locations[x])
                col_date, col_time = st.columns(2)
                with col_date:
                    schedule_task = st.checkbox("Programar atividade?", value=current_due_date is not None)
                    if schedule_task:
                        due_date = st.date_input("Data", value=current_due_date or datetime.now().date())
                    else:
                        due_date = None
                with col_time:
                    if schedule_task and due_date:
                        due_time = st.time_input("Hora", value=current_due_time or datetime.now().time())
                    else:
                        due_time = None
            st.markdown("#### ⚙️ Configurações")
            col1, col2 = st.columns(2)
            with col1:
                priority_options = list(PRIORITIES_WITH_EMOJIS.keys())
                priority_index = priority_options.index(current_priority) if current_priority in priority_options else 2
                priority = st.selectbox("Prioridade", options=priority_options,
                                      index=priority_index,
                                      format_func=lambda x: PRIORITIES_WITH_EMOJIS[x]["label"])
            with col2:
                recurrence_map = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
                reverse_recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
                current_recurrence_display = recurrence_map.get(current_recurrence, "Nenhuma")
                recurrence_display = st.selectbox("Recorrência", 
                                                options=["Nenhuma", "Diária", "Semanal", "Mensal"],
                                                index=["Nenhuma", "Diária", "Semanal", "Mensal"].index(current_recurrence_display))
                recurrence = reverse_recurrence_map[recurrence_display]
            st.markdown("#### 📝 Observações Técnicas")
            notes = st.text_area("Observações", value=current_notes, height=150)
            if schedule_task and due_date and due_time:
                due_datetime = datetime.combine(due_date, due_time)
                auto_status = determine_task_status(due_datetime, True)
            else:
                auto_status = "scheduled"
            st.info(f"**Status:** {status_labels.get(auto_status, auto_status)} *(determinado automaticamente)*")
            submitted = st.form_submit_button("💾 Salvar Alterações", type="primary")
            if submitted:
                if not title or not specialty or not location_id:
                    st.error("Preencha os campos obrigatórios (*)")
                else:
                    try:
                        due_datetime_iso = None
                        if schedule_task and due_date and due_time:
                            due_datetime = datetime.combine(due_date, due_time)
                            due_datetime_iso = due_datetime.isoformat()
                        updated_task = {
                            "title": title,
                            "description": description,
                            "specialty": specialty,
                            "technician_id": technician_id,
                            "location_id": location_id,
                            "due_date": due_datetime_iso,
                            "priority": priority,
                            "recurrence": recurrence,
                            "notes": notes,
                            "status": auto_status
                        }
                        supabase.table("maintenance_tasks").update(updated_task).eq("id", task_id).execute()
                        st.success("✅ Informações básicas salvas com sucesso!")
                        st.toast("✅ Atividade atualizada!", icon="💾")
                    except Exception as e:
                        st.error(f"❌ Erro ao salvar: {str(e)}")
    with tab2:
        st.markdown("#### 📋 Tabelas de Materiais")
        st.info("Gerencie as tabelas de materiais para esta atividade")
        tables = load_task_materials_tables(task_id)
        if st.button("🔄 Carregar Tabelas", key=f"load_tables_{task_id}"):
            load_task_materials_tables(task_id, force_reload=True)
            st.rerun()
        show_materials_tables_manager(task_id, tables)
    with tab3:
        st.markdown("#### ✅ Checklist")
        checklist_text = st.text_area(
    "Itens do checklist (um por linha)", 
    value="\n".join([item["item"] for item in checklist_data]),
    placeholder="Item 1\nItem 2\nItem 3...",
    height=200,
    key=f"checklist_edit_{task_id}"
)
        if st.button("💾 Atualizar Checklist", key=f"update_checklist_{task_id}", type="primary"):
            try:
                supabase.table("checklists").delete().eq("task_id", task_id).execute()
                if checklist_text.strip():
                    items = [item.strip() for item in checklist_text.split("\n") if item.strip()]
                    for item in items:
                        supabase.table("checklists").insert({
                            "task_id": task_id,
                            "item": item,
                            "is_completed": False
                        }).execute()
                st.success("✅ Checklist atualizado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao atualizar checklist: {str(e)}")
    if st.button("Fechar", use_container_width=True, key=f"close_edit_{task_id}"):
        st.session_state["show_edit_form"] = False
        st.rerun()

# ----------- MODAL DE DETALHES DA TAREFA (com novo botão de relatório) -----------
def show_task_modal(task):
    if not isinstance(task, dict) or "id" not in task:
        st.error("❌ Tarefa inválida")
        if st.button("Fechar", use_container_width=True):
            st.session_state["selected_task"] = None
            st.rerun()
        return
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
    task_id = task["id"]
    is_editing = st.session_state.get("editing_task_id") == task_id
    st.subheader(f"🔍 {task['title']}")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if not is_editing:
            if st.button("✏️ Editar Tudo", use_container_width=True, key=f"start_edit_{task_id}"):
                st.session_state["editing_task_id"] = task_id
                st.rerun()
        else:
            if st.button("💾 Salvar", use_container_width=True, type="primary", key=f"save_edit_{task_id}"):
                st.session_state["editing_task_id"] = None
                st.toast("✅ Alterações salvas!", icon="💾")
                st.rerun()
    with col2:
        if st.button("📋 Clonar", use_container_width=True, key=f"clone_{task_id}"):
            st.session_state["cloning_task_id"] = task_id
            st.session_state["show_clone_form"] = True
            st.rerun()
    with col3:
        if st.button("📄 Gerar Relatório", use_container_width=True, key=f"report_{task_id}"):
            # Carregar dados complementares
            checklist_items = load_checklist(task_id)
            materials_tables = load_task_materials_tables(task_id)
            attachments = load_attachments(task_id)
            technicians = load_technicians()
            locations = load_locations()
            
            html_report = generate_html_report(
                task=task,
                checklist_items=checklist_items,
                materials_tables=materials_tables,
                attachments=attachments,
                technicians=technicians,
                locations=locations
            )
            st.session_state["generated_report_html"] = html_report
            st.session_state["show_report"] = True
            st.rerun()
    with col4:
        if st.button("🗑️ Excluir", use_container_width=True, type="secondary", key=f"delete_{task_id}"):
            with st.popover("⚠️ Confirmar Exclusão"):
                st.warning("Tem certeza que deseja excluir esta atividade?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("Sim, excluir", type="primary"):
                        supabase.table("checklists").delete().eq("task_id", task_id).execute()
                        supabase.table("task_materials").delete().eq("task_id", task_id).execute()
                        supabase.table("maintenance_tasks").delete().eq("id", task_id).execute()
                        st.session_state["selected_task"] = None
                        st.toast("🗑️ Tarefa excluída!", icon="🗑️")
                        st.rerun()
                with col_no:
                    if st.button("Cancelar"):
                        st.rerun()
    
    st.divider()
    with st.container(border=True):
        st.markdown("#### 📝 Informações da Atividade")
        if is_editing:
            with st.form(f"inline_edit_{task_id}"):
                col1, col2 = st.columns(2)
                with col1:
                    title = st.text_input("Título", value=task.get("title", ""))
                    description = st.text_area("Descrição", value=task.get("description", ""), height=100)
                    specialties = get_specialties_list()
                    current_specialty = task.get("specialty", "")
                    specialty_index = specialties.index(current_specialty) if current_specialty in specialties else 0
                    specialty = st.selectbox("Especialidade", specialties, index=specialty_index)
                    technicians = load_technicians()
                    current_tech = task.get("technician_id")
                    if technicians:
                        tech_options = list(technicians.keys())
                        tech_index = tech_options.index(current_tech) + 1 if current_tech in tech_options else 0
                        technician_id = st.selectbox("Técnico", options=[None] + tech_options, 
                                                   index=tech_index,
                                                   format_func=lambda x: "Não atribuído" if x is None else f"{technicians[x]['name']}")
                with col2:
                    locations = load_locations()
                    current_location = task.get("location_id")
                    loc_options = list(locations.keys())
                    loc_index = loc_options.index(current_location) if current_location in loc_options else 0
                    location_id = st.selectbox("Localidade", options=loc_options, 
                                             index=loc_index, 
                                             format_func=lambda x: locations[x])
                    current_due_date = None
                    current_due_time = None
                    if task.get("due_date"):
                        try:
                            dt = datetime.fromisoformat(task["due_date"])
                            current_due_date = dt.date()
                            current_due_time = dt.time()
                        except:
                            current_due_date = datetime.now().date()
                            current_due_time = datetime.now().time()
                    col_date, col_time = st.columns(2)
                    with col_date:
                        schedule_task = st.checkbox("Programada?", value=current_due_date is not None)
                        if schedule_task:
                            due_date = st.date_input("Data", value=current_due_date or datetime.now().date())
                        else:
                            due_date = None
                    with col_time:
                        if schedule_task and due_date:
                            due_time = st.time_input("Hora", value=current_due_time or datetime.now().time())
                        else:
                            due_time = None
                    current_priority = task.get("priority", "media")
                    priority_options = list(PRIORITIES_WITH_EMOJIS.keys())
                    priority_index = priority_options.index(current_priority) if current_priority in priority_options else 2
                    priority = st.selectbox("Prioridade", options=priority_options,
                                          index=priority_index,
                                          format_func=lambda x: PRIORITIES_WITH_EMOJIS[x]["label"])
                notes = st.text_area("Observações", value=task.get("notes", ""), height=150)
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                        try:
                            due_datetime_iso = None
                            if schedule_task and due_date and due_time:
                                due_datetime = datetime.combine(due_date, due_time)
                                due_datetime_iso = due_datetime.isoformat()
                            status = determine_task_status(due_datetime_iso if due_datetime_iso else None, schedule_task)
                            updated_task = {
                                "title": title,
                                "description": description,
                                "specialty": specialty,
                                "technician_id": technician_id,
                                "location_id": location_id,
                                "due_date": due_datetime_iso,
                                "priority": priority,
                                "notes": notes,
                                "status": status
                            }
                            supabase.table("maintenance_tasks").update(updated_task).eq("id", task_id).execute()
                            st.success("✅ Atividade atualizada!")
                            st.session_state["editing_task_id"] = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao salvar: {str(e)}")
                with col_cancel:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state["editing_task_id"] = None
                        st.rerun()
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Título:** {task['title']}")
                st.markdown(f"**Descrição:** {task.get('description', '—')}")
                st.markdown(f"**Especialidade:** {task.get('specialty', '—')}")
                st.markdown(f"**Técnico:** {get_technician_name(task['technician_id'], load_technicians())}")
                st.markdown(f"**Local:** {get_location_name(task['location_id'], load_locations())}")
            with col2:
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
    st.divider()
    st.markdown("#### 📋 Lista de Materiais")
    tables_exist = render_materials_tables(task_id)
    if not tables_exist:
        st.info("📝 Nenhuma tabela de materiais cadastrada.")
    if st.button("📊 Gerenciar Tabelas", key=f"manage_tables_{task_id}", use_container_width=True):
        st.session_state["active_materials_editor"] = task_id
        st.rerun()
    if st.session_state.get("active_materials_editor") == task_id:
        st.divider()
        show_materials_tables_manager(task_id)
        if st.button("✅ Concluir Edição", key=f"finish_edit_tables_{task_id}", use_container_width=True, type="primary"):
            st.session_state["active_materials_editor"] = None
            st.rerun()
    st.divider()
    st.markdown("#### ✅ Checklist")
    checklist_data = load_checklist(task_id)
    checklist_key = f"checklist_{task_id}"
    if checklist_key not in st.session_state:
        st.session_state[checklist_key] = checklist_data
    total_items = len(st.session_state[checklist_key])
    completed_items = sum(1 for item in st.session_state[checklist_key] if item.get("is_completed", False))
    progress = completed_items / total_items if total_items > 0 else 0
    st.progress(progress)
    st.caption(f"Progresso: {completed_items}/{total_items} ({progress:.0%})")
    with st.form(f"checklist_form_{task_id}"):
        updated_checklist = []
        for i, item in enumerate(st.session_state[checklist_key]):
            col1, col2, col3 = st.columns([1, 20, 1])
            with col1:
                is_checked = st.checkbox("", value=item.get("is_completed", False),
                                       key=f"check_{task_id}_{i}")
            with col2:
                if is_checked:
                    st.markdown(f"<div class='checklist-item-completed'>{item['item']} ✅</div>", 
                              unsafe_allow_html=True)
                else:
                    st.markdown(item["item"])
            with col3:
                if st.form_submit_button("🗑️", key=f"delete_item_{task_id}_{i}", 
                                       help="Excluir item"):
                    try:
                        if item.get("id"):
                            supabase.table("checklists").delete().eq("id", item["id"]).execute()
                        st.session_state[checklist_key].pop(i)
                        st.toast("Item removido!", icon="🗑️")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir item: {str(e)}")
            updated_checklist.append({
                "id": item["id"],
                "item": item["item"],
                "is_completed": is_checked
            })
        col_save, col_reset, col_add = st.columns(3)
        with col_save:
            save_checklist = st.form_submit_button("💾 Salvar", use_container_width=True, type="primary")
        with col_reset:
            reset_checklist = st.form_submit_button("🔄 Reiniciar", use_container_width=True)
        with col_add:
            add_item = st.form_submit_button("➕ Novo Item", use_container_width=True)
        if save_checklist:
            try:
                for item in updated_checklist:
                    if item["id"]:
                        supabase.table("checklists").update({
                            "is_completed": item["is_completed"]
                        }).eq("id", item["id"]).execute()
                st.session_state[checklist_key] = updated_checklist
                st.toast("✅ Checklist salvo!", icon="💾")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao salvar: {str(e)}")
        if reset_checklist:
            try:
                for item in st.session_state[checklist_key]:
                    if item["id"]:
                        supabase.table("checklists").update({
                            "is_completed": False
                        }).eq("id", item["id"]).execute()
                reset_data = [{"id": item["id"], "item": item["item"], "is_completed": False} 
                            for item in st.session_state[checklist_key]]
                st.session_state[checklist_key] = reset_data
                st.toast("🔄 Checklist reiniciado!", icon="🔄")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao reiniciar: {str(e)}")
    if add_item:
        with st.form(f"new_item_{task_id}"):
            new_item = st.text_input("Novo item:", placeholder="Digite o novo item...")
            col_add, col_cancel = st.columns(2)
            with col_add:
                if st.form_submit_button("✅ Adicionar", use_container_width=True):
                    if new_item.strip():
                        try:
                            supabase.table("checklists").insert({
                                "task_id": task_id,
                                "item": new_item.strip(),
                                "is_completed": False
                            }).execute()
                            st.toast("✅ Item adicionado!", icon="➕")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")
            with col_cancel:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    st.rerun()
    st.divider()
    st.markdown("### 📎 Anexos")
    uploaded_files = st.file_uploader("Adicionar imagens", 
                                     type=['png', '.jpg', '.jpeg'], 
                                     accept_multiple_files=True, 
                                     key=f"upload_{task_id}")
    if uploaded_files:
        for f in uploaded_files:
            handle_file_upload(task_id, f)
    attachments = load_attachments(task_id)
    if attachments:
        cols = st.columns(3)
        for i, att in enumerate(attachments):
            with cols[i % 3]:
                url = get_attachment_url(task_id, att['name'])
                if url and is_image_file(att['name']):
                    st.image(url, caption=att['name'], use_column_width=True)
    else:
        st.caption("📷 Nenhuma imagem anexada.")
    st.divider()
    st.markdown("### 📝 Observações Técnicas")
    notes = task.get('notes', '')
    if notes:
        st.text(notes)
    else:
        st.caption("_Nenhuma observação._")
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        if task["status"] in ["scheduled", "overdue"]:
            if st.button("▶️ Iniciar", use_container_width=True, key=f"start_{task_id}"):
                supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task_id).execute()
                st.toast("▶️ Tarefa iniciada!", icon="▶️")
                st.rerun()
        elif task["status"] == "in_progress":
            if st.button("✅ Concluir", use_container_width=True, key=f"complete_{task_id}"):
                supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task_id).execute()
                checklist_items = [{"text": item["item"], "checked": item["is_completed"]} 
                                 for item in st.session_state[checklist_key]]
                archive_task(task, checklist_items)
                if task.get("recurrence"):
                    create_recurring_task(task)
                st.toast("✅ Tarefa concluída e arquivada!", icon="✅")
                st.rerun()
    with col2:
        if st.button("✏️ Edição Completa", use_container_width=True, key=f"full_edit_{task_id}"):
            st.session_state["show_edit_form"] = True
            st.session_state["editing_task_data"] = {"id": task_id}
            st.rerun()
    with col3:
        if st.button("Fechar", use_container_width=True, key=f"close_{task_id}"):
            st.session_state["selected_task"] = None
            st.session_state["editing_task_id"] = None
            st.session_state["active_materials_editor"] = None
            st.rerun()

# ----------- FORMULÁRIO NOVA ATIVIDADE -----------
def show_new_activity_form():
    st.subheader("➕ Nova Atividade")
    tab1, tab2 = st.tabs(["📝 Informações Básicas", "📋 Tabelas de Materiais"])
    with tab1:
        with st.form("new_activity", clear_on_submit=True):
            st.markdown("#### 📝 Informações da Atividade")
            title = st.text_input("Título *", placeholder="Título da atividade...")
            description = st.text_area("Descrição", placeholder="Descrição detalhada...", height=100)
            col1, col2 = st.columns(2)
            with col1:
                specialty = st.selectbox("Especialidade *", get_specialties_list())
                technicians = load_technicians()
                technician_id = None
                if technicians:
                    technician_options = list(technicians.keys())
                    technician_id = st.selectbox("Técnico", options=[None] + technician_options,
                                               format_func=lambda x: "Não atribuído" if x is None else f"{technicians[x]['name']}")
            with col2:
                locations = load_locations()
                location_id = st.selectbox("Localidade *", options=list(locations.keys()), 
                                         format_func=lambda x: locations[x])
                col_date, col_time = st.columns(2)
                with col_date:
                    schedule_now = st.checkbox("Programar agora?", value=False)
                    if schedule_now:
                        due_date = st.date_input("Data", value=datetime.now())
                    else:
                        due_date = None
                with col_time:
                    if schedule_now and due_date:
                        due_time = st.time_input("Hora", value=datetime.now().time())
                    else:
                        due_time = None
            st.markdown("#### ⚙️ Configurações")
            col1, col2 = st.columns(2)
            with col1:
                priority = st.selectbox("Prioridade", options=list(PRIORITIES_WITH_EMOJIS.keys()),
                                      format_func=lambda x: PRIORITIES_WITH_EMOJIS[x]["label"], 
                                      index=2)
            with col2:
                recurrence = st.selectbox("Recorrência", options=["Nenhuma", "Diária", "Semanal", "Mensal"])
                recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
            st.markdown("#### 📝 Observações Técnicas")
            notes = st.text_area("Observações", placeholder="Observações técnicas...", height=150)
            st.markdown("#### ✅ Checklist Inicial")
            checklist_text = st.text_area(
    "Itens do checklist (um por linha)", 
    value="\n".join([item["item"] for item in checklist_data]),
    placeholder="Item 1\nItem 2\nItem 3...",
    height=200,
    key=f"checklist_edit_{task_id}"
)
            submitted = st.form_submit_button("Criar Atividade", type="primary")
            if submitted:
                if not title or not specialty or not location_id:
                    st.error("Preencha os campos obrigatórios (*)")
                else:
                    try:
                        due_datetime_iso = None
                        if schedule_now and due_date and due_time:
                            due_datetime = datetime.combine(due_date, due_time)
                            due_datetime_iso = due_datetime.isoformat()
                        status = determine_task_status(due_datetime_iso if due_datetime_iso else None, schedule_now)
                        new_task = {
                            "title": title,
                            "description": description,
                            "specialty": specialty,
                            "technician_id": technician_id,
                            "location_id": location_id,
                            "due_date": due_datetime_iso,
                            "priority": priority,
                            "recurrence": recurrence_map[recurrence],
                            "notes": notes,
                            "status": status
                        }
                        res = supabase.table("maintenance_tasks").insert(new_task).execute()
                        new_task_id = res.data[0]["id"] if res.data else None
                        if new_task_id:
                            if checklist_items:
                                items = [item.strip() for item in checklist_text.split("\n") if item.strip()]
                                for item in items:
                                    supabase.table("checklists").insert({
                                        "task_id": new_task_id,
                                        "item": item,
                                        "is_completed": False
                                    }).execute()
                            if "new_task_tables" in st.session_state:
                                save_task_materials_tables(new_task_id, st.session_state["new_task_tables"])
                                del st.session_state["new_task_tables"]
                            st.success("✅ Atividade criada com sucesso!")
                            st.toast("✅ Atividade criada com sucesso!", icon="✅")
                            st.session_state["show_new_form"] = False
                            st.rerun()
                        else:
                            st.error("❌ Erro ao criar atividade")
                    except Exception as e:
                        st.error(f"❌ Erro ao criar: {str(e)}")
    with tab2:
        st.markdown("#### 📋 Tabelas de Materiais (Opcional)")
        st.info("Você pode criar tabelas de materiais agora ou depois na edição da atividade.")
        if "new_task_tables" not in st.session_state:
            st.session_state["new_task_tables"] = []
        show_materials_tables_manager("new_task", st.session_state["new_task_tables"])
    if st.button("Fechar", use_container_width=True, key="close_new_form"):
        st.session_state["show_new_form"] = False
        if "new_task_tables" in st.session_state:
            del st.session_state["new_task_tables"]
        st.rerun()

# ----------- FORMULÁRIO CLONAR -----------
def show_clone_form():
    st.subheader("📋 Clonar Tarefa")
    if not st.session_state["cloning_task_id"]:
        st.error("❌ ID da tarefa para clonar não encontrado")
        if st.button("Fechar", use_container_width=True):
            st.session_state["show_clone_form"] = False
            st.rerun()
        return
    task_id = st.session_state["cloning_task_id"]
    task_res = supabase.table("maintenance_tasks").select("*").eq("id", task_id).execute()
    if not task_res.data:
        st.error("❌ Tarefa não encontrada")
        if st.button("Fechar", use_container_width=True):
            st.session_state["show_clone_form"] = False
            st.rerun()
        return
    task = task_res.data[0]
    checklist_data = load_checklist(task_id)
    if "clone_form_data" not in st.session_state or not st.session_state["clone_form_data"]:
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
    clone_data = st.session_state["clone_form_data"]
    with st.form("clone_form"):
        st.markdown("#### 📝 Informações Básicas")
        title = st.text_input("Título *", value=clone_data.get("title", ""))
        description = st.text_area("Descrição", value=clone_data.get("description", ""))
        col1, col2 = st.columns(2)
        with col1:
            specialty = st.selectbox("Especialidade *", get_specialties_list(),
                                   index=get_specialties_list().index(clone_data.get("specialty")) if clone_data.get("specialty") in get_specialties_list() else 0)
            technicians = load_technicians()
            if technicians:
                st.markdown("#### 👥 Técnicos")
                tech_options = list(technicians.keys())
                tech_names = [f"{technicians[t]['name']} ({technicians[t].get('specialty', 'N/A')})" for t in tech_options]
                original_tech_id = clone_data.get("technician_id")
                original_tech_name = f"{technicians[original_tech_id]['name']} ({technicians[original_tech_id].get('specialty', 'N/A')})" if original_tech_id in technicians else ""
                selected_tech_names = st.multiselect(
                    "Técnicos (equipe)",
                    options=tech_names,
                    default=[original_tech_name] if original_tech_name in tech_names else [],
                    help="Selecione um ou mais técnicos"
                )
                name_to_tech_id = {f"{technicians[t]['name']} ({technicians[t].get('specialty', 'N/A')})": t for t in tech_options}
                selected_technician_ids = [name_to_tech_id[name] for name in selected_tech_names if name in name_to_tech_id]
            else:
                selected_technician_ids = []
        with col2:
            st.markdown("#### 🏢 Localidades")
            all_locations = load_locations()
            location_names = list(all_locations.values())
            location_ids = list(all_locations.keys())
            name_to_id = {name: loc_id for loc_id, name in all_locations.items()}
            original_location_id = clone_data.get("location_id")
            original_location_name = all_locations.get(original_location_id, "")
            selected_location_names = st.multiselect(
                "Localidades *",
                options=location_names,
                default=[original_location_name] if original_location_name in location_names else [],
                help="Selecione uma ou mais localidades"
            )
            selected_location_ids = [name_to_id[name] for name in selected_location_names if name in name_to_id]
            col_date, col_time = st.columns(2)
            with col_date:
                schedule_now = st.checkbox("Programar agora?", value=True)
                if schedule_now:
                    due_date = st.date_input("Data", value=datetime.now())
                else:
                    due_date = None
            with col_time:
                if schedule_now and due_date:
                    due_time = st.time_input("Hora", value=datetime.now().time())
                else:
                    due_time = None
        st.markdown("#### ⚙️ Configurações")
        col1, col2 = st.columns(2)
        with col1:
            priority = st.selectbox("Prioridade", options=list(PRIORITIES_WITH_EMOJIS.keys()),
                                  index=list(PRIORITIES_WITH_EMOJIS.keys()).index(clone_data.get("priority", "media")),
                                  format_func=lambda x: PRIORITIES_WITH_EMOJIS[x]["label"])
        with col2:
            recurrence = st.selectbox("Recorrência", options=["Nenhuma", "Diária", "Semanal", "Mensal"],
                                    index=["Nenhuma", "Diária", "Semanal", "Mensal"].index(clone_data.get("recurrence", "Nenhuma")))
            recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
        st.markdown("#### 📝 Observações Técnicas")
        notes = st.text_area("Observações", value=clone_data.get("notes", ""), height=150)
        checklist_text = st.text_area(
    "Itens do checklist (um por linha)", 
    value="\n".join([item["item"] for item in checklist_data]),
    placeholder="Item 1\nItem 2\nItem 3...",
    height=200,
    key=f"checklist_edit_{task_id}"
)
        if selected_location_names:
            total_tasks = len(selected_location_ids)
            st.markdown(f'<div class="multi-select-info">', unsafe_allow_html=True)
            st.markdown(f"**📋 Resumo da Clonagem:**")
            st.markdown(f"- **Localidades:** {len(selected_location_names)} → **{total_tasks} atividades**")
            if selected_technician_ids:
                if len(selected_technician_ids) > 1:
                    st.markdown(f"- **Equipe:** {len(selected_technician_ids)} técnicos")
                else:
                    tech_name = technicians.get(selected_technician_ids[0], {}).get('name', 'N/A')
                    st.markdown(f"- **Técnico:** {tech_name}")
            st.markdown('</div>', unsafe_allow_html=True)
        submitted = st.form_submit_button(f"🚀 Criar {len(selected_location_ids)} Atividades" if selected_location_ids else "Criar Cópia", 
                                         type="primary")
        if submitted:
            if not title or not selected_location_ids or not specialty:
                st.error("Preencha os campos obrigatórios (*)")
            else:
                try:
                    created_count = 0
                    due_datetime_iso = None
                    if schedule_now and due_date and due_time:
                        due_datetime = datetime.combine(due_date, due_time)
                        due_datetime_iso = due_datetime.isoformat()
                    status = determine_task_status(due_datetime_iso if due_datetime_iso else None, schedule_now)
                    for location_id in selected_location_ids:
                        location_name = all_locations.get(location_id, "")
                        task_title = f"{title} - {location_name}" if len(selected_location_names) > 1 else title
                        new_task = {
                            "title": task_title,
                            "description": description,
                            "specialty": specialty,
                            "technician_id": selected_technician_ids[0] if selected_technician_ids else None,
                            "location_id": location_id,
                            "due_date": due_datetime_iso,
                            "priority": priority,
                            "recurrence": recurrence_map[recurrence],
                            "notes": notes,
                            "status": status
                        }
                        if len(selected_technician_ids) > 1:
                            new_task["technician_team"] = ",".join(selected_technician_ids)
                        res = supabase.table("maintenance_tasks").insert(new_task).execute()
                        new_task_id = res.data[0]["id"] if res.data else None
                        if new_task_id:
                            if checklist_items:
                                items = [item.strip() for item in checklist_text.split("\n") if item.strip()]
                                for item in items:
                                    supabase.table("checklists").insert({
                                        "task_id": new_task_id,
                                        "item": item,
                                        "is_completed": False
                                    }).execute()
                            original_tables = load_task_materials_tables(task_id)
                            save_task_materials_tables(new_task_id, original_tables)
                            created_count += 1
                    st.success(f"✅ {created_count} atividade(s) criada(s) com sucesso!")
                    st.session_state.update({"show_clone_form": False, "cloning_task_id": None, "clone_form_data": {}})
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao criar atividades: {str(e)}")
    if st.button("Fechar", use_container_width=True, key="close_clone_form"):
        st.session_state.update({"show_clone_form": False, "cloning_task_id": None, "clone_form_data": {}})
        st.rerun()

# ----------- FUNÇÕES PARA RENDERIZAÇÃO -----------
def render_kanban_checklist(task):
    checklist_data = load_checklist(task["id"])
    if not checklist_data:
        return
    total = len(checklist_data)
    completed = sum(1 for item in checklist_data if item["is_completed"])
    if total > 0:
        progress = completed / total
        st.progress(progress)
        st.caption(f"Checklist: {completed}/{total} ({progress:.0%})")
        for i, item in enumerate(checklist_data[:2]):
            status = "✅" if item["is_completed"] else "⏳"
            st.markdown(f"{status} {item['item'][:30]}{'...' if len(item['item']) > 30 else ''}")
        if total > 2:
            st.caption(f"... e mais {total - 2} itens")

def render_task_row(task, techs, locs):
    is_unscheduled = task["status"] == "unscheduled"
    card_class = "unscheduled-card" if is_unscheduled else ""
    with st.container():
        st.markdown(f'<div class="card {card_class}">', unsafe_allow_html=True)
        col1, col2, col3, col4, col5, col6, col7 = st.columns([3, 2, 2, 1, 1, 1, 1])
        with col1:
            st.markdown(f"**{task['title']}**")
            if task.get("description"):
                st.caption(f"{task['description'][:50]}...")
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
            st.caption(status_display)
        with col6:
            if st.button("✏️", key=f"edit_{task['id']}", help="Editar"):
                st.session_state["show_edit_form"] = True
                st.session_state["editing_task_data"] = {"id": task["id"]}
                st.rerun()
        with col7:
            if st.button("🔍", key=f"open_{task['id']}", help="Detalhes"):
                st.session_state["selected_task"] = task
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def render_list_view(tasks_all, techs, locs):
    grouped = {}
    for t in tasks_all:
        grouped.setdefault(t["status"], []).append(t)
    status_order = ["unscheduled", "overdue", "scheduled", "in_progress", "completed"]
    for status in status_order:
        if status not in grouped:
            continue
        tasks = grouped[status]
        with st.expander(f"{status_labels[status]} ({len(tasks)})", 
                        expanded=st.session_state["expanded_groups"].get(status, True)):
            for task in tasks:
                render_task_row(task, techs, locs)

# ----------- PÁGINA PRINCIPAL -----------
st.set_page_config(page_title="🔧 Manutenção Preventiva", layout="wide")
update_overdue_tasks()
st.title("🔧 Sistema de Manutenção Preventiva")

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

# Modais
if st.session_state["show_new_form"]:
    show_new_activity_form()
if st.session_state["show_edit_form"] and st.session_state.get("editing_task_data"):
    show_edit_form(st.session_state["editing_task_data"]["id"])
if st.session_state["show_clone_form"] and st.session_state["cloning_task_id"]:
    show_clone_form()
selected_task = st.session_state.get("selected_task")
if selected_task and isinstance(selected_task, dict) and "id" in selected_task:
    show_task_modal(selected_task)

# Conteúdo principal
if not any([
    st.session_state.get("show_new_form"),
    st.session_state.get("show_clone_form"),
    st.session_state.get("selected_task"),
    st.session_state.get("show_edit_form")
]):
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

    tasks_all = get_filtered_tasks(["scheduled", "in_progress", "completed", "overdue", "unscheduled"])
    if st.session_state["view_mode"] == "list":
        render_list_view(tasks_all, techs, locs)
    else:
        st.subheader("📊 Quadro Kanban")
        kanban_columns = [
            ("unscheduled", "⏳ Não Programadas"),
            ("scheduled", "📅 Agendadas"),
            ("in_progress", "🛠️ Em Andamento"),
            ("completed", "✅ Concluídas")
        ]
        cols = st.columns(len(kanban_columns))
        for i, (status, label) in enumerate(kanban_columns):
            with cols[i]:
                st.markdown(f"### {label}")
                tasks = get_filtered_tasks([status])
                for task in tasks:
                    is_unscheduled = task["status"] == "unscheduled"
                    card_class = "unscheduled-card" if is_unscheduled else ""
                    with st.container(border=True):
                        st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
                        st.markdown(f"**{task['title']}**")
                        if task.get("description"):
                            st.caption(f"{task['description'][:50]}...")
                        st.markdown(get_priority_badge(task.get('priority', 'media')), unsafe_allow_html=True)
                        st.caption(f"📍 {get_location_name(task['location_id'], locs)}")
                        st.caption(f"👷 {get_technician_name(task['technician_id'], techs)}")
                        if task['due_date']:
                            st.caption(f"📅 {task['due_date'][:16].replace('T', ' ')}")
                        else:
                            st.caption("⏳ Não programada")
                        render_kanban_checklist(task)
                        col_btn1, col_btn2, col_btn3 = st.columns(3)
                        with col_btn1:
                            if task["status"] in ["scheduled", "overdue", "unscheduled"]:
                                if st.button("▶️", key=f"start_k_{task['id']}", help="Iniciar"):
                                    supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task["id"]).execute()
                                    st.toast("▶️ Tarefa iniciada!", icon="▶️")
                                    st.rerun()
                            elif task["status"] == "in_progress":
                                if st.button("✅", key=f"complete_k_{task['id']}", help="Concluir"):
                                    supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task["id"]).execute()
                                    checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in load_checklist(task["id"])]
                                    archive_task(task, checklist_items)
                                    if task.get("recurrence"):
                                        create_recurring_task(task)
                                    st.toast("✅ Tarefa concluída!", icon="✅")
                                    st.rerun()
                        with col_btn2:
                            if st.button("✏️", key=f"edit_k_{task['id']}", help="Editar"):
                                st.session_state["show_edit_form"] = True
                                st.session_state["editing_task_data"] = {"id": task["id"]}
                                st.rerun()
                        with col_btn3:
                            if st.button("🔍", key=f"det_k_{task['id']}", help="Detalhes"):
                                st.session_state["selected_task"] = task
                                st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

# Histórico
if st.session_state.get("show_history"):
    st.markdown("## 📋 Histórico")
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Início", value=datetime.now() - timedelta(days=30), key="hist_start")
    with col2:
        end = st.date_input("Fim", value=datetime.now(), key="hist_end")
    try:
        res = supabase.table("task_history").select("*")\
            .gte("completed_at", str(start))\
            .lte("completed_at", str(end))\
            .order("completed_at", desc=True)\
            .execute()
        if res.data:
            for h in res.data:
                with st.expander(f"✅ {h['title']} — {h['completed_at'][:10]}"):
                    st.write(f"**Técnico:** {get_technician_name(h['technician_id'], load_technicians())}")
                    st.write(f"**Local:** {get_location_name(h['location_id'], load_locations())}")
                    st.write(f"**Concluído em:** {h['completed_at'][:16].replace('T', ' ')}")
                    if h.get("notes"):
                        st.write(f"📝 **Observações:** {h['notes']}")
                    if h.get("checklist"):
                        st.write("✅ **Checklist:**")
                        for item in h["checklist"]:
                            status = "✅" if item.get("is_completed") else "⏳"
                            st.write(f"{status} {item.get('item', '')}")
        else:
            st.info("Nenhum registro no período selecionado.")
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {str(e)}")
    if st.button("Voltar", key="back_from_history"):
        st.session_state["show_history"] = False
        st.rerun()
        # --- Visualização do relatório gerado ---
if st.session_state.get("show_report") and st.session_state.get("generated_report_html"):
    st.markdown("## 📄 Relatório para Impressão")
    st.components.v1.html(st.session_state["generated_report_html"], height=800, scrolling=True)
    if st.button("⬅️ Voltar à Tarefa", use_container_width=True):
        st.session_state["show_report"] = False
        st.rerun()