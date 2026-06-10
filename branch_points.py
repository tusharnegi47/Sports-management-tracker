"""
agents/analytics_agent/branch_points.py
Branch Points System — Agent 5

Tracks NIT Delhi branch-wise medal standings.
Gold = match win (3 pts), Silver = runner-up (2 pts), Bronze = 3rd place (1 pt)
"""

from typing import Dict, List
import pandas as pd

from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import BranchStanding, Tournament, Match, Team
from shared.constants.sports import NIT_DELHI_BRANCHES
from shared.logging.logger import get_analytics_logger

logger = get_analytics_logger()


def compute_branch_medals(tournament_id: str) -> Dict[str, Dict]:
    """Compute medal counts per branch based on completed matches."""
    db = get_db_session()
    matches = (
        db.query(Match)
        .filter(Match.tournament_id == tournament_id, Match.status == "completed")
        .all()
    )

    branch_medals: Dict[str, Dict] = {
        b: {"gold": 0, "silver": 0, "bronze": 0, "total_points": 0}
        for b in NIT_DELHI_BRANCHES
    }

    for m in matches:
        if not m.winner_id:
            continue
        winner_team = db.query(Team).filter(Team.id == m.winner_id).first()
        loser_id = str(m.team_a_id) if str(m.winner_id) == str(m.team_b_id) else str(m.team_b_id)
        loser_team = db.query(Team).filter(Team.id == loser_id).first()

        if winner_team and winner_team.branch in branch_medals:
            branch_medals[winner_team.branch]["gold"] += 1

        if loser_team and loser_team.branch in branch_medals:
            branch_medals[loser_team.branch]["silver"] += 1

    # Total points: Gold=3, Silver=2, Bronze=1
    for b in branch_medals:
        m_data = branch_medals[b]
        m_data["total_points"] = (
            m_data["gold"] * 3 + m_data["silver"] * 2 + m_data["bronze"] * 1
        )

    # Upsert to DB
    for branch, pts in branch_medals.items():
        existing = db.query(BranchStanding).filter(
            BranchStanding.tournament_id == tournament_id,
            BranchStanding.branch == branch,
        ).first()
        if existing:
            existing.gold         = pts["gold"]
            existing.silver       = pts["silver"]
            existing.bronze       = pts["bronze"]
            existing.total_points = pts["total_points"]
        else:
            db.add(BranchStanding(
                tournament_id=tournament_id,
                branch=branch,
                **pts,
            ))
    db.commit()
    db.close()
    logger.info(f"Branch medals computed for tournament {tournament_id}")
    return branch_medals


def get_branch_medals_df(tournament_id: str) -> pd.DataFrame:
    """Ranked DataFrame of branch medal standings."""
    db = get_db_session()
    rows = (
        db.query(BranchStanding)
        .filter(BranchStanding.tournament_id == tournament_id)
        .order_by(BranchStanding.total_points.desc())
        .all()
    )
    db.close()

    if not rows:
        return pd.DataFrame()

    data = [{
        "Branch":      r.branch,
        "🥇 Gold":     r.gold,
        "🥈 Silver":   r.silver,
        "🥉 Bronze":   r.bronze,
        "Total Pts":   r.total_points,
    } for r in rows if r.total_points > 0]

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df.index = range(1, len(df) + 1)
    return df


def get_branch_rank(tournament_id: str, branch: str) -> int:
    """Return the rank of a specific branch in a tournament."""
    df = get_branch_medals_df(tournament_id)
    if df.empty or "Branch" not in df.columns:
        return 0
    matches = df[df["Branch"] == branch]
    return int(matches.index[0]) if not matches.empty else 0


def get_all_time_branch_leaders() -> pd.DataFrame:
    """Aggregate branch medals across ALL tournaments."""
    db = get_db_session()
    rows = db.query(BranchStanding).all()
    db.close()

    if not rows:
        return pd.DataFrame()

    branch_totals: Dict[str, Dict] = {}
    for r in rows:
        b = r.branch
        if b not in branch_totals:
            branch_totals[b] = {"Branch": b, "🥇 Gold": 0, "🥈 Silver": 0,
                                 "🥉 Bronze": 0, "Total Pts": 0}
        branch_totals[b]["🥇 Gold"]   += r.gold
        branch_totals[b]["🥈 Silver"] += r.silver
        branch_totals[b]["🥉 Bronze"] += r.bronze
        branch_totals[b]["Total Pts"] += r.total_points

    df = pd.DataFrame(list(branch_totals.values()))
    return df.sort_values("Total Pts", ascending=False).reset_index(drop=True)
