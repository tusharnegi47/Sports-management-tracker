"""
agents/database_agent/models.py
SQLAlchemy ORM Models — Agent 1
Database-agnostic (works with SQLite for dev, PostgreSQL for prod).
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Boolean, Float, DateTime,
    ForeignKey, Text, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


# ── Users & Auth ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id            = Column(String(36), primary_key=True, default=gen_uuid)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    name          = Column(String(100), nullable=False)
    roll_number   = Column(String(20), unique=True, nullable=True)
    branch        = Column(String(10), nullable=True)
    batch         = Column(String(4), nullable=True)
    password_hash = Column(String(255), nullable=False)
    phone         = Column(String(15), nullable=True)
    is_active     = Column(Boolean, default=True)
    is_verified   = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=utcnow)
    updated_at    = Column(DateTime, default=utcnow, onupdate=utcnow)
    last_login    = Column(DateTime, nullable=True)

    roles        = relationship("UserRole", back_populates="user", cascade="all, delete-orphan",
                                foreign_keys="UserRole.user_id")
    player_stats = relationship("PlayerStats", back_populates="user")
    audit_logs   = relationship("AuditLog", back_populates="user")


class Role(Base):
    __tablename__ = "roles"
    id          = Column(String(36), primary_key=True, default=gen_uuid)
    name        = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=utcnow)

    users       = relationship("UserRole", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class UserRole(Base):
    __tablename__ = "user_roles"
    id         = Column(String(36), primary_key=True, default=gen_uuid)
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id    = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    context_id = Column(String(36), nullable=True)
    granted_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id], back_populates="roles")
    role = relationship("Role", back_populates="users")


class Permission(Base):
    __tablename__ = "permissions"
    id          = Column(String(36), primary_key=True, default=gen_uuid)
    name        = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    resource    = Column(String(50), nullable=False)
    action      = Column(String(50), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id            = Column(String(36), primary_key=True, default=gen_uuid)
    role_id       = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"))
    permission_id = Column(String(36), ForeignKey("permissions.id", ondelete="CASCADE"))
    role          = relationship("Role", back_populates="permissions")
    permission    = relationship("Permission")


# ── Sports & Tournaments ──────────────────────────────────────────────────────

class Sport(Base):
    __tablename__ = "sports"
    id         = Column(String(36), primary_key=True, default=gen_uuid)
    name       = Column(String(50), unique=True, nullable=False)
    slug       = Column(String(50), unique=True, nullable=False)
    icon       = Column(String(10), nullable=True)
    is_active  = Column(Boolean, default=True)
    config     = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)

    tournaments = relationship("Tournament", back_populates="sport")
    teams       = relationship("Team", back_populates="sport")


class Tournament(Base):
    __tablename__ = "tournaments"
    id          = Column(String(36), primary_key=True, default=gen_uuid)
    name        = Column(String(150), nullable=False)
    slug        = Column(String(150), unique=True, nullable=False)
    sport_id    = Column(String(36), ForeignKey("sports.id"), nullable=False)
    created_by  = Column(String(36), ForeignKey("users.id"), nullable=False)
    status      = Column(String(20), default="upcoming")
    description = Column(Text, nullable=True)
    start_date  = Column(DateTime, nullable=True)
    end_date    = Column(DateTime, nullable=True)
    venue       = Column(String(200), nullable=True)
    max_teams   = Column(Integer, default=8)
    format      = Column(String(50), default="round_robin")
    overs       = Column(Integer, default=20)
    rules       = Column(JSON, default=dict)
    banner_url  = Column(String(500), nullable=True)
    created_at  = Column(DateTime, default=utcnow)
    updated_at  = Column(DateTime, default=utcnow, onupdate=utcnow)

    sport   = relationship("Sport", back_populates="tournaments")
    matches = relationship("Match", back_populates="tournament")
    teams   = relationship("TournamentTeam", back_populates="tournament")


class TournamentTeam(Base):
    __tablename__ = "tournament_teams"
    id            = Column(String(36), primary_key=True, default=gen_uuid)
    tournament_id = Column(String(36), ForeignKey("tournaments.id", ondelete="CASCADE"))
    team_id       = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"))
    group_name    = Column(String(10), nullable=True)
    seed          = Column(Integer, nullable=True)
    registered_at = Column(DateTime, default=utcnow)

    tournament = relationship("Tournament", back_populates="teams")
    team       = relationship("Team")


# ── Teams & Rosters ───────────────────────────────────────────────────────────

class Team(Base):
    __tablename__ = "teams"
    id           = Column(String(36), primary_key=True, default=gen_uuid)
    name         = Column(String(100), nullable=False)
    short_name   = Column(String(10), nullable=True)
    sport_id     = Column(String(36), ForeignKey("sports.id"), nullable=False)
    captain_id   = Column(String(36), ForeignKey("users.id"), nullable=True)
    branch       = Column(String(10), nullable=True)
    batch        = Column(String(4), nullable=True)
    logo_url     = Column(String(500), nullable=True)
    jersey_color = Column(String(20), nullable=True)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=utcnow)

    sport      = relationship("Sport", back_populates="teams")
    captain    = relationship("User", foreign_keys=[captain_id])
    roster     = relationship("Roster", back_populates="team", cascade="all, delete-orphan")
    join_codes = relationship("JoinCode", back_populates="team", cascade="all, delete-orphan")


class Roster(Base):
    __tablename__ = "rosters"
    id            = Column(String(36), primary_key=True, default=gen_uuid)
    team_id       = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"))
    user_id       = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    jersey_number = Column(Integer, nullable=True)
    position      = Column(String(50), nullable=True)
    is_playing_xi = Column(Boolean, default=False)
    status        = Column(String(20), default="active")
    joined_at     = Column(DateTime, default=utcnow)

    team = relationship("Team", back_populates="roster")
    user = relationship("User")


class JoinCode(Base):
    __tablename__ = "join_codes"
    id         = Column(String(36), primary_key=True, default=gen_uuid)
    code       = Column(String(10), unique=True, nullable=False, index=True)
    team_id    = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"))
    created_by = Column(String(36), ForeignKey("users.id"))
    expires_at = Column(DateTime, nullable=False)
    max_uses   = Column(Integer, default=20)
    used_count = Column(Integer, default=0)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    team = relationship("Team", back_populates="join_codes")


# ── Matches ───────────────────────────────────────────────────────────────────

class Match(Base):
    __tablename__ = "matches"
    id             = Column(String(36), primary_key=True, default=gen_uuid)
    tournament_id  = Column(String(36), ForeignKey("tournaments.id"), nullable=False)
    team_a_id      = Column(String(36), ForeignKey("teams.id"), nullable=False)
    team_b_id      = Column(String(36), ForeignKey("teams.id"), nullable=False)
    sport_id       = Column(String(36), ForeignKey("sports.id"), nullable=False)
    scorer_id      = Column(String(36), ForeignKey("users.id"), nullable=True)
    winner_id      = Column(String(36), ForeignKey("teams.id"), nullable=True)
    status         = Column(String(20), default="scheduled")
    venue          = Column(String(200), nullable=True)
    scheduled_at   = Column(DateTime, nullable=True)
    started_at     = Column(DateTime, nullable=True)
    finished_at    = Column(DateTime, nullable=True)
    round_name     = Column(String(50), nullable=True)
    match_number   = Column(Integer, nullable=True)
    toss_winner_id = Column(String(36), ForeignKey("teams.id"), nullable=True)
    toss_decision  = Column(String(10), nullable=True)
    result_summary = Column(Text, nullable=True)
    meta           = Column(JSON, default=dict)
    created_at     = Column(DateTime, default=utcnow)
    updated_at     = Column(DateTime, default=utcnow, onupdate=utcnow)

    tournament = relationship("Tournament", back_populates="matches")
    sport      = relationship("Sport")
    team_a     = relationship("Team", foreign_keys=[team_a_id])
    team_b     = relationship("Team", foreign_keys=[team_b_id])
    winner     = relationship("Team", foreign_keys=[winner_id])
    scorer     = relationship("User", foreign_keys=[scorer_id])
    innings    = relationship("Innings", back_populates="match", cascade="all, delete-orphan")
    events     = relationship("MatchEvent", back_populates="match", cascade="all, delete-orphan")
    live_score = relationship("LiveScore", back_populates="match", uselist=False,
                              cascade="all, delete-orphan")


class Innings(Base):
    __tablename__ = "innings"
    id              = Column(String(36), primary_key=True, default=gen_uuid)
    match_id        = Column(String(36), ForeignKey("matches.id", ondelete="CASCADE"))
    batting_team_id = Column(String(36), ForeignKey("teams.id"))
    bowling_team_id = Column(String(36), ForeignKey("teams.id"))
    innings_number  = Column(Integer, nullable=False)
    runs            = Column(Integer, default=0)
    wickets         = Column(Integer, default=0)
    overs_played    = Column(Float, default=0.0)
    extras          = Column(JSON, default=dict)
    is_complete     = Column(Boolean, default=False)
    target          = Column(Integer, nullable=True)
    created_at      = Column(DateTime, default=utcnow)
    updated_at      = Column(DateTime, default=utcnow, onupdate=utcnow)

    match        = relationship("Match", back_populates="innings")
    batting_team = relationship("Team", foreign_keys=[batting_team_id])
    bowling_team = relationship("Team", foreign_keys=[bowling_team_id])
    deliveries   = relationship("Delivery", back_populates="innings", cascade="all, delete-orphan")


class Delivery(Base):
    __tablename__ = "deliveries"
    id             = Column(String(36), primary_key=True, default=gen_uuid)
    innings_id     = Column(String(36), ForeignKey("innings.id", ondelete="CASCADE"))
    over_number    = Column(Integer, nullable=False)
    ball_number    = Column(Integer, nullable=False)
    batter_id      = Column(String(36), ForeignKey("users.id"), nullable=True)
    bowler_id      = Column(String(36), ForeignKey("users.id"), nullable=True)
    runs_scored    = Column(Integer, default=0)
    extra_type     = Column(String(20), nullable=True)
    extra_runs     = Column(Integer, default=0)
    is_wicket      = Column(Boolean, default=False)
    dismissal_type = Column(String(50), nullable=True)
    fielder_id     = Column(String(36), ForeignKey("users.id"), nullable=True)
    is_valid_ball  = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=utcnow)

    innings = relationship("Innings", back_populates="deliveries")
    batter  = relationship("User", foreign_keys=[batter_id])
    bowler  = relationship("User", foreign_keys=[bowler_id])


class LiveScore(Base):
    __tablename__ = "live_scores"
    id         = Column(String(36), primary_key=True, default=gen_uuid)
    match_id   = Column(String(36), ForeignKey("matches.id", ondelete="CASCADE"), unique=True)
    score_data = Column(JSON, nullable=False, default=dict)
    last_event = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    match = relationship("Match", back_populates="live_score")


class MatchEvent(Base):
    __tablename__ = "match_events"
    id          = Column(String(36), primary_key=True, default=gen_uuid)
    match_id    = Column(String(36), ForeignKey("matches.id", ondelete="CASCADE"))
    event_type  = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    payload     = Column(JSON, default=dict)
    created_by  = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at  = Column(DateTime, default=utcnow)

    match = relationship("Match", back_populates="events")


# ── Player Stats ──────────────────────────────────────────────────────────────

class PlayerStats(Base):
    __tablename__ = "player_stats"
    id            = Column(String(36), primary_key=True, default=gen_uuid)
    user_id       = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    match_id      = Column(String(36), ForeignKey("matches.id", ondelete="CASCADE"))
    team_id       = Column(String(36), ForeignKey("teams.id"))
    sport_id      = Column(String(36), ForeignKey("sports.id"))
    tournament_id = Column(String(36), ForeignKey("tournaments.id"))
    runs_scored   = Column(Integer, default=0)
    balls_faced   = Column(Integer, default=0)
    fours         = Column(Integer, default=0)
    sixes         = Column(Integer, default=0)
    wickets_taken = Column(Integer, default=0)
    overs_bowled  = Column(Float, default=0.0)
    runs_given    = Column(Integer, default=0)
    catches       = Column(Integer, default=0)
    run_outs      = Column(Integer, default=0)
    is_not_out    = Column(Boolean, default=True)
    raid_points   = Column(Integer, default=0)
    tackle_points = Column(Integer, default=0)
    bonus_points  = Column(Integer, default=0)
    super_raids   = Column(Integer, default=0)
    aces          = Column(Integer, default=0)
    kills         = Column(Integer, default=0)
    blocks        = Column(Integer, default=0)
    sets_won      = Column(Integer, default=0)
    mvp_score     = Column(Float, default=0.0)
    raw_data      = Column(JSON, default=dict)
    created_at    = Column(DateTime, default=utcnow)
    updated_at    = Column(DateTime, default=utcnow, onupdate=utcnow)

    user       = relationship("User", back_populates="player_stats")
    match      = relationship("Match")
    team       = relationship("Team")
    sport      = relationship("Sport")
    tournament = relationship("Tournament")


# ── Leaderboard & Standings ───────────────────────────────────────────────────

class LeaderboardCache(Base):
    __tablename__ = "leaderboard_cache"
    id            = Column(String(36), primary_key=True, default=gen_uuid)
    tournament_id = Column(String(36), ForeignKey("tournaments.id", ondelete="CASCADE"))
    team_id       = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"))
    played        = Column(Integer, default=0)
    won           = Column(Integer, default=0)
    lost          = Column(Integer, default=0)
    drawn         = Column(Integer, default=0)
    points        = Column(Integer, default=0)
    nrr           = Column(Float, default=0.0)
    for_score     = Column(Float, default=0.0)
    against_score = Column(Float, default=0.0)
    position      = Column(Integer, default=0)
    updated_at    = Column(DateTime, default=utcnow, onupdate=utcnow)


class BranchStanding(Base):
    __tablename__ = "branch_standings"
    id            = Column(String(36), primary_key=True, default=gen_uuid)
    tournament_id = Column(String(36), ForeignKey("tournaments.id", ondelete="CASCADE"))
    branch        = Column(String(10), nullable=False)
    gold          = Column(Integer, default=0)
    silver        = Column(Integer, default=0)
    bronze        = Column(Integer, default=0)
    total_points  = Column(Integer, default=0)
    position      = Column(Integer, default=0)
    updated_at    = Column(DateTime, default=utcnow, onupdate=utcnow)


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id          = Column(String(36), primary_key=True, default=gen_uuid)
    user_id     = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action      = Column(String(100), nullable=False)
    resource    = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    ip_address  = Column(String(45), nullable=True)
    details     = Column(JSON, default=dict)
    created_at  = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="audit_logs")
