"""
agents/admin_agent/admin_dashboard.py
Admin Control Center + Analytics — Agent 2 & 5 UI
"""

import streamlit as st
from sqlalchemy.orm import joinedload
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import (
    User, Tournament, Match, Team, Sport, UserRole, Role
)
from agents.database_agent.permissions import is_admin


def render_admin_dashboard(user):
    user_id = user["id"]
    db = get_db_session()
    if not is_admin(db, user_id):
        db.close()
        st.error("⛔ Admin access required")
        return
    db.close()

    st.markdown("# ⚙️ Admin Dashboard")
    tabs = st.tabs(["🏆 Tournaments", "📅 Matches", "👥 Users & Roles", "⚡ Control Center"])

    with tabs[0]:
        _tournament_manager(user_id)
    with tabs[1]:
        _match_manager(user_id)
    with tabs[2]:
        _user_manager(user_id)
    with tabs[3]:
        _control_center(user_id)


def _tournament_manager(user_id):
    st.subheader("Create Tournament")
    with st.form("create_tournament"):
        col1, col2 = st.columns(2)
        with col1:
            name    = st.text_input("Tournament Name", placeholder="ZEAL 2025")
            db = get_db_session()
            sports = db.query(Sport).filter(Sport.is_active == True).all()
            db.close()
            sport_opts = {s.name: s for s in sports}
            sport_name = st.selectbox("Sport", list(sport_opts.keys()))
            venue   = st.text_input("Venue", placeholder="NIT Delhi Sports Ground")
        with col2:
            import datetime
            start = st.date_input("Start Date")
            end   = st.date_input("End Date")
            fmt   = st.selectbox("Format", ["round_robin", "knockout", "league"])
            overs = st.number_input("Overs (Cricket)", 5, 50, 20)

        desc      = st.text_area("Description", placeholder="Annual sports fest...")
        submitted = st.form_submit_button("🚀 Create Tournament", use_container_width=True)

    if submitted and name:
        try:
            import re, datetime as dt
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            db = get_db_session()
            sport = sport_opts[sport_name]
            t = Tournament(
                name=name, slug=slug,
                sport_id=sport.id, created_by=user_id,
                venue=venue, start_date=dt.datetime.combine(start, dt.time()),
                end_date=dt.datetime.combine(end, dt.time()),
                format=fmt, overs=overs, description=desc,
            )
            db.add(t)
            db.commit()
            tournament_id = str(t.id)  # save before session closes
            db.close()

            from shared.event_bus import get_event_bus, create_event, EventType
            get_event_bus().publish(create_event(
                EventType.TOURNAMENT_CREATED, "ADMIN_AGENT",
                tournament_id, {"name": name, "sport": sport_name}
            ))
            st.success(f"✅ Tournament **{name}** created!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()
    st.subheader("All Tournaments")
    db = get_db_session()
    tournaments = (
        db.query(Tournament)
        .options(joinedload(Tournament.sport))
        .order_by(Tournament.created_at.desc())
        .limit(20).all()
    )
    db.close()

    for t in tournaments:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"**{t.name}** — {t.sport.name}")
            st.caption(f"{t.venue or 'TBD'} | {t.format} | {t.status}")
        with col2:
            new_status = st.selectbox("Status", ["upcoming","active","completed","archived"],
                                       index=["upcoming","active","completed","archived"].index(t.status),
                                       key=f"tstatus_{t.id}", label_visibility="collapsed")
        with col3:
            if st.button("Update", key=f"tupd_{t.id}"):
                db = get_db_session()
                db.query(Tournament).filter(Tournament.id == t.id).update({"status": new_status})
                db.commit()
                db.close()
                st.rerun()


def _match_manager(user_id):
    st.subheader("Schedule a Match")
    db = get_db_session()
    tournaments = db.query(Tournament).filter(Tournament.status.in_(["upcoming","active"])).all()
    teams       = db.query(Team).filter(Team.is_active == True).all()
    users       = db.query(User).filter(User.is_active == True).all()
    db.close()

    if not tournaments:
        st.info("Create a tournament first.")
        return

    with st.form("create_match"):
        col1, col2 = st.columns(2)
        with col1:
            t_opts   = {t.name: t for t in tournaments}
            t_name   = st.selectbox("Tournament", list(t_opts.keys()))
            selected_t = t_opts[t_name]
            sport_teams = [t for t in teams if str(t.sport_id) == str(selected_t.sport_id)]
            if len(sport_teams) < 2:
                st.warning("This tournament's sport needs at least two teams before a match can be scheduled.")
            team_names = [t.name for t in sport_teams]
            team_a   = st.selectbox("Team A", team_names if team_names else ["No teams available"])
            team_b_options = [t.name for t in sport_teams if t.name != team_a]
            team_b   = st.selectbox("Team B", team_b_options if team_b_options else ["No opponent available"])
        with col2:
            venue    = st.text_input("Venue")
            round_nm = st.text_input("Round", placeholder="Group Stage / Final")
            import datetime
            sched_dt = st.date_input("Match Date")
            sched_tm = st.time_input("Match Time")
            scorer   = st.selectbox("Assign Scorer", ["— None —"] + [u.name for u in users])

        submitted = st.form_submit_button("📅 Schedule Match", use_container_width=True)

    if submitted:
        try:
            import datetime as dt
            db  = get_db_session()
            sel_t  = t_opts[t_name]
            if team_a in ("No teams available", "No opponent available") or team_b in ("No teams available", "No opponent available"):
                db.close()
                st.error("Add at least two teams for this tournament sport before scheduling a match.")
                return
            ta = next(t for t in teams if t.name == team_a and str(t.sport_id) == str(sel_t.sport_id))
            tb = next(t for t in teams if t.name == team_b and str(t.sport_id) == str(sel_t.sport_id))
            scorer_user = next((u for u in users if u.name == scorer), None) if scorer != "— None —" else None
            scheduled_at = dt.datetime.combine(sched_dt, sched_tm)
            m = Match(
                tournament_id=sel_t.id,
                team_a_id=ta.id, team_b_id=tb.id,
                sport_id=sel_t.sport_id,
                scorer_id=scorer_user.id if scorer_user else None,
                venue=venue, round_name=round_nm,
                scheduled_at=scheduled_at,
            )
            db.add(m)
            db.flush()
            match_id = str(m.id)
            db.commit()
            db.close()
            from shared.event_bus import get_event_bus, create_event, EventType
            get_event_bus().publish(create_event(
                EventType.MATCH_CREATED, "ADMIN_AGENT", match_id,
                {"team_a": team_a, "team_b": team_b, "tournament": t_name}
            ))
            st.success("✅ Match scheduled!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()
    st.subheader("All Matches")
    db = get_db_session()
    matches = (
        db.query(Match)
        .options(
            joinedload(Match.team_a),
            joinedload(Match.team_b),
            joinedload(Match.tournament),
        )
        .order_by(Match.scheduled_at.desc())
        .limit(20).all()
    )
    db.close()

    for m in matches:
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            st.write(f"**{m.team_a.name} vs {m.team_b.name}**")
            st.caption(f"{m.tournament.name} | {m.round_name or ''} | {m.status} | {m.venue or 'TBD'}")
        with col2:
            if m.status == "scheduled":
                if st.button("▶️ Start", key=f"mstart_{m.id}"):
                    from agents.scoring_agent.match_state_manager import start_match
                    start_match(m.id, user_id)
                    st.rerun()
        with col3:
            if m.status == "live":
                if st.button("⏸ Pause", key=f"mpause_{m.id}"):
                    from agents.scoring_agent.match_state_manager import pause_match
                    pause_match(m.id, user_id)
                    st.rerun()


def _user_manager(user_id):
    st.subheader("Users & Role Assignment")
    db = get_db_session()
    users = db.query(User).filter(User.is_active == True).all()
    roles_list = db.query(Role).all()
    db.close()

    search = st.text_input("Search by name / roll number")
    filtered = [u for u in users if not search or search.lower() in u.name.lower() or
                search.lower() in (u.roll_number or "").lower()]

    for u in filtered[:20]:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.write(f"**{u.name}** ({u.roll_number or 'N/A'})")
            st.caption(f"{u.branch or '—'} | {u.email}")
        with col2:
            role_names = [r.name for r in roles_list]
            new_role = st.selectbox("Assign Role", role_names, key=f"urole_{u.id}",
                                     label_visibility="collapsed")
        with col3:
            if st.button("Assign", key=f"uassign_{u.id}"):
                from agents.database_agent.permissions import assign_role
                try:
                    db = get_db_session()
                    assign_role(db, user_id, u.id, new_role)
                    db.commit()
                    db.close()
                    st.toast(f"Role '{new_role}' assigned to {u.name}")
                except Exception as e:
                    st.error(str(e))


def _control_center(user_id):
    st.subheader("⚡ Emergency Controls")
    st.warning("Use these controls carefully. Actions affect live matches.")

    db = get_db_session()
    live_matches = (
        db.query(Match)
        .options(joinedload(Match.team_a), joinedload(Match.team_b))
        .filter(Match.status == "live").all()
    )
    db.close()

    if not live_matches:
        st.info("No live matches currently.")
        return

    for m in live_matches:
        with st.expander(f"🔴 {m.team_a.name} vs {m.team_b.name}"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⏸ Pause Match", key=f"ep_{m.id}", use_container_width=True):
                    from agents.scoring_agent.match_state_manager import pause_match
                    pause_match(m.id, user_id, "Admin override")
                    st.rerun()
                result = st.text_input("Result (for override)", key=f"er_{m.id}")
                winner = st.radio("Winner", [m.team_a.name, m.team_b.name], key=f"ew_{m.id}", horizontal=True)
            with col2:
                if st.button("🏆 Force Complete", key=f"ef_{m.id}", use_container_width=True):
                    wid = str(m.team_a_id) if winner == m.team_a.name else str(m.team_b_id)
                    db = get_db_session()
                    from datetime import datetime, timezone
                    db.query(Match).filter(Match.id == m.id).update({
                        "status": "completed", "winner_id": wid,
                        "result_summary": result, "finished_at": datetime.now(timezone.utc)
                    })
                    db.commit()
                    db.close()
                    st.success("Match marked complete!")
                    st.rerun()


# ── Analytics Page ────────────────────────────────────────────────────────────

def render_analytics(user):
    st.markdown("# 📊 Analytics & Leaderboards")

    db = get_db_session()
    tournaments = (
        db.query(Tournament)
        .options(joinedload(Tournament.sport))
        .all()
    )
    db.close()

    if not tournaments:
        st.info("No tournaments yet.")
        return

    t_opts = {t.name: t for t in tournaments}
    selected = st.selectbox("Tournament", list(t_opts.keys()))
    t = t_opts[selected]

    tab1, tab2, tab3, tab4 = st.tabs(
        ["🏆 Leaderboard", "📈 Player Stats", "🏛️ Branch Standings", "⭐ MVP Rankings"]
    )

    from agents.analytics_agent.analytics_engine import (
        get_leaderboard, get_cricket_batting_stats, get_cricket_bowling_stats,
        get_kabaddi_stats, get_volleyball_stats, get_branch_standings, get_top_players
    )
    from agents.analytics_agent.charts import (
        leaderboard_chart, batting_runs_chart, bowling_wickets_chart,
        kabaddi_points_chart, volleyball_stats_chart, branch_standings_chart
    )

    with tab1:
        df = get_leaderboard(t.id)
        if df.empty:
            st.info("No leaderboard data yet.")
        else:
            st.plotly_chart(leaderboard_chart(df), use_container_width=True)
            st.dataframe(df, use_container_width=True)

    with tab2:
        sport = t.sport.slug if t.sport else "cricket"
        if sport == "cricket":
            col1, col2 = st.columns(2)
            with col1:
                bat_df = get_cricket_batting_stats(t.id)
                st.plotly_chart(batting_runs_chart(bat_df), use_container_width=True)
                if not bat_df.empty: st.dataframe(bat_df.head(15), use_container_width=True, hide_index=True)
            with col2:
                bowl_df = get_cricket_bowling_stats(t.id)
                st.plotly_chart(bowling_wickets_chart(bowl_df), use_container_width=True)
                if not bowl_df.empty: st.dataframe(bowl_df.head(15), use_container_width=True, hide_index=True)
        elif sport == "kabaddi":
            df = get_kabaddi_stats(t.id)
            st.plotly_chart(kabaddi_points_chart(df), use_container_width=True)
            if not df.empty: st.dataframe(df.head(15), use_container_width=True, hide_index=True)
        elif sport == "volleyball":
            df = get_volleyball_stats(t.id)
            st.plotly_chart(volleyball_stats_chart(df), use_container_width=True)
            if not df.empty: st.dataframe(df.head(15), use_container_width=True, hide_index=True)

    with tab3:
        branch_df = get_branch_standings(t.id)
        if branch_df.empty:
            st.info("No branch standings yet.")
        else:
            st.plotly_chart(branch_standings_chart(branch_df), use_container_width=True)
            st.dataframe(branch_df, use_container_width=True)

    with tab4:
        mvp_df = get_top_players(t.id)
        if mvp_df.empty:
            st.info("No player rankings yet.")
        else:
            st.dataframe(mvp_df, use_container_width=True)
