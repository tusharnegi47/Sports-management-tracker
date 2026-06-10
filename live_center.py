"""
agents/player_experience_agent/live_center.py
Live Match Center — Agent 4 Streamlit page
Auto-refreshes every 10 seconds.
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from sqlalchemy.orm import joinedload
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import Match, LiveScore, Tournament, Innings, Delivery, PlayerStats, User, Team


def render_live_center(user):
    st_autorefresh(interval=10000, key="live_center_refresh")
    st.markdown("# 📺 Live Center")
    st.caption("Auto-refreshes every 10 seconds")

    db = get_db_session()

    # Filters
    col1, col2 = st.columns([3, 1])
    with col1:
        tournaments = db.query(Tournament).filter(Tournament.status == "active").all()
        t_options = {"All Active Tournaments": None}
        t_options.update({t.name: t.id for t in tournaments})
        selected_t = st.selectbox("Tournament", list(t_options.keys()))
        t_id = t_options[selected_t]

    with col2:
        sport_filter = st.selectbox("Sport", ["All", "Cricket", "Kabaddi", "Volleyball"])

    # Live matches
    q = db.query(Match).options(
        joinedload(Match.team_a),
        joinedload(Match.team_b),
        joinedload(Match.sport),
    ).filter(Match.status == "live")
    if t_id:
        q = q.filter(Match.tournament_id == t_id)
    live_matches = q.all()

    # Scheduled upcoming
    upcoming = db.query(Match).options(
        joinedload(Match.team_a),
        joinedload(Match.team_b),
        joinedload(Match.sport),
    ).filter(Match.status == "scheduled").limit(10).all()
    db.close()

    tab_live, tab_upcoming, tab_completed = st.tabs(
        [f"🔴 Live ({len(live_matches)})", "📅 Upcoming", "✅ Recent Results"]
    )

    with tab_live:
        if not live_matches:
            st.info("No live matches right now. Check the Upcoming tab!")
        for m in live_matches:
            if sport_filter != "All" and m.sport.name.lower() != sport_filter.lower():
                continue
            _live_match_card(m)
        selected_match_id = st.session_state.get("live_scorecard_match_id")
        if selected_match_id:
            st.divider()
            _render_full_scorecard(selected_match_id)

    with tab_upcoming:
        if not upcoming:
            st.info("No upcoming matches scheduled.")
        for m in upcoming:
            _upcoming_match_card(m)

    with tab_completed:
        _render_recent_results()


def _live_match_card(match):
    db = get_db_session()
    live = db.query(LiveScore).filter(LiveScore.match_id == match.id).first()
    score_data = live.score_data if live else {}
    db.close()

    sport = match.sport.slug if match.sport else "cricket"
    sport_icon = {"cricket": "🏏", "kabaddi": "🤼", "volleyball": "🏐"}.get(sport, "🏅")

    with st.container():
        st.markdown(f"""
        <div class='score-card'>
            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem;'>
                <span style='color:#9AA0AC; font-size:0.85rem;'>{sport_icon} {match.sport.name if match.sport else sport} &nbsp;|&nbsp; {match.venue or 'NIT Delhi Ground'}</span>
                <span class='badge-live'>🔴 LIVE</span>
            </div>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <div style='text-align:left;'>
                    <div style='font-size:1.3rem; font-weight:700;'>{match.team_a.name}</div>
                </div>
                <div style='text-align:center; padding:0 1rem;'>
                    {_format_live_score(sport, score_data, match)}
                </div>
                <div style='text-align:right;'>
                    <div style='font-size:1.3rem; font-weight:700;'>{match.team_b.name}</div>
                </div>
            </div>
            {f"<div style='margin-top:0.5rem; color:#9AA0AC; font-size:0.8rem;'>{score_data.get('last_event','')}</div>" if score_data.get('last_event') else ''}
        </div>
        """, unsafe_allow_html=True)
        if st.button("View full scorecard", key=f"scorecard_{match.id}", use_container_width=True):
            st.session_state["live_scorecard_match_id"] = str(match.id)
            st.rerun()


def _format_live_score(sport, score_data, match):
    if sport == "cricket":
        innings = score_data.get("innings", [])
        if not innings:
            return "<span style='color:#9AA0AC;'>Yet to bat</span>"
        parts = []
        for inn in innings:
            parts.append(f"<div style='font-size:1.8rem; font-weight:800; color:#43E97B;'>{inn['runs']}/{inn['wickets']}</div>"
                         f"<div style='font-size:0.8rem; color:#9AA0AC;'>({inn['overs']} ov)</div>")
        return "".join(parts)
    elif sport == "kabaddi":
        a = score_data.get("team_a_score", 0)
        b = score_data.get("team_b_score", 0)
        return f"<div style='font-size:2.2rem; font-weight:800;'><span style='color:#43E97B;'>{a}</span><span style='color:#9AA0AC; margin:0 0.5rem;'>–</span><span style='color:#6C63FF;'>{b}</span></div>"
    elif sport == "volleyball":
        a_sets = score_data.get("team_a_sets", 0)
        b_sets = score_data.get("team_b_sets", 0)
        sets = score_data.get("sets", [])
        cur = next((s for s in sets if s.get("winner") is None), {})
        return (f"<div style='font-size:1.5rem; font-weight:800;'>{a_sets}–{b_sets}</div>"
                f"<div style='font-size:0.8rem; color:#9AA0AC;'>Sets | Current: {cur.get('team_a_pts',0)}–{cur.get('team_b_pts',0)}</div>")
    return "–"


def _upcoming_match_card(match):
    sport_icon = {"cricket": "🏏", "kabaddi": "🤼", "volleyball": "🏐"}.get(
        match.sport.slug if match.sport else "", "🏅"
    )
    scheduled = match.scheduled_at.strftime("%d %b %Y, %H:%M") if match.scheduled_at else "TBD"
    st.markdown(f"""
    <div class='score-card' style='border-left: 3px solid #6C63FF;'>
        <div style='color:#9AA0AC; font-size:0.8rem; margin-bottom:0.5rem;'>
            {sport_icon} {match.sport.name if match.sport else ''} &nbsp;|&nbsp; 📅 {scheduled} &nbsp;|&nbsp; 📍 {match.venue or 'TBD'}
        </div>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <span style='font-size:1.1rem; font-weight:600;'>{match.team_a.name}</span>
            <span style='color:#9AA0AC;'>vs</span>
            <span style='font-size:1.1rem; font-weight:600;'>{match.team_b.name}</span>
        </div>
        <div style='color:#9AA0AC; font-size:0.75rem; margin-top:0.3rem;'>{match.round_name or ''}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_recent_results():
    db = get_db_session()
    completed = (
        db.query(Match)
        .options(
            joinedload(Match.team_a),
            joinedload(Match.team_b),
            joinedload(Match.winner),
        )
        .filter(Match.status == "completed")
        .order_by(Match.finished_at.desc())
        .limit(10).all()
    )
    db.close()
    if not completed:
        st.info("No completed matches yet.")
        return
    for m in completed:
        winner_name = m.winner.name if m.winner else "Draw"
        st.markdown(f"""
        <div class='score-card' style='border-left: 3px solid #43E97B;'>
            <div style='color:#43E97B; font-size:0.8rem;'>✅ COMPLETED</div>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <span style='font-size:1.1rem; font-weight:600;'>{m.team_a.name}</span>
                <span style='color:#9AA0AC;'>vs</span>
                <span style='font-size:1.1rem; font-weight:600;'>{m.team_b.name}</span>
            </div>
            <div style='color:#FFD700; font-size:0.85rem; margin-top:0.3rem;'>🏆 {winner_name} wins &nbsp;|&nbsp; {m.result_summary or ''}</div>
        </div>
        """, unsafe_allow_html=True)


def _render_full_scorecard(match_id):
    db = get_db_session()
    match = (
        db.query(Match)
        .options(joinedload(Match.team_a), joinedload(Match.team_b), joinedload(Match.sport))
        .filter(Match.id == match_id)
        .first()
    )
    if not match:
        db.close()
        return
    match_title = f"{match.team_a.name} vs {match.team_b.name}"
    team_a_id = str(match.team_a_id)
    team_a_name = match.team_a.name
    team_b_name = match.team_b.name

    innings = (
        db.query(Innings)
        .filter(Innings.match_id == match_id)
        .order_by(Innings.innings_number)
        .all()
    )
    stats = (
        db.query(PlayerStats, User.name, Team.name.label("team_name"))
        .join(User, PlayerStats.user_id == User.id)
        .join(Team, PlayerStats.team_id == Team.id)
        .filter(PlayerStats.match_id == match_id)
        .all()
    )
    events = (
        db.query(Delivery, User.name.label("batter"), User.email)
        .outerjoin(User, Delivery.batter_id == User.id)
        .join(Innings, Delivery.innings_id == Innings.id)
        .filter(Innings.match_id == match_id)
        .order_by(Delivery.created_at.desc())
        .limit(30)
        .all()
    )
    innings_rows = [
        {
            "batting": team_a_name if str(inn.batting_team_id) == team_a_id else team_b_name,
            "runs": inn.runs,
            "wickets": inn.wickets,
            "overs": inn.overs_played,
            "target": inn.target,
            "extras": inn.extras or {},
        }
        for inn in innings
    ]
    batting_rows = []
    bowling_rows = []
    for ps, player_name, team_name in stats:
        if ps.runs_scored or ps.balls_faced or not ps.is_not_out:
            batting_rows.append({
                "Batter": player_name,
                "Team": team_name,
                "R": ps.runs_scored,
                "B": ps.balls_faced,
                "4s": ps.fours,
                "6s": ps.sixes,
                "SR": round((ps.runs_scored / ps.balls_faced) * 100, 1) if ps.balls_faced else 0,
                "Out": "" if ps.is_not_out else "out",
            })
        if ps.overs_bowled or ps.wickets_taken:
            bowling_rows.append({
                "Bowler": player_name,
                "Team": team_name,
                "O": ps.overs_bowled,
                "R": ps.runs_given,
                "W": ps.wickets_taken,
                "Econ": round(ps.runs_given / ps.overs_bowled, 1) if ps.overs_bowled else 0,
            })
    event_rows = [
        {
            "Over": f"{delivery.over_number}.{delivery.ball_number}",
            "Batter": batter or "-",
            "Runs": delivery.runs_scored,
            "Extra": delivery.extra_type or "",
            "Extra Runs": delivery.extra_runs,
            "Wicket": "Yes" if delivery.is_wicket else "",
            "Dismissal": delivery.dismissal_type or "",
        }
        for delivery, batter, _ in events
    ]
    db.close()

    st.subheader(match_title)
    if st.button("Close scorecard", key=f"close_scorecard_{match_id}"):
        st.session_state.pop("live_scorecard_match_id", None)
        st.rerun()

    for inn in innings_rows:
        st.markdown(f"### {inn['batting']} - {inn['runs']}/{inn['wickets']} ({inn['overs']:.1f} ov)")
        if inn["target"]:
            st.caption(f"Target: {inn['target']}")
        st.caption(f"Extras: {inn['extras']}")

    if batting_rows or bowling_rows:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Batting")
            st.dataframe(batting_rows, use_container_width=True, hide_index=True)
        with col2:
            st.markdown("#### Bowling")
            st.dataframe(bowling_rows, use_container_width=True, hide_index=True)

    if event_rows:
        st.markdown("#### Recent Balls")
        st.dataframe(event_rows, use_container_width=True, hide_index=True)
