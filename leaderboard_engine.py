"""
agents/analytics_agent/leaderboard_engine.py
Leaderboard Engine — Agent 5

Provides leaderboard computation and retrieval.
Wraps analytics_engine functions for cleaner imports.
"""

from typing import Optional
import pandas as pd

from agents.analytics_agent.analytics_engine import (
    refresh_leaderboard,
    get_leaderboard,
    refresh_branch_standings,
    get_branch_standings,
)
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import Tournament, LeaderboardCache, Team
from shared.logging.logger import get_analytics_logger

logger = get_analytics_logger()


def compute_and_get_leaderboard(tournament_id: str, force_refresh: bool = False) -> pd.DataFrame:
    """Refresh then return leaderboard for a tournament."""
    if force_refresh:
        refresh_leaderboard(tournament_id)
    return get_leaderboard(tournament_id)


def compute_and_get_branch_standings(tournament_id: str, force_refresh: bool = False) -> pd.DataFrame:
    """Refresh then return branch standings."""
    if force_refresh:
        refresh_branch_standings(tournament_id)
    return get_branch_standings(tournament_id)


def get_team_position(tournament_id: str, team_id: str) -> Optional[int]:
    """Return a team's current position in the leaderboard."""
    db = get_db_session()
    entry = db.query(LeaderboardCache).filter(
        LeaderboardCache.tournament_id == tournament_id,
        LeaderboardCache.team_id == team_id,
    ).first()
    db.close()
    return entry.position if entry else None


def get_team_record(tournament_id: str, team_id: str) -> dict:
    """Return win/loss/points record for a team in a tournament."""
    db = get_db_session()
    entry = db.query(LeaderboardCache).filter(
        LeaderboardCache.tournament_id == tournament_id,
        LeaderboardCache.team_id == team_id,
    ).first()
    db.close()
    if not entry:
        return {}
    return {
        "played": entry.played,
        "won":    entry.won,
        "lost":   entry.lost,
        "drawn":  entry.drawn,
        "points": entry.points,
        "nrr":    entry.nrr,
    }


def get_points_table_summary(tournament_id: str) -> list:
    """Return raw list of dicts for the points table (used by API consumers)."""
    db = get_db_session()
    rows = (
        db.query(LeaderboardCache, Team.name)
        .join(Team, LeaderboardCache.team_id == Team.id)
        .filter(LeaderboardCache.tournament_id == tournament_id)
        .order_by(LeaderboardCache.points.desc(), LeaderboardCache.nrr.desc())
        .all()
    )
    db.close()
    return [
        {
            "position": i + 1,
            "team":     team_name,
            "played":   lc.played,
            "won":      lc.won,
            "lost":     lc.lost,
            "points":   lc.points,
            "nrr":      lc.nrr,
        }
        for i, (lc, team_name) in enumerate(rows)
    ]
