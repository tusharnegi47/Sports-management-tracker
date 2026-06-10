# NIT Delhi Sports Management System 🏟️

> A production-grade, multi-sport tournament management platform for NIT Delhi, inspired by Cricheroes.

**Supports:** Cricket 🏏 · Kabaddi 🤼 · Volleyball 🏐  
**Tournaments:** ZEAL · NDPL · Inter-College Events

---

## 🏗️ Architecture

5 autonomous agents communicate via a shared event bus:

| Agent | Responsibility |
|---|---|
| **Agent 1** — Database + Auth | PostgreSQL schema, ORM, JWT auth, RBAC |
| **Agent 2** — Admin + Tournament | Tournament creation, match scheduling, admin control |
| **Agent 3** — Scoring Engine | Live scoring for all 3 sports, ball-by-ball |
| **Agent 4** — Player Experience | Student dashboard, captain tools, join codes, live center |
| **Agent 5** — Analytics | Leaderboards, player stats, branch standings, MVP |

---

## 🚀 Quick Start

### Option 1 — Docker (Recommended)

```bash
cp .env.example .env          # Configure environment
docker-compose up --build     # Start everything
```

Open: http://localhost:8501  
Default admin: `admin@nitdelhi.ac.in` / `admin123`

### Option 2 — Local (requires PostgreSQL)

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env → set your DATABASE_URL

# 4. Run
streamlit run app.py
```

---

## 📁 Project Structure

```
sports_project/
├── app.py                    ← Streamlit entry point
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
│
├── shared/
│   ├── event_bus.py          ← Inter-agent pub/sub
│   ├── constants/sports.py  ← Roster limits, sport rules
│   └── logging/logger.py
│
├── agents/
│   ├── database_agent/       ← Agent 1
│   │   ├── models.py         ← All ORM models
│   │   ├── auth.py           ← JWT + bcrypt
│   │   ├── permissions.py    ← RBAC
│   │   ├── db_service.py     ← Connection + seeding
│   │   └── schema.sql        ← Raw SQL schema
│   │
│   ├── admin_agent/          ← Agent 2
│   │   └── admin_dashboard.py
│   │
│   ├── scoring_agent/        ← Agent 3
│   │   ├── cricket_engine.py
│   │   ├── kabaddi_engine.py
│   │   ├── volleyball_engine.py
│   │   ├── match_state_manager.py
│   │   └── scorer_ui.py
│   │
│   ├── player_experience_agent/  ← Agent 4
│   │   ├── live_center.py
│   │   ├── captain_dashboard.py
│   │   ├── student_dashboard.py
│   │   ├── roster_manager.py
│   │   ├── profile_pages.py
│   │   └── join_code_service.py
│   │
│   └── analytics_agent/      ← Agent 5
│       ├── analytics_engine.py
│       └── charts.py
```

---

## 🎭 Roles

| Role | Capabilities |
|---|---|
| **Admin** | Full access — create tournaments, manage all |
| **Captain** | Create team, manage roster, generate join codes |
| **Scorer** | Live score assigned matches |
| **Student** | View schedules, join teams, see stats |

---

## 📡 Event System

All agents communicate via `shared/event_bus.py` (pub/sub):

```
SCORE_UPDATED → Live Center auto-refreshes
MATCH_FINISHED → Analytics recalculates leaderboard
PLAYER_JOINED_TEAM → Roster updates
TOURNAMENT_CREATED → Admin & Scoring agents notified
```

---

## 🌐 Deployment

### Streamlit Cloud
1. Push to GitHub
2. Connect at share.streamlit.io
3. Set `DATABASE_URL` in Secrets
4. Use Neon PostgreSQL (free tier) or Supabase

### Neon PostgreSQL (Free)
1. Create account at neon.tech
2. Copy connection string
3. Set as `DATABASE_URL` in `.env`

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | localhost |
| `JWT_SECRET_KEY` | Token signing key | ⚠️ Change! |
| `ADMIN_EMAIL` | Default admin account | admin@nitdelhi.ac.in |
| `ADMIN_PASSWORD` | Default admin password | ⚠️ Change! |

---

## 🏆 Supported Tournaments

- **ZEAL** — Annual inter-branch sports fest
- **NDPL** — NIT Delhi Premier League (cricket)
- **Inter-College** — Multi-college expansion ready

---

*Built for NIT Delhi · Scalable to all universities*
