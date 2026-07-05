import uuid
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from database.models import DetectionResult, UserBanRecord
from utils.logger import setup_logger

logger = setup_logger()


class AppealContextService:
    """Collects user context for appeal review."""

    async def gather_user_context(
        self,
        application_id: str,
        user_id: Optional[str],
        db: Session,
    ) -> dict:
        context = {
            "recent_requests": [],
            "ban_history": [],
        }

        if not user_id:
            return context

        try:
            app_uuid = uuid.UUID(application_id)

            recent_detections = (
                db.query(DetectionResult)
                .filter(
                    DetectionResult.application_id == app_uuid,
                    DetectionResult.user_id == user_id,
                )
                .order_by(desc(DetectionResult.created_at))
                .limit(10)
                .all()
            )

            for detection in recent_detections:
                context["recent_requests"].append({
                    "request_id": detection.request_id,
                    "content": detection.content[:200] + "..."
                    if len(detection.content) > 200
                    else detection.content,
                    "security_risk": detection.security_risk_level,
                    "compliance_risk": detection.compliance_risk_level,
                    "data_risk": detection.data_risk_level,
                    "action": detection.suggest_action,
                    "created_at": detection.created_at.isoformat() if detection.created_at else None,
                })

            ban_records = (
                db.query(UserBanRecord)
                .filter(
                    UserBanRecord.application_id == app_uuid,
                    UserBanRecord.user_id == user_id,
                )
                .order_by(desc(UserBanRecord.created_at))
                .limit(5)
                .all()
            )

            for ban in ban_records:
                context["ban_history"].append({
                    "banned_at": ban.banned_at.isoformat() if ban.banned_at else None,
                    "ban_until": ban.ban_until.isoformat() if ban.ban_until else None,
                    "risk_level": ban.risk_level,
                    "reason": ban.reason,
                    "is_active": ban.is_active,
                })
        except Exception as exc:
            logger.error(f"Failed to gather user context: {exc}")

        return context
