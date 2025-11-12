# app.py — Sistema de Manutenção Preventiva (sem ambientes, com calendário)
import streamlit as st
from datetime import datetime, timedelta
from supabase_client import get_supabase_client
from fpdf import FPDF
import os
from streamlit_drawable_canvas import st_canvas
from streamlit_calendar import calendar  # ← Novo: calendário

supabase = get_supabase_client()

if "show_new_form" not in st.session_state:
    st.session_state["show_new_form"] = False
if "show_history" not in st.session_state:
    st.session_state["show_history"] = False
if "selected_task" not in st.session_state:
    st.session_state["selected_task"] = None
if "view_mode" not in st.session_state:
    st.session_state["view_mode"] = "kanban"

status_labels = {
    "scheduled": "📅 Agendada",
    "in_progress": "🛠️ Em Execução",
    "completed": "✅ Concluída",
    "overdue": "❗ Atrasada"
}

COLORS = {
    "Refrigeração": "#e3f2fd",
    "Elétrica": "#fff8e1",
    "Hidráulica": "#f3e5f5",
    "Mecânica": "#e8f5e9",
    "Outra": "#eeeeee"
}

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

def load_templates():
    res = supabase.table("templates").select("*").execute()
    return res.data if res.data else []

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

# ----------- Função: Gerar PDF -----------
def generate_pdf(task, technician_name, location_name, checklist_items):
    font_normal = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
    font_bold = os.path.join(os.path.dirname(__file__), "DejaVuSans-Bold.ttf")
    if not os.path.exists(font_normal): raise FileNotFoundError("Falta: DejaVuSans.ttf")
    if not os.path.exists(font_bold): raise FileNotFoundError("Falta: DejaVuSans-Bold.ttf")

    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", font_normal, uni=True)
    pdf.add_font("DejaVu", "B", font_bold, uni=True)
    pdf.set_font("DejaVu", "", 12)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Relatório de Atividade", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, f"Título: {task['title']}", ln=True)
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Descrição: {task.get('description', '—')}", ln=True)
    pdf.cell(0, 8, f"Especialidade: {task.get('specialty', '—')}", ln=True)
    pdf.cell(0, 8, f"Técnico: {technician_name}", ln=True)
    pdf.cell(0, 8, f"Localidade: {location_name}", ln=True)
    due = task['due_date'][:16].replace('T', ' ')
    pdf.cell(0, 8, f"Agendado para: {due}", ln=True)
    pdf.cell(0, 8, f"Status: {status_labels.get(task['status'], task['status'])}", ln=True)
    recurrence_map_display = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
    pdf.cell(0, 8, f"Recorrência: {recurrence_map_display.get(task.get('recurrence'), 'Nenhuma')}", ln=True)
    pdf.ln(5)
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
            "notes": ""
        }).execute()
    except Exception as e:
        st.error(f"Erro ao arquivar: {str(e)}")

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

# --- Sidebar: Cadastros (sem ambientes) ---
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

    # --- Modelos ---
    st.header("📂 Modelos")
    templates = load_templates()
    if templates:
        selected_template = st.selectbox(
            "Usar modelo",
            options=[t["id"] for t in templates],
            format_func=lambda x: next(t["title"] for t in templates if t["id"] == x)
        )
        if st.button("➕ Criar com Modelo"):
            template = next(t for t in templates if t["id"] == selected_template)
            st.session_state["cloned_task"] = {
                "title": template["title"],
                "description": template["description"],
                "specialty": template["specialty"],
                "technician_id": template["technician_id"],
                "location_id": template["location_id"],
                "checklist_input": "\n".join(template.get("checklist", [])),
                "recurrence": template.get("recurrence")
            }
            st.session_state["show_new_form"] = True
            st.rerun()
    else:
        st.info("Nenhum modelo salvo.")

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
    all_specialties = get_specialties_list()
    selected_specialty = st.selectbox("Especialidade", ["Todas"] + all_specialties)
with col2:
    all_locs = load_locations()
    selected_loc = st.selectbox("Localidade", ["Todas"] + list(all_locs.values()))
with col3:
    filter_date = st.date_input("Data específica", value=None)

st.divider()

# --- Botão Nova Atividade ---
if st.button("➕ Nova Atividade", type="primary"):
    st.session_state["show_new_form"] = True

# --------------- FORMULÁRIO: Nova Atividade (sem ambiente) ---------------
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

        due_date = st.date_input("Data de Agendamento *", value=datetime.now())
        due_time = st.time_input("Hora *", value=datetime.now().time())

        recurrence_map_inv = {None: "Nenhuma", "daily": "Diária", "weekly": "Semanal", "monthly": "Mensal"}
        current_recurrence = cloned.get("recurrence", "Nenhuma")
        rec_index = ["Nenhuma", "Diária", "Semanal", "Mensal"].index(current_recurrence) if current_recurrence in ["Nenhuma", "Diária", "Semanal", "Mensal"] else 0
        recurrence = st.selectbox("Recorrência", ["Nenhuma", "Diária", "Semanal", "Mensal"], index=rec_index)

        checklist_input = st.text_area("Checklist (um item por linha)", 
                                       value=cloned.get("checklist_input", ""), 
                                       help="Será salvo com a tarefa")

        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("✅ Criar")
        with col2:
            cancel = st.form_submit_button("Cancelar")

        if submit:
            if not title or not loc_id or not specialty:
                st.error("Título, localidade e especialidade são obrigatórios.")
            else:
                due_dt = datetime.combine(due_date, due_time)
                status = "scheduled" if due_dt >= datetime.now() else "overdue"
                recurrence_map = {"Nenhuma": None, "Diária": "daily", "Semanal": "weekly", "Mensal": "monthly"}
                res = supabase.table("maintenance_tasks").insert({
                    "title": title,
                    "description": description,
                    "specialty": specialty,
                    "technician_id": tech_id,
                    "location_id": str(loc_id),
                    "due_date": due_dt.isoformat(),
                    "recurrence": recurrence_map[recurrence],
                    "status": status,
                    "is_template": False
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

# --------------- DETALHE DA ATIVIDADE EM MODAL ---------------
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
        st.markdown(f"**Localidade:** 📍 `{loc_name}`")  # Destaque
        st.markdown(f"**Agendado para:** {task['due_date'][:16].replace('T', ' ')}")
        st.markdown(f"**Status:** {status_labels.get(task['status'], task['status'])}")

        # Checklist com expandir/retrair
        checklist_data = load_checklist(task["id"])
        expand_key = f"expand_checklist_{task['id']}"
        if expand_key not in st.session_state:
            st.session_state[expand_key] = False

        if st.button("📋 Ver Checklist" if not st.session_state[expand_key] else "❌ Ocultar Checklist", use_container_width=True):
            st.session_state[expand_key] = not st.session_state[expand_key]

        if st.session_state[expand_key]:
            st.markdown("**Checklist:**")
            for i, item in enumerate(checklist_data):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"{'✅' if item['is_completed'] else '🔲'} {item['item']}")
                with col2:
                    new_status = st.checkbox("", value=item["is_completed"], key=f"chk_{task['id']}_{i}")
                    # Armazena estado temporário
                    if f"chk_{task['id']}_{i}_state" not in st.session_state:
                        st.session_state[f"chk_{task['id']}_{i}_state"] = item["is_completed"]
                    st.session_state[f"chk_{task['id']}_{i}_state"] = new_status

        # Upload de imagem
        st.markdown("### 📎 Anexos")
        uploaded_file = st.file_uploader("Anexar imagem", type=["png", "jpg", "jpeg"], key=f"upload_{task['id']}")
        if uploaded_file:
            try:
                supabase.storage.from_("task-attachments").upload(
                    f"{task['id']}/{uploaded_file.name}",
                    uploaded_file.getvalue(),
                    file_options={"content-type": uploaded_file.type}
                )
                st.success("✅ Imagem anexada!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao enviar: {str(e)}")

        # Anexos existentes
        try:
            files = supabase.storage.from_("task-attachments").list(f"{task['id']}/")
            if files:
                for file in files:
                    url = supabase.storage.from_("task-attachments").get_public_url(f"{task['id']}/{file['name']}")
                    st.image(url, width=200, caption=file["name"])
            else:
                st.caption("_Nenhum anexo_")
        except:
            st.caption("_Falha ao carregar anexos_")

        # Assinatura
        signature_url = task.get("signature_url")
        if signature_url:
            st.image(signature_url, caption="Assinatura do técnico", width=300)

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
                        new_status = st.session_state.get(f"chk_{task['id']}_{i}_state", item["is_completed"])
                        if new_status != item["is_completed"]:
                            supabase.table("checklists").update({"is_completed": new_status}).eq("id", item["id"]).execute()
                    
                    # Assinatura digital
                    with st.expander("Assinatura Digital", expanded=True):
                        canvas_result = st_canvas(
                            fill_color="rgba(255, 255, 255, 0)",
                            stroke_width=2,
                            stroke_color="#000000",
                            background_color="#ffffff",
                            height=150,
                            width=400,
                            drawing_mode="freedraw",
                            key=f"canvas_modal_{task['id']}"
                        )
                        if canvas_result.image_data is not None:
                            from PIL import Image
                            import io
                            img = Image.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            img_bytes = buf.getvalue()
                            signature_url = f"signatures/{task['id']}.png"
                            try:
                                supabase.storage.from_("signatures").upload(signature_url, img_bytes, file_options={"content-type": "image/png"})
                                signature_url = supabase.storage.from_("signatures").get_public_url(signature_url)
                            except Exception as e:
                                st.error(f"Erro ao salvar assinatura: {str(e)}")
                                signature_url = None
                        else:
                            signature_url = None

                    supabase.table("maintenance_tasks").update({"status": "completed", "signature_url": signature_url}).eq("id", task["id"]).execute()
                    # 🔁 Arquivar
                    checklist_items = [{"text": item["item"], "checked": st.session_state.get(f"chk_{task['id']}_{i}_state", item["is_completed"])} for i, item in enumerate(checklist_data)]
                    archive_task(task, checklist_items)
                    # 🔁 Recorrência
                    if task.get("recurrence"):
                        create_recurring_task(task)
                    st.success("✅ Tarefa concluída!")
                    st.rerun()

        with col2:
            if st.button("📋 Clonar", use_container_width=True):
                st.session_state["cloned_task"] = {
                    "title": task["title"],
                    "description": task.get("description"),
                    "specialty": task.get("specialty"),
                    "technician_id": task.get("technician_id"),
                    "location_id": task.get("location_id"),
                    "checklist_input": "\n".join([item["item"] for item in checklist_data]),
                    "recurrence": task.get("recurrence")
                }
                st.session_state["show_new_form"] = True
                st.rerun()

        with col3:
            if st.button("🗑️ Excluir", use_container_width=True):
                supabase.table("checklists").delete().eq("task_id", task["id"]).execute()
                supabase.table("maintenance_tasks").delete().eq("id", task["id"]).execute()
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
        if selected_specialty != "Todas":
            query = query.eq("specialty", selected_specialty)
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
        for task in tasks_all:
            with st.container(border=True):
                col1, col2, col3 = st.columns([4, 2, 1])
                with col1:
                    st.markdown(f"**{task['title']}**")
                    st.caption(f"📍 {get_location_name(task['location_id'], locs)}")
                with col2:
                    st.write(status_labels.get(task["status"]))
                with col3:
                    if st.button("🔍", key=f"open_{task['id']}"):
                        st.session_state["selected_task"] = task
                        st.rerun()

    # Modo: Kanban
    elif st.session_state["view_mode"] == "kanban":
        st.subheader("📊 Quadro Kanban")
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
                    with st.expander(f"**{task['title']}**", expanded=False):
                        st.markdown(f"**Especialidade:** `{task.get('specialty', '—')}`")
                        st.markdown(f"**Técnico:** {get_technician_name(task['technician_id'], techs)}")
                        st.markdown(f"**Local:** 📍 `{get_location_name(task['location_id'], locs)}`")  # 🔥 Destaque
                        due = task['due_date'][:16].replace('T', ' ')
                        st.markdown(f"**Agendado para:** {due}")

                        # Checklist com expandir/retrair
                        checklist_data = load_checklist(task["id"])
                        expand_key = f"expand_checklist_kanban_{task['id']}"
                        if expand_key not in st.session_state:
                            st.session_state[expand_key] = False

                        if st.button("📋 Ver Checklist" if not st.session_state[expand_key] else "❌ Ocultar Checklist", key=f"toggle_chk_{task['id']}", use_container_width=True):
                            st.session_state[expand_key] = not st.session_state[expand_key]

                        if st.session_state[expand_key]:
                            st.markdown("**Checklist:**")
                            for item in checklist_data:
                                mark = "✅" if item["is_completed"] else "🔲"
                                st.markdown(f"{mark} {item['item']}")

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
                                    archive_task(task, [{"text": item["item"], "checked": item["is_completed"]} for item in checklist_data])
                                    create_recurring_task(task)
                                    st.rerun()
                        with col2:
                            if st.button("📋 Clonar", key=f"clone_{task['id']}", use_container_width=True):
                                st.session_state["cloned_task"] = {
                                    "title": task["title"],
                                    "description": task.get("description"),
                                    "specialty": task.get("specialty"),
                                    "technician_id": task.get("technician_id"),
                                    "location_id": task.get("location_id"),
                                    "checklist_input": "\n".join([item["item"] for item in checklist_data]),
                                    "recurrence": task.get("recurrence")
                                }
                                st.session_state["show_new_form"] = True
                                st.rerun()
                        with col3:
                            if st.button("📄 PDF", key=f"pdf_{task['id']}", use_container_width=True):
                                try:
                                    pdf_bytes = generate_pdf(task, get_technician_name(task['technician_id'], techs), get_location_name(task['location_id'], locs), checklist_data)
                                    st.download_button(
                                        "📥 Baixar",
                                        data=pdf_bytes,
                                        file_name=f"atividade_{task['id']}.pdf",
                                        mime="application/pdf",
                                        key=f"download_pdf_{task['id']}"
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

    if st.button("Voltar"):
        st.session_state["show_history"] = False
        st.rerun()