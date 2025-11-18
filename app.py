# app.py — Sistema de Manutenção Preventiva (com layout moderno e cards retráteis)
import streamlit as st
from datetime import datetime, timedelta
from supabase_client import get_supabase_client
from fpdf import FPDF
import os
from streamlit_drawable_canvas import st_canvas
from streamlit_calendar import calendar

supabase = get_supabase_client()

if "show_new_form" not in st.session_state:
    st.session_state["show_new_form"] = False
if "show_history" not in st.session_state:
    st.session_state["show_history"] = False
if "selected_task" not in st.session_state:
    st.session_state["selected_task"] = None
if "view_mode" not in st.session_state:
    st.session_state["view_mode"] = "kanban"
# 🔁 CLONE: Novo estado para controle do clone
if "show_clone_form" not in st.session_state:
    st.session_state["show_clone_form"] = False
if "clone_data" not in st.session_state:
    st.session_state["clone_data"] = {}

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
</style>
""", unsafe_allow_html=True)

# ----------- Funções Auxiliares (sem ambientes) -----------
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
    res = supabase.table("checklists").select("*").eq("task_id", task_id).execute()
    return [{"id": item["id"], "item": item["item"], "is_completed": item["is_completed"]} for item in res.data] if res.data else []

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

# ----------- Função: Gerar PDF (com miniaturas de imagens do Storage) -----------
def generate_pdf(task, technician_name, location_name, checklist_items):
    import tempfile
    import requests
    from PIL import Image as PILImage

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Título Principal ---
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 15, "RELATÓRIO DE MANUTENÇÃO PREVENTIVA", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "", 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, task["title"], ln=True, align="C")
    pdf.set_text_color(128, 128, 128)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 10, f"#MAN-{task['id'][:6].upper()}", ln=True, align="C")
    pdf.ln(10)

    # --- Linha divisória ---
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(10)

    # --- Função auxiliar para adicionar linhas ---
    def add_info_row(label, value):
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(50, 8, label + ":", border=0, fill=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 8, str(value), border=0, ln=True)

    # --- Informações da Tarefa ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "INFORMAÇÕES DA TAREFA", ln=True)
    pdf.ln(3)
    add_info_row("Título", task["title"])
    add_info_row("Especialidade", task.get("specialty", "—"))
    add_info_row("Local", location_name)
    add_info_row("Técnico", technician_name)
    due = task['due_date'][:16].replace('T', ' ')
    add_info_row("Agendado para", due)
    status_text = status_labels.get(task["status"], task["status"]).replace("📅 ", "").replace("🛠️ ", "").replace("✅ ", "").replace("❗ ", "")
    add_info_row("Status", status_text)
    recurrence_map_display = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
    add_info_row("Recorrência", recurrence_map_display.get(task.get("recurrence"), "Nenhuma"))
    add_info_row("Tipo de Manutenção", "Preventiva")
    add_info_row("Prioridade", task.get("priority", "Alta"))
    add_info_row("Observações", task.get("notes", "—"))

    pdf.ln(8)

    # --- Checklist ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "CHECKLIST", ln=True)
    pdf.ln(3)

    if checklist_items:
        completed_count = sum(1 for item in checklist_items if item["checked"])
        pdf.cell(0, 6, f"{completed_count}/{len(checklist_items)} Itens concluídos", ln=True)
        pdf.ln(2)
        for i, item in enumerate(checklist_items):
            pdf.set_font("Arial", "", 10)
            mark = "X" if item["checked"] else "O"
            text = f"{i+1}. {item['text']}"
            pdf.multi_cell(0, 6, f"({mark}) {text}")
            pdf.ln(1)
    else:
        pdf.cell(0, 6, "Nenhum item no checklist.", ln=True)

    pdf.ln(8)

    # --- Imagens Anexadas ---
    try:
        files = supabase.storage.from_("task-attachments").list(f"{task['id']}/")
        if files:
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, "IMAGENS ANEXADAS", ln=True)
            pdf.ln(5)
            for file in files:
                if file['name'].lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    # Baixar imagem temporariamente
                    image_url = supabase.storage.from_("task-attachments").get_public_url(f"{task['id']}/{file['name']}")
                    response = requests.get(image_url)
                    if response.status_code == 200:
                        img_data = response.content
                        # Salvar em arquivo temporário
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
                            tmp_img.write(img_data)
                            temp_path = tmp_img.name

                        # Abrir imagem com PIL para redimensionar
                        pil_img = PILImage.open(temp_path)
                        # Converter para RGB se necessário (evita erro com RGBA ou CMYK)
                        if pil_img.mode in ("RGBA", "LA", "P"):
                            pil_img = pil_img.convert("RGB")
                        # Redimensionar para miniatura (ex: 100x100)
                        pil_img.thumbnail((100, 100))

                        # Salvar miniatura em novo arquivo temporário
                        thumb_path = temp_path + "_thumb.jpg"
                        pil_img.save(thumb_path, "JPEG")

                        # Adicionar miniatura ao PDF
                        pdf.image(thumb_path, w=30, h=30)
                        # Legenda
                        pdf.set_font("Arial", "", 8)
                        pdf.cell(30, 5, file['name'][:20] + "...", ln=True, align="C")
                        pdf.ln(5)

                        # Apagar arquivos temporários
                        import os
                        os.unlink(temp_path)
                        os.unlink(thumb_path)
                else:
                    # Se não for imagem, apenas liste o nome
                    pdf.set_font("Arial", "", 10)
                    pdf.cell(0, 6, f"[ARQ] {file['name']}", ln=True)  # ← SUBSTITUIU EMOJI POR [ARQ]
            pdf.ln(10)
    except Exception as e:
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, f"[Falha ao carregar imagens: {str(e)}]", ln=True)
        pdf.ln(10)

    # --- Rodapé ---
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 8, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Sistema de Manutenção Preventiva", ln=True, align="C")

    return bytes(pdf.output(dest='S'))

# ----------- Função: Arquivar tarefa ao concluir -----------
def archive_task(task, checklist_items):
    try:
        supabase.table("task_history").insert({
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
        }).execute()
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
                "notes": original_task.get("notes")
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

# ----------- Página Principal -----------
st.set_page_config(page_title="🔧 Manutenção Preventiva", layout="wide")
st.title("🔧 Sistema de Manutenção Preventiva")

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
col1, col2, col3 = st.columns(3)
with col1:
    all_specialities = get_specialties_list()
    selected_speciality = st.selectbox("Especialidade", ["Todas"] + all_specialities)
with col2:
    all_locs = load_locations()
    selected_loc = st.selectbox("Localidade", ["Todas"] + list(all_locs.values()))
with col3:
    filter_date = st.date_input("Data específica", value=None)

st.divider()

# --- Botão Nova Atividade ---
if st.button("➕ Nova Atividade", type="primary"):
    st.session_state["show_new_form"] = True

# --------------- FORMULÁRIO: Nova Atividade (com múltiplas localidades) ---------------
if st.session_state.get("show_new_form"):
    st.markdown("### ➕ Nova Atividade de Manutenção")
    cloned = st.session_state.get("cloned_task", {})
    with st.form("form_new_task"):
        title = st.text_input("Título *", value=cloned.get("title", ""))
        description = st.text_area("Descrição", value=cloned.get("description", ""))
        specialty = st.selectbox("Especialidade *", get_specialties_list() + ["Outra"], index=get_specialties_list().index(cloned.get("specialty")) if cloned.get("specialty") and cloned.get("specialty") in get_specialties_list() else len(get_specialties_list()))
        if specialty == "Outra":
            specialty = st.text_input("Nova especialidade", value=cloned.get("specialty", ""))
        techs = load_technicians()
        default_tech_idx = list(techs.keys()).index(cloned["technician_id"]) + 1 if cloned.get("technician_id") and cloned["technician_id"] in techs else 0
        tech_id = st.selectbox("Técnico", options=[None] + list(techs.keys()), format_func=lambda x: techs[x]["name"] if x else "—", index=default_tech_idx)
        locs = load_locations()
        default_loc_idx = list(locs.keys()).index(cloned["location_id"]) + 1 if cloned.get("location_id") and cloned["location_id"] in locs else 0
        loc_id = st.selectbox("Localidade *", options=[None] + list(locs.keys()), format_func=lambda x: locs[x] if x else "—", index=default_loc_idx)
        # 🔥 Nova funcionalidade: Múltiplas localidades
        use_multiple_locs = st.checkbox("Aplicar em múltiplas localidades", value=False)
        selected_locs = []
        if use_multiple_locs:
            selected_locs = st.multiselect("Selecione as localidades", options=list(locs.keys()), format_func=lambda x: locs[x])
        due_date = st.date_input("Data de Agendamento *", value=datetime.now())
        # Substituído por prioridade
        priority = st.selectbox("Prioridade", ["Baixa", "Média", "Alta"], index=2)
        recurrence_map_inv = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
        current_recurrence = cloned.get("recurrence", "Nenhuma")
        rec_index = ["Nenhuma", "Diária", "Semanal", "Mensal"].index(current_recurrence) if current_recurrence in ["Nenhuma", "Diária", "Semanal", "Mensal"] else 0
        recurrence = st.selectbox("Recorrência", ["Nenhuma", "Diária", "Semanal", "Mensal"], index=rec_index)
        checklist_input = st.text_area("Checklist (um item por linha)", 
                                       value=cloned.get("checklist_input", ""), 
                                       help="Será salvo com a tarefa")
        # 🔥 Campo de observações técnicas
        notes_input = st.text_area("Observações Técnicas", value=cloned.get("notes", ""), help="Informações adicionais sobre a tarefa")

        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("✅ Criar")
        with col2:
            cancel = st.form_submit_button("Cancelar")

        if submit:
            if not title or (not loc_id and not use_multiple_locs):
                st.error("Título e localidade são obrigatórios.")
            else:
                due_dt = datetime.combine(due_date, datetime.now().time())
                status = "scheduled" if due_dt >= datetime.now() else "overdue"
                recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
                if use_multiple_locs and selected_locs:
                    # Criar múltiplas tarefas
                    for loc_id_single in selected_locs:
                        res = supabase.table("maintenance_tasks").insert({
                            "title": title,
                            "description": description,
                            "specialty": specialty,
                            "technician_id": tech_id,
                            "location_id": str(loc_id_single),
                            "due_date": due_dt.isoformat(),
                            "recurrence": recurrence_map[recurrence],
                            "status": status,
                            "is_template": False,
                            "notes": notes_input,
                            "priority": priority
                        }).execute()
                        task_id = res.data[0]["id"] if res.data else None
                        if checklist_input and task_id:
                            items = [line.strip() for line in checklist_input.split("\n") if line.strip()]
                            for item in items:
                                supabase.table("checklists").insert({
                                    "task_id": task_id,
                                    "item": item,
                                    "is_completed": False
                                }).execute()
                    st.success(f"✅ {len(selected_locs)} tarefas criadas!")
                else:
                    # Criar uma tarefa normal
                    res = supabase.table("maintenance_tasks").insert({
                        "title": title,
                        "description": description,
                        "specialty": specialty,
                        "technician_id": tech_id,
                        "location_id": str(loc_id),
                        "due_date": due_dt.isoformat(),
                        "recurrence": recurrence_map[recurrence],
                        "status": status,
                        "is_template": False,
                        "notes": notes_input,
                        "priority": priority
                    }).execute()
                    task_id = res.data[0]["id"] if res.data else None
                    if checklist_input and task_id:
                        items = [line.strip() for line in checklist_input.split("\n") if line.strip()]
                        for item in items:
                            supabase.table("checklists").insert({
                                "task_id": task_id,
                                "item": item,
                                "is_completed": False
                            }).execute()
                    st.success("✅ Atividade criada!")

                st.session_state.pop("cloned_task", None)
                st.session_state["show_new_form"] = False
                st.rerun()

        if cancel:
            st.session_state.pop("cloned_task", None)
            st.session_state["show_new_form"] = False
            st.rerun()

# --------------- FORMULÁRIO: Clonar Atividade (com múltiplas localidades) ---------------
if st.session_state.get("show_clone_form"):
    cloning_data = st.session_state["clone_data"]
    original_task = cloning_data["original_task"]
    checklist_data = cloning_data["checklist"]

    st.markdown("### 📋 Clonar Atividade")
    with st.form("form_clone_task"):
        title = st.text_input("Título", value=original_task["title"])
        description = st.text_area("Descrição", value=original_task.get("description", ""))
        specialty = st.selectbox("Especialidade", get_specialties_list() + ["Outra"], index=get_specialties_list().index(original_task.get("specialty")) if original_task.get("specialty") in get_specialties_list() else 0)
        if specialty == "Outra":
            specialty = st.text_input("Nova especialidade", value=original_task.get("specialty", ""))

        techs = load_technicians()
        default_tech_idx = list(techs.keys()).index(original_task["technician_id"]) + 1 if original_task["technician_id"] in techs else 0
        tech_id = st.selectbox("Técnico", options=[None] + list(techs.keys()), format_func=lambda x: techs[x]["name"] if x else "—", index=default_tech_idx)

        due_date = st.date_input("Data de Agendamento", value=datetime.fromisoformat(original_task["due_date"][:10]))
        priority = st.selectbox("Prioridade", ["Baixa", "Média", "Alta"], index=["Baixa", "Média", "Alta"].index(original_task.get("priority", "Alta")))

        recurrence_map_inv = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
        current_recurrence = original_task.get("recurrence", "Nenhuma")
        rec_index = ["Nenhuma", "Diária", "Semanal", "Mensal"].index(current_recurrence) if current_recurrence in ["Nenhuma", "Diária", "Semanal", "Mensal"] else 0
        recurrence = st.selectbox("Recorrência", ["Nenhuma", "Diária", "Semanal", "Mensal"], index=rec_index)

        checklist_items = [item["item"] for item in checklist_data]
        checklist_str = "\n".join(checklist_items)
        checklist_input = st.text_area("Checklist (um item por linha)", value=checklist_str, help="Pode editar os itens do checklist original")

        notes_input = st.text_area("Observações Técnicas", value=original_task.get("notes", ""), help="Informações adicionais sobre a tarefa")

        locs = load_locations()
        selected_locs = st.multiselect("Selecione as localidades de destino", options=list(locs.keys()), format_func=lambda x: locs[x])

        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("✅ Clonar")
        with col2:
            cancel = st.form_submit_button("Cancelar")

        if submit:
            if not title or not selected_locs:
                st.error("Título e localidades são obrigatórios.")
            else:
                due_dt = datetime.combine(due_date, datetime.now().time())
                status = "scheduled" if due_dt >= datetime.now() else "overdue"
                recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}

                for loc_id_single in selected_locs:
                    res = supabase.table("maintenance_tasks").insert({
                        "title": title,
                        "description": description,
                        "specialty": specialty,
                        "technician_id": tech_id,
                        "location_id": str(loc_id_single),
                        "due_date": due_dt.isoformat(),
                        "recurrence": recurrence_map[recurrence],
                        "status": status,
                        "is_template": False,
                        "notes": notes_input,
                        "priority": priority
                    }).execute()
                    task_id = res.data[0]["id"] if res.data else None
                    if checklist_input and task_id:
                        items = [line.strip() for line in checklist_input.split("\n") if line.strip()]
                        for item in items:
                            supabase.table("checklists").insert({
                                "task_id": task_id,
                                "item": item,
                                "is_completed": False
                            }).execute()
                st.success(f"✅ {len(selected_locs)} tarefa(s) clonada(s) com sucesso!")
                st.session_state["show_clone_form"] = False
                st.rerun()

        if cancel:
            st.session_state["show_clone_form"] = False
            st.rerun()

# --------------- DETALHE DA ATIVIDADE EM MODAL (atualizado para upload de mídia) ---------------
def show_task_modal(task):
    techs = load_technicians()
    locs = load_locations()
    tech_name = get_technician_name(task["technician_id"], techs)
    loc_name = get_location_name(task["location_id"], locs)
    with st.container(border=True):
        st.markdown(f"### ✅ Detalhes: **{task['title']}**")
        st.markdown(f"**Descrição:** {task.get('description', '—')}")
        st.markdown(f"**Especialidade:** {task.get('specialty', '—')}")
        st.markdown(f"**Técnico:** {tech_name}")
        st.markdown(f"**Localidade:** 📍 `{loc_name}`")
        due = task['due_date'][:16].replace('T', ' ')
        st.markdown(f"**Agendado para:** {due}")
        st.markdown(f"**Status:** {status_labels.get(task['status'], task['status'])}")

        # Checklist com expandir/retrair
        checklist_data = load_checklist(task["id"])
        expand_key = f"expand_checklist_{task['id']}"
        if expand_key not in st.session_state:
            st.session_state[expand_key] = False
        if st.button("📋 Ver Checklist" if not st.session_state[expand_key] else "❌ Ocultar Checklist", key=f"toggle_chk_{task['id']}", use_container_width=True):
            st.session_state[expand_key] = not st.session_state[expand_key]
        if st.session_state[expand_key]:
            st.markdown("**Checklist:**")
            if checklist_data:
                total = len(checklist_data)
                done = sum(1 for i in checklist_data if i["is_completed"])
                progress = done / total if total > 0 else 0
                st.progress(progress)
                st.caption(f"✔️ {done}/{total} concluídos")
                for i, item in enumerate(checklist_data):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"{'✅' if item['is_completed'] else '🔲'} {item['item']}")
                    with col2:
                        new_status = st.checkbox("", value=item["is_completed"], key=f"chk_modal_{task['id']}_{i}")
                        # Armazena estado temporário
                        if f"chk_modal_{task['id']}_{i}_state" not in st.session_state:
                            st.session_state[f"chk_modal_{task['id']}_{i}_state"] = item["is_completed"]
                        st.session_state[f"chk_modal_{task['id']}_{i}_state"] = new_status
            else:
                st.caption("_Nenhum checklist_")

        # Observações técnicas
        st.markdown("### 📝 Observações Técnicas")
        note_key = f"note_{task['id']}"
        if note_key not in st.session_state:
            # Carrega observação do banco (simulado como não existente, pois não temos login)
            # Supondo que o campo 'notes' exista na tabela
            res = supabase.table("maintenance_tasks").select("notes").eq("id", task["id"]).execute()
            current_note = res.data[0]["notes"] if res.data and res.data[0].get("notes") else ""
            st.session_state[note_key] = current_note
        observation = st.text_area(
            "Digite suas observações finais...",
            value=st.session_state[note_key],
            height=100,
            help="Ex: 'Filtro limpo, pressão normalizada'"
        )
        st.session_state[note_key] = observation  # Atualiza em tempo real

        # Upload de Múltiplas Imagens e Vídeos
        st.markdown("### 📎 Anexos")
        uploaded_files = st.file_uploader(
            "Anexar fotos e vídeos",
            type=["png", "jpg", "jpeg", "webp", "mp4", "mov", "avi", "mkv"],
            accept_multiple_files=True,
            key=f"upload_{task['id']}"
        )
        if uploaded_files:
            for uploaded_file in uploaded_files:
                try:
                    # Gera nome único para evitar conflitos
                    file_ext = uploaded_file.name.split(".")[-1]
                    file_unique_name = f"{task['id']}/{uploaded_file.name}"
                    supabase.storage.from_("task-attachments").upload(
                        file_unique_name,
                        uploaded_file.getvalue(),
                        file_options={"content-type": uploaded_file.type}
                    )
                    st.success(f"✅ {uploaded_file.name} anexado!")
                except Exception as e:
                    st.error(f"Erro ao enviar {uploaded_file.name}: {str(e)}")

        # Mostrar Arquivos Anexados
        try:
            files = supabase.storage.from_("task-attachments").list(f"{task['id']}/")
            if files:
                st.markdown("#### 🖼️ Mídias Anexadas:")
                cols_media = st.columns(3)
                for idx, file in enumerate(files):
                    url = supabase.storage.from_("task-attachments").get_public_url(f"{task['id']}/{file['name']}")
                    with cols_media[idx % 3]:
                        if file['name'].lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                            st.image(url, caption=file["name"], use_column_width=True)
                        elif file['name'].lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                            st.video(url, format="video/mp4")
                        else:
                            st.caption(f"📎 [{file['name']}]({url})")
            else:
                st.caption("_Nenhuma mídia anexada._")
        except Exception as e:
            st.caption(f"_Falha ao carregar mídias: {str(e)}_")

        # Botões
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if task["status"] in ["scheduled", "overdue"]:
                if st.button("▶️ Iniciar", use_container_width=True):
                    supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task["id"]).execute()
                    st.success("✅ Status atualizado!")
                    st.rerun()
            elif task["status"] == "in_progress":
                if st.button("✅ Concluir", use_container_width=True):
                    # Salvar checklist marcado
                    for i, item in enumerate(checklist_data):
                        new_status = st.session_state.get(f"chk_modal_{task['id']}_{i}_state", item["is_completed"])
                        if new_status != item["is_completed"]:
                            supabase.table("checklists").update({"is_completed": new_status}).eq("id", item["id"]).execute()
                    # Salvar observação técnica
                    supabase.table("maintenance_tasks").update({
                        "status": "completed",
                        "notes": st.session_state[note_key]
                    }).eq("id", task["id"]).execute()
                    # 🔁 Arquivar
                    checklist_items = [{"text": item["item"], "checked": st.session_state.get(f"chk_modal_{task['id']}_{i}_state", item["is_completed"])} for i, item in enumerate(checklist_data)]
                    archive_task(task, checklist_items)
                    # 🔁 Recorrência
                    if task.get("recurrence"):
                        create_recurring_task(task)
                    st.success("✅ Tarefa concluída!")
                    st.rerun()
        with col2:
            if st.button("📋 Clonar", use_container_width=True):
                locations = load_locations()
                with st.expander(f"Clonar para múltiplas localidades", expanded=True):
                    selected_locations = st.multiselect(
                        "Selecione as localidades",
                        options=list(locations.keys()),
                        format_func=lambda x: locations[x],
                        key=f"multi_loc_{task['id']}"
                    )
                    if st.button("Clonar para selecionadas", key=f"do_clone_{task['id']}", use_container_width=True):
                        checklist_data = load_checklist(task["id"])
                        if selected_locations:
                            for loc_id in selected_locations:
                                res = supabase.table("maintenance_tasks").insert({
                                    "title": task["title"],
                                    "description": task.get("description"),
                                    "specialty": task.get("specialty"),
                                    "technician_id": task.get("technician_id"),
                                    "location_id": str(loc_id),
                                    "due_date": task["due_date"],
                                    "recurrence": task.get("recurrence"),
                                    "status": "scheduled",
                                    "is_template": False,
                                    "notes": task.get("notes", "")  # 🔥 Copia observações
                                }).execute()
                                new_task_id = res.data[0]["id"] if res.data else None
                                if checklist_data and new_task_id:
                                    for item in checklist_data:
                                        supabase.table("checklists").insert({
                                            "task_id": new_task_id,
                                            "item": item["item"],
                                            "is_completed": False
                                        }).execute()
                            st.success(f"✅ {len(selected_locations)} tarefas clonadas!")
                            st.rerun()
                        else:
                            st.warning("Selecione pelo menos uma localidade.")
        with col3:
            if st.button("🗑️ Excluir", use_container_width=True):
                supabase.table("checklists").delete().eq("task_id", task["id"]).execute()
                supabase.table("maintenance_tasks").delete().eq("id", task["id"]).execute()
                # Apaga arquivos do storage (opcional)
                try:
                    supabase.storage.from_("task-attachments").remove([f"{task['id']}/{f['name']}" for f in files])
                except:
                    pass  # Não faz nada se não houver arquivos
                st.success("✅ Tarefa excluída!")
                st.session_state["selected_task"] = None
                st.rerun()
        with col4:
            if st.button("← Voltar", use_container_width=True):
                st.session_state["selected_task"] = None
                st.rerun()

# Se houver tarefa selecionada, mostra o modal
if st.session_state["selected_task"]:
    show_task_modal(st.session_state["selected_task"])
else:
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
        return query.execute().data or []

    tasks_all = get_filtered_tasks(["scheduled", "in_progress", "completed", "overdue"])

    # Modo: Lista
if st.session_state["view_mode"] == "list":
    st.subheader("📋 Visão em Lista")
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
    for task in tasks_all:
        # 🔥 Card com sombra e borda
        with st.container(border=True):
            col1, col2, col3, col4, col5, col6 = st.columns([1, 3, 2, 1, 1, 1])
            with col1:
                if st.session_state.get(bulk_key, False):
                    key = f"bulk_list_{task['id']}"
                    is_selected = st.checkbox("", value=task["id"] in st.session_state[select_key], key=key)
                    if is_selected and task["id"] not in st.session_state[select_key]:
                        st.session_state[select_key].append(task["id"])
                    elif not is_selected and task["id"] in st.session_state[select_key]:
                        st.session_state[select_key].remove(task["id"])
            with col2:
                st.markdown(f"**{task['title']}**")
                st.caption(f"📍 {get_location_name(task['location_id'], locs)}")
            with col3:
                st.write(status_labels.get(task["status"]))
            with col4:
                if st.button("🔍", key=f"open_{task['id']}"):
                    st.session_state["selected_task"] = task
                    st.rerun()
            with col5:
                # Botão PDF
                checklist_data = load_checklist(task["id"])
                checklist_items = [{"text": item["item"], "checked": item["is_completed"]} for item in checklist_data]
                if st.button("📄", key=f"pdf_list_{task['id']}", help="Gerar PDF"):
                    try:
                        pdf_bytes = generate_pdf(task, get_technician_name(task['technician_id'], techs), get_location_name(task['location_id'], locs), checklist_items)
                        st.download_button(
                            label="📥",
                            data=pdf_bytes,
                            file_name=f"atividade_{task['id']}.pdf",
                            mime="application/pdf",
                            key=f"download_pdf_list_{task['id']}",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Erro ao gerar PDF: {str(e)}")
            with col6:
                st.markdown(f"<small>{task['due_date'][:16].replace('T', ' ')}</small>", unsafe_allow_html=True)

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
                    # 🔥 Card retrátil com sombra e borda
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
                        col1, col2, col3, col4 = st.columns(4)
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
                                st.session_state["clone_data"] = {
                                    "original_task": task,
                                    "checklist": checklist_data
                                }
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

    # Modo: Calendário
elif st.session_state["view_mode"] == "calendar":
        st.subheader("📅 Visão em Calendário")
        events = []
        for task in tasks_all:
            events.append({
                "title": task["title"],
                "start": task["due_date"][:16].replace("T", " "),
                "color": COLORS.get(task.get("specialty"), "#eee"),
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

# --------------- HISTÓRICO DE ATIVIDADES ---------------
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