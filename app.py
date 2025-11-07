# app.py
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase_client import get_supabase_client

import streamlit as st
from datetime import datetime
from supabase_client import get_supabase_client

# Page config (uma vez)
st.set_page_config(page_title="🔧 Sistema de Manutenção", layout="wide")

# Global supabase client (reutilizável)
supabase = get_supabase_client()

# ----------- Funções Auxiliares (ESCOPO GLOBAL) -----------
def load_technicians():
    sup = get_supabase_client()
    res = sup.table("technicians").select("*").execute()
    return {t["id"]: t for t in (res.data or [])}

def load_locations():
    sup = get_supabase_client()
    res = sup.table("locations").select("*").execute()
    return {l["id"]: l["name"] for l in (res.data or [])}

def load_environments_by_location(loc_id):
    if not loc_id:
        return {}
    sup = get_supabase_client()
    res = sup.table("environments").select("*").eq("location_id", loc_id).execute()
    return {e["id"]: e["name"] for e in (res.data or [])}

def get_technician_name(tech_id, tech_dict):
    return tech_dict.get(tech_id, {}).get("name", "Não atribuído")

def get_location_name(loc_id, loc_dict):
    return loc_dict.get(loc_id, "—")

def get_specialties_list():
    sup = get_supabase_client()
    res = sup.table("technicians").select("specialty").execute()
    specialties = {r.get("specialty") for r in (res.data or []) if r.get("specialty")}
    return sorted(specialties) if specialties else ["Refrigeração", "Elétrica", "Hidráulica", "Mecânica"]

# ----------- Login -----------
def show_login():
    sup = get_supabase_client()
    st.title("🔐 Login - Sistema de Manutenção")
    email = st.text_input("E-mail", key="login_email")
    password = st.text_input("Senha", type="password", key="login_password")
    if st.button("Entrar", key="login_btn"):
        try:
            response = sup.auth.sign_in_with_password({"email": email, "password": password})
            # se login bem sucedido, buscar dados do técnico
            tech_res = sup.table("technicians").select("id, role, specialty").eq("email", email).execute()
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
            st.error(f"Erro no login: {e}")
    st.markdown("💡 **Primeiro acesso?** Use 'Esqueci a senha' após tentar entrar.")

# ----------- App Principal -----------
def show_main_app():
    sup = get_supabase_client()

    user = st.session_state["user"]
    user_role = user["role"]
    user_specialty = user.get("specialty")

    # Sidebar
    st.sidebar.title("🔧 Manutenção Preventiva")
    st.sidebar.write(f"Usuário: {user['email']}")
    st.sidebar.write(f"Função: {'Gestor' if user_role == 'manager' else 'Técnico'}")
    if user_specialty:
        st.sidebar.write(f"Especialidade: {user_specialty}")
    if st.sidebar.button("Sair", key="logout_btn"):
        sup.auth.sign_out()
        st.session_state["user"] = None
        st.rerun()

    st.title("🔧 Sistema de Manutenção Preventiva")

    # Abas
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
                        sup.table("technicians").insert({
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
                    sup.table("locations").insert({"name": loc_name}).execute()
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
                            sup.table("environments").insert({"name": env_name, "location_id": loc_id}).execute()
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
                        # Inserir a tarefa
                        res = sup.table("maintenance_tasks").insert(task_data).execute()
                        # Se vier checklist_input, inserir itens na tabela checklists
                        if checklist_input:
                            lines = [l.strip() for l in checklist_input.splitlines() if l.strip()]
                            # obter id da task inserida (res.data)
                            inserted_task = res.data[0] if res.data else None
                            task_id = inserted_task.get("id") if inserted_task else None
                            if task_id:
                                for line in lines:
                                    sup.table("checklists").insert({
                                        "task_id": task_id,
                                        "item": line,
                                        "checked": False,
                                        "is_completed": False
                                    }).execute()
                        st.success("✅ Manutenção criada!")
                        st.rerun()

    # --- ABA: Kanban (todos) ---
    with tab_kanban:
        st.subheader("Quadro Kanban – Manutenções (arraste para atualizar futuramente)")

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
        # Para cada coluna/estatus, buscamos as tasks daquele status
        for i, status in enumerate(statuses):
            with cols[i]:
                st.markdown(f"### {status_labels[status]}")
                # Monta query
                try:
                    query = sup.table("maintenance_tasks").select("*").eq("status", status).order("due_date", desc=False)
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
                    tasks = query.execute().data or []
                except Exception as e:
                    st.error(f"Erro ao consultar tarefas: {e}")
                    tasks = []

                # filtro por busca
                if search_query:
                    tasks = [t for t in tasks if search_query.lower() in (t.get("title") or "").lower()]

                # Renderiza tarefas dessa coluna
                for task in tasks:
                    # Cada tarefa dentro de um expander
                    with st.expander(f"**{task.get('title', 'Sem título')}**", expanded=False):
                        st.write(f"📍 Local: {get_location_name(task.get('location_id'), locs)}")
                        st.write(f"🔧 Especialidade: {task.get('specialty', '—')}")
                        st.write(f"👤 Técnico: {get_technician_name(task.get('technician_id'), techs)}")
                        due = task.get("due_date")
                        if due:
                            st.write(f"📆 Vencimento: {due[:16].replace('T', ' ')}")

                        # --------- Checklist: carregar e renderizar (salva automaticamente) ---------
                        task_id = task.get("id") or task.get("task_id")
                        if not task_id:
                            st.info("Tarefa sem ID válida.")
                        else:
                            # buscar checklist desta task (tabela: checklists)
                            try:
                                checklist_query = sup.table("checklists").select("*").eq("task_id", task_id).order("id", desc=False).execute()
                                checklist = checklist_query.data or []
                            except Exception as e:
                                st.error(f"Erro ao carregar checklist: {e}")
                                checklist = []

                            # Conta concluídos para progresso/auto status
                            completed_count = sum(1 for it in checklist if (it.get("checked") is True or it.get("is_completed") is True))
                            total_items = len(checklist)

                            # Mostrar progresso simples
                            if total_items > 0:
                                pct = int((completed_count / total_items) * 100)
                                st.progress(pct)

                            # Renderizar cada item com chave única: task + item id
                            for it in checklist:
                                item_id = it["id"]
                                item_name = it.get("item") or "Item sem nome"
                                checked_state = True if (it.get("checked") is True or it.get("is_completed") is True) else False

                                checkbox_key = f"check_{task_id}_{item_id}"

                                # Checkbox — detecta alteração e salva imediatamente
                                checked = st.checkbox(item_name, value=checked_state, key=checkbox_key)

                                # Se mudou, atualiza DB
                                if checked != checked_state:
                                    try:
                                        sup.table("checklists").update({"checked": checked, "is_completed": checked}).eq("id", item_id).execute()
                                    except Exception as e:
                                        st.error(f"Erro ao salvar checklist: {e}")
                                    else:
                                        # Atualiza contagem local e força rerun para refletir mudança
                                        st.rerun()

                            # Auto-update do status da task (se todos marcados -> completed; se algum marcado -> in_progress)
                            # Rebuscar para garantia de consistência
                            try:
                                checklist_latest = sup.table("checklists").select("*").eq("task_id", task_id).execute().data or []
                            except Exception:
                                checklist_latest = checklist

                            completed_latest = sum(1 for it in checklist_latest if (it.get("checked") is True or it.get("is_completed") is True))
                            total_latest = len(checklist_latest)

                            # determinar novo status
                            new_status = task.get("status")
                            if total_latest > 0 and completed_latest == total_latest:
                                new_status = "completed"
                            else:
                                # se algum marcado mas não todos -> in_progress; se nenhum marcado -> keep scheduled or overdue
                                if completed_latest > 0:
                                    # prefer in_progress only if task wasn't completed already
                                    if task.get("status") != "completed":
                                        new_status = "in_progress"
                                # else leave as-is

                            if new_status != task.get("status"):
                                try:
                                    sup.table("maintenance_tasks").update({"status": new_status}).eq("id", task_id).execute()
                                    # re-run so the task migrates to the right column
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao atualizar status da tarefa: {e}")

                        # --- edição/exclusão (visível para quem pode) ---
                        can_edit = (user_role == "manager") or (task.get("technician_id") == user["id"])
                        if can_edit:
                            col_edit, col_delete = st.columns(2)
                            with col_edit:
                                if st.button("✏️ Editar", key=f"edit_{task['id']}", use_container_width=True):
                                    st.session_state["editing_task"] = task
                                    st.session_state["show_edit_form"] = True
                                    st.rerun()
                            with col_delete:
                                if st.button("🗑️ Excluir", key=f"delete_{task['id']}", use_container_width=True):
                                    st.session_state["deleting_task"] = task["id"]
                                    st.rerun()

                    # Confirmação de exclusão (fora do expander para não repetir)
                    if st.session_state.get("deleting_task") == task.get("id"):
                        st.warning("Tem certeza que deseja excluir esta manutenção?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("Sim, excluir", key=f"confirm_delete_{task['id']}"):
                                try:
                                    sup.table("maintenance_tasks").delete().eq("id", task.get("id")).execute()
                                except Exception as e:
                                    st.error(f"Erro ao excluir: {e}")
                                else:
                                    st.session_state["deleting_task"] = None
                                    st.rerun()
                        with col_no:
                            if st.button("Cancelar", key=f"cancel_delete_{task['id']}"):
                                st.session_state["deleting_task"] = None
                                st.rerun()

    # --- ABA: Minhas Atividades (só técnicos) ---
    if user_role == "technician":
        with tab_minhas:
            st.subheader("📝 Minhas Atividades")
            try:
                query = sup.table("maintenance_tasks").select("*").order("due_date", desc=False)
                if user_specialty:
                    query = query.eq("specialty", user_specialty)
                else:
                    query = query.eq("technician_id", user["id"])
                tasks = query.execute().data or []
            except Exception as e:
                st.error(f"Erro ao buscar atividades: {e}")
                tasks = []

            if tasks:
                for task in tasks:
                    status_emoji = {"scheduled": "📅", "in_progress": "🛠️", "completed": "✅", "overdue": "❗"}.get(task.get("status"), "❓")
                    st.markdown(f"**{status_emoji} {task.get('title','Sem título')}**")
                    st.write(f"- Especialidade: {task.get('specialty','—')}")
                    st.write(f"- Local: {get_location_name(task.get('location_id'), load_locations())}")
                    due = task.get("due_date")
                    if due:
                        st.write(f"- Vencimento: {due[:16].replace('T',' ')}")
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

# --- Formulário de Edição (fora das abas) ---
if st.session_state.get("show_edit_form"):
    st.markdown("### ✏️ Editar Manutenção")
    task = st.session_state["editing_task"]
    sup = get_supabase_client()
    techs = load_technicians()
    locs = load_locations()
    specialties = get_specialties_list()

    with st.form("edit_maintenance"):
        title = st.text_input("Título", value=task.get("title"))
        description = st.text_area("Descrição", value=task.get("description") or "")
        specialty = st.selectbox("Especialidade", specialties, 
                                index=specialties.index(task.get("specialty")) if task.get("specialty") in specialties else 0)
        tech_id = st.selectbox("Técnico", options=[None] + list(techs.keys()),
                               format_func=lambda x: techs[x]["name"] if x else "Nenhum",
                               index=(list(techs.keys()).index(task.get("technician_id")) + 1) if task.get("technician_id") in techs else 0)
        loc_id = st.selectbox("Localidade", options=[None] + list(locs.keys()),
                              format_func=lambda x: locs[x] if x else "Selecione",
                              index=(list(locs.keys()).index(task.get("location_id")) + 1) if task.get("location_id") in locs else 0)
        envs = load_environments_by_location(loc_id)
        env_id = st.selectbox("Ambiente", options=[None] + list(envs.keys()),
                              format_func=lambda x: envs[x] if x else "Selecione",
                              index=(list(envs.keys()).index(task.get("environment_id")) + 1) if task.get("environment_id") in envs else 0)
        due_date = st.date_input("Data", value=datetime.fromisoformat(task.get("due_date")[:10]) if task.get("due_date") else datetime.now())
        due_time = st.time_input("Hora", value=datetime.fromisoformat(task.get("due_date")[:19]).time() if task.get("due_date") else datetime.now().time())
        status = st.selectbox("Status", ["scheduled", "in_progress", "completed", "overdue"],
                              index=["scheduled", "in_progress", "completed", "overdue"].index(task.get("status")) if task.get("status") in ["scheduled","in_progress","completed","overdue"] else 0)

        if st.form_submit_button("Salvar Alterações"):
            due_datetime = datetime.combine(due_date, due_time)
            sup.table("maintenance_tasks").update({
                "title": title,
                "description": description,
                "specialty": specialty,
                "technician_id": tech_id,
                "location_id": loc_id,
                "environment_id": env_id,
                "due_date": due_datetime.isoformat(),
                "status": status
            }).eq("id", task.get("id")).execute()
            st.success("✅ Atualizado com sucesso!")
            st.session_state["show_edit_form"] = False
            st.rerun()
    
    if st.button("Cancelar"):
        st.session_state["show_edit_form"] = False
        st.rerun()
