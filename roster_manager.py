"""
agents/player_experience_agent/roster_manager.py
Roster Management UI — Agent 4
"""

import uuid
import streamlit as st
from sqlalchemy.orm import joinedload
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import Team, Roster, User, Tournament, TournamentTeam, Role, UserRole
from agents.database_agent.auth import hash_password


def render_roster_manager(user, roles):
    st.markdown("# 📝 Roster Manager")
    user_id = user["id"]

    db = get_db_session()
    if "admin" in roles:
        teams = db.query(Team).options(joinedload(Team.sport)).filter(Team.is_active == True).all()
    else:
        teams = db.query(Team).options(joinedload(Team.sport)).filter(Team.captain_id == user_id, Team.is_active == True).all()
    db.close()

    if not teams:
        st.info("No teams available to manage.")
        return

    team_opts = {f"{t.name} ({t.sport.name})": t for t in teams}
    selected  = st.selectbox("Select Team", list(team_opts.keys()))
    team      = team_opts[selected]

    tab_roster, tab_register = st.tabs(["👥 Current Roster", "🏆 Register for Tournament"])

    with tab_roster:
        db = get_db_session()
        roster = (
            db.query(Roster, User)
            .join(User, Roster.user_id == User.id)
            .filter(Roster.team_id == team.id)
            .all()
        )
        db.close()

        st.markdown(f"**{len(roster)} players** | Max: {_roster_limit(team.sport.slug if team.sport else 'cricket')}")
        st.divider()

        with st.expander("Add player to this team"):
            with st.form(f"add_guest_player_{team.id}"):
                name = st.text_input("Player Name")
                email = st.text_input("Email (optional)", placeholder="player@example.com")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    branch = st.text_input("Branch / College (optional)")
                with col_b:
                    jersey_number = st.number_input("Jersey", 1, 99, value=1)
                with col_c:
                    is_playing = st.checkbox("Playing XI")
                submitted = st.form_submit_button("Add Player", use_container_width=True)

            if submitted:
                result = _add_player_to_team(
                    team_id=team.id,
                    name=name,
                    email=email,
                    branch=branch,
                    jersey_number=int(jersey_number),
                    is_playing=is_playing,
                )
                if result["success"]:
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.error(result["error"])

        for r, u in roster:
            cols = st.columns([3, 2, 1, 1, 1])
            with cols[0]:
                st.write(f"**{u.name}**")
            with cols[1]:
                st.caption(f"{u.branch or '—'} | {u.roll_number or '—'}")
            with cols[2]:
                jersey = st.number_input("Jersey", 1, 99,
                    value=r.jersey_number or 1, key=f"j_{r.id}", label_visibility="collapsed")
            with cols[3]:
                playing = st.checkbox("XI", value=r.is_playing_xi, key=f"xi_{r.id}")
            with cols[4]:
                if st.button("💾", key=f"save_{r.id}"):
                    db2 = get_db_session()
                    db2.query(Roster).filter(Roster.id == r.id).update({
                        "jersey_number": jersey, "is_playing_xi": playing
                    })
                    db2.commit()
                    db2.close()
                    st.toast("Saved!", icon="✅")

    with tab_register:
        st.subheader(f"Register {team.name} in a Tournament")
        db = get_db_session()
        from agents.database_agent.models import Sport
        tournaments = (
            db.query(Tournament)
            .filter(Tournament.status.in_(["upcoming", "active"]), Tournament.sport_id == team.sport_id)
            .all()
        )
        already_in = [str(tt.tournament_id) for tt in
                      db.query(TournamentTeam).filter(TournamentTeam.team_id == team.id).all()]
        db.close()

        available = [t for t in tournaments if str(t.id) not in already_in]
        if not available:
            st.info("No available tournaments for this sport, or already registered in all.")
        else:
            t_opts = {t.name: t for t in available}
            t_name = st.selectbox("Tournament", list(t_opts.keys()))
            if st.button("✅ Register Team", use_container_width=True):
                db = get_db_session()
                db.add(TournamentTeam(tournament_id=t_opts[t_name].id, team_id=team.id))
                db.commit()
                db.close()
                st.success(f"Registered in **{t_name}**!")


def _roster_limit(sport_slug):
    return {"cricket": 15, "kabaddi": 11, "volleyball": 10}.get(sport_slug, 15)


def _add_player_to_team(team_id, name, email="", branch="", jersey_number=None, is_playing=False):
    name = (name or "").strip()
    email = (email or "").strip().lower()
    branch = (branch or "").strip() or None

    if not name:
        return {"success": False, "error": "Player name is required"}

    db = get_db_session()
    try:
        team = db.query(Team).options(joinedload(Team.sport)).filter(Team.id == team_id).first()
        if not team:
            return {"success": False, "error": "Team not found"}

        limit = _roster_limit(team.sport.slug if team.sport else "cricket")
        active_count = db.query(Roster).filter(Roster.team_id == team_id, Roster.status == "active").count()
        if active_count >= limit:
            return {"success": False, "error": f"Team is full ({limit} players maximum)"}

        user = db.query(User).filter(User.email == email).first() if email else None
        if not user:
            user = User(
                email=email or f"guest-{uuid.uuid4().hex[:12]}@external.players",
                name=name,
                branch=branch,
                password_hash=hash_password(uuid.uuid4().hex),
                is_verified=True,
            )
            db.add(user)
            db.flush()
            student_role = db.query(Role).filter(Role.name == "student").first()
            if student_role:
                db.add(UserRole(user_id=user.id, role_id=student_role.id))

        existing = db.query(Roster).filter(Roster.team_id == team_id, Roster.user_id == user.id).first()
        if existing and existing.status == "active":
            return {"success": False, "error": "This player is already in the team"}
        if existing:
            existing.status = "active"
            existing.jersey_number = jersey_number
            existing.is_playing_xi = is_playing
        else:
            db.add(Roster(
                team_id=team_id,
                user_id=user.id,
                jersey_number=jersey_number,
                is_playing_xi=is_playing,
                status="active",
            ))

        db.commit()
        return {"success": True, "message": f"{name} added to {team.name}"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
