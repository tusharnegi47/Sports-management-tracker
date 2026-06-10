"""
agents/analytics_agent/rankings.py
Player Rankings Engine — Agent 5

Computes tournament-wide player rankings across all sports.
"""

from typing import List, Dict, Optional
import pandas as pd

from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import PlayerStats, User, Team, Match
from shared.logging.logger import get_analytics_logger

logger = get_analytics_logger()


def get_tournament_rankings(tournament_id: str, sport_slug: str = "cricket") -> pd.DataFrame:
    """
    Returns ranked players for a tournament by sport.
    Cricket: ranked by runs + wickets composite.
    Kabaddi: ranked by total points.
    Volleyball: ranked by aces + kills + blocks.
    """
    db = get_db_session()
    rows = (
        db.query(PlayerStats, User.name, User.branch, User.roll_number, Team.name.label("team_name"))
        .join(User, PlayerStats.user_id == User.id)
        .join(Team, PlayerStats.team_id == Team.id)
        .filter(PlayerStats.tournament_id == tournament_id)
        .all()
    )

    if not rows:
        db.close()
        return pd.DataFrame()

    # Aggregate per player — still inside open session
    player_map: Dict[str, Dict] = {}
    for ps, name, branch, roll, team_name in rows:
        uid = str(ps.user_id)
        if uid not in player_map:
            player_map[uid] = {
                "Player": name, "Roll": roll or "—",
                "Branch": branch or "—", "Team": team_name,
                "Runs": 0, "Balls": 0, "Wickets": 0, "Overs": 0.0,
                "Catches": 0, "Fours": 0, "Sixes": 0,
                "Raid Pts": 0, "Tackle Pts": 0, "Bonus Pts": 0,
                "Aces": 0, "Kills": 0, "Blocks": 0,
                "MVP Score": 0.0, "Matches": 0,
            }
        p = player_map[uid]
        p["Matches"]    += 1
        p["Runs"]       += ps.runs_scored
        p["Balls"]      += ps.balls_faced
        p["Wickets"]    += ps.wickets_taken
        p["Overs"]      += ps.overs_bowled
        p["Catches"]    += ps.catches
        p["Fours"]      += ps.fours
        p["Sixes"]      += ps.sixes
        p["Raid Pts"]   += ps.raid_points
        p["Tackle Pts"] += ps.tackle_points
        p["Bonus Pts"]  += ps.bonus_points
        p["Aces"]       += ps.aces
        p["Kills"]      += ps.kills
        p["Blocks"]     += ps.blocks
        p["MVP Score"]  += ps.mvp_score
    db.close()

    data = list(player_map.values())

    if sport_slug == "cricket":
        for p in data:
            p["SR"]  = round((p["Runs"] / p["Balls"]) * 100, 1) if p["Balls"] else 0
            p["Avg"] = round(p["Runs"] / max(p["Matches"], 1), 1)
            p["Eco"] = round(p["Runs"] / p["Overs"], 1) if p["Overs"] else 0
        sort_key = "Runs"
    elif sport_slug == "kabaddi":
        for p in data:
            p["Total"] = p["Raid Pts"] + p["Tackle Pts"] + p["Bonus Pts"]
        sort_key = "Total"
    else:  # volleyball
        for p in data:
            p["Total"] = p["Aces"] + p["Kills"] + p["Blocks"]
        sort_key = "Total"

    df = pd.DataFrame(data).sort_values("MVP Score", ascending=False).reset_index(drop=True)
    df.index = range(1, len(df) + 1)
    return df


def get_most_valuable_players(tournament_id: str, top_n: int = 5) -> List[Dict]:
    """Return top N MVP players across all sports for a tournament."""
    db = get_db_session()
    rows = (
        db.query(PlayerStats, User.name, User.branch, Team.name.label("team_name"))
        .join(User, PlayerStats.user_id == User.id)
        .join(Team, PlayerStats.team_id == Team.id)
        .filter(PlayerStats.tournament_id == tournament_id)
        .all()
    )

    player_mvp: Dict[str, Dict] = {}
    for ps, name, branch, team_name in rows:
        uid = str(ps.user_id)
        if uid not in player_mvp:
            player_mvp[uid] = {"name": name, "branch": branch or "—",
                                "team": team_name, "mvp": 0.0}
        player_mvp[uid]["mvp"] += ps.mvp_score
    db.close()

    sorted_players = sorted(player_mvp.values(), key=lambda x: x["mvp"], reverse=True)
    return sorted_players[:top_n]


def get_player_career_stats(user_id: str) -> Dict:
    """Aggregated career stats for a player across all tournaments."""
    db = get_db_session()
    all_stats = db.query(PlayerStats).filter(PlayerStats.user_id == user_id).all()

    if not all_stats:
        db.close()
        return {}

    result = {
        "matches":       len({s.match_id for s in all_stats}),
        "tournaments":   len({s.tournament_id for s in all_stats}),
        "total_runs":    sum(s.runs_scored for s in all_stats),
        "total_wickets": sum(s.wickets_taken for s in all_stats),
        "total_fours":   sum(s.fours for s in all_stats),
        "total_sixes":   sum(s.sixes for s in all_stats),
        "total_catches": sum(s.catches for s in all_stats),
        "raid_points":   sum(s.raid_points for s in all_stats),
        "tackle_points": sum(s.tackle_points for s in all_stats),
        "aces":          sum(s.aces for s in all_stats),
        "kills":         sum(s.kills for s in all_stats),
        "total_mvp":     round(sum(s.mvp_score for s in all_stats), 2),
        "best_mvp":      round(max((s.mvp_score for s in all_stats), default=0), 2),
    }
    db.close()
    return result
