# app.py
import streamlit as st
from datetime import datetime

# ----------- Funções Auxiliares (ESCOPO GLOBAL) -----------
def load_technicians():
    from supabase_client import get_supabase_client
    supabase = get_supabase_client()
    res = supabase.table("technicians").select("*").execute()
    return {t["id"]: t for t in res.data} if res.data else {}

def load_locations():
    from supabase_client import get_supabase_client
    supabase = get_supabase_client()
    res = supabase.table("locations").select("*").execute()
    return {l["id"]: l["name"] for l in res.data} if res.data else {}

def load_environments_by_location(loc_id):
    from supabase_client import get_supabase_client
    supabase = get_supabase_client()
    if not loc_id:
        return {}
    res = supabase.table("environments").select("*").eq("location_id", loc_id).execute()
    return {e["id"]: e["name"] for e in res.data} if res.data else {}

def get_technician_name(tech_id, tech_dict):
    return tech_dict.get(tech_id, {}).get("name", "Não atribuído")

def get_location_name(loc_id, loc_dict):
    return loc_dict.get(loc_id, "—")

def get_specialties_list():
    from supabase_client import get_supabase_client
    supabase = get_supabase_client()
    res = supabase.table("technicians").select("specialty").execute()
    specialties = {r["specialty"] for r in res.data if r.get("specialty")}
    return sorted(specialties) if specialties else ["Refrigeração", "Elétrica", "Hidráulica", "Mecânica"]

# ----------- Login -----------
def show_login():
    from supabase_client import get_supabase_client
    supabase = get_supabase_client()
    
    st.set_page_config(page_title="🔐 Login", layout="centered")
    st.title("🔐 Login - Sistema de Manutenção")
    email = st.text_input("E-mail", key="login_email")
    password = st.text_input("Senha", type="password", key="login_password")
    if st.button("Entrar", key="login_btn"):
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            tech_res = supabase.table("technicians").select("id, role, specialty").eq("email", email).execute()
            if tech_res.data:
                tech = tech_res.data[0]
                st.session_state["user"] = {
                    "id": str(response.user.id),
                    "email": response.user.email,
                    "role": tech.get("role", "technician"),
                    "specialty": tech.get("specialty")
                }
                st.rerun()
            else:
                st.error("Usuário não encontrado na base de técnicos.")
        except Exception as e:
            st.error(f"Erro no login: {str(e)}")
    st.markdown("💡 **Primeiro acesso?** Use 'Esqueci a senha' após tentar entrar.")

# ----------- App Principal -----------
def show_main_app():
    from supabase_client import get_supabase_client
    supabase = get_supabase_client()
    
    user = st.session_state["user"]
    user_role = user["role"]
    user_specialty = user.get("specialty")

    st.set_page_config(page_title="🔧 Manutenção Preventiva", layout="wide")
    st.sidebar.title("🔧 Manutenção Preventiva")
    st.sidebar.write(f"Usuário: {user['email']}")
    st.sidebar.write(f"Função: {'Gestor' if user_role == 'manager' else 'Técnico'}")
    if user_specialty:
        st.sidebar.write(f"Especialidade: {user_specialty}")
    if st.sidebar.button("Sair", key="logout_btn"):
        supabase.auth.sign_out()
        st.session_state["user"] = None
        st.rerun()

    st.title("🔧 Sistema de Manutenção Preventiva")

    # Definir abas com base na função do usuário
    if user_role == "manager":
        tabs = st.tabs(["📋 Cadastrar Dados", "➕ Nova Manutenção", "📊 Kanban", "📁 Anexos", "⚙️ Configurações"])
        tab_cad, tab_new, tab_kanban, tab_anexos, tab_config = tabs
    else:
        tabs = st.tabs(["📊 Kanban", "📝 Minhas Atividades"])
        tab_kanban, tab_minhas = tabs

    # --- ABA: Cadastro (só gestores) ---
    if user_role == "manager":
        with tab_cad:
            st.subheader("Cadastro de Técnicos")
            with st.form("add_technician"):
                name = st.text_input("Nome do Técnico", key="tech_name")
                email = st.text_input("Email (para login)", key="tech_email")
                role = st.selectbox("Função", ["technician", "manager"], format_func=lambda x: "Técnico" if x == "technician" else "Gestor", key="tech_role")
                specialties = get_specialties_list()
                specialty = st.selectbox("Especialidade", specialties + ["Outra"], key="tech_specialty")
                if specialty == "Outra":
                    specialty = st.text_input("Nova especialidade", key="tech_specialty_new")
                if st.form_submit_button("Salvar Técnico"):
                    if name and email:
                        supabase.table("technicians").insert({
                            "name": name,
                            "email": email,
                            "role": role,
                            "specialty": specialty
                        }).execute()
                        st.success("✅ Técnico cadastrado!")
                        st.rerun()
                    else:
                        st.error("Preencha nome e e-mail.")

            st.subheader("Cadastro de Localidades")
            with st.form("add_location"):
                loc_name = st.text_input("Nome da Localidade", key="loc_name")
                if st.form_submit_button("Salvar Localidade"):
                    supabase.table("locations").insert({"name": loc_name}).execute()
                    st.success("✅ Localidade salva!")
                    st.rerun()

            st.subheader("Cadastro de Ambientes")
            locations = load_locations()
            if locations:
                loc_id = st.selectbox("Localidade", options=list(locations.keys()), format_func=lambda x: locations[x])
                with st.form("add_environment"):
                    env_name = st.text_input("Nome do Ambiente")
                    if st.form_submit_button("Salvar Ambiente"):
                        if loc_id:
                            supabase.table("environments").insert({"name": env_name, "location_id": loc_id}).execute()
                            st.success("✅ Ambiente salvo!")
                            st.rerun()
                        else:
                            st.error("Selecione uma localidade.")
            else:
                st.info("Cadastre uma localidade primeiro.")

    # --- ABA: Nova Manutenção (só gestores) ---
    if user_role == "manager":
        with tab_new:
            st.subheader("Criar Nova Manutenção Preventiva")
            techs = load_technicians()
            locs = load_locations()
            specialties = get_specialties_list()

            with st.form("new_maintenance"):
                title = st.text_input("Título da Manutenção")
                description = st.text_area("Descrição")
                specialty = st.selectbox("Especialidade", specialties + ["Outra"])
                if specialty == "Outra":
                    specialty = st.text_input("Nova especialidade")
                tech_id = st.selectbox("Atribuir a Técnico", options=[None] + list(techs.keys()), format_func=lambda x: techs[x]["name"] if x else "Nenhum")
                loc_id = st.selectbox("Localidade", options=[None] + list(locs.keys()), format_func=lambda x: locs[x] if x else "Selecione")
                envs = load_environments_by_location(loc_id)
                env_id = st.selectbox("Ambiente", options=[None] + list(envs.keys()), format_func=lambda x: envs[x] if x else "Selecione")
                due_date = st.date_input("Data de Agendamento")
                due_time = st.time_input("Hora")
                recurrence = st.selectbox("Recorrência", ["Nenhuma", "Diária", "Semanal", "Mensal"])
                checklist_input = st.text_area("Checklist (um item por linha)")
                submitted = st.form_submit_button("Criar Manutenção")
                if submitted:
                    if not title or not loc_id or not specialty:
                        st.error("Título, localidade e especialidade são obrigatórios.")
                    else:
                        due_datetime = datetime.combine(due_date, due_time)
                        status = "scheduled"
                        if due_datetime < datetime.now():
                            status = "overdue"
                        task_data = {
                            "title": title,
                            "description": description,
                            "specialty": specialty,
                            "technician_id": tech_id,
                            "location_id": loc_id,
                            "environment_id": env_id,
                            "due_date": due_datetime.isoformat(),
                            "recurrence": recurrence if recurrence != "Nenhuma" else None,
                            "status": status
                        }
                        supabase.table("maintenance_tasks").insert(task_data).execute()
                        st.success("✅ Manutenção criada!")
                        st.rerun()

    # --- ABA: Kanban (todos) ---
    with tab_kanban:
        st.subheader("Quadro Kanban – Manutenções")

        # Filtros
        all_specialties = get_specialties_list()
        selected_specialty = st.selectbox("Filtrar por Especialidade", ["Todas"] + all_specialties, key="filter_specialty")
        all_locations = load_locations()
        selected_location = st.selectbox("Filtrar por Localidade", ["Todas"] + list(all_locations.values()), key="filter_location")
        search_query = st.text_input("Buscar por título", key="search_title")

        techs = load_technicians()
        locs = load_locations()
        statuses = ["scheduled", "in_progress", "completed", "overdue"]
        status_labels = {
            "scheduled": "📅 Agendada",
            "in_progress": "🛠️ Em Execução",
            "completed": "✅ Concluída",
            "overdue": "❗ Atrasada"
        }
        cols = st.columns(len(statuses))
        for i, status in enumerate(statuses):
            with cols[i]:
                st.markdown(f"### {status_labels[status]}")
                query = supabase.table("maintenance_tasks").select("*").eq("status", status).order("due_date", desc=False)
                
                if selected_specialty != "Todas":
                    query = query.eq("specialty", selected_specialty)
                if selected_location != "Todas":
                    loc_id_by_name = {v: k for k, v in all_locations.items()}
                    loc_id = loc_id_by_name.get(selected_location)
                    if loc_id:
                        query = query.eq("location_id", loc_id)
                if user_role == "technician":
                    if user_specialty:
                        query = query.eq("specialty", user_specialty)
                    else:
                        query = query.eq("technician_id", user["id"])
                
                tasks = query.execute().data
                if search_query:
                    tasks = [t for t in tasks if search_query.lower() in t["title"].lower()]
                
                for task in tasks:
                    with st.expander(f"**{task['title']}**", expanded=False):
                        st.write(f"📍 Local: {get_location_name(task['location_id'], locs)}")
                        st.write(f"🔧 Especialidade: {task.get('specialty', '—')}")
                        st.write(f"👤 Técnico: {get_technician_name(task['technician_id'], techs)}")
                        st.write(f"📆 Vencimento: {task['due_date'][:16].replace('T', ' ')}")
                        
                        # Checklist interativo
                        checklist = supabase.table("checklists").select("*").eq("task_id", task["id"]).execute().data
                        if checklist:
                            st.write("**Checklist:**")
                            for item in checklist:
                                can_edit_check = (user_role == "manager") or (task["technician_id"] == user["id"])
                                checked = st.checkbox(
                                    item["item"],
                                    value=item["is_completed"],
                                    key=f"check_{item['id']}",
                                    disabled=not can_edit_check
                                )
                                if checked != item["is_completed"]:
                                    supabase.table("checklists").update({"is_completed": checked}).eq("id", item["id"]).execute()
                                    st.rerun()
                        
                        can_act = (user_role == "manager") or (task["technician_id"] == user["id"])
                        if can_act:
                            col_a, col_b = st.columns(2)
                            with col_a:
                                if st.button("Iniciar", key=f"start_{task['id']}", use_container_width=True):
                                    supabase.table("maintenance_tasks").update({"status": "in_progress"}).eq("id", task["id"]).execute()
                                    st.rerun()
                            with col_b:
                                if st.button("Concluir", key=f"done_{task['id']}", use_container_width=True):
                                    supabase.table("maintenance_tasks").update({"status": "completed"}).eq("id", task["id"]).execute()
                                    st.rerun()

    # --- ABA: Minhas Atividades (só técnicos) ---
    if user_role == "technician":
        with tab_minhas:
            st.subheader("📝 Minhas Atividades")
            query = supabase.table("maintenance_tasks").select("*").order("due_date", desc=False)
            if user_specialty:
                query = query.eq("specialty", user_specialty)
            else:
                query = query.eq("technician_id", user["id"])
            tasks = query.execute().data
            if tasks:
                for task in tasks:
                    status_emoji = {"scheduled": "📅", "in_progress": "🛠️", "completed": "✅", "overdue": "❗"}.get(task["status"], "❓")
                    st.markdown(f"**{status_emoji} {task['title']}**")
                    st.write(f"- Especialidade: {task.get('specialty', '—')}")
                    st.write(f"- Local: {get_location_name(task['location_id'], load_locations())}")
                    st.write(f"- Vencimento: {task['due_date'][:16].replace('T', ' ')}")
                    st.divider()
            else:
                st.info("Nenhuma atividade atribuída.")

    # --- Abas extras (só gestores) ---
    if user_role == "manager":
        with tab_anexos:
            st.write("📎 Anexar arquivos (em breve)")
        with tab_config:
            st.write("⚙️ Configurações (em breve)")

# ----------- Execução Principal -----------
if "user" not in st.session_state:
    st.session_state["user"] = None

if st.session_state["user"] is None:
    show_login()
else:
    show_main_app()