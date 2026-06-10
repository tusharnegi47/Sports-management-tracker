"""
agents/database_agent/auth.py
JWT Authentication + Password Hashing — Agent 1
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from agents.database_agent.models import User, Role, UserRole
from shared.logging.logger import get_db_logger
from shared.event_bus import get_event_bus, create_event, EventType

logger = get_db_logger()
bus    = get_event_bus()

# ── Crypto Setup ─────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET    = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-prod")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_M  = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))


# ── Password Helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire  = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=JWT_EXPIRE_M))
    payload.update({"exp": expire, "iat": datetime.now(timezone.utc), "jti": str(uuid.uuid4())})
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        return None


# ── Registration ──────────────────────────────────────────────────────────────

def register_user(
    db: Session,
    email: str,
    name: str,
    password: str,
    roll_number: Optional[str] = None,
    branch: Optional[str] = None,
    batch: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Register a new user. Returns token + user info."""
    # Duplicate check
    if db.query(User).filter(User.email == email).first():
        return {"success": False, "error": "Email already registered"}
    if roll_number and db.query(User).filter(User.roll_number == roll_number).first():
        return {"success": False, "error": "Roll number already registered"}

    user = User(
        email=email,
        name=name,
        roll_number=roll_number,
        branch=branch,
        batch=batch,
        phone=phone,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()  # populate user.id before using it in UserRole

    # Assign default student role
    student_role = db.query(Role).filter(Role.name == "student").first()
    if student_role:
        db.add(UserRole(user_id=user.id, role_id=student_role.id))

    db.commit()
    db.refresh(user)
    logger.info(f"User registered: {email} ({roll_number})")

    bus.publish(create_event(
        EventType.USER_REGISTERED,
        source_agent="DATABASE_AGENT",
        entity_id=user.id,
        payload={"email": email, "name": name, "branch": branch, "batch": batch},
    ))

    token = create_access_token({"sub": user.id, "email": user.email, "name": user.name})
    return {"success": True, "token": token, "user": _user_dict(user)}


# ── Login ─────────────────────────────────────────────────────────────────────

def login_user(db: Session, email: str, password: str) -> Dict[str, Any]:
    """Authenticate and return JWT token."""
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_password(password, user.password_hash):
        return {"success": False, "error": "Invalid credentials"}

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    roles = [ur.role.name for ur in user.roles if ur.role]
    token = create_access_token({
        "sub":   user.id,
        "email": user.email,
        "name":  user.name,
        "roles": roles,
    })
    logger.info(f"User logged in: {email}")
    bus.publish(create_event(
        EventType.USER_LOGIN,
        source_agent="DATABASE_AGENT",
        entity_id=user.id,
        payload={"email": email},
    ))
    return {"success": True, "token": token, "user": _user_dict(user), "roles": roles}


# ── Token Validation ──────────────────────────────────────────────────────────

def get_current_user(db: Session, token: str) -> Optional[User]:
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def get_user_roles(db: Session, user_id: str) -> list:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []
    return [ur.role.name for ur in user.roles if ur.role]


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _user_dict(user: User) -> Dict[str, Any]:
    return {
        "id":          user.id,
        "email":       user.email,
        "name":        user.name,
        "roll_number": user.roll_number,
        "branch":      user.branch,
        "batch":       user.batch,
        "is_active":   user.is_active,
    }
