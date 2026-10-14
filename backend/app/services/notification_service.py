import logging
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import Notification
from app.config import settings

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    user_id: str,
    title: str,
    message: str,
    notification_type: str,
    related_request_id: Optional[str] = None
) -> Notification:
    """
    Creates an in-app notification with duplicate prevention for unread notices.
    """
    # Prevent duplicate identical notifications if already unread
    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.title == title,
            Notification.notification_type == notification_type,
            Notification.related_request_id == related_request_id,
            Notification.is_read == False
        )
        .first()
    )
    if existing:
        return existing

    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_request_id=related_request_id,
        is_read=False
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    # Optional SMTP Dispatch logging
    if settings.SMTP_HOST and settings.SMTP_USERNAME:
        logger.info(f"[EMAIL DISPATCH] Queued email notification to user {user_id}: {title}")
    else:
        logger.debug(f"[IN-APP NOTIF] Generated notification for user {user_id}: {title}")

    return notif
