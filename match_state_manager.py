"""
agents/scoring_agent/match_state_manager.py
Match Lifecycle Controller — Agent 3
Handles start/pause/resume/cancel and assigns scorer.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone

from agents.database_agent.db_service import get_db
from agents.database_agent.models import Match, MatchEvent
from agents.database_agent.permissions import is_admin, is_scorer
from shared.event_bus import get_event_bus, create_event, EventType
from shared.logging.logger import get_scoring_logger

logger = get_scoring_logger()
bus    = get_event_bus()

AGENT = "SCORING_AGENT"


def start_match(match_id: str, actor_id: str, toss_winner_id: Optional[str] = None, toss_decision: Optional[str] = None) -> Dict:
    with get_db() as db:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return {"success": False, "error": "Match not found"}
        if not is_admin(db, actor_id) and str(match.scorer_id) != str(actor_id):
            raise PermissionError("Only an admin or the assigned scorer can start a match")
        if match.status != "scheduled":
            return {"success": False, "error": f"Cannot start match in status: {match.status}"}
        match.status       = "live"
        match.started_at   = datetime.now(timezone.utc)
        if toss_winner_id:
            match.toss_winner_id = toss_winner_id
        if toss_decision:
            match.toss_decision = toss_decision

        db.add(MatchEvent(match_id=match_id, event_type="MATCH_STARTED",
                          description="Match started", created_by=actor_id))

    bus.publish(create_event(EventType.MATCH_STARTED, AGENT, match_id,
                              {"toss_winner": toss_winner_id, "decision": toss_decision}))
    logger.info(f"Match {match_id} started")
    return {"success": True}


def pause_match(match_id: str, actor_id: str, reason: str = "") -> Dict:
    with get_db() as db:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match or match.status != "live":
            return {"success": False, "error": "Match is not live"}
        match.status = "paused"
        db.add(MatchEvent(match_id=match_id, event_type="MATCH_PAUSED",
                          description=reason or "Match paused", created_by=actor_id))

    bus.publish(create_event(EventType.MATCH_PAUSED, AGENT, match_id, {"reason": reason}))
    return {"success": True}


def resume_match(match_id: str, actor_id: str) -> Dict:
    with get_db() as db:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match or match.status != "paused":
            return {"success": False, "error": "Match is not paused"}
        match.status = "live"
        db.add(MatchEvent(match_id=match_id, event_type="MATCH_RESUMED",
                          description="Match resumed", created_by=actor_id))

    bus.publish(create_event(EventType.MATCH_RESUMED, AGENT, match_id, {}))
    return {"success": True}


def cancel_match(match_id: str, actor_id: str, reason: str = "") -> Dict:
    with get_db() as db:
        if not is_admin(db, actor_id):
            raise PermissionError("Only admin can cancel a match")
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return {"success": False, "error": "Match not found"}
        match.status = "cancelled"
        db.add(MatchEvent(match_id=match_id, event_type="MATCH_CANCELLED",
                          description=reason or "Match cancelled", created_by=actor_id))

    bus.publish(create_event(EventType.MATCH_CANCELLED, AGENT, match_id, {"reason": reason}))
    return {"success": True}


def assign_scorer(match_id: str, scorer_user_id: str, admin_id: str) -> Dict:
    with get_db() as db:
        if not is_admin(db, admin_id):
            raise PermissionError("Only admin can assign scorers")
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return {"success": False, "error": "Match not found"}
        match.scorer_id = scorer_user_id
        logger.info(f"Scorer {scorer_user_id} assigned to match {match_id}")
    return {"success": True}


def get_match_status(match_id: str) -> Dict[str, Any]:
    with get_db() as db:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return {}
        return {
            "id":           match.id,
            "status":       match.status,
            "team_a_id":    str(match.team_a_id),
            "team_b_id":    str(match.team_b_id),
            "scorer_id":    str(match.scorer_id) if match.scorer_id else None,
            "scheduled_at": match.scheduled_at.isoformat() if match.scheduled_at else None,
            "started_at":   match.started_at.isoformat() if match.started_at else None,
            "finished_at":  match.finished_at.isoformat() if match.finished_at else None,
            "venue":        match.venue,
            "round_name":   match.round_name,
        }
