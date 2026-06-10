"""
agents/admin_agent/role_manager.py
Role Management Service — Agent 2
"""

from typing import List, Dict
from agents.database_agent.db_service import get_db_session
from agents.database_agent.models import User, Role, UserRole
from agents.database_agent.permissions import assign_role, is_admin
from shared.logging.logger import get_admin_logger

logger = get_admin_logger()


def list_all_users_with_roles() -> List[Dict]:
    from sqlalchemy.orm import joinedload
    db = get_db_session()
    users = (
        db.query(User)
        .options(joinedload(User.roles).joinedload(UserRole.role))
        .filter(User.is_active == True)
        .all()
    )
    result = []
    for u in users:
        roles = [ur.role.name for ur in u.roles if ur.role]
        result.append({
            "id":          u.id,
            "name":        u.name,
            "email":       u.email,
            "roll_number": u.roll_number or "—",
            "branch":      u.branch or "—",
            "batch":       u.batch or "—",
            "roles":       roles,
        })
    db.close()
    return result


def assign_scorer_to_match(admin_id: str, scorer_user_id: str, match_id: str) -> bool:
    from agents.database_agent.models import Match
    db = get_db_session()
    if not is_admin(db, admin_id):
        db.close()
        raise PermissionError("Admin access required")
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        db.close()
        return False
    match.scorer_id = scorer_user_id
    db.commit()
    db.close()
    logger.info(f"Scorer {scorer_user_id} assigned to match {match_id}")
    return True


def revoke_role(admin_id: str, target_user_id: str, role_name: str, context_id: str = None) -> bool:
    db = get_db_session()
    if not is_admin(db, admin_id):
        db.close()
        raise PermissionError("Admin access required")
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        db.close()
        return False
    q = db.query(UserRole).filter(
        UserRole.user_id == target_user_id,
        UserRole.role_id == role.id,
    )
    if context_id:
        q = q.filter(UserRole.context_id == context_id)
    q.delete()
    db.commit()
    db.close()
    logger.info(f"Role '{role_name}' revoked from user {target_user_id}")
    return True
