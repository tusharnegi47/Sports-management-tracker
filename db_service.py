"""
agents/database_agent/db_service.py
Database Connection + Session — SQLite for dev, PostgreSQL for prod.
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from agents.database_agent.models import Base
from shared.logging.logger import get_db_logger

logger = get_db_logger()

# Default to SQLite locally; set DATABASE_URL in .env for PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sports.db")

# SQLite needs check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.getenv("DEBUG", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"DB session error: {e}")
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    return SessionLocal()


def init_db() -> bool:
    Base.metadata.create_all(bind=engine)
    _seed_roles()
    _seed_sports()
    logger.info("✅ Database initialized")
    return True


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        return False


def _seed_roles():
    from agents.database_agent.models import Role
    roles_data = [
        {"name": "admin",   "description": "Full system access"},
        {"name": "captain", "description": "Team management"},
        {"name": "scorer",  "description": "Live scoring"},
        {"name": "student", "description": "View + join teams"},
    ]
    with get_db() as db:
        for rd in roles_data:
            if not db.query(Role).filter(Role.name == rd["name"]).first():
                db.add(Role(**rd))
        db.flush()  # ensure roles are queryable before seeding admin
        _seed_admin_user(db)


def _seed_sports():
    from agents.database_agent.models import Sport
    sports_data = [
        {"name": "Cricket",    "slug": "cricket",    "icon": "🏏"},
        {"name": "Kabaddi",    "slug": "kabaddi",    "icon": "🤼"},
        {"name": "Volleyball", "slug": "volleyball", "icon": "🏐"},
    ]
    with get_db() as db:
        for sd in sports_data:
            if not db.query(Sport).filter(Sport.slug == sd["slug"]).first():
                db.add(Sport(**sd))


def _seed_admin_user(db: Session):
    from agents.database_agent.models import User, Role, UserRole
    from agents.database_agent.auth import hash_password
    admin_email = os.getenv("ADMIN_EMAIL", "admin@nitdelhi.ac.in")
    admin_pass  = os.getenv("ADMIN_PASSWORD", "admin123")
    if db.query(User).filter(User.email == admin_email).first():
        return
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    user = User(
        email=admin_email,
        name="System Admin",
        password_hash=hash_password(admin_pass),
        is_verified=True,
    )
    db.add(user)
    db.flush()
    if admin_role:
        db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    logger.info(f"Admin seeded: {admin_email}")
