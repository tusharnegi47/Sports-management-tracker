"""
agents/analytics_agent/player_history.py
Player History & Timeline — Agent 5

Tracks player performance over time for trend charts.
"""

from typing import Dict, List, Optional
import pandas as pd

from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import PlayerStats, Match, Tournament
from shared.logging.logger import get_analytics_logger

logger = get_analytics_logger()


def get_player_match_history(user_id: str, sport_slug: str = "cricket") -> pd.DataFrame:
    """
    Returns match-by-match performance history for a player.
    Useful for trend charts showing improvement over time.
    """
    db = get_db_session()
    rows = (
        db.query(PlayerStats, Match.scheduled_at, Tournament.name.label("t_name"))
        .join(Match, PlayerStats.match_id == Match.id)
        .join(Tournament, PlayerStats.tournament_id == Tournament.id)
        .filter(PlayerStats.user_id == user_id)
        .order_by(Match.scheduled_at)
        .all()
    )

    if not rows:
        db.close()
        return pd.DataFrame()

    data = []
    for ps, match_date, t_name in rows:
        entry = {
            "Date":       match_date.strftime("%d %b %Y") if match_date else "—",
            "Tournament": t_name,
        }
        if sport_slug == "cricket":
            sr = round((ps.runs_scored / ps.balls_faced) * 100, 1) if ps.balls_faced else 0
            entry.update({
                "Runs": ps.runs_scored, "Balls": ps.balls_faced,
                "SR":   sr, "Wickets": ps.wickets_taken,
                "4s":   ps.fours, "6s": ps.sixes,
            })
        elif sport_slug == "kabaddi":
            entry.update({
                "Raid Pts": ps.raid_points, "Tackle Pts": ps.tackle_points,
                "Bonus":    ps.bonus_points, "Super Raids": ps.super_raids,
                "Total":    ps.raid_points + ps.tackle_points + ps.bonus_points,
            })
        elif sport_slug == "volleyball":
            entry.update({
                "Aces":  ps.aces, "Kills": ps.kills,
                "Blocks": ps.blocks, "Sets Won": ps.sets_won,
                "Total": ps.aces + ps.kills + ps.blocks,
            })
        entry["MVP Score"] = round(ps.mvp_score, 2)
        data.append(entry)
    db.close()

    return pd.DataFrame(data)


def get_player_tournament_summary(user_id: str) -> pd.DataFrame:
    """Aggregated stats per tournament for a player."""
    db = get_db_session()
    rows = (
        db.query(PlayerStats, Tournament.name.label("t_name"), Tournament.id.label("t_id"))
        .join(Tournament, PlayerStats.tournament_id == Tournament.id)
        .filter(PlayerStats.user_id == user_id)
        .all()
    )

    if not rows:
        db.close()
        return pd.DataFrame()

    t_agg: Dict[str, Dict] = {}
    for ps, t_name, t_id in rows:
        if t_id not in t_agg:
            t_agg[t_id] = {
                "Tournament": t_name, "Matches": 0,
                "Runs": 0, "Wickets": 0,
                "Raid Pts": 0, "Tackle Pts": 0,
                "Aces": 0, "Kills": 0,
                "MVP Total": 0.0,
            }
        a = t_agg[t_id]
        a["Matches"]    += 1
        a["Runs"]       += ps.runs_scored
        a["Wickets"]    += ps.wickets_taken
        a["Raid Pts"]   += ps.raid_points
        a["Tackle Pts"] += ps.tackle_points
        a["Aces"]       += ps.aces
        a["Kills"]      += ps.kills
        a["MVP Total"]  += ps.mvp_score
    db.close()

    df = pd.DataFrame(list(t_agg.values()))
    df["MVP Total"] = df["MVP Total"].round(2)
    return df.sort_values("MVP Total", ascending=False).reset_index(drop=True)


def get_form_last_n(user_id: str, n: int = 5) -> Dict:
    """Return last N matches performance summary — 'current form'."""
    db = get_db_session()
    rows = (
        db.query(PlayerStats)
        .filter(PlayerStats.user_id == user_id)
        .order_by(PlayerStats.created_at.desc())
        .limit(n)
        .all()
    )

    if not rows:
        db.close()
        return {"form": "No data", "avg_mvp": 0}

    avg_runs    = sum(r.runs_scored for r in rows) / len(rows)
    avg_mvp     = sum(r.mvp_score for r in rows) / len(rows)
    avg_wickets = sum(r.wickets_taken for r in rows) / len(rows)
    db.close()

    if avg_mvp > 20:
        form = "🔥 Excellent"
    elif avg_mvp > 10:
        form = "📈 Good"
    elif avg_mvp > 5:
        form = "📊 Average"
    else:
        form = "📉 Poor"

    return {
        "form":         form,
        "avg_mvp":      round(avg_mvp, 2),
        "avg_runs":     round(avg_runs, 1),
        "avg_wickets":  round(avg_wickets, 1),
        "matches":      len(rows),
    }
