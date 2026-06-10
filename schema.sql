"""
agents/database_agent/schema.sql
Full PostgreSQL schema — run this to initialize from scratch.
Auto-generated from SQLAlchemy models for reference.
"""

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Users & Auth ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    name          VARCHAR(100) NOT NULL,
    roll_number   VARCHAR(20) UNIQUE,
    branch        VARCHAR(10),
    batch         VARCHAR(4),
    password_hash VARCHAR(255) NOT NULL,
    phone         VARCHAR(15),
    is_active     BOOLEAN DEFAULT TRUE,
    is_verified   BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    last_login    TIMESTAMPTZ
);
CREATE INDEX ix_users_email ON users(email);

CREATE TABLE IF NOT EXISTS roles (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS permissions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    resource    VARCHAR(50) NOT NULL,
    action      VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS user_roles (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id    UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    context_id UUID,
    granted_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, role_id, context_id)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id       UUID REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES permissions(id) ON DELETE CASCADE,
    UNIQUE(role_id, permission_id)
);

-- ── Sports ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sports (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name       VARCHAR(50) UNIQUE NOT NULL,
    slug       VARCHAR(50) UNIQUE NOT NULL,
    icon       VARCHAR(10),
    is_active  BOOLEAN DEFAULT TRUE,
    config     JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Tournaments ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tournaments (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(150) NOT NULL,
    slug        VARCHAR(150) UNIQUE NOT NULL,
    sport_id    UUID NOT NULL REFERENCES sports(id),
    created_by  UUID NOT NULL REFERENCES users(id),
    status      VARCHAR(20) DEFAULT 'upcoming',
    description TEXT,
    start_date  TIMESTAMPTZ,
    end_date    TIMESTAMPTZ,
    venue       VARCHAR(200),
    max_teams   INT DEFAULT 8,
    format      VARCHAR(50) DEFAULT 'round_robin',
    overs       INT DEFAULT 20,
    rules       JSONB DEFAULT '{}',
    banner_url  VARCHAR(500),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Teams ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS teams (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name         VARCHAR(100) NOT NULL,
    short_name   VARCHAR(10),
    sport_id     UUID NOT NULL REFERENCES sports(id),
    captain_id   UUID REFERENCES users(id),
    branch       VARCHAR(10),
    batch        VARCHAR(4),
    logo_url     VARCHAR(500),
    jersey_color VARCHAR(20),
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tournament_teams (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    team_id       UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    group_name    VARCHAR(10),
    seed          INT,
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tournament_id, team_id)
);

CREATE TABLE IF NOT EXISTS rosters (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id       UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    jersey_number INT,
    position      VARCHAR(50),
    is_playing_xi BOOLEAN DEFAULT FALSE,
    status        VARCHAR(20) DEFAULT 'active',
    joined_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_id, user_id)
);

CREATE TABLE IF NOT EXISTS join_codes (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code       VARCHAR(10) UNIQUE NOT NULL,
    team_id    UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    max_uses   INT DEFAULT 20,
    used_count INT DEFAULT 0,
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_join_codes_code ON join_codes(code);

-- ── Matches ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS matches (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tournament_id  UUID NOT NULL REFERENCES tournaments(id),
    team_a_id      UUID NOT NULL REFERENCES teams(id),
    team_b_id      UUID NOT NULL REFERENCES teams(id),
    sport_id       UUID NOT NULL REFERENCES sports(id),
    scorer_id      UUID REFERENCES users(id),
    winner_id      UUID REFERENCES teams(id),
    status         VARCHAR(20) DEFAULT 'scheduled',
    venue          VARCHAR(200),
    scheduled_at   TIMESTAMPTZ,
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    round_name     VARCHAR(50),
    match_number   INT,
    toss_winner_id UUID REFERENCES teams(id),
    toss_decision  VARCHAR(10),
    result_summary TEXT,
    meta           JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_matches_status     ON matches(status);
CREATE INDEX ix_matches_tournament ON matches(tournament_id);

CREATE TABLE IF NOT EXISTS innings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id        UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    batting_team_id UUID REFERENCES teams(id),
    bowling_team_id UUID REFERENCES teams(id),
    innings_number  INT NOT NULL,
    runs            INT DEFAULT 0,
    wickets         INT DEFAULT 0,
    overs_played    FLOAT DEFAULT 0.0,
    extras          JSONB DEFAULT '{}',
    is_complete     BOOLEAN DEFAULT FALSE,
    target          INT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deliveries (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    innings_id     UUID NOT NULL REFERENCES innings(id) ON DELETE CASCADE,
    over_number    INT NOT NULL,
    ball_number    INT NOT NULL,
    batter_id      UUID REFERENCES users(id),
    bowler_id      UUID REFERENCES users(id),
    runs_scored    INT DEFAULT 0,
    extra_type     VARCHAR(20),
    extra_runs     INT DEFAULT 0,
    is_wicket      BOOLEAN DEFAULT FALSE,
    dismissal_type VARCHAR(50),
    fielder_id     UUID REFERENCES users(id),
    is_valid_ball  BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS live_scores (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id   UUID UNIQUE NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    score_data JSONB NOT NULL DEFAULT '{}',
    last_event TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS match_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id    UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    event_type  VARCHAR(50) NOT NULL,
    description TEXT,
    payload     JSONB DEFAULT '{}',
    created_by  UUID REFERENCES users(id),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_match_events_match_id ON match_events(match_id);

-- ── Player Stats ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS player_stats (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    match_id      UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    team_id       UUID REFERENCES teams(id),
    sport_id      UUID REFERENCES sports(id),
    tournament_id UUID REFERENCES tournaments(id),
    runs_scored   INT DEFAULT 0,
    balls_faced   INT DEFAULT 0,
    fours         INT DEFAULT 0,
    sixes         INT DEFAULT 0,
    wickets_taken INT DEFAULT 0,
    overs_bowled  FLOAT DEFAULT 0.0,
    runs_given    INT DEFAULT 0,
    catches       INT DEFAULT 0,
    run_outs      INT DEFAULT 0,
    is_not_out    BOOLEAN DEFAULT TRUE,
    raid_points   INT DEFAULT 0,
    tackle_points INT DEFAULT 0,
    bonus_points  INT DEFAULT 0,
    super_raids   INT DEFAULT 0,
    aces          INT DEFAULT 0,
    kills         INT DEFAULT 0,
    blocks        INT DEFAULT 0,
    sets_won      INT DEFAULT 0,
    mvp_score     FLOAT DEFAULT 0.0,
    raw_data      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, match_id)
);

-- ── Leaderboards ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS leaderboard_cache (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    team_id       UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    played        INT DEFAULT 0,
    won           INT DEFAULT 0,
    lost          INT DEFAULT 0,
    drawn         INT DEFAULT 0,
    points        INT DEFAULT 0,
    nrr           FLOAT DEFAULT 0.0,
    for_score     FLOAT DEFAULT 0.0,
    against_score FLOAT DEFAULT 0.0,
    position      INT DEFAULT 0,
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tournament_id, team_id)
);

CREATE TABLE IF NOT EXISTS branch_standings (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    branch        VARCHAR(10) NOT NULL,
    gold          INT DEFAULT 0,
    silver        INT DEFAULT 0,
    bronze        INT DEFAULT 0,
    total_points  INT DEFAULT 0,
    position      INT DEFAULT 0,
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tournament_id, branch)
);

-- ── Audit ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(100) NOT NULL,
    resource    VARCHAR(100) NOT NULL,
    resource_id VARCHAR(100),
    ip_address  VARCHAR(45),
    details     JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_audit_logs_created_at ON audit_logs(created_at);

-- ── Default Data ──────────────────────────────────────────────────────────────

INSERT INTO roles (name, description) VALUES
    ('admin',   'Full system access'),
    ('captain', 'Team management access'),
    ('scorer',  'Live scoring access'),
    ('student', 'View-only + team join access')
ON CONFLICT (name) DO NOTHING;

INSERT INTO sports (name, slug, icon) VALUES
    ('Cricket',    'cricket',    '🏏'),
    ('Kabaddi',    'kabaddi',    '🤼'),
    ('Volleyball', 'volleyball', '🏐')
ON CONFLICT (slug) DO NOTHING;
