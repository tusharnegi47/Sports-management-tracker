import streamlit as st
from sqlalchemy.orm import joinedload
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import Team, Tournament, Sport
from agents.player_experience_agent.join_code_service import generate_join_code, get_team_join_code
from shared.constants.sports import NIT_DELHI_BRANCHES


def render_captain_dashboard(user, roles):
    st.markdown("# ⚽ Team Management")
    user_id = user["id"]

    db  = get_db_session()
    my_teams = (
        db.query(Team)
        .options(joinedload(Team.sport), joinedload(Team.captain))
        .filter(Team.captain_id == user_id, Team.is_active == True)
        .all()
    )
    # Eagerly read all needed attributes before closing session
    teams_data = [(t.id, t.name, t.sport.name if t.sport else "?", t.sport.slug if t.sport else "", t) for t in my_teams]
    db.close()

    tab_create, tab_manage = st.tabs(["➕ Create Team", "⚙️ Manage Teams"])

    with tab_create:
        _create_team_form(user_id)

    with tab_manage:
        if not my_teams:
            st.info("You haven't created any teams yet.")
            return
        team_options = {f"{t.name} ({t.sport.name})": t for t in my_teams}
        selected = st.selectbox("Select Team", list(team_options.keys()))
        team = team_options[selected]
        _team_detail(team, user_id)


def _create_team_form(user_id):
    st.subheader("Create a New Team")
    with st.form("create_team_form"):
        col1, col2 = st.columns(2)
        with col1:
            team_name  = st.text_input("Team Name", placeholder="CSE Strikers")
            short_name = st.text_input("Short Name (max 5 chars)", placeholder="CSEST")
            branch     = st.selectbox("Branch", NIT_DELHI_BRANCHES)
        with col2:
            db = get_db_session()
            sports = db.query(Sport).filter(Sport.is_active == True).all()
            db.close()
            sport_opts = {s.name: s for s in sports}
            sport_name = st.selectbox("Sport", list(sport_opts.keys()))
            batch      = st.selectbox("Batch", ["2021","2022","2023","2024","2025"])
            jersey     = st.color_picker("Jersey Color", "#6C63FF")

        submitted = st.form_submit_button("🚀 Create Team", use_container_width=True)

    if submitted and team_name:
        try:
            db = get_db_session()
            sport = sport_opts[sport_name]
            from agents.database_agent.models import UserRole, Role
            # Grant captain role
            captain_role = db.query(Role).filter(Role.name == "captain").first()
            team = Team(
                name=team_name,
                short_name=short_name[:5] if short_name else team_name[:5].upper(),
                sport_id=sport.id,
                captain_id=user_id,
                branch=branch,
                batch=batch,
                jersey_color=jersey,
            )
            db.add(team)
            db.flush()
            if captain_role:
                db.add(UserRole(user_id=user_id, role_id=captain_role.id, context_id=team.id))
            # Add captain to roster
            from agents.database_agent.models import Roster
            db.add(Roster(team_id=team.id, user_id=user_id, status="active"))
            db.commit()

            from shared.event_bus import get_event_bus, create_event, EventType
            get_event_bus().publish(create_event(
                EventType.TEAM_CREATED, "PLAYER_EXPERIENCE_AGENT",
                team.id, {"name": team_name, "sport": sport_name}
            ))
            st.success(f"✅ Team **{team_name}** created!")
            db.close()
            st.rerun()
        except Exception as e:
            st.error(f"Failed to create team: {e}")


def _team_detail(team, user_id):
    col1, col2, col3 = st.columns(3)
    db = get_db_session()
    from agents.database_agent.models import Roster
    roster_count = db.query(Roster).filter(Roster.team_id == team.id, Roster.status == "active").count()
    db.close()

    with col1:
        st.markdown(f"""<div class='metric-card'>
            <h2 style='color:#43E97B;'>{roster_count}</h2>
            <p>Players Registered</p></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class='metric-card'>
            <h2 style='color:#6C63FF;'>{team.sport.name}</h2>
            <p>Sport</p></div>""", unsafe_allow_html=True)
    with col3:
        code = get_team_join_code(team.id)
        st.markdown(f"""<div class='metric-card'>
            <h2 style='color:#F5A623; font-size:1.6rem; letter-spacing:0.2rem;'>{code or '—'}</h2>
            <p>Join Code</p></div>""", unsafe_allow_html=True)

    st.divider()
    if st.button("🔄 Generate New Join Code", use_container_width=True):
        result = generate_join_code(team.id, user_id)
        if result["success"]:
            st.success(f"New code: **{result['code']}** (expires {result['expires_at'][:10]})")
            st.rerun()

    st.subheader("Registered Players")
    db = get_db_session()
    from agents.database_agent.models import Roster, User
    roster = (
        db.query(Roster, User)
        .join(User, Roster.user_id == User.id)
        .filter(Roster.team_id == team.id, Roster.status == "active")
        .all()
    )
    db.close()

    for r, u in roster:
        col_a, col_b, col_c = st.columns([3, 2, 1])
        with col_a:
            st.write(f"**{u.name}**")
        with col_b:
            st.caption(f"{u.branch or '—'} | {u.roll_number or '—'}")
        with col_c:
            if u.id != user_id:
                if st.button("Remove", key=f"remove_{r.id}"):
                    db = get_db_session()
                    db.query(Roster).filter(Roster.id == r.id).update({"status": "removed"})
                    db.commit()
                    db.close()
                    st.rerun()
