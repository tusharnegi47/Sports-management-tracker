"""
agents/admin_agent/scheduler.py
Match Scheduler Service — Agent 2

Handles round-robin and knockout fixture generation.
"""

import itertools
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone

from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import Match, Tournament, TournamentTeam, Team
from shared.event_bus import get_event_bus, create_event, EventType
from shared.logging.logger import get_admin_logger

logger = get_admin_logger()
bus    = get_event_bus()

AGENT = "ADMIN_AGENT"


def generate_round_robin(
    tournament_id: str,
    admin_user_id: str,
    start_datetime: datetime,
    match_duration_minutes: int = 120,
    venue: str = "NIT Delhi Ground",
) -> List[Dict]:
    """
    Auto-generate round-robin fixtures for all teams in a tournament.
    Returns list of created match dicts.
    """
    db = get_db_session()
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        db.close()
        raise ValueError(f"Tournament {tournament_id} not found")

    # Extract plain values before session closes
    t_sport_id   = tournament.sport_id
    t_name       = tournament.name

    t_teams = (
        db.query(TournamentTeam, Team)
        .join(Team, TournamentTeam.team_id == Team.id)
        .filter(TournamentTeam.tournament_id == tournament_id)
        .all()
    )
    # Extract team data as plain dicts before closing session
    teams = [{"id": t.id, "name": t.name} for _, t in t_teams]
    db.close()

    if len(teams) < 2:
        raise ValueError("At least 2 teams required to generate fixtures")

    pairs = list(itertools.combinations(teams, 2))
    created = []
    current_dt = start_datetime

    db = get_db_session()
    for i, (team_a, team_b) in enumerate(pairs, start=1):
        match = Match(
            tournament_id=tournament_id,
            team_a_id=team_a["id"],
            team_b_id=team_b["id"],
            sport_id=t_sport_id,
            venue=venue,
            scheduled_at=current_dt,
            round_name="Group Stage",
            match_number=i,
        )
        db.add(match)
        db.flush()
        created.append({
            "match_id": str(match.id),
            "team_a": team_a["name"],
            "team_b": team_b["name"],
            "scheduled_at": current_dt.isoformat(),
        })
        current_dt += timedelta(minutes=match_duration_minutes)

        bus.publish(create_event(
            EventType.MATCH_CREATED, AGENT, str(match.id),
            {"team_a": team_a["name"], "team_b": team_b["name"], "tournament": t_name}
        ))

    db.commit()
    db.close()
    logger.info(f"Generated {len(created)} round-robin fixtures for tournament {tournament_id}")
    return created


def generate_knockout_bracket(
    tournament_id: str,
    seeded_team_ids: List[str],
    start_datetime: datetime,
    venue: str = "NIT Delhi Ground",
) -> List[Dict]:
    """
    Generate first-round knockout bracket from seeded team list.
    Teams are paired: 1v8, 2v7, 3v6, 4v5 (standard seeding).
    """
    db = get_db_session()
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        db.close()
        raise ValueError("Tournament not found")

    # Extract plain values before session closes
    t_sport_id = tournament.sport_id

    team_objs = [db.query(Team).filter(Team.id == tid).first() for tid in seeded_team_ids]
    # Convert to plain dicts immediately
    teams = [{"id": t.id, "name": t.name} for t in team_objs if t]
    db.close()

    n = len(teams)
    if n < 2:
        raise ValueError("Need at least 2 teams for knockout")

    # Pair 1st vs last, 2nd vs second-last, etc.
    pairs = [(teams[i], teams[n - 1 - i]) for i in range(n // 2)]
    created = []
    current_dt = start_datetime

    db = get_db_session()
    for i, (team_a, team_b) in enumerate(pairs, start=1):
        match = Match(
            tournament_id=tournament_id,
            team_a_id=team_a["id"],
            team_b_id=team_b["id"],
            sport_id=t_sport_id,
            venue=venue,
            scheduled_at=current_dt,
            round_name="Round of 16" if n >= 16 else "Quarter Final" if n >= 8 else "Semi Final",
            match_number=i,
        )
        db.add(match)
        db.flush()
        created.append({
            "match_id": str(match.id),
            "team_a": team_a["name"],
            "team_b": team_b["name"],
            "scheduled_at": current_dt.isoformat(),
        })
        current_dt += timedelta(hours=2)

    db.commit()
    db.close()
    logger.info(f"Generated {len(created)} knockout fixtures")
    return created


def get_tournament_fixtures(tournament_id: str) -> List[Dict]:
    """Return all matches for a tournament ordered by schedule."""
    from sqlalchemy.orm import joinedload
    db = get_db_session()
    matches = (
        db.query(Match)
        .options(
            joinedload(Match.team_a),
            joinedload(Match.team_b),
            joinedload(Match.winner),
        )
        .filter(Match.tournament_id == tournament_id)
        .order_by(Match.scheduled_at)
        .all()
    )
    result = [
        {
            "id":          str(m.id),
            "team_a":      m.team_a.name if m.team_a else "",
            "team_b":      m.team_b.name if m.team_b else "",
            "status":      m.status,
            "venue":       m.venue or "",
            "round_name":  m.round_name or "",
            "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else "",
            "winner":      m.winner.name if m.winner else None,
        }
        for m in matches
    ]
    db.close()
    return result
