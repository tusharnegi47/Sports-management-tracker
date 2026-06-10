"""
agents/player_experience_agent/join_code_service.py
Join Code Generation & Validation — Agent 4
"""

import random
import string
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from agents.database_agent.db_service import get_db
from agents.database_agent.models import JoinCode, Roster, Team, User
from agents.database_agent.permissions import is_captain
from shared.constants.sports import JOIN_CODE_LENGTH, JOIN_CODE_EXPIRY_HOURS, ROSTER_LIMITS
from shared.event_bus import get_event_bus, create_event, EventType
from shared.logging.logger import get_player_logger

logger = get_player_logger()
bus    = get_event_bus()

AGENT = "PLAYER_EXPERIENCE_AGENT"


def generate_join_code(team_id: str, captain_user_id: str) -> Dict[str, Any]:
    """Generate a unique 6-char join code for a team."""
    with get_db() as db:
        if not is_captain(db, captain_user_id, team_id):
            raise PermissionError("Only team captain or admin can generate join codes")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return {"success": False, "error": "Team not found"}

        # Deactivate old codes
        db.query(JoinCode).filter(
            JoinCode.team_id == team_id,
            JoinCode.is_active == True,
        ).update({"is_active": False})

        # Generate unique code
        code = _gen_unique_code(db)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=JOIN_CODE_EXPIRY_HOURS)

        jc = JoinCode(
            code=code,
            team_id=team_id,
            created_by=captain_user_id,
            expires_at=expires_at,
        )
        db.add(jc)
        logger.info(f"Join code {code} generated for team {team_id}")

    bus.publish(create_event(
        EventType.JOIN_CODE_GENERATED,
        AGENT,
        team_id,
        {"code": code, "expires_at": expires_at.isoformat()},
    ))
    return {"success": True, "code": code, "expires_at": expires_at.isoformat()}


def use_join_code(code: str, user_id: str) -> Dict[str, Any]:
    """Student uses a join code to join a team."""
    with get_db() as db:
        now = datetime.now(timezone.utc)
        jc  = db.query(JoinCode).filter(
            JoinCode.code == code,
            JoinCode.is_active == True,
        ).first()

        if not jc:
            return {"success": False, "error": "Invalid or expired join code"}
        if jc.expires_at.replace(tzinfo=timezone.utc) < now:
            jc.is_active = False
            return {"success": False, "error": "Join code has expired"}
        if jc.used_count >= jc.max_uses:
            return {"success": False, "error": "Join code has reached maximum uses"}

        # Check already in team
        existing = db.query(Roster).filter(
            Roster.team_id == jc.team_id,
            Roster.user_id == user_id,
        ).first()
        if existing:
            return {"success": False, "error": "You are already in this team"}

        # Check roster limit
        team = db.query(Team).filter(Team.id == jc.team_id).first()
        sport_slug = team.sport.slug if team and team.sport else "cricket"
        limit = ROSTER_LIMITS.get(sport_slug, {}).get("max", 15)
        current_size = db.query(Roster).filter(
            Roster.team_id == jc.team_id,
            Roster.status == "active",
        ).count()
        if current_size >= limit:
            return {"success": False, "error": f"Team is full ({limit} players maximum)"}

        # Add to roster
        roster_entry = Roster(
            team_id=str(jc.team_id),
            user_id=user_id,
            status="active",
        )
        db.add(roster_entry)
        jc.used_count += 1
        joined_team_id = str(jc.team_id)  # save before session closes
        logger.info(f"User {user_id} joined team {joined_team_id} via code {code}")

    bus.publish(create_event(
        EventType.PLAYER_JOINED_TEAM,
        AGENT,
        user_id,
        {"team_id": joined_team_id, "code": code},
    ))
    return {"success": True, "team_id": joined_team_id}


def _gen_unique_code(db, length: int = JOIN_CODE_LENGTH) -> str:
    chars = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = "".join(random.choices(chars, k=length))
        if not db.query(JoinCode).filter(JoinCode.code == code).first():
            return code
    raise RuntimeError("Could not generate unique join code after 20 attempts")


def get_team_join_code(team_id: str) -> Optional[str]:
    with get_db() as db:
        jc = db.query(JoinCode).filter(
            JoinCode.team_id == team_id,
            JoinCode.is_active == True,
        ).order_by(JoinCode.created_at.desc()).first()
        if jc and jc.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            return jc.code
    return None
