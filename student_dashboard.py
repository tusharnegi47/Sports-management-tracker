"""
agents/player_experience_agent/student_dashboard.py
Student Schedule + Join Team — Agent 4
"""

import streamlit as st
from sqlalchemy.orm import joinedload
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import Match, Tournament, Roster, Team


def render_schedule(user):
    st.markdown("# 📅 Match Schedule")
    user_id = user["id"]

    tab_schedule, tab_join = st.tabs(["📅 Schedule", "🤝 Join a Team"])

    with tab_schedule:
        db = get_db_session()
        tournaments = db.query(Tournament).filter(Tournament.status.in_(["active","upcoming"])).all()
        db.close()

        if not tournaments:
            st.info("No active tournaments scheduled yet.")
        else:
            t_opts = {t.name: t.id for t in tournaments}
            selected_t = st.selectbox("Select Tournament", list(t_opts.keys()))
            t_id = t_opts[selected_t]

            db = get_db_session()
            matches = (
                db.query(Match)
                .options(
                    joinedload(Match.team_a),
                    joinedload(Match.team_b),
                    joinedload(Match.winner),
                )
                .filter(Match.tournament_id == t_id)
                .order_by(Match.scheduled_at)
                .all()
            )
            db.close()

            if not matches:
                st.info("No matches scheduled yet.")
            else:
                for m in matches:
                    status_color = {"live": "#FF6584", "completed": "#43E97B",
                                    "scheduled": "#6C63FF", "cancelled": "#9AA0AC"}.get(m.status, "#9AA0AC")
                    scheduled = m.scheduled_at.strftime("%d %b, %H:%M") if m.scheduled_at else "TBD"
                    winner_text = f" · 🏆 {m.winner.name}" if m.winner else ""
                    st.markdown(f"""
                    <div class='score-card' style='border-left:3px solid {status_color}; padding:1rem 1.5rem; margin-bottom:0.6rem;'>
                        <div style='color:{status_color}; font-size:0.75rem; font-weight:700;'>
                            {m.status.upper()}{winner_text}
                        </div>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin:0.3rem 0;'>
                            <span style='font-weight:600;'>{m.team_a.name}</span>
                            <span style='color:#9AA0AC; font-size:0.85rem;'>{scheduled}</span>
                            <span style='font-weight:600;'>{m.team_b.name}</span>
                        </div>
                        <div style='color:#9AA0AC; font-size:0.75rem;'>📍 {m.venue or 'TBD'} &nbsp;|&nbsp; {m.round_name or ''}</div>
                    </div>
                    """, unsafe_allow_html=True)

    with tab_join:
        st.subheader("Join a Team with Code")
        with st.form("join_team_form"):
            code = st.text_input("Enter 6-character Join Code", placeholder="ABC123",
                                  max_chars=6).strip().upper()
            submitted = st.form_submit_button("🤝 Join Team", use_container_width=True)

        if submitted and code:
            from agents.player_experience_agent.join_code_service import use_join_code
            result = use_join_code(code, user_id)
            if result["success"]:
                st.success("✅ Successfully joined the team!")
                st.balloons()
            else:
                st.error(result["error"])

        # Show my teams
        st.subheader("My Teams")
        db = get_db_session()
        my_rosters = (
            db.query(Roster, Team)
            .join(Team, Roster.team_id == Team.id)
            .options(joinedload(Team.captain), joinedload(Team.sport))
            .filter(Roster.user_id == user_id, Roster.status == "active")
            .all()
        )
        db.close()

        if not my_rosters:
            st.info("You haven't joined any teams yet. Use a join code above!")
        else:
            for r, t in my_rosters:
                captain_name = t.captain.name if t.captain else "N/A"
                st.markdown(f"""
                <div class='score-card' style='padding:1rem 1.5rem; margin-bottom:0.5rem;'>
                    <div style='font-weight:700; font-size:1.1rem;'>{t.name}</div>
                    <div style='color:#9AA0AC; font-size:0.8rem;'>{t.sport.name} &nbsp;|&nbsp; Captain: {captain_name}</div>
                    <div style='color:#9AA0AC; font-size:0.8rem;'>{t.branch or ''} {t.batch or ''}</div>
                </div>
                """, unsafe_allow_html=True)
