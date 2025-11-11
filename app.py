# app.py — Sistema de Manutenção Preventiva (com histórico, arquivamento e notificações)
import streamlit as st
from datetime import datetime, timedelta
from supabase_client import get_supabase_client
from fpdf import FPDF
import os

supabase = get_supabase_client()

if "show_new_form" not in st.session_state:
    st.session_state["show_new_form"] = False
if "show_history" not in st.session_state:
    st.session_state["show_history"] = False

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
    return {e["id"]: e["name"] for e in res.data} if res.data else {}

def load_environments_by_location(loc_id):
    if not loc_id:
        return {}
    res = supabase.table("environments").select("*").eq("location_id", loc_id).execute()
    return {e["id"]: e["name"] for e in res.data} if res.data else {}

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

def load_templates():
    res = supabase.table("templates").select("*").execute()
    return res.data if res.data else []

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

# ----------- Função: Gerar PDF (com verificação de existência de fonte) -----------
def generate_pdf(task, technician_name, location_name, environment_name, checklist_items):
    font_normal = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
    font_bold = os.path.join(os.path.dirname(__file__), "DejaVuSans-Bold.ttf")

    if not os.path.exists(font_normal):
        raise FileNotFoundError("Falta: DejaVuSans.ttf")
    if not os.path.exists(font_bold):
        raise FileNotFoundError("Falta: DejaVuSans-Bold.ttf")

    pdf = FPDF()
    pdf.add_page()
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

# ----------- Função: Mostrar notificações internas -----------
def show_notifications():
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    # Buscar tarefas próximas ou atrasadas
    res = supabase.table("maintenance_tasks").select("*").in_("status", ["scheduled", "overdue"]).execute()
    tasks = res.data or []
    late = [t for t in tasks if t["status"] == "overdue"]
    upcoming = [t for t in tasks if t["due_date"].startswith(str(tomorrow))]

    if late:
        st.warning(f"❗ {len(late)} tarefa(s) atrasada(s)")

    if upcoming:
        st.info(f"📅 {len(upcoming)} tarefa(s) agendada(s) para amanhã")

# ----------- Função: Arquivar tarefa automaticamente ao concluir -----------
def archive_task(task, checklist_items):
    try:
        supabase.table("task_history").insert({
            "task_id": task["id"],
            "title": task["title"],
            "description": task.get("description"),
            "specialty": task.get("specialty"),
            "technician_id": task.get("technician_id"),
            "location_id": task.get("location_id"),
            "environment_name": task.get("environment_id"),
            "due_date": task["due_date"],
            "completed_at": datetime.now().isoformat(),
            "checklist": [
                {"item": item["text"], "is_completed": item["is_completed"]}
                for item in checklist_items
            ],
            "recurrence": task.get("recurrence"),
            "created_from_template": task.get("is_template", False),
            "notes": ""
        }).execute()
    except Exception as e:
        st.error(f"Erro ao arquivar: {str(e)}")

# ----------- Página Principal -----------
st.set_page_config(page_title="🔧 Manutenção Preventiva", layout="wide")
st.title("🔧 Sistema de Manutenção Preventiva")

# Verificação de fontes (com debug)
base_dir = os.path.dirname(__file__)
required = ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"]
found = []
missing = []

for font in required:
    font_path = os.path.join(base_dir, font)
    if os.path.exists(font_path):
        found.append(font)
    else:
        missing.append(font)

if missing:
    st.sidebar.error(f"⚠️ Fontes ausentes: {', '.join(missing)}")
    st.sidebar.info("💡 Certifique-se de que os arquivos estão na mesma pasta do app.py")
else:
    st.sidebar.success("✅ Fontes OK")

# Mostrar notificações
show_notifications()

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
                "location_id": None,
                "environment_id": None,
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
    
    # Se veio de clonagem ou modelo, carrega os dados
    cloned = st.session_state.get("cloned_task", {})
    
    with st.form("form_new_task"):
        title = st.text_input("Título *", value=cloned.get("title", ""))
        description = st.text_area("Descrição", value=cloned.get("description", ""))
        specialties = get_specialties_list()
        specialty = st.selectbox("Especialidade *", specialties + ["Outra"], index=specialties.index(cloned.get("specialty")) if cloned.get("specialty") and cloned.get("specialty") in specialties else len(specialties))
        if specialty == "Outra":
            specialty = st.text_input("Nova especialidade", value=cloned.get("specialty", ""))

        techs = load_technicians()
        default_tech_idx = list(techs.keys()).index(cloned["technician_id"]) + 1 if cloned.get("technician_id") and cloned["technician_id"] in techs else 0
        tech_id = st.selectbox("Técnico", options=[None] + list(techs.keys()), format_func=lambda x: techs[x]["name"] if x else "—", index=default_tech_idx)

        locs = load_locations()
        default_loc_idx = list(locs.keys()).index(cloned["location_id"]) + 1 if cloned.get("location_id") and cloned["location_id"] in locs else 0
        loc_id = st.selectbox("Localidade *", options=[None] + list(locs.keys()), format_func=lambda x: locs[x] if x else "—", index=default_loc_idx)

        # 🔥 Ambiente agora é campo de texto
        environment_name = st.text_input("Nome do Ambiente", value=cloned.get("environment_id", ""), help="Digite o nome do ambiente onde a atividade será executada")

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
                    "environment_id": None,  # 🔥 Agora ambiente é salvo como texto no card, não como ID
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
                st.write(f"**Local:** {get_location_name(h['location_id'], load_locations())} → {h['environment_name']}")
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

# --------------- QUADRO KANBAN COM CHECKLIST OTIMIZADO ---------------
elif not st.session_state.get("show_history"):
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
                    st.markdown(f"**Local:** {get_location_name(task['location_id'], locs)} → {task.get('environment_id', '—')}")  # 🔥 Agora exibe nome do ambiente
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
                                "environment_id": original_task.get("environment_id"),  # 🔥 Mantém o ambiente original como texto
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

                # Botões
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
                            # 🔁 Arquivar antes de criar recorrência
                            checklist_items = [{"text": item["item"], "is_completed": item["is_completed"]} for item in checklist_data]
                            archive_task(task, checklist_items)
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
                                # 🔁 Arquivar antes de criar recorrência
                                checklist_items = [{"text": item["item"], "is_completed": item["is_completed"]} for item in current_checklist]
                                archive_task(task, checklist_items)
                                create_recurring_task(task)
                            st.session_state[edit_mode_key] = False
                            st.success("✅ Alterações salvas!")
                            st.rerun()
                    else:
                        if st.button("✏️ Editar", key=f"btn_edit_{task['id']}", use_container_width=True):
                            st.session_state[edit_mode_key] = True
                            st.rerun()

                with col3:
                    # Botão Clonar
                    if st.button("📋 Clonar", key=f"btn_clone_{task['id']}", use_container_width=True):
                        st.session_state["cloned_task"] = {
                            "title": task["title"],
                            "description": task.get("description"),
                            "specialty": task.get("specialty"),
                            "technician_id": task.get("technician_id"),
                            "location_id": None,
                            "environment_id": None,
                            "checklist_input": "\n".join([item["item"] for item in checklist_data]),
                            "recurrence": task.get("recurrence")
                        }
                        st.session_state["show_new_form"] = True
                        st.rerun()

                with col4:
                    # Botão Salvar como Modelo
                    if st.button("💾 Modelo", key=f"btn_model_{task['id']}", use_container_width=True):
                        try:
                            checklist_items = [item["item"] for item in checklist_data]
                            supabase.table("templates").insert({
                                "title": task["title"],
                                "description": task.get("description"),
                                "specialty": task.get("specialty"),
                                "technician_id": task.get("technician_id"),
                                "location_id": task.get("location_id"),
                                "environment_id": task.get("environment_id"),
                                "checklist": checklist_items,
                                "recurrence": task.get("recurrence")
                            }).execute()
                            st.success("✅ Salvo como modelo!")
                        except Exception as e:
                            st.error(f"Erro ao salvar modelo: {str(e)}")

                    # Botão PDF
                    technician_name = get_technician_name(task['technician_id'], techs)
                    location_name = get_location_name(task['location_id'], locs)
                    environment_name = task.get('environment_id', '—')  # 🔥 Agora exibe nome do ambiente
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
                    st.markdown(f"**Local:** {get_location_name(task['location_id'], locs)} → {task.get('environment_id', '—')}")  # 🔥 Exibe nome do ambiente
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

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("🗑️ Excluir", key=f"btn_del_done_{task['id']}", use_container_width=True):
                        supabase.table("checklists").delete().eq("task_id", task["id"]).execute()
                        supabase.table("maintenance_tasks").delete().eq("id", task["id"]).execute()
                        st.rerun()
                with col2:
                    # Botão Clonar
                    if st.button("📋 Clonar", key=f"btn_clone_done_{task['id']}", use_container_width=True):
                        st.session_state["cloned_task"] = {
                            "title": task["title"],
                            "description": task.get("description"),
                            "specialty": task.get("specialty"),
                            "technician_id": task.get("technician_id"),
                            "location_id": None,
                            "environment_id": None,
                            "checklist_input": "\n".join([item["item"] for item in checklist_data]),
                            "recurrence": task.get("recurrence")
                        }
                        st.session_state["show_new_form"] = True
                        st.rerun()
                with col3:
                    # Botão PDF
                    technician_name = get_technician_name(task['technician_id'], techs)
                    location_name = get_location_name(task['location_id'], locs)
                    environment_name = task.get('environment_id', '—')  # 🔥 Exibe nome do ambiente
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