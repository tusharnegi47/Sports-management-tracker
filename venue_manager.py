"""
agents/admin_agent/venue_manager.py
Venue Management — Agent 2
"""

from typing import List, Dict
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import Match, Tournament

NIT_VENUES = [
    "NIT Delhi Main Ground",
    "NIT Delhi Indoor Hall",
    "NIT Delhi Basketball Court",
    "NIT Delhi Volleyball Court",
    "NIT Delhi Cricket Pitch A",
    "NIT Delhi Cricket Pitch B",
]


def get_available_venues() -> List[str]:
    """Return list of all NIT Delhi sports venues."""
    return NIT_VENUES


def get_venue_schedule(venue: str) -> List[Dict]:
    """Return all scheduled/live matches at a given venue."""
    from sqlalchemy.orm import joinedload
    db = get_db_session()
    matches = (
        db.query(Match)
        .options(
            joinedload(Match.team_a),
            joinedload(Match.team_b),
            joinedload(Match.tournament),
        )
        .filter(Match.venue == venue, Match.status.in_(["scheduled", "live"]))
        .order_by(Match.scheduled_at)
        .all()
    )
    result = [
        {
            "match_id":    str(m.id),
            "team_a":      m.team_a.name if m.team_a else "",
            "team_b":      m.team_b.name if m.team_b else "",
            "status":      m.status,
            "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else "TBD",
            "tournament":  m.tournament.name if m.tournament else "",
        }
        for m in matches
    ]
    db.close()
    return result


def update_match_venue(match_id: str, new_venue: str, admin_id: str) -> bool:
    """Update the venue for a scheduled match."""
    from agents.database_agent.permissions import is_admin
    db = get_db_session()
    if not is_admin(db, admin_id):
        db.close()
        raise PermissionError("Admin access required")
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        db.close()
        return False
    match.venue = new_venue
    db.commit()
    db.close()
    return True
