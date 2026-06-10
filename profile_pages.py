"""
agents/player_experience_agent/profile_pages.py
Player Profile + Stats — Agent 4
"""

import streamlit as st
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import User, PlayerStats, Roster, Team, Match, Tournament


def render_profile(user):
    st.markdown("# 👤 My Profile")
    user_id = user["id"]

    db = get_db_session()
    u = db.query(User).filter(User.id == user_id).first()
    all_stats = db.query(PlayerStats).filter(PlayerStats.user_id == user_id).all()
    db.close()

    if not u:
        st.error("User not found")
        return

    # Profile header
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(f"""
        <div style='background:linear-gradient(135deg,#6C63FF,#5A52E0);
             border-radius:50%; width:90px; height:90px;
             display:flex; align-items:center; justify-content:center;
             font-size:2.5rem; font-weight:800; color:white; margin:auto;'>
            {u.name[0].upper()}
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"## {u.name}")
        st.caption(f"🎓 {u.branch or '—'} | Batch {u.batch or '—'}")
        st.caption(f"🏷️ Roll: {u.roll_number or 'N/A'}")
        st.caption(f"📧 {u.email}")

    st.divider()

    # Aggregate career stats
    total_runs = sum(s.runs_scored for s in all_stats)
    total_wkts = sum(s.wickets_taken for s in all_stats)
    total_raid = sum(s.raid_points for s in all_stats)
    total_mvp  = sum(s.mvp_score for s in all_stats)
    matches_played = len({s.match_id for s in all_stats})

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, val, label, color in [
        (c1, matches_played, "Matches", "#6C63FF"),
        (c2, total_runs, "🏏 Runs", "#43E97B"),
        (c3, total_wkts, "🎳 Wickets", "#FF6584"),
        (c4, total_raid, "🤼 Raid Pts", "#F5A623"),
        (c5, round(total_mvp, 1), "⭐ MVP Score", "#FFD700"),
    ]:
        with col:
            st.markdown(f"""<div class='metric-card'>
                <h2 style='color:{color};'>{val}</h2>
                <p>{label}</p></div>""", unsafe_allow_html=True)

    st.divider()

    # Edit profile
    with st.expander("✏️ Edit Profile"):
        with st.form("edit_profile"):
            new_name  = st.text_input("Name", value=u.name)
            new_phone = st.text_input("Phone", value=u.phone or "")
            submitted = st.form_submit_button("Save Changes")
        if submitted:
            db = get_db_session()
            db.query(User).filter(User.id == user_id).update({"name": new_name, "phone": new_phone})
            db.commit()
            db.close()
            st.success("Profile updated!")
            st.session_state["user"]["name"] = new_name
            st.rerun()

    # Match history
    st.subheader("📊 Match History")
    if not all_stats:
        st.info("No match history yet. Play some matches!")
        return

    from sqlalchemy.orm import joinedload
    db = get_db_session()
    rows = []
    for s in all_stats[-10:]:
        match = (
            db.query(Match)
            .options(joinedload(Match.team_a), joinedload(Match.team_b))
            .filter(Match.id == s.match_id)
            .first()
        )
        if not match:
            continue
        opp_team = match.team_b.name if str(s.team_id) == str(match.team_a_id) else match.team_a.name
        rows.append({
            "Opponent":  opp_team,
            "Runs":      s.runs_scored,
            "Wkts":      s.wickets_taken,
            "Raid Pts":  s.raid_points,
            "MVP":       s.mvp_score,
        })
    db.close()

    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
