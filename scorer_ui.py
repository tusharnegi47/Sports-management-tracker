"""
agents/scoring_agent/scorer_ui.py
Scorer Panel — Streamlit UI for Agent 3
Supports Cricket, Kabaddi, Volleyball scoring.
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from sqlalchemy.orm import joinedload
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import Match, Innings, LiveScore, Delivery, Roster, User
from shared.constants.sports import CRICKET_DISMISSALS, CRICKET_EXTRAS


def render_scorer_ui(user):
    st.markdown("# 🎯 Scorer Panel")
    st.caption("Only assigned scorer can update live matches.")

    db = get_db_session()
    user_id = user["id"]

    assigned_matches = (
        db.query(Match)
        .options(
            joinedload(Match.team_a),
            joinedload(Match.team_b),
            joinedload(Match.sport),
            joinedload(Match.tournament),
        )
        .filter(Match.scorer_id == user_id, Match.status.in_(["scheduled", "live", "paused"]))
        .all()
    )
    db.close()

    if not assigned_matches:
        st.info("No matches assigned to you yet. Ask admin to assign you as scorer.")
        return

    match_options = {f"{m.team_a.name} vs {m.team_b.name} [{m.status.upper()}]": m for m in assigned_matches}
    selected_label = st.selectbox("Select Match", list(match_options.keys()))
    match = match_options[selected_label]

    st.divider()
    sport = match.sport.slug if match.sport else "cricket"

    # Match Controls
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if match.status == "scheduled":
            if st.button("▶️ Start Match", use_container_width=True):
                from agents.scoring_agent.match_state_manager import start_match
                r = start_match(match.id, user_id)
                st.success("Match started!") if r["success"] else st.error(r.get("error"))
                st.rerun()
    with col2:
        if match.status == "live":
            if st.button("⏸ Pause", use_container_width=True):
                from agents.scoring_agent.match_state_manager import pause_match
                pause_match(match.id, user_id)
                st.rerun()
    with col3:
        if match.status == "paused":
            if st.button("▶️ Resume", use_container_width=True):
                from agents.scoring_agent.match_state_manager import resume_match
                resume_match(match.id, user_id)
                st.rerun()
    with col4:
        st.markdown(f"**Status:** `{match.status.upper()}`")

    if match.status not in ("live", "paused"):
        return

    st.divider()

    if sport == "cricket":
        _cricket_scorer(match, user_id)
    elif sport == "kabaddi":
        _kabaddi_scorer(match, user_id)
    elif sport == "volleyball":
        _volleyball_scorer(match, user_id)

    st_autorefresh(interval=10000, key="scorer_refresh")


# ── Cricket Scorer UI ─────────────────────────────────────────────────────────

def _cricket_scorer(match, user_id):
    from agents.scoring_agent.cricket_engine import CricketEngine
    engine = CricketEngine(match.id, user_id)

    db = get_db_session()
    innings_list = db.query(Innings).filter(Innings.match_id == match.id).order_by(Innings.innings_number).all()
    live = db.query(LiveScore).filter(LiveScore.match_id == match.id).first()
    db.close()

    # Start new innings if none exist
    if not innings_list:
        st.subheader("Playing XI and First Innings")
        team_a_name = match.team_a.name
        team_b_name = match.team_b.name
        team_a_players = _team_players(match.team_a_id, playing_only=False)
        team_b_players = _team_players(match.team_b_id, playing_only=False)
        if not team_a_players or not team_b_players:
            st.warning("Both teams need roster players before cricket scoring can start.")
            return

        col_xi_a, col_xi_b = st.columns(2)
        with col_xi_a:
            team_a_xi = st.multiselect(
                f"{team_a_name} Playing XI",
                [p["name"] for p in team_a_players],
                default=[p["name"] for p in team_a_players[:11]],
                max_selections=11,
            )
        with col_xi_b:
            team_b_xi = st.multiselect(
                f"{team_b_name} Playing XI",
                [p["name"] for p in team_b_players],
                default=[p["name"] for p in team_b_players[:11]],
                max_selections=11,
            )
        batting = st.radio("Batting First", [team_a_name, team_b_name], horizontal=True)
        if st.button("Start Innings 1", use_container_width=True):
            if len(team_a_xi) != 11 or len(team_b_xi) != 11:
                st.error("Select exactly 11 players for both teams.")
                return
            _save_playing_xi(match.team_a_id, team_a_players, team_a_xi)
            _save_playing_xi(match.team_b_id, team_b_players, team_b_xi)
            batting_id = str(match.team_a_id) if batting == team_a_name else str(match.team_b_id)
            bowling_id = str(match.team_b_id) if batting == team_a_name else str(match.team_a_id)
            r = engine.start_innings(batting_id, bowling_id, 1)
            if r["success"]: st.rerun()
        return

    current_innings = next((i for i in innings_list if not i.is_complete), None)
    if not current_innings:
        # Both innings done
        winner_col, result_col = st.columns(2)
        with winner_col:
            winner = st.radio("Winner", [match.team_a.name, match.team_b.name])
        with result_col:
                result_text = st.text_input("Result Summary", placeholder="Team A won by 24 runs")
        if st.button("🏆 Finish Match", use_container_width=True):
            winner_id = str(match.team_a_id) if winner == match.team_a.name else str(match.team_b_id)
            engine.finish_match(winner_id, result_text)
            st.success("Match finished!")
            st.rerun()
        return

    db = get_db_session()
    deliveries = (
        db.query(Delivery)
        .filter(Delivery.innings_id == current_innings.id)
        .order_by(Delivery.created_at.asc())
        .all()
    )
    db.close()

    over_num, ball_num = _next_delivery_numbers(deliveries)
    legal_balls = sum(1 for d in deliveries if d.is_valid_ball)
    current_overs = _balls_to_overs(legal_balls)
    crr = round(current_innings.runs / (legal_balls / 6), 2) if legal_balls else 0
    batting_name = _team_name(match, current_innings.batting_team_id)
    bowling_name = _team_name(match, current_innings.bowling_team_id)
    target_text = f"Target {current_innings.target}" if current_innings.target else f"{match.tournament.overs if match.tournament else 20} overs"
    dismissed_ids = _dismissed_batter_ids(deliveries)
    batting_players = [
        player for player in _team_players(current_innings.batting_team_id, playing_only=True)
        if player["id"] not in dismissed_ids
    ]
    bowling_players = _team_players(current_innings.bowling_team_id, playing_only=True)

    st.markdown("""
    <style>
    .cricket-phone {
        max-width: 430px;
        margin: 0 auto 1rem;
        border: 1px solid #2D3039;
        border-radius: 28px;
        overflow: hidden;
        background: #101318;
        box-shadow: 0 24px 70px rgba(0,0,0,0.45);
    }
    .cricket-hero {
        background:
            linear-gradient(rgba(7,9,12,0.78), rgba(7,9,12,0.88)),
            radial-gradient(circle at 50% 20%, rgba(108,99,255,0.35), transparent 45%);
        padding: 1rem 1.1rem 1.2rem;
        min-height: 245px;
    }
    .cricket-topline {
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #E8EAED;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .cricket-score {
        text-align: center;
        padding: 2.4rem 0 1.8rem;
    }
    .cricket-score-main {
        font-size: 3.2rem;
        line-height: 1;
        font-weight: 800;
        color: #F4F7FB;
    }
    .cricket-score-sub {
        color: #C8CDD6;
        font-size: 0.8rem;
        margin-top: 0.55rem;
    }
    .cricket-player-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.8rem;
        border-top: 1px solid rgba(255,255,255,0.12);
        padding-top: 0.9rem;
    }
    .cricket-player {
        color: #E8EAED;
        font-size: 0.82rem;
    }
    .cricket-player span {
        color: #9AA0AC;
        display: block;
        font-size: 0.72rem;
        margin-top: 0.15rem;
    }
    .ball-strip {
        display: flex;
        justify-content: center;
        gap: 0.55rem;
        padding: 0.8rem 0.8rem 1rem;
        background: #20242B;
    }
    .ball-chip {
        width: 2.15rem;
        height: 2.15rem;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: #F4F7FB;
        color: #101318;
        font-weight: 800;
        font-size: 0.82rem;
    }
    .ball-chip.boundary { background: #A6CE39; }
    .ball-chip.wicket { background: #FF6584; color: white; }
    .scoring-grid-note {
        max-width: 430px;
        margin: 0 auto 0.5rem;
        color: #9AA0AC;
        font-size: 0.8rem;
        text-align: center;
    }
    div[data-testid="column"] .stButton > button {
        min-height: 58px;
        border-radius: 0;
        background: #F7F8FA;
        color: #343840;
        border: 1px solid #E2E5EA;
        box-shadow: none;
        font-weight: 700;
    }
    div[data-testid="column"] .stButton > button:hover {
        background: #EDEFF3;
        color: #101318;
        transform: none;
        box-shadow: none;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="cricket-phone">
        <div class="cricket-hero">
            <div class="cricket-topline">
                <span>{batting_name}</span>
                <span>{target_text}</span>
            </div>
            <div class="cricket-score">
                <div class="cricket-score-main">{current_innings.runs}/{current_innings.wickets}</div>
                <div class="cricket-score-sub">Overs {current_overs:.1f} · CRR {crr}</div>
            </div>
            <div class="cricket-player-row">
                <div class="cricket-player">Batting<span>{batting_name}</span></div>
                <div class="cricket-player">Bowling<span>{bowling_name}</span></div>
            </div>
        </div>
        <div class="ball-strip">
            {_recent_ball_chips(deliveries)}
        </div>
    </div>
    <div class="scoring-grid-note">Next ball: {over_num}.{ball_num}</div>
    """, unsafe_allow_html=True)

    if ball_num == 1 and legal_balls > 0:
        st.info("New over: select the new bowler before recording the next ball.")
    if deliveries and deliveries[-1].is_wicket:
        st.warning("Wicket fallen: select the new batsman before recording the next ball.")

    striker_key = f"striker_{match.id}_{current_innings.id}"
    non_striker_key = f"non_striker_{match.id}_{current_innings.id}"
    bowler_key = f"bowler_{match.id}_{current_innings.id}_{over_num}"
    _ensure_batter_state(striker_key, non_striker_key, batting_players)

    col_striker, col_non_striker, col_bowler = st.columns(3)
    with col_striker:
        striker_id = _player_selectbox(
            "Batsman on strike",
            batting_players,
            key=striker_key,
        )
    with col_non_striker:
        non_striker_id = _player_selectbox(
            "Non-striker",
            batting_players,
            key=non_striker_key,
            exclude_id=striker_id,
        )
    with col_bowler:
        bowler_id = _player_selectbox(
            "Bowler",
            bowling_players,
            key=bowler_key,
        )

    dismissal = st.selectbox("Dismissal", CRICKET_DISMISSALS, label_visibility="collapsed")

    def record(runs=0, extra_type=None, extra_runs=0, is_wicket=False, dismissal_type=None):
        if not striker_id:
            st.error("Select the batsman on strike before scoring this ball.")
            return
        if not non_striker_id:
            st.error("Select the non-striker before scoring this ball.")
            return
        if striker_id == non_striker_id:
            st.error("Striker and non-striker must be different players.")
            return
        if not bowler_id:
            st.error("Select a bowler before scoring this ball.")
            return
        result = engine.record_delivery(
            innings_id=current_innings.id,
            over_number=over_num,
            ball_number=ball_num,
            runs_scored=int(runs),
            extra_type=extra_type,
            extra_runs=int(extra_runs),
            is_wicket=is_wicket,
            dismissal_type=dismissal_type,
            batter_id=striker_id,
            bowler_id=bowler_id,
        )
        if result["success"]:
            swap_key = f"pending_strike_swap_{match.id}_{current_innings.id}"
            st.session_state[swap_key] = _should_swap_strike(
                runs=int(runs),
                extra_type=extra_type,
                is_wicket=is_wicket,
                ball_num=ball_num,
            )
            st.toast(result["description"], icon="✅")
            st.rerun()
        st.error(result.get("error", "Could not record ball"))

    for row in ([0, 1, 2, "UNDO"], [3, 4, 6, "OUT"], ["WD", "NB", "BYE", "LB"]):
        cols = st.columns(4, gap="small")
        for col, item in zip(cols, row):
            with col:
                if item == "UNDO":
                    if st.button("UNDO", use_container_width=True, key="cricket_undo"):
                        engine.undo_last_delivery(current_innings.id)
                        st.toast("Last delivery undone", icon="↩️")
                        st.rerun()
                elif item == "OUT":
                    if st.button("OUT", use_container_width=True, key="cricket_out"):
                        record(is_wicket=True, dismissal_type=dismissal)
                elif item == "WD":
                    if st.button("WD", use_container_width=True, key="cricket_wd"):
                        record(extra_type="wide", extra_runs=1)
                elif item == "NB":
                    if st.button("NB", use_container_width=True, key="cricket_nb"):
                        record(extra_type="no_ball", extra_runs=1)
                elif item == "BYE":
                    if st.button("BYE", use_container_width=True, key="cricket_bye"):
                        record(extra_type="bye", extra_runs=1)
                elif item == "LB":
                    if st.button("LB", use_container_width=True, key="cricket_lb"):
                        record(extra_type="leg_bye", extra_runs=1)
                else:
                    label = f"{item}\nFOUR" if item == 4 else f"{item}\nSIX" if item == 6 else str(item)
                    if st.button(label, use_container_width=True, key=f"cricket_run_{item}"):
                        record(runs=item)

    with st.expander("More scoring options"):
        col1, col2, col3 = st.columns(3)
        with col1:
            manual_runs = st.number_input("Runs", min_value=0, max_value=6, value=0, step=1)
        with col2:
            manual_extra = st.selectbox("Extra", [""] + CRICKET_EXTRAS)
        with col3:
            manual_extra_runs = st.number_input("Extra runs", min_value=0, max_value=7, value=0, step=1)
        manual_wicket = st.checkbox("Wicket on this ball")
        if st.button("Record Custom Ball", use_container_width=True):
            record(
                runs=manual_runs,
                extra_type=manual_extra or None,
                extra_runs=manual_extra_runs,
                is_wicket=manual_wicket,
                dismissal_type=dismissal if manual_wicket else None,
            )

    if st.button("End Innings", use_container_width=True):
        engine.complete_innings(current_innings.id)
        if current_innings.innings_number == 1:
            target = current_innings.runs + 1
            engine.start_innings(
                str(current_innings.bowling_team_id),
                str(current_innings.batting_team_id),
                2, target
            )
        st.rerun()


def _next_delivery_numbers(deliveries):
    legal_balls = sum(1 for d in deliveries if d.is_valid_ball)
    return (legal_balls // 6) + 1, (legal_balls % 6) + 1


def _balls_to_overs(legal_balls):
    return float(f"{legal_balls // 6}.{legal_balls % 6}")


def _team_name(match, team_id):
    if str(team_id) == str(match.team_a_id):
        return match.team_a.name
    if str(team_id) == str(match.team_b_id):
        return match.team_b.name
    return "Team"


def _dismissed_batter_ids(deliveries):
    return {str(d.batter_id) for d in deliveries if d.is_wicket and d.batter_id}


def _team_players(team_id, playing_only=False):
    db = get_db_session()
    query = (
        db.query(User, Roster)
        .join(Roster, Roster.user_id == User.id)
        .filter(Roster.team_id == team_id, Roster.status == "active")
        .order_by(User.name.asc())
    )
    if playing_only:
        query = query.filter(Roster.is_playing_xi == True)
    rows = query.all()
    if playing_only and not rows:
        rows = (
            db.query(User, Roster)
            .join(Roster, Roster.user_id == User.id)
            .filter(Roster.team_id == team_id, Roster.status == "active")
            .order_by(User.name.asc())
            .all()
        )
    players = [{"id": str(user.id), "name": user.name} for user, _ in rows]
    db.close()
    return players


def _player_selectbox(label, players, key, exclude_id=None):
    if not players:
        st.warning(f"No players in this team roster. Add players from Roster Manager.")
        return None
    available = [player for player in players if player["id"] != exclude_id]
    if not available:
        st.warning(f"No available player for {label}.")
        return None
    options = {player["name"]: player["id"] for player in available}
    if key in st.session_state and st.session_state[key] not in options:
        st.session_state.pop(key, None)
    selected = st.selectbox(label, list(options.keys()), key=key)
    return options[selected]


def _save_playing_xi(team_id, players, selected_names):
    selected_ids = {p["id"] for p in players if p["name"] in selected_names}
    db = get_db_session()
    roster = db.query(Roster).filter(Roster.team_id == team_id, Roster.status == "active").all()
    for entry in roster:
        entry.is_playing_xi = str(entry.user_id) in selected_ids
    db.commit()
    db.close()


def _ensure_batter_state(striker_key, non_striker_key, batting_players):
    swap_key = f"pending_strike_swap_{striker_key.removeprefix('striker_')}"
    if st.session_state.pop(swap_key, False):
        current_striker = st.session_state.get(striker_key)
        current_non_striker = st.session_state.get(non_striker_key)
        if current_striker and current_non_striker:
            st.session_state[striker_key] = current_non_striker
            st.session_state[non_striker_key] = current_striker

    names_by_id = {player["id"]: player["name"] for player in batting_players}
    if striker_key not in st.session_state and batting_players:
        st.session_state[striker_key] = batting_players[0]["name"]
    if non_striker_key not in st.session_state and len(batting_players) > 1:
        st.session_state[non_striker_key] = batting_players[1]["name"]
    if striker_key in st.session_state and st.session_state[striker_key] not in names_by_id.values():
        st.session_state.pop(striker_key, None)
    if non_striker_key in st.session_state and st.session_state[non_striker_key] not in names_by_id.values():
        st.session_state.pop(non_striker_key, None)


def _should_swap_strike(runs, extra_type, is_wicket, ball_num):
    valid_ball = extra_type not in ("wide", "no_ball") if extra_type else True
    should_swap = False
    if not is_wicket and runs % 2 == 1:
        should_swap = not should_swap
    if valid_ball and ball_num == 6:
        should_swap = not should_swap
    return should_swap


def _recent_ball_chips(deliveries):
    recent = deliveries[-6:]
    if not recent:
        return "".join("<span class='ball-chip'>-</span>" for _ in range(6))

    chips = []
    for delivery in recent:
        label = _delivery_label(delivery)
        css = "ball-chip"
        if delivery.is_wicket:
            css += " wicket"
        elif delivery.runs_scored in (4, 6):
            css += " boundary"
        chips.append(f"<span class='{css}'>{label}</span>")
    while len(chips) < 6:
        chips.insert(0, "<span class='ball-chip'>-</span>")
    return "".join(chips)


def _delivery_label(delivery):
    if delivery.is_wicket:
        return "W"
    if delivery.extra_type == "wide":
        return "WD"
    if delivery.extra_type == "no_ball":
        return "NB"
    if delivery.extra_type == "bye":
        return f"B{delivery.extra_runs}"
    if delivery.extra_type == "leg_bye":
        return f"LB{delivery.extra_runs}"
    return str(delivery.runs_scored)


# ── Kabaddi Scorer UI ─────────────────────────────────────────────────────────

def _kabaddi_scorer(match, user_id):
    from agents.scoring_agent.kabaddi_engine import KabaddiEngine
    engine = KabaddiEngine(match.id, user_id)

    live_data = KabaddiEngine.get_scorecard(match.id)
    a_score = live_data.get("team_a_score", 0)
    b_score = live_data.get("team_b_score", 0)

    col1, col2, col3 = st.columns([2, 1, 2])
    with col1:
        st.markdown(f"<div class='score-card'><div class='score-header'>{match.team_a.name}</div>"
                    f"<div class='score-main' style='color:#43E97B;'>{a_score}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div style='text-align:center;padding-top:2rem;font-size:1.5rem;color:#9AA0AC;'>vs</div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='score-card'><div class='score-header'>{match.team_b.name}</div>"
                    f"<div class='score-main' style='color:#6C63FF;'>{b_score}</div></div>", unsafe_allow_html=True)

    st.subheader("Record Raid")
    with st.form("raid_form", clear_on_submit=True):
        raiding_team = st.radio("Raiding Team", [match.team_a.name, match.team_b.name], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            raid_pts   = st.number_input("Raid Points", 0, 6, 0)
            is_bonus   = st.checkbox("Bonus Point")
            is_super   = st.checkbox("Super Raid")
        with col2:
            tackled     = st.checkbox("Tackled!")
            tackle_pts  = st.number_input("Tackle Points", 0, 7, 1) if tackled else 0

        if st.form_submit_button("✅ Record Raid", use_container_width=True):
            team_id = str(match.team_a_id) if raiding_team == match.team_a.name else str(match.team_b_id)
            result = engine.record_raid(
                raiding_team_id=team_id,
                raider_id=user_id,
                raid_points=int(raid_pts),
                is_bonus=is_bonus,
                is_super_raid=is_super,
                tackled=tackled,
                tackle_points=int(tackle_pts),
            )
            if result["success"]:
                st.rerun()

    if st.button("🏆 Finish Match", use_container_width=True):
        engine.finish_match(f"{match.team_a.name} {a_score} – {b_score} {match.team_b.name}")
        st.success("Match complete!")


# ── Volleyball Scorer UI ──────────────────────────────────────────────────────

def _volleyball_scorer(match, user_id):
    from agents.scoring_agent.volleyball_engine import VolleyballEngine
    engine = VolleyballEngine(match.id, user_id)

    live_data = VolleyballEngine.get_scorecard(match.id)
    sets      = live_data.get("sets", [])
    a_sets    = live_data.get("team_a_sets", 0)
    b_sets    = live_data.get("team_b_sets", 0)
    cur_set   = live_data.get("current_set", 1)
    cur_set_obj = next((s for s in sets if s["set_number"] == cur_set), {"team_a_pts": 0, "team_b_pts": 0})

    st.markdown(f"### Set {cur_set} &nbsp; | &nbsp; {match.team_a.name} **{a_sets}–{b_sets}** {match.team_b.name} (Sets)")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(match.team_a.name, cur_set_obj["team_a_pts"])
        if st.button(f"➕ Point — {match.team_a.name}", use_container_width=True):
            engine.add_point(str(match.team_a_id))
            st.rerun()
    with col2:
        st.metric(match.team_b.name, cur_set_obj["team_b_pts"])
        if st.button(f"➕ Point — {match.team_b.name}", use_container_width=True):
            engine.add_point(str(match.team_b_id))
            st.rerun()

    if sets:
        st.subheader("Set History")
        for s in sets:
            if s.get("winner"):
                st.write(f"Set {s['set_number']}: {s['team_a_pts']}–{s['team_b_pts']} ({'Team A' if s['winner'] == str(match.team_a_id) else 'Team B'} wins)")
