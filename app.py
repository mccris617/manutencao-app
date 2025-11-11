# app.py — Sistema de Manutenção Preventiva (versão com debug de ambientes)
import streamlit as st
from datetime import datetime, timedelta
from supabase_client import get_supabase_client
from fpdf import FPDF
import os

supabase = get_supabase_client()

if "show_new_form" not in st.session_state:
    st.session_state["show_new_form"] = False

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

# ----------- Funções Auxiliares -----------
def load_technicians():
    res = supabase.table("technicians").select("*").execute()
    return {t["id"]: t for t in res.data} if res.data else {}

def load_locations():
    res = supabase.table("locations").select("*").execute()
    return {l["id"]: l["name"] for l in res.data} if res.data else {}

def load_environments():
    res = supabase.table("environments").select("*").execute()
    return {e["id"]: e for e in res.data} if res.data else {}

def get_technician_name(tech_id, tech_dict):
    return tech_dict.get(str(tech_id), {}).get("name", "Não atribuído")

def get_location_name(loc_id, loc_dict):
    return loc_dict.get(str(loc_id), "—")

def get_environment_name(env_id, env_dict):
    return env_dict.get(str(env_id), "—") if env_dict and env_id else "—"

def get_specialties_list():
    res = supabase.table("technicians").select("specialty").execute()
    specialties = {r["specialty"] for r in res.data if r.get("specialty")}
    return sorted(specialties) if specialties else ["Refrigeração", "Elétrica", "Hidráulica", "Mecânica"]

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
def generate_pdf(task, technician_name, location_name, environment_name, checklist_items):
    pdf = FPDF()
    pdf.add_page()
    base_dir = os.path.dirname(__file__)
    font_normal = os.path.join(base_dir, "DejaVuSans.ttf")
    font_bold = os.path.join(base_dir, "DejaVuSans-Bold.ttf")
    if not os.path.exists(font_normal):
        raise FileNotFoundError("Falta: DejaVuSans.ttf")
    if not os.path.exists(font_bold):
        raise FileNotFoundError("Falta: DejaVuSans-Bold.ttf")
    pdf.add_font("DejaVu", "", font_normal, uni=True)
    pdf.add_font("DejaVu", "B", font_bold, uni=True)
    pdf.add_font("DejaVu", "I", font_normal, uni=True)
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
    pdf.cell(0, 8, f"Ambiente: {environment_name}", ln=True)
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

# ----------- Página Principal -----------
st.set_page_config(page_title="🔧 Manutenção Preventiva", layout="wide")
st.title("🔧 Sistema de Manutenção Preventiva")

base_dir = os.path.dirname(__file__)
required = ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"]
missing = [f for f in required if not os.path.exists(os.path.join(base_dir, f))]
if missing:
    st.sidebar.error(f"⚠️ Fontes ausentes: {', '.join(missing)}")
else:
    st.sidebar.success("✅ Fontes OK")

# --- Cadastros na sidebar ---
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
    with st.expander("🏢 Ambientes"):
        locations = load_locations()
        if locations:
            loc_id = st.selectbox("Localidade", options=list(locations.keys()), format_func=lambda x: locations[x])
            with st.form("add_environment"):
                env_name = st.text_input("Nome do Ambiente")
                if st.form_submit_button("Salvar"):
                    if loc_id and env_name:
                        supabase.table("environments").insert({
                            "name": env_name,
                            "location_id": str(loc_id)
                        }).execute()
                        st.success("✅ Ambiente salvo!")
                        st.rerun()
        else:
            st.info("Cadastre uma localidade primeiro.")

# --- Filtros principais ---
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

# --------------- FORMULÁRIO: Nova Atividade (com campo de texto para ambiente) ---------------
if st.session_state.get("show_new_form"):
    st.markdown("### ➕ Nova Atividade de Manutenção")
    
    with st.form("form_new_task"):
        title = st.text_input("Título *")
        description = st.text_area("Descrição")
        specialties = get_specialties_list()
        specialty = st.selectbox("Especialidade *", specialties + ["Outra"])
        if specialty == "Outra":
            specialty = st.text_input("Nova especialidade")
        techs = load_technicians()
        tech_id = st.selectbox("Técnico", options=[None] + list(techs.keys()), format_func=lambda x: techs[x]["name"] if x else "—")
        
        # Localidade (mantém como selectbox)
        locs = load_locations()
        loc_id = st.selectbox(
            "Localidade *",
            options=[None] + list(locs.keys()),
            format_func=lambda x: locs[x] if x else "Selecione uma localidade"
        )

        # 🔥 Ambiente agora é campo de texto
        environment_name = st.text_input("Nome do Ambiente *", help="Digite o nome do ambiente onde a atividade será executada")

        due_date = st.date_input("Data de Agendamento *")
        due_time = st.time_input("Hora *")
        recurrence = st.selectbox("Recorrência", ["Nenhuma", "Diária", "Semanal", "Mensal"])
        checklist_input = st.text_area("Checklist (um item por linha)", help="Será salvo com a tarefa")
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("✅ Criar")
        with col2:
            cancel = st.form_submit_button("Cancelar")
        if submit:
            if not title or not loc_id or not environment_name or not specialty:
                st.error("Título, localidade, ambiente e especialidade são obrigatórios.")
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
                    "environment_id": None,  # 🔥 Agora não usamos mais ID de ambiente
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
                st.session_state["show_new_form"] = False
                st.rerun()
        if cancel:
            st.session_state["show_new_form"] = False
            st.rerun()

# --------------- QUADRO KANBAN COM CHECKLIST OTIMIZADO ---------------
else:
    st.markdown("## 📋 Quadro de Atividades")

    techs = load_technicians()
    locs = load_locations()
    all_locs = locs

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

    cols = st.columns([1, 1])

    # Coluna 1: A fazer + Em andamento
    with cols[0]:
        st.markdown("### 📅 A Fazer & Em Andamento")
        tasks_active = get_filtered_tasks(["scheduled", "overdue", "in_progress"])
        if not tasks_active:
            st.caption("_Nenhuma tarefa ativa_")
        for task in tasks_active:
            specialty_color = COLORS.get(task.get("specialty"), "#eeeeee")
            expand_data_key = f"expand_data_{task['id']}"
            expand_checklist_key = f"expand_checklist_{task['id']}"
            if expand_data_key not in st.session_state:
                st.session_state[expand_data_key] = False
            if expand_checklist_key not in st.session_state:
                st.session_state[expand_checklist_key] = False

            with st.container(border=True):
                st.markdown(
                    f"<div style='background-color:{specialty_color};padding:10px;border-radius:8px;'>"
                    f"<h4 style='margin:0;color:#1a1a1a;'>{task['title']}</h4>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.markdown(f"**Status:** {status_labels.get(task['status'], task['status'])}")

                if st.button(
                    "🔍 Ver Detalhes" if not st.session_state[expand_data_key] else "❌ Ocultar Detalhes",
                    key=f"toggle_data_{task['id']}",
                    use_container_width=True
                ):
                    st.session_state[expand_data_key] = not st.session_state[expand_data_key]

                if st.session_state[expand_data_key]:
                    st.markdown(f"**Especialidade:** `{task.get('specialty', '—')}`")
                    st.markdown(f"**Técnico:** {get_technician_name(task['technician_id'], techs)}")
                    st.markdown(f"**Local:** {get_location_name(task['location_id'], locs)} → {get_environment_name(task['environment_id'], load_environments())}")
                    due = task['due_date'][:16].replace('T', ' ')
                    st.markdown(f"**Agendado para:** {due}")
                    st.markdown(f"**Recorrência:** {task.get('recurrence', 'Nenhuma')}")

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

                checklist_data = supabase.table("checklists").select("*").eq("task_id", task["id"]).execute().data or []
                edit_mode_key = f"edit_mode_{task['id']}"
                checklist_state_key = f"checklist_{task['id']}"
                if edit_mode_key not in st.session_state:
                    st.session_state[edit_mode_key] = False
                if checklist_state_key not in st.session_state:
                    st.session_state[checklist_state_key] = [
                        {"id": item["id"], "item": item["item"], "is_completed": item["is_completed"]}
                        for item in checklist_data
                    ]

                is_editing = st.session_state[edit_mode_key]
                current_checklist = st.session_state[checklist_state_key]

                if checklist_data:
                    if not is_editing:
                        if st.button(
                            "📋 Ver Checklist" if not st.session_state[expand_checklist_key] else "❌ Ocultar Checklist",
                            key=f"toggle_checklist_{task['id']}",
                            use_container_width=True
                        ):
                            st.session_state[expand_checklist_key] = not st.session_state[expand_checklist_key]

                        if st.session_state[expand_checklist_key]:
                            st.markdown("**Checklist:**")
                            for item in checklist_data:
                                mark = "✅" if item["is_completed"] else "🔲"
                                st.markdown(f"{mark} {item['item']}")
                    else:
                        st.markdown("### 📝 Checklist (edição)")
                        edited_items = []
                        for i, item in enumerate(current_checklist):
                            new_text = st.text_input(f"Item {i+1}", value=item["item"], key=f"checklist_text_{task['id']}_{i}")
                            checked = st.checkbox("Concluído", value=item["is_completed"], key=f"checklist_check_{task['id']}_{i}")
                            edited_items.append({"id": item["id"], "item": new_text, "is_completed": checked})
                        st.session_state[checklist_state_key] = edited_items
                else:
                    st.caption("_Nenhum checklist_")

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
                                "environment_id": original_task.get("environment_id"),
                                "due_date": next_due.isoformat(),
                                "recurrence": recurrence,
                                "status": "scheduled",
                                "is_template": False
                            }).execute()
                            new_task_id = res.data[0]["id"] if res.data else None
                            if checklist_data:
                                for item in checklist_data:
                                    supabase.table("checklists").insert({
                                        "task_id": new_task_id,
                                        "item": item["item"],
                                        "is_completed": False
                                    }).execute()
                    except Exception as e:
                        st.error(f"Erro ao criar tarefa recorrente: {str(e)}")

                col1, col2, col3, col4 = st.columns(4)
                if task["status"] in ["scheduled", "overdue"]:
                    with col1:
                        if st.button("▶️ Iniciar", key=f"btn_start_{task['id']}", use_container_width=True):
                            supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task["id"]).execute()
                            st.rerun()
                elif task["status"] == "in_progress":
                    with col1:
                        if st.button("✅ Concluir", key=f"btn_done_{task['id']}", use_container_width=True):
                            supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task["id"]).execute()
                            create_recurring_task(task)
                            st.rerun()
                with col2:
                    if is_editing:
                        if st.button("💾 Salvar", key=f"btn_save_{task['id']}", use_container_width=True):
                            for item in current_checklist:
                                supabase.table("checklists").update({
                                    "item": item["item"],
                                    "is_completed": item["is_completed"]
                                }).eq("id", item["id"]).execute()
                            all_done = all(item["is_completed"] for item in current_checklist) if current_checklist else False
                            if all_done and task["status"] != "completed":
                                supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task["id"]).execute()
                                create_recurring_task(task)
                            st.session_state[edit_mode_key] = False
                            st.success("✅ Alterações salvas!")
                            st.rerun()
                    else:
                        if st.button("✏️ Editar", key=f"btn_edit_{task['id']}", use_container_width=True):
                            st.session_state[edit_mode_key] = True
                            st.rerun()
                with col3:
                    if st.button("🗑️ Excluir", key=f"btn_del_{task['id']}", use_container_width=True):
                        supabase.table("checklists").delete().eq("task_id", task["id"]).execute()
                        supabase.table("maintenance_tasks").delete().eq("id", task["id"]).execute()
                        st.rerun()
                with col4:
                    technician_name = get_technician_name(task['technician_id'], techs)
                    location_name = get_location_name(task['location_id'], locs)
                    environment_name = get_environment_name(task['environment_id'], load_environments())
                    checklist_items = [{"id": item["id"], "text": item["item"], "checked": item["is_completed"]} for item in checklist_data]
                    try:
                        pdf_bytes = generate_pdf(task, technician_name, location_name, environment_name, checklist_items)
                        st.download_button(
                            "🖨️ PDF",
                            data=pdf_bytes,
                            file_name=f"atividade_{task['id']}.pdf",
                            mime="application/pdf",
                            key=f"btn_pdf_{task['id']}",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"PDF: {str(e)}")

    # Coluna 2: Concluído
    with cols[1]:
        st.markdown("### ✅ Concluído")
        tasks_done = get_filtered_tasks(["completed"])
        if not tasks_done:
            st.caption("_Nenhuma tarefa concluída_")
        for task in tasks_done:
            with st.container(border=True):
                st.markdown(
                    f"<div style='background-color:#e8f5e9;padding:10px;border-radius:8px;'>"
                    f"<h4 style='margin:0;color:#1a1a1a;'>{task['title']}</h4>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.markdown(f"**Status:** ✅ Concluída")

                expand_data_key = f"expand_data_done_{task['id']}"
                expand_checklist_key = f"expand_checklist_done_{task['id']}"
                if expand_data_key not in st.session_state:
                    st.session_state[expand_data_key] = False
                if expand_checklist_key not in st.session_state:
                    st.session_state[expand_checklist_key] = False

                if st.button(
                    "🔍 Ver Detalhes" if not st.session_state[expand_data_key] else "❌ Ocultar Detalhes",
                    key=f"toggle_data_done_{task['id']}",
                    use_container_width=True
                ):
                    st.session_state[expand_data_key] = not st.session_state[expand_data_key]

                if st.session_state[expand_data_key]:
                    st.markdown(f"**Especialidade:** `{task.get('specialty', '—')}`")
                    st.markdown(f"**Técnico:** {get_technician_name(task['technician_id'], techs)}")
                    st.markdown(f"**Local:** {get_location_name(task['location_id'], locs)} → {get_environment_name(task['environment_id'], load_environments())}")
                    due = task['due_date'][:16].replace('T', ' ')
                    st.markdown(f"**Agendado para:** {due}")

                checklist_data = supabase.table("checklists").select("*").eq("task_id", task["id"]).execute().data or []
                if checklist_data:
                    if st.button(
                        "📋 Ver Checklist" if not st.session_state[expand_checklist_key] else "❌ Ocultar Checklist",
                        key=f"toggle_checklist_done_{task['id']}",
                        use_container_width=True
                    ):
                        st.session_state[expand_checklist_key] = not st.session_state[expand_checklist_key]

                    if st.session_state[expand_checklist_key]:
                        st.markdown("**Checklist:**")
                        for item in checklist_data:
                            mark = "✅" if item["is_completed"] else "🔲"
                            st.markdown(f"{mark} {item['item']}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Excluir", key=f"btn_del_done_{task['id']}", use_container_width=True):
                        supabase.table("checklists").delete().eq("task_id", task["id"]).execute()
                        supabase.table("maintenance_tasks").delete().eq("id", task["id"]).execute()
                        st.rerun()
                with col2:
                    technician_name = get_technician_name(task['technician_id'], techs)
                    location_name = get_location_name(task['location_id'], locs)
                    environment_name = get_environment_name(task['environment_id'], load_environments())
                    checklist_items = [{"id": item["id"], "text": item["item"], "checked": item["is_completed"]} for item in checklist_data]
                    try:
                        pdf_bytes = generate_pdf(task, technician_name, location_name, environment_name, checklist_items)
                        st.download_button(
                            "🖨️ PDF",
                            data=pdf_bytes,
                            file_name=f"atividade_{task['id']}.pdf",
                            mime="application/pdf",
                            key=f"btn_pdf_done_{task['id']}",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"PDF: {str(e)}")