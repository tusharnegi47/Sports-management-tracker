"""
agents/scoring_agent/scoring_engine.py
Scoring Engine Router — Agent 3

Dispatches to the correct sport engine based on match sport.
This is the single entry point for all scoring operations.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import joinedload
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import Match
from shared.logging.logger import get_scoring_logger

logger = get_scoring_logger()


def get_engine(match_id: str, scorer_user_id: str):
    """
    Factory — returns the correct sport engine for a match.
    Usage:
        engine = get_engine(match_id, scorer_id)
        engine.record_delivery(...)   # cricket
        engine.record_raid(...)       # kabaddi
        engine.add_point(...)         # volleyball
    """
    db = get_db_session()
    match = db.query(Match).options(joinedload(Match.sport)).filter(Match.id == match_id).first()
    db.close()

    if not match:
        raise ValueError(f"Match {match_id} not found")

    sport_slug = match.sport.slug if match.sport else "cricket"

    if sport_slug == "cricket":
        from agents.scoring_agent.cricket_engine import CricketEngine
        return CricketEngine(match_id, scorer_user_id)
    elif sport_slug == "kabaddi":
        from agents.scoring_agent.kabaddi_engine import KabaddiEngine
        return KabaddiEngine(match_id, scorer_user_id)
    elif sport_slug == "volleyball":
        from agents.scoring_agent.volleyball_engine import VolleyballEngine
        return VolleyballEngine(match_id, scorer_user_id)
    else:
        raise ValueError(f"No engine found for sport: {sport_slug}")


def get_live_scorecard(match_id: str) -> Dict[str, Any]:
    """Fetch live score for any sport without needing scorer auth."""
    db = get_db_session()
    match = db.query(Match).options(joinedload(Match.sport)).filter(Match.id == match_id).first()
    db.close()

    if not match:
        return {}

    sport_slug = match.sport.slug if match.sport else "cricket"

    if sport_slug == "cricket":
        from agents.scoring_agent.cricket_engine import CricketEngine
        return CricketEngine.get_scorecard(match_id)
    elif sport_slug == "kabaddi":
        from agents.scoring_agent.kabaddi_engine import KabaddiEngine
        return KabaddiEngine.get_scorecard(match_id)
    elif sport_slug == "volleyball":
        from agents.scoring_agent.volleyball_engine import VolleyballEngine
        return VolleyballEngine.get_scorecard(match_id)
    return {}


def get_all_live_matches() -> list:
    """Return list of all currently live matches with scores."""
    from sqlalchemy.orm import joinedload
    db = get_db_session()
    matches = (
        db.query(Match)
        .options(
            joinedload(Match.team_a),
            joinedload(Match.team_b),
            joinedload(Match.sport),
            joinedload(Match.tournament),
        )
        .filter(Match.status == "live")
        .all()
    )
    result = []
    for m in matches:
        score = get_live_scorecard(str(m.id))
        result.append({
            "match_id":   str(m.id),
            "team_a":     m.team_a.name if m.team_a else "",
            "team_b":     m.team_b.name if m.team_b else "",
            "sport":      m.sport.slug if m.sport else "",
            "venue":      m.venue or "",
            "tournament": m.tournament.name if m.tournament else "",
            "score":      score,
        })
    db.close()
    return result
