"""
agents/database_agent/permissions.py
RBAC Permission Enforcement — Agent 1
"""

from typing import Optional
from sqlalchemy.orm import Session

from agents.database_agent.models import User, UserRole, Role
from shared.logging.logger import get_db_logger

logger = get_db_logger()

# ── Permission Matrix ─────────────────────────────────────────────────────────

ROLE_PERMISSIONS = {
    "admin": {
        "tournament": ["create", "read", "update", "delete", "archive"],
        "match":      ["create", "read", "update", "delete", "score", "override"],
        "team":       ["create", "read", "update", "delete"],
        "user":       ["create", "read", "update", "delete", "assign_role"],
        "analytics":  ["read", "export"],
        "venue":      ["create", "read", "update", "delete"],
    },
    "captain": {
        "team":       ["create", "read", "update"],
        "roster":     ["create", "read", "update", "delete"],
        "join_code":  ["create", "read"],
        "match":      ["read"],
        "analytics":  ["read"],
        "tournament": ["read"],
    },
    "scorer": {
        "match":      ["read", "score"],
        "tournament": ["read"],
        "team":       ["read"],
        "analytics":  ["read"],
    },
    "student": {
        "match":      ["read"],
        "tournament": ["read"],
        "team":       ["read", "join"],
        "analytics":  ["read"],
        "roster":     ["read"],
    },
}


def get_user_role_names(db: Session, user_id: str, context_id: Optional[str] = None) -> list:
    """Get all role names for a user, optionally scoped to a context."""
    query = db.query(UserRole).filter(UserRole.user_id == user_id)
    if context_id:
        query = query.filter(
            (UserRole.context_id == context_id) | (UserRole.context_id == None)
        )
    user_roles = query.all()
    return [ur.role.name for ur in user_roles if ur.role]


def has_permission(
    db: Session,
    user_id: str,
    resource: str,
    action: str,
    context_id: Optional[str] = None,
) -> bool:
    """Check if user has permission to perform action on resource."""
    roles = get_user_role_names(db, user_id, context_id)
    for role_name in roles:
        allowed = ROLE_PERMISSIONS.get(role_name, {}).get(resource, [])
        if action in allowed:
            return True
    logger.warning(f"Permission denied: user={user_id} role={roles} {action}:{resource}")
    return False


def require_permission(
    db: Session,
    user_id: str,
    resource: str,
    action: str,
    context_id: Optional[str] = None,
) -> None:
    """Raise PermissionError if user lacks permission."""
    if not has_permission(db, user_id, resource, action, context_id):
        roles = get_user_role_names(db, user_id)
        raise PermissionError(
            f"Role(s) {roles} cannot perform '{action}' on '{resource}'"
        )


def is_admin(db: Session, user_id: str) -> bool:
    return has_permission(db, user_id, "user", "assign_role")


def is_captain(db: Session, user_id: str, team_id: Optional[str] = None) -> bool:
    roles = get_user_role_names(db, user_id, team_id)
    return "captain" in roles or "admin" in roles


def is_scorer(db: Session, user_id: str, match_id: Optional[str] = None) -> bool:
    roles = get_user_role_names(db, user_id, match_id)
    return "scorer" in roles or "admin" in roles


def assign_role(
    db: Session,
    admin_user_id: str,
    target_user_id: str,
    role_name: str,
    context_id: Optional[str] = None,
) -> bool:
    """Assign a role to a user. Only admins can do this."""
    require_permission(db, admin_user_id, "user", "assign_role")
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise ValueError(f"Role '{role_name}' does not exist")

    existing = db.query(UserRole).filter(
        UserRole.user_id == target_user_id,
        UserRole.role_id == role.id,
        UserRole.context_id == context_id,
    ).first()

    if not existing:
        db.add(UserRole(
            user_id=target_user_id,
            role_id=role.id,
            context_id=context_id,
            granted_by=admin_user_id,
        ))
        db.commit()
        logger.info(f"Role '{role_name}' assigned to user {target_user_id}")
        return True
    return False
