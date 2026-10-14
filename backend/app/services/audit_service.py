import json
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import AuditLog

logger = logging.getLogger(__name__)


def create_audit_log(
    db: Session,
    action: str,
    entity_type: str,
    actor_user_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """
    Records an administrative or sensitive action to the immutable audit log.
    Strictly prevents saving passwords, tokens, or private medical details.
    """
    safe_metadata = {}
    if metadata:
        # Strip potential sensitive keys
        sanitized = {k: v for k, v in metadata.items() if k not in {"password", "token", "password_hash", "access_token", "jwt"}}
        safe_metadata = sanitized

    log_entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=json.dumps(safe_metadata)
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"[AUDIT] Action '{action}' on '{entity_type}:{entity_id}' by '{actor_user_id}'")
    return log_entry
