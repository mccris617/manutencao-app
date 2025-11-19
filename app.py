# app.py — Sistema de Manutenção Preventiva (com layout moderno e cards retráteis)
import streamlit as st
from datetime import datetime, timedelta
from supabase_client import get_supabase_client
from fpdf import FPDF
import os
import re
import uuid
from streamlit_drawable_canvas import st_canvas
from streamlit_calendar import calendar

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
# Estados para controle do clone
if "show_clone_form" not in st.session_state:
    st.session_state["show_clone_form"] = False
if "cloning_task_id" not in st.session_state:
    st.session_state["cloning_task_id"] = None
if "clone_form_data" not in st.session_state:
    st.session_state["clone_form_data"] = {}
# Estado para controle de uploads
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = {}
# Estado para controle de grupos expandidos na lista
if "expanded_groups" not in st.session_state:
    st.session_state["expanded_groups"] = {
        "scheduled": True,
        "in_progress": True,
        "completed": True,
        "overdue": True
    }

status_labels = {
    "scheduled": "📅 Agendada",
    "in_progress": "🛠️ Em Execução",
    "completed": "✅ Concluída",
    "overdue": "❗ Atrasada"
}

# Paleta de cores para especialidades
COLORS = {
    "Refrigeração": "#e3f2fd",
    "Elétrica": "#fff8e1",
    "Hidráulica": "#f3e5f5",
    "Mecânica": "#e8f5e9",
    "Outra": "#eeeeee"
}

# Prioridades
PRIORITIES = {
    "missao_critica": {"label": "🚨 Missão Crítica", "color": "#ff4444"},
    "alta": {"label": "🔴 Alta", "color": "#ff6b6b"},
    "media": {"label": "🟡 Média", "color": "#ffd93d"},
    "baixa": {"label": "🟢 Baixa", "color": "#6bcf7f"}
}

# --- Estilo CSS personalizado ---
st.markdown("""
<style>
.card {
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 10px;
    background-color: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    transition: all 0.2s ease-in-out;
}
.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.15);
}
.priority-badge {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: bold;
    display: inline-block;
}
.group-header {
    background-color: #f8f9fa;
    padding: 12px 16px;
    border-radius: 8px;
    margin: 10px 0;
    border-left: 4px solid #007bff;
    cursor: pointer;
    transition: all 0.2s ease;
}
.group-header:hover {
    background-color: #e9ecef;
}
.group-content {
    padding: 0 10px;
    animation: fadeIn 0.3s ease-in;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}
.task-row {
    display: flex;
    align-items: center;
    padding: 12px;
    border-bottom: 1px solid #f0f0f0;
    transition: background-color 0.2s ease;
}
.task-row:hover {
    background-color: #f8f9fa;
}
.task-row-selected {
    background-color: #e3f2fd;
}
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
    return tech_dict.get(str(tech_id), {}).get("name", "Não atribuído")

def get_location_name(loc_id, loc_dict):
    return loc_dict.get(str(loc_id), "—")

def get_specialties_list():
    res = supabase.table("technicians").select("specialty").execute()
    specialties = {r["specialty"] for r in res.data if r.get("specialty")}
    return sorted(specialties) if specialties else ["Refrigeração", "Elétrica", "Hidráulica", "Mecânica"]

def load_checklist(task_id):
    """Carrega checklist de uma tarefa"""
    try:
        res = supabase.table("checklists").select("*").eq("task_id", task_id).execute()
        return [{"id": item["id"], "item": item["item"], "is_completed": item["is_completed"]} 
                for item in res.data] if res.data else []
    except Exception as e:
        st.error(f"Erro ao carregar checklist: {str(e)}")
        return []

def get_priority_badge(priority):
    """Retorna o badge de prioridade formatado"""
    priority_info = PRIORITIES.get(priority, PRIORITIES["media"])
    return f'<span class="priority-badge" style="background-color: {priority_info["color"]}20; color: {priority_info["color"]}; border: 1px solid {priority_info["color"]};">{priority_info["label"]}</span>'

def sanitize_filename(filename):
    """Sanitiza nomes de arquivos para remover caracteres especiais"""
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    unique_id = str(uuid.uuid4())[:8]
    return f"{name}_{unique_id}{ext}"

def handle_file_upload(task_id, uploaded_file):
    """Função para lidar com upload de arquivos de forma controlada"""
    try:
        # Verificar se este arquivo já foi processado
        upload_key = f"{task_id}_{uploaded_file.name}_{uploaded_file.size}"
        
        if upload_key in st.session_state.uploaded_files:
            st.warning("📎 Este arquivo já foi enviado anteriormente.")
            return
        
        # Sanitiza o nome do arquivo
        safe_filename = sanitize_filename(uploaded_file.name)
        file_path = f"{task_id}/{safe_filename}"
        
        # Fazer upload
        supabase.storage.from_("task-attachments").upload(
            file_path,
            uploaded_file.getvalue(),
            file_options={"content-type": uploaded_file.type}
        )
        
        # Marcar como processado
        st.session_state.uploaded_files[upload_key] = True
        st.success("✅ Imagem anexada!")
        st.rerun()
        
    except Exception as e:
        st.error(f"Erro ao enviar: {str(e)}")

# ----------- Função: Calcular próxima data com recorrência -----------
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

# ----------- Função: Gerar PDF -----------
def generate_pdf(task, technician_name, location_name, checklist_items):
    # Caminho para as fontes
    font_normal = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
    font_bold = os.path.join(os.path.dirname(__file__), "DejaVuSans-Bold.ttf")

    # Verifica se as fontes existem
    if not os.path.exists(font_normal) or not os.path.exists(font_bold):
        raise FileNotFoundError("Faltam os arquivos DejaVuSans.ttf ou DejaVuSans-Bold.ttf na pasta do projeto.")

    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", font_normal, uni=True)
    pdf.add_font("DejaVu", "B", font_bold, uni=True)
    pdf.set_font("DejaVu", "", 12)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("DejaVu", "B", 16)

    # --- Título Principal ---
    pdf.cell(0, 10, "Relatório de Atividade", ln=True, align="C")
    pdf.ln(10)

    # --- Dados da manutenção ---
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, f"Título: {task['title']}", ln=True)
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Descrição: {task.get('description', '—')}", ln=True)
    pdf.cell(0, 8, f"Especialidade: {task.get('specialty', '—')}", ln=True)
    pdf.cell(0, 8, f"Técnico: {technician_name}", ln=True)
    pdf.cell(0, 8, f"Localidade: {location_name}", ln=True)
    due = task['due_date'][:16].replace('T', ' ')
    pdf.cell(0, 8, f"Agendado para: {due}", ln=True)
    
    # Prioridade no PDF
    priority_display = PRIORITIES.get(task.get('priority', 'media'), PRIORITIES['media'])["label"]
    pdf.cell(0, 8, f"Prioridade: {priority_display}", ln=True)
    
    pdf.cell(0, 8, f"Status: {status_labels.get(task['status'], task['status'])}", ln=True)
    recurrence_map_display = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
    pdf.cell(0, 8, f"Recorrência: {recurrence_map_display.get(task.get('recurrence'), 'Nenhuma')}", ln=True)
    pdf.ln(5)

    # --- Checklist ---
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, "Checklist:", ln=True)
    pdf.set_font("DejaVu", "", 12)

    if checklist_items:
        for item in checklist_items:
            mark = "[x]" if item["checked"] else "[ ]"
            pdf.cell(0, 8, f"{mark} {item['text']}", ln=True)
    else:
        pdf.cell(0, 8, "Nenhum item no checklist.", ln=True)

    pdf.ln(10)
    pdf.set_font("DejaVu", "I", 10)
    pdf.cell(0, 8, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)

    return bytes(pdf.output(dest='S'))

# ----------- Função: Arquivar tarefa ao concluir -----------
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
            "created_from_template": task.get("is_template", False),
            "notes": task.get("notes", "")
        }
        supabase.table("task_history").insert(archive_data).execute()
    except Exception as e:
        st.error(f"Erro ao arquivar: {str(e)}")

# ----------- Função: Criar tarefa recorrente -----------
def create_recurring_task(original_task):
    recurrence = original_task.get("recurrence")
    if not recurrence:
        return
    try:
        current_due = datetime.fromisoformat(original_task["due_date"])
        next_due = get_next_due_date(current_due, recurrence)
        if next_due:
            res = supabase.table("maintenance_tasks").insert({
                "title": original_task["title"],
                "description": original_task.get("description"),
                "specialty": original_task.get("specialty"),
                "technician_id": original_task.get("technician_id"),
                "location_id": original_task.get("location_id"),
                "due_date": next_due.isoformat(),
                "recurrence": recurrence,
                "status": "scheduled",
                "is_template": False,
                "notes": original_task.get("notes"),
                "priority": original_task.get("priority", "media")
            }).execute()
            new_task_id = res.data[0]["id"] if res.data else None
            checklist_data = load_checklist(original_task["id"])
            if checklist_data:
                for item in checklist_data:
                    supabase.table("checklists").insert({
                        "task_id": new_task_id,
                        "item": item["item"],
                        "is_completed": False
                    }).execute()
    except Exception as e:
        st.error(f"Erro ao criar tarefa recorrente: {str(e)}")

# ----------- Função: Excluir tarefas em massa -----------
def delete_tasks_in_bulk(task_ids):
    try:
        for task_id in task_ids:
            supabase.table("checklists").delete().eq("task_id", task_id).execute()
            supabase.table("maintenance_tasks").delete().eq("id", task_id).execute()
        st.success(f"✅ {len(task_ids)} tarefa(s) excluída(s)!")
        # Limpar seleção
        for task_id in task_ids:
            key = f"bulk_select_{task_id}"
            if key in st.session_state:
                del st.session_state[key]
    except Exception as e:
        st.error(f"Erro ao excluir: {str(e)}")

# ----------- Modal de Nova Atividade -----------
def show_new_activity_form():
    """Mostra o formulário para criar nova atividade"""
    st.subheader("➕ Nova Atividade de Manutenção")
    
    with st.form("new_activity", clear_on_submit=True):
        title = st.text_input("Título *", placeholder="Descreva a atividade...")
        description = st.text_area("Descrição", placeholder="Detalhes adicionais...")
        
        col1, col2 = st.columns(2)
        with col1:
            specialties = get_specialties_list()
            specialty = st.selectbox("Especialidade *", specialties)
            
            technicians = load_technicians()
            # Filtrar técnicos pela especialidade selecionada
            filtered_techs = {k: v for k, v in technicians.items() if v.get("specialty") == specialty}
            if not filtered_techs:
                st.warning("Nenhum técnico cadastrado para essa especialidade.")
                technician_id = None
            else:
                technician_id = st.selectbox(
                    "Técnico", 
                    options=list(filtered_techs.keys()),
                    format_func=lambda x: filtered_techs[x].get("name")
                )
        
        with col2:
            locations = load_locations()
            location_id = st.selectbox(
                "Localidade *", 
                options=list(locations.keys()),
                format_func=lambda x: locations[x]
            )
            
            due_date = st.date_input("Data de Vencimento *", value=datetime.now())
            due_time = st.time_input("Hora de Vencimento *", value=datetime.now().time())
        
        col3, col4 = st.columns(2)
        with col3:
            priority = st.selectbox(
                "Prioridade", 
                options=list(PRIORITIES.keys()),
                format_func=lambda x: PRIORITIES[x]["label"],
                index=2  # Média como padrão
            )
        
        with col4:
            recurrence = st.selectbox(
                "Recorrência", 
                options=["Nenhuma", "Diária", "Semanal", "Mensal"]
            )
            recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
        
        notes = st.text_area("Observações Técnicas", placeholder="Anotações para a execução...")
        
        # Checklist
        st.markdown("**Checklist** (opcional)")
        checklist_items = st.text_area(
            "Itens do checklist (um por linha)", 
            placeholder="Cada linha será um item do checklist..."
        )
        
        submitted = st.form_submit_button("Salvar Atividade", type="primary")
        if submitted:
            if not title or not specialty or not location_id:
                st.error("Preencha os campos obrigatórios (*)")
            else:
                due_datetime = datetime.combine(due_date, due_time).isoformat()
                try:
                    # Inserir tarefa
                    new_task = {
                        "title": title,
                        "description": description,
                        "specialty": specialty,
                        "technician_id": technician_id,
                        "location_id": location_id,
                        "due_date": due_datetime,
                        "priority": priority,
                        "recurrence": recurrence_map[recurrence],
                        "notes": notes,
                        "status": "scheduled"
                    }
                    res = supabase.table("maintenance_tasks").insert(new_task).execute()
                    new_task_id = res.data[0]["id"] if res.data else None
                    
                    # Inserir checklist
                    if checklist_items:
                        items = [item.strip() for item in checklist_items.split("\n") if item.strip()]
                        for item in items:
                            supabase.table("checklists").insert({
                                "task_id": new_task_id,
                                "item": item,
                                "is_completed": False
                            }).execute()
                    
                    st.success("✅ Atividade criada com sucesso!")
                    st.session_state["show_new_form"] = False
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Erro ao criar atividade: {str(e)}")
    
    if st.button("Fechar", use_container_width=True):
        st.session_state["show_new_form"] = False
        st.rerun()

# ----------- Modal de Detalhes da Tarefa -----------
def show_task_modal(task):
    """Mostra modal com detalhes completos da tarefa"""
    st.subheader(f"🔍 Detalhes: {task['title']}")
    
    # Carregar dados atualizados
    task_res = supabase.table("maintenance_tasks").select("*").eq("id", task["id"]).execute()
    if task_res.data:
        task = task_res.data[0]
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**Título:** {task['title']}")
            st.markdown(f"**Descrição:** {task.get('description', '—')}")
            st.markdown(f"**Especialidade:** {task.get('specialty', '—')}")
            st.markdown(f"**Técnico:** {get_technician_name(task['technician_id'], load_technicians())}")
            st.markdown(f"**Localidade:** {get_location_name(task['location_id'], load_locations())}")
        
        with col2:
            due_date = task['due_date'][:10]
            due_time = task['due_date'][11:16]
            st.markdown(f"**Data:** {due_date}")
            st.markdown(f"**Hora:** {due_time}")
            st.markdown(f"**Prioridade:** {PRIORITIES.get(task.get('priority', 'media'), PRIORITIES['media'])['label']}")
            st.markdown(f"**Status:** {status_labels.get(task['status'], task['status'])}")
            recurrence_map = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
            st.markdown(f"**Recorrência:** {recurrence_map.get(task.get('recurrence'), 'Nenhuma')}")
    
    # Checklist
    st.markdown("### 📋 Checklist")
    checklist_data = load_checklist(task["id"])
    
    if checklist_data:
        total_items = len(checklist_data)
        completed_items = sum(1 for item in checklist_data if item["is_completed"])
        progress = completed_items / total_items if total_items > 0 else 0
        
        st.progress(progress)
        st.caption(f"Progresso: {completed_items}/{total_items} itens concluídos")
        
        for item in checklist_data:
            col1, col2 = st.columns([0.9, 0.1])
            with col1:
                if item["is_completed"]:
                    st.markdown(f"✅ ~~{item['item']}~~")
                else:
                    st.markdown(f"🔲 {item['item']}")
            with col2:
                if st.button("🔄", key=f"toggle_{item['id']}", help="Alternar status"):
                    supabase.table("checklists").update({"is_completed": not item["is_completed"]}).eq("id", item["id"]).execute()
                    st.rerun()
    else:
        st.info("Nenhum checklist definido para esta atividade.")
    
    # Ações
    st.markdown("### 🛠️ Ações")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if task["status"] in ["scheduled", "overdue"]:
            if st.button("▶️ Iniciar Tarefa", use_container_width=True):
                supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task["id"]).execute()
                st.success("✅ Tarefa iniciada!")
                st.rerun()
        elif task["status"] == "in_progress":
            if st.button("✅ Concluir Tarefa", use_container_width=True):
                supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task["id"]).execute()
                checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in checklist_data]
                archive_task(task, checklist_items)
                if task.get("recurrence"):
                    create_recurring_task(task)
                st.success("✅ Tarefa concluída e arquivada!")
                st.rerun()
    
    with col2:
        if st.button("📋 Clonar Tarefa", use_container_width=True):
            st.session_state["cloning_task_id"] = task["id"]
            st.session_state["show_clone_form"] = True
            st.rerun()
    
    with col3:
        try:
            checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in checklist_data]
            pdf_bytes = generate_pdf(
                task, 
                get_technician_name(task['technician_id'], load_technicians()), 
                get_location_name(task['location_id'], load_locations()), 
                checklist_items
            )
            st.download_button(
                "📄 Gerar PDF",
                data=pdf_bytes,
                file_name=f"atividade_{task['id']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {str(e)}")
    
    with col4:
        if st.button("🗑️ Excluir Tarefa", type="secondary", use_container_width=True):
            supabase.table("checklists").delete().eq("task_id", task["id"]).execute()
            supabase.table("maintenance_tasks").delete().eq("id", task["id"]).execute()
            st.session_state["selected_task"] = None
            st.success("✅ Tarefa excluída!")
            st.rerun()
    
    if st.button("Fechar", use_container_width=True):
        st.session_state["selected_task"] = None
        st.rerun()

# ----------- Modal de Clone -----------
def show_clone_form():
    """Mostra formulário para clonar tarefa"""
    st.subheader("📋 Clonar Tarefa")
    
    with st.form("clone_form"):
        title = st.text_input("Título *", value=st.session_state["clone_form_data"].get("title", ""))
        description = st.text_area("Descrição", value=st.session_state["clone_form_data"].get("description", ""))
        
        col1, col2 = st.columns(2)
        with col1:
            specialties = get_specialties_list()
            specialty = st.selectbox(
                "Especialidade *", 
                specialties,
                index=specialties.index(st.session_state["clone_form_data"].get("specialty")) if st.session_state["clone_form_data"].get("specialty") in specialties else 0
            )
            
            technicians = load_technicians()
            filtered_techs = {k: v for k, v in technicians.items() if v.get("specialty") == specialty}
            technician_id = st.selectbox(
                "Técnico", 
                options=list(filtered_techs.keys()) if filtered_techs else [None],
                format_func=lambda x: filtered_techs[x].get("name") if x else "Não atribuído"
            )
        
        with col2:
            locations = load_locations()
            location_id = st.selectbox(
                "Localidade *", 
                options=list(locations.keys()),
                index=list(locations.keys()).index(st.session_state["clone_form_data"].get("location_id")) if st.session_state["clone_form_data"].get("location_id") in locations else 0,
                format_func=lambda x: locations[x]
            )
            
            due_date = st.date_input("Data de Vencimento *", value=datetime.now())
            due_time = st.time_input("Hora de Vencimento *", value=datetime.now().time())
        
        priority = st.selectbox(
            "Prioridade", 
            options=list(PRIORITIES.keys()),
            index=list(PRIORITIES.keys()).index(st.session_state["clone_form_data"].get("priority", "media")),
            format_func=lambda x: PRIORITIES[x]["label"]
        )
        
        recurrence = st.selectbox(
            "Recorrência", 
            options=["Nenhuma", "Diária", "Semanal", "Mensal"],
            index=["Nenhuma", "Diária", "Semanal", "Mensal"].index(st.session_state["clone_form_data"].get("recurrence", "Nenhuma"))
        )
        recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
        
        notes = st.text_area("Observações Técnicas", value=st.session_state["clone_form_data"].get("notes", ""))
        
        # Checklist
        st.markdown("**Checklist**")
        default_checklist = "\n".join(st.session_state["clone_form_data"].get("checklist", []))
        checklist_items = st.text_area(
            "Itens do checklist (um por linha)", 
            value=default_checklist,
            placeholder="Cada linha será um item do checklist..."
        )
        
        submitted = st.form_submit_button("Criar Cópia", type="primary")
        if submitted:
            if not title or not specialty or not location_id:
                st.error("Preencha os campos obrigatórios (*)")
            else:
                due_datetime = datetime.combine(due_date, due_time).isoformat()
                try:
                    new_task = {
                        "title": title,
                        "description": description,
                        "specialty": specialty,
                        "technician_id": technician_id,
                        "location_id": location_id,
                        "due_date": due_datetime,
                        "priority": priority,
                        "recurrence": recurrence_map[recurrence],
                        "notes": notes,
                        "status": "scheduled"
                    }
                    res = supabase.table("maintenance_tasks").insert(new_task).execute()
                    new_task_id = res.data[0]["id"] if res.data else None
                    
                    # Inserir checklist
                    if checklist_items:
                        items = [item.strip() for item in checklist_items.split("\n") if item.strip()]
                        for item in items:
                            supabase.table("checklists").insert({
                                "task_id": new_task_id,
                                "item": item,
                                "is_completed": False
                            }).execute()
                    
                    st.success("✅ Tarefa clonada com sucesso!")
                    st.session_state["show_clone_form"] = False
                    st.session_state["cloning_task_id"] = None
                    st.session_state["clone_form_data"] = {}
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Erro ao clonar tarefa: {str(e)}")
    
    if st.button("Fechar", use_container_width=True):
        st.session_state["show_clone_form"] = False
        st.session_state["cloning_task_id"] = None
        st.session_state["clone_form_data"] = {}
        st.rerun()

# ----------- Renderização da Lista de Tarefas -----------
def render_list_view(tasks_all, techs, locs):
    """Renderiza a visualização em lista com agrupamento por status"""
    
    # Agrupar tarefas por status
    grouped_tasks = {}
    for task in tasks_all:
        status = task["status"]
        if status not in grouped_tasks:
            grouped_tasks[status] = []
        grouped_tasks[status].append(task)
    
    # Ordem desejada dos grupos
    status_order = ["overdue", "scheduled", "in_progress", "completed"]
    
    # Menu ⋯ para ações em massa
    col_menu, col_counter = st.columns([4, 1])
    with col_menu:
        bulk_key = "bulk_list_active"
        select_key = "bulk_selected_list"
        if bulk_key not in st.session_state:
            st.session_state[bulk_key] = False
        if select_key not in st.session_state:
            st.session_state[select_key] = []
        if st.button("⋮", help="Menu de ações", key="menu_bulk_list"):
            st.session_state[bulk_key] = not st.session_state[bulk_key]
            st.rerun()
        if st.session_state[bulk_key]:
            if st.button("🗑️ Selecionar para excluir", key="enable_bulk_list", use_container_width=True):
                st.session_state[bulk_key] = True
                st.rerun()
            if st.session_state[select_key]:
                count = len(st.session_state[select_key])
                if st.button(f"🗑️ Excluir {count} tarefa(s)", type="secondary", use_container_width=True):
                    delete_tasks_in_bulk(st.session_state[select_key])
                    st.session_state[select_key] = []
                    st.rerun()
    with col_counter:
        if st.session_state[select_key]:
            st.caption(f"🟢 {len(st.session_state[select_key])} selecionada(s)")
    
    # Renderizar cada grupo
    for status in status_order:
        if status not in grouped_tasks or not grouped_tasks[status]:
            continue
            
        tasks = grouped_tasks[status]
        group_label = status_labels.get(status, status)
        task_count = len(tasks)
        
        # Header do grupo
        col1, col2, col3 = st.columns([1, 6, 1])
        with col1:
            # Ícone de expandir/recolher
            expand_icon = "▼" if st.session_state["expanded_groups"][status] else "▶"
            if st.button(expand_icon, key=f"toggle_{status}", help=f"{'Recolher' if st.session_state['expanded_groups'][status] else 'Expandir'} {group_label}"):
                st.session_state["expanded_groups"][status] = not st.session_state["expanded_groups"][status]
                st.rerun()
        
        with col2:
            st.markdown(f"### {group_label} ({task_count})")
        
        with col3:
            # Progresso do grupo (para status com checklist)
            if status in ["in_progress", "completed"]:
                total_items = 0
                completed_items = 0
                for task in tasks:
                    checklist = load_checklist(task["id"])
                    total_items += len(checklist)
                    completed_items += sum(1 for item in checklist if item["is_completed"])
                
                if total_items > 0:
                    progress = completed_items / total_items
                    st.progress(progress)
                    st.caption(f"{completed_items}/{total_items}")
        
        # Conteúdo do grupo (se expandido)
        if st.session_state["expanded_groups"][status]:
            for task in tasks:
                render_task_row(task, techs, locs, bulk_key, select_key)

def render_task_row(task, techs, locs, bulk_key, select_key):
    """Renderiza uma linha individual de tarefa na lista"""
    
    # Determinar classe CSS baseada na seleção
    row_class = "task-row-selected" if task["id"] in st.session_state[select_key] else "task-row"
    
    with st.container():
        st.markdown(f'<div class="{row_class}">', unsafe_allow_html=True)
        
        col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 3, 2, 2, 1, 1, 1])
        
        with col1:
            if st.session_state.get(bulk_key, False):
                key = f"bulk_list_{task['id']}"
                is_selected = st.checkbox("", value=task["id"] in st.session_state[select_key], key=key, label_visibility="collapsed")
                if is_selected and task["id"] not in st.session_state[select_key]:
                    st.session_state[select_key].append(task["id"])
                elif not is_selected and task["id"] in st.session_state[select_key]:
                    st.session_state[select_key].remove(task["id"])
        
        with col2:
            st.markdown(f"**{task['title']}**")
            st.caption(f"📍 {get_location_name(task['location_id'], locs)} • 👷 {get_technician_name(task['technician_id'], techs)}")
            
            # Mostrar progresso do checklist se existir
            checklist_data = load_checklist(task["id"])
            if checklist_data:
                total = len(checklist_data)
                done = sum(1 for i in checklist_data if i["is_completed"])
                if total > 0:
                    progress = done / total
                    st.progress(progress)
                    st.caption(f"✔️ {done}/{total}")
        
        with col3:
            # Prioridade
            st.markdown(get_priority_badge(task.get('priority', 'media')), unsafe_allow_html=True)
            
            # Especialidade
            specialty_color = COLORS.get(task.get("specialty"), "#eee")
            st.markdown(
                f'<span style="background-color:{specialty_color}; padding:2px 6px; border-radius:4px; font-size:0.8em;">{task.get("specialty", "—")}</span>',
                unsafe_allow_html=True
            )
        
        with col4:
            # Datas
            due_date = task['due_date'][:10]
            due_time = task['due_date'][11:16]
            st.markdown(f"**Data:** {due_date}")
            st.markdown(f"**Hora:** {due_time}")
            
            # Status
            status_info = status_labels.get(task["status"], task["status"])
            st.markdown(f"**Status:** {status_info}")
        
        with col5:
            # Botão de detalhes
            if st.button("🔍", key=f"open_{task['id']}", help="Ver detalhes"):
                st.session_state["selected_task"] = task
                st.rerun()
        
        with col6:
            # Botão PDF
            checklist_data = load_checklist(task["id"])
            checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in checklist_data]
            if st.button("📄", key=f"pdf_list_{task['id']}", help="Gerar PDF"):
                try:
                    pdf_bytes = generate_pdf(task, get_technician_name(task['technician_id'], techs), get_location_name(task['location_id'], locs), checklist_items)
                    st.download_button(
                        "📥",
                        data=pdf_bytes,
                        file_name=f"atividade_{task['id']}.pdf",
                        mime="application/pdf",
                        key=f"download_pdf_list_{task['id']}",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {str(e)}")
        
        with col7:
            # Ações rápidas baseadas no status
            if task["status"] in ["scheduled", "overdue"]:
                if st.button("▶️", key=f"start_quick_{task['id']}", help="Iniciar tarefa"):
                    supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task["id"]).execute()
                    st.rerun()
            elif task["status"] == "in_progress":
                if st.button("✅", key=f"complete_quick_{task['id']}", help="Concluir tarefa"):
                    supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task["id"]).execute()
                    checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in checklist_data]
                    archive_task(task, checklist_items)
                    if task.get("recurrence"):
                        create_recurring_task(task)
                    st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# ----------- Página Principal -----------
st.set_page_config(page_title="🔧 Manutenção Preventiva", layout="wide")
st.title("🔧 Sistema de Manutenção Preventiva")

# Verificação de fontes
base_dir = os.path.dirname(__file__)
required_fonts = ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"]
missing = [f for f in required_fonts if not os.path.exists(os.path.join(base_dir, f))]
if missing:
    st.sidebar.error(f"⚠️ Fontes ausentes: {', '.join(missing)}")
else:
    st.sidebar.success("✅ Fontes OK")

# --- Sidebar: Cadastros ---
with st.sidebar:
    st.header("📁 Cadastros")
    with st.expander("👷 Técnicos"):
        with st.form("add_technician"):
            name = st.text_input("Nome")
            specialties = get_specialties_list()
            specialty = st.selectbox("Especialidade", specialties + ["Outra"])
            if specialty == "Outra":
                specialty = st.text_input("Nova especialidade")
            if st.form_submit_button("Salvar"):
                if name and specialty:
                    supabase.table("technicians").insert({
                        "name": name,
                        "specialty": specialty
                    }).execute()
                    st.success("✅ Técnico salvo!")
                    st.rerun()

    with st.expander("📍 Localidades"):
        with st.form("add_location"):
            loc_name = st.text_input("Nome da Localidade")
            if st.form_submit_button("Salvar"):
                if loc_name:
                    supabase.table("locations").insert({"name": loc_name}).execute()
                    st.success("✅ Localidade salva!")
                    st.rerun()

    # --- Histórico ---
    if st.button("📋 Histórico"):
        st.session_state["show_history"] = True
        st.rerun()

# --- Layout de Visualização ---
st.markdown("### 🖼️ Modo de Visualização")
view_mode = st.radio("Escolha como visualizar", ["📋 Lista", "📊 Kanban", "📅 Calendário"], key="view_mode_radio")
if view_mode == "📋 Lista":
    st.session_state["view_mode"] = "list"
elif view_mode == "📊 Kanban":
    st.session_state["view_mode"] = "kanban"
elif view_mode == "📅 Calendário":
    st.session_state["view_mode"] = "calendar"

# --- Filtros ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    all_specialities = get_specialties_list()
    selected_speciality = st.selectbox("Especialidade", ["Todas"] + all_specialities)
with col2:
    all_locs = load_locations()
    selected_loc = st.selectbox("Localidade", ["Todas"] + list(all_locs.values()))
with col3:
    filter_date = st.date_input("Data específica", value=None)
with col4:
    priority_filter = st.selectbox("Prioridade", ["Todas"] + [PRIORITIES[p]["label"] for p in PRIORITIES])

st.divider()

# --- Botão Nova Atividade ---
if st.button("➕ Nova Atividade", type="primary"):
    st.session_state["show_new_form"] = True

# --- Exibir Modais ---
if st.session_state["show_new_form"]:
    show_new_activity_form()

if st.session_state["show_clone_form"] and st.session_state["cloning_task_id"]:
    # Carregar dados da tarefa a ser clonada
    task_res = supabase.table("maintenance_tasks").select("*").eq("id", st.session_state["cloning_task_id"]).execute()
    if task_res.data:
        task = task_res.data[0]
        checklist_data = load_checklist(task["id"])
        checklist_items = [item["item"] for item in checklist_data]
        
        st.session_state["clone_form_data"] = {
            "title": task["title"],
            "description": task.get("description", ""),
            "specialty": task.get("specialty", ""),
            "technician_id": task.get("technician_id"),
            "location_id": task.get("location_id"),
            "due_date": datetime.fromisoformat(task["due_date"]).date(),
            "priority": task.get("priority", "media"),
            "recurrence": "Nenhuma" if not task.get("recurrence") else 
                         {"daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}.get(task.get("recurrence"), "Nenhuma"),
            "checklist": checklist_items,
            "notes": task.get("notes", "")
        }
        show_clone_form()

if st.session_state["selected_task"]:
    show_task_modal(st.session_state["selected_task"])

# --- Exibir Conteúdo Principal ---
if not st.session_state["show_new_form"] and not st.session_state["show_clone_form"] and not st.session_state["selected_task"]:
    # --------------- LISTA DE ATIVIDADES (por modo) ---------------
    techs = load_technicians()
    locs = load_locations()

    def get_filtered_tasks(status_list):
        query = supabase.table("maintenance_tasks")\
            .select("*")\
            .in_("status", status_list)\
            .eq("is_template", False)\
            .order("due_date", desc=False)
        if selected_speciality != "Todas":
            query = query.eq("specialty", selected_speciality)
        if selected_loc != "Todas":
            loc_id_by_name = {v: k for k, v in all_locs.items()}
            loc_id = loc_id_by_name.get(selected_loc)
            if loc_id:
                query = query.eq("location_id", loc_id)
        if filter_date:
            start = datetime.combine(filter_date, datetime.min.time()).isoformat()
            end = datetime.combine(filter_date, datetime.max.time()).isoformat()
            query = query.gte("due_date", start).lte("due_date", end)
        # Filtro por prioridade
        if priority_filter != "Todas":
            priority_key = next((key for key, value in PRIORITIES.items() if value["label"] == priority_filter), None)
            if priority_key:
                query = query.eq("priority", priority_key)
        return query.execute().data or []

    tasks_all = get_filtered_tasks(["scheduled", "in_progress", "completed", "overdue"])

    # Modo: Lista (MELHORADO)
    if st.session_state["view_mode"] == "list":
        st.subheader("📋 Visão em Lista")
        render_list_view(tasks_all, techs, locs)

    # Modo: Kanban
    elif st.session_state["view_mode"] == "kanban":
        st.subheader("📊 Quadro Kanban")
        # Menu ⋯ para ações em massa
        col_menu, col_counter = st.columns([4, 1])
        with col_menu:
            bulk_key = "bulk_kanban_active"
            select_key = "bulk_selected_kanban"
            if bulk_key not in st.session_state:
                st.session_state[bulk_key] = False
            if select_key not in st.session_state:
                st.session_state[select_key] = []
            if st.button("⋮", help="Menu de ações", key="menu_bulk_kanban"):
                st.session_state[bulk_key] = not st.session_state[bulk_key]
                st.rerun()
            if st.session_state[bulk_key]:
                if st.button("🗑️ Selecionar para excluir", key="enable_bulk_kanban", use_container_width=True):
                    st.session_state[bulk_key] = True
                    st.rerun()
                if st.session_state[select_key]:
                    count = len(st.session_state[select_key])
                    if st.button(f"🗑️ Excluir {count} tarefa(s)", type="secondary", use_container_width=True):
                        delete_tasks_in_bulk(st.session_state[select_key])
                        st.session_state[select_key] = []
                        st.rerun()
        with col_counter:
            if st.session_state[select_key]:
                st.caption(f"🟢 {len(st.session_state[select_key])} selecionada(s)")
        cols = st.columns(3)
        status_groups = {
            "scheduled": "📅 Agendadas",
            "in_progress": "🛠️ Em Andamento",
            "completed": "✅ Concluídas"
        }
        for idx, (status, label) in enumerate(status_groups.items()):
            with cols[idx]:
                st.markdown(f"### {label}")
                tasks = get_filtered_tasks([status])
                if not tasks:
                    st.caption("_Vazio_")
                for task in tasks:
                    # Card retrátil com sombra e borda
                    expand_key = f"expand_kanban_{task['id']}"
                    if expand_key not in st.session_state:
                        st.session_state[expand_key] = False
                    with st.container(border=True):
                        # Título com cor de fundo
                        specialty_color = COLORS.get(task.get("specialty"), "#eee")
                        st.markdown(
                            f"<div style='background-color:{specialty_color};padding:8px;border-radius:8px;'>"
                            f"<b>{task['title']}</b>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        
                        # Exibe prioridade no Kanban
                        st.markdown(get_priority_badge(task.get('priority', 'media')), unsafe_allow_html=True)
                        
                        st.markdown(f"**Especialidade:** `{task.get('specialty', '—')}`")
                        st.markdown(f"**Técnico:** {get_technician_name(task['technician_id'], techs)}")
                        st.markdown(f"**Local:** 📍 `{get_location_name(task['location_id'], locs)}`")
                        due = task['due_date'][:16].replace('T', ' ')
                        st.markdown(f"**Agendado para:** {due}")

                        # Botão para expandir/recolher detalhes
                        if st.button("📋 Ver Detalhes" if not st.session_state[expand_key] else "❌ Ocultar Detalhes", key=f"toggle_expand_{task['id']}", use_container_width=True):
                            st.session_state[expand_key] = not st.session_state[expand_key]
                        if st.session_state[expand_key]:
                            st.markdown("---")
                            checklist_data = load_checklist(task["id"])
                            if checklist_data:
                                st.markdown("**Checklist:**")
                                total = len(checklist_data)
                                done = sum(1 for i in checklist_data if i["is_completed"])
                                progress = done / total if total > 0 else 0
                                st.progress(progress)
                                st.caption(f"✔️ {done}/{total} concluídos")
                                for item in checklist_data:
                                    mark = "✅" if item["is_completed"] else "🔲"
                                    st.markdown(f"{mark} {item['item']}")
                            else:
                                st.caption("_Nenhum checklist_")
                            # Observações
                            if task.get("notes"):
                                st.markdown("📝 **Observações Técnicas:**")
                                st.caption(f"*{task['notes']}*")

                        # Botões
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1:
                            if task["status"] in ["scheduled", "overdue"]:
                                if st.button("▶️ Iniciar", key=f"start_{task['id']}", use_container_width=True):
                                    supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task["id"]).execute()
                                    st.rerun()
                            elif task["status"] == "in_progress":
                                if st.button("✅ Concluir", key=f"done_{task['id']}", use_container_width=True):
                                    supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task["id"]).execute()
                                    checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in checklist_data]
                                    archive_task(task, checklist_items)
                                    create_recurring_task(task)
                                    st.rerun()
                        with col2:
                            if st.button("📋 Clonar", key=f"clone_{task['id']}", use_container_width=True):
                                checklist_data = load_checklist(task["id"])
                                checklist_items = [item["item"] for item in checklist_data]
                                
                                st.session_state["clone_form_data"] = {
                                    "title": task["title"],
                                    "description": task.get("description", ""),
                                    "specialty": task.get("specialty", ""),
                                    "technician_id": task.get("technician_id"),
                                    "due_date": datetime.fromisoformat(task["due_date"]).date(),
                                    "priority": task.get("priority", "media"),
                                    "recurrence": "Nenhuma" if not task.get("recurrence") else 
                                                 {"daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}.get(task.get("recurrence"), "Nenhuma"),
                                    "checklist": checklist_items,
                                    "notes": task.get("notes", "")
                                }
                                st.session_state["cloning_task_id"] = task["id"]
                                st.session_state["show_clone_form"] = True
                                st.rerun()
                        with col3:
                            if st.button("📄 PDF", key=f"pdf_{task['id']}", use_container_width=True):
                                try:
                                    checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in checklist_data]
                                    pdf_bytes = generate_pdf(task, get_technician_name(task['technician_id'], techs), get_location_name(task['location_id'], locs), checklist_items)
                                    st.download_button(
                                        "📥 Baixar",
                                        data=pdf_bytes,
                                        file_name=f"atividade_{task['id']}.pdf",
                                        mime="application/pdf",
                                        key=f"download_pdf_{task['id']}",
                                        use_container_width=True
                                    )
                                except Exception as e:
                                    st.error(f"Erro ao gerar PDF: {str(e)}")
                        with col4:
                            if st.button("🔍 Detalhes", key=f"det_{task['id']}", use_container_width=True):
                                st.session_state["selected_task"] = task
                                st.rerun()
                        with col5:
                            if st.button("🗑️", key=f"del_{task['id']}", help="Excluir"):
                                supabase.table("checklists").delete().eq("task_id", task["id"]).execute()
                                supabase.table("maintenance_tasks").delete().eq("id", task["id"]).execute()
                                st.success("✅ Tarefa excluída!")
                                st.rerun()

    # Modo: Calendário
    elif st.session_state["view_mode"] == "calendar":
        st.subheader("📅 Visão em Calendário")
        events = []
        for task in tasks_all:
            # Usa cor da prioridade no calendário
            priority_color = PRIORITIES.get(task.get('priority', 'media'), PRIORITIES['media'])["color"]
            events.append({
                "title": task["title"],
                "start": task["due_date"][:16].replace("T", " "),
                "color": priority_color,
                "resourceId": task["technician_id"] or "sem_tecnico"
            })
        calendar(events=events, options={
            "initialView": "dayGridMonth",
            "editable": True,
            "selectable": True,
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay"
            },
            "eventClick": "js:function(event) { alert('Tarefa: ' + event.event.title); }"
        })

# ----------- HISTÓRICO DE ATIVIDADES ---------------
if st.session_state.get("show_history"):
    st.markdown("## 📋 Histórico de Atividades")
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Data inicial", value=datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("Data final", value=datetime.now())

    # Carregar histórico
    res = supabase.table("task_history").select("*")\
        .gte("completed_at", str(start_date))\
        .lte("completed_at", str(end_date))\
        .order("completed_at", desc=True).execute()
    history = res.data or []

    if not history:
        st.info("Nenhuma atividade encontrada no período.")
    else:
        for h in history:
            with st.expander(f"✅ {h['title']} — {get_technician_name(h['technician_id'], load_technicians())} ({h['completed_at'][:10]})"):
                st.write(f"**Técnico:** {get_technician_name(h['technician_id'], load_technicians())}")
                st.write(f"**Local:** {get_location_name(h['location_id'], load_locations())}")
                st.write(f"**Agendado para:** {h['due_date'][:16].replace('T', ' ')}")
                st.write(f"**Concluído em:** {h['completed_at'][:16].replace('T', ' ')}")
                # Não exibe prioridade no histórico pois a coluna não existe
                st.write(f"**Recorrência:** {h.get('recurrence', '—')}")
                if h.get("checklist"):
                    st.write("**Checklist:**")
                    for item in h["checklist"]:
                        mark = "✅" if item["is_completed"] else "🔲"
                        st.write(f"{mark} {item['item']}")
                else:
                    st.caption("_Sem checklist_")
                if h.get("notes"):
                    st.write(f"📝 Observações: {h['notes']}")
    if st.button("Voltar"):
        st.session_state["show_history"] = False
        st.rerun()