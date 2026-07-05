"""Application-aware user ban policy persistence and enforcement."""

import logging  # fcg-rewrite
import uuid  # fcg-rewrite
from datetime import datetime, timedelta, timezone  # fcg-rewrite
from typing import Any, Dict, List, Optional  # fcg-rewrite

from sqlalchemy import text  # fcg-rewrite

from database.connection import get_admin_db_session  # fcg-rewrite
from utils.i18n import format_ban_reason  # fcg-rewrite

logger = logging.getLogger(__name__)  # fcg-rewrite
_RISK_SCORE = {"low_risk": 1, "medium_risk": 2, "high_risk": 3}  # fcg-rewrite
_RISK_ALIASES = {"低风险": "low_risk", "中风险": "medium_risk", "高风险": "high_risk"}  # fcg-rewrite
_POLICY_COLUMNS = (  # fcg-rewrite
    "id",
    "tenant_id",  # fcg-rewrite
    "application_id",  # fcg-rewrite
    "enabled",  # fcg-rewrite
    "risk_level",  # fcg-rewrite
    "trigger_count",  # fcg-rewrite
    "time_window_minutes",  # fcg-rewrite
    "ban_duration_minutes",  # fcg-rewrite
    "created_at",  # fcg-rewrite
    "updated_at",  # fcg-rewrite
)
_BAN_COLUMNS = (  # fcg-rewrite
    "id",
    "user_id",  # fcg-rewrite
    "banned_at",  # fcg-rewrite
    "ban_until",  # fcg-rewrite
    "trigger_count",  # fcg-rewrite
    "risk_level",  # fcg-rewrite
    "reason",  # fcg-rewrite
)


def utcnow():  # fcg-rewrite
    return datetime.now(timezone.utc)  # fcg-rewrite


def _record(columns, row) -> Optional[Dict[str, Any]]:  # fcg-rewrite
    if not row:  # fcg-rewrite
        return None  # fcg-rewrite
    result = dict(zip(columns, row))  # fcg-rewrite
    if "id" in result:  # fcg-rewrite
        result["id"] = str(result["id"])  # fcg-rewrite
    for key in ("tenant_id", "application_id", "detection_result_id"):  # fcg-rewrite
        if result.get(key) is not None:  # fcg-rewrite
            result[key] = str(result[key])  # fcg-rewrite
    return result  # fcg-rewrite


def _risk_level(value: str) -> str:  # fcg-rewrite
    return _RISK_ALIASES.get(value, value)  # fcg-rewrite


class BanPolicyManager:  # fcg-rewrite
    @staticmethod  # fcg-rewrite
    async def get_ban_policy(application_id: str) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        db = get_admin_db_session()  # fcg-rewrite
        try:
            row = db.execute(  # fcg-rewrite
                text(
                    """
                    SELECT id, tenant_id, application_id, enabled, risk_level,
                           trigger_count, time_window_minutes, ban_duration_minutes,
                           created_at, updated_at
                    FROM ban_policies WHERE application_id = :application_id
                    """
                ),
                {"application_id": application_id},  # fcg-rewrite
            ).fetchone()  # fcg-rewrite
            return _record(_POLICY_COLUMNS, row)  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    async def update_ban_policy(  # fcg-rewrite
        application_id: str, policy_data: Dict[str, Any]  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        db = get_admin_db_session()  # fcg-rewrite
        values = {  # fcg-rewrite
            "application_id": application_id,  # fcg-rewrite
            "enabled": policy_data.get("enabled", False),  # fcg-rewrite
            "risk_level": _risk_level(policy_data.get("risk_level", "high_risk")),  # fcg-rewrite
            "trigger_count": policy_data.get("trigger_count", 3),  # fcg-rewrite
            "time_window_minutes": policy_data.get("time_window_minutes", 10),  # fcg-rewrite
            "ban_duration_minutes": policy_data.get("ban_duration_minutes", 60),  # fcg-rewrite
        }
        try:
            app = db.execute(  # fcg-rewrite
                text("SELECT tenant_id FROM applications WHERE id = :application_id"),  # fcg-rewrite
                {"application_id": application_id},  # fcg-rewrite
            ).fetchone()  # fcg-rewrite
            if not app:  # fcg-rewrite
                raise ValueError(f"Application {application_id} not found")  # fcg-rewrite
            values["tenant_id"] = str(app[0])  # fcg-rewrite
            existing = db.execute(  # fcg-rewrite
                text("SELECT id FROM ban_policies WHERE application_id = :application_id"),  # fcg-rewrite
                {"application_id": application_id},  # fcg-rewrite
            ).fetchone()  # fcg-rewrite
            if existing:  # fcg-rewrite
                statement = """
                    UPDATE ban_policies SET enabled=:enabled, risk_level=:risk_level,
                        trigger_count=:trigger_count, time_window_minutes=:time_window_minutes,
                        ban_duration_minutes=:ban_duration_minutes, updated_at=CURRENT_TIMESTAMP
                    WHERE application_id=:application_id
                    RETURNING id, tenant_id, application_id, enabled, risk_level,
                        trigger_count, time_window_minutes, ban_duration_minutes,
                        created_at, updated_at
                """
            else:
                values["id"] = str(uuid.uuid4())  # fcg-rewrite
                statement = """
                    INSERT INTO ban_policies (
                        id, tenant_id, application_id, enabled, risk_level,
                        trigger_count, time_window_minutes, ban_duration_minutes
                    ) VALUES (
                        :id, :tenant_id, :application_id, :enabled, :risk_level,
                        :trigger_count, :time_window_minutes, :ban_duration_minutes
                    ) RETURNING id, tenant_id, application_id, enabled, risk_level,
                        trigger_count, time_window_minutes, ban_duration_minutes,
                        created_at, updated_at
                """
            row = db.execute(text(statement), values).fetchone()  # fcg-rewrite
            db.commit()  # fcg-rewrite
            return _record(_POLICY_COLUMNS, row)  # fcg-rewrite
        except Exception:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            raise
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    async def check_user_banned(scope_id: str, user_id: str) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        db = get_admin_db_session()  # fcg-rewrite
        try:
            row = db.execute(  # fcg-rewrite
                text(
                    """
                    SELECT id, user_id, banned_at, ban_until, trigger_count, risk_level, reason
                    FROM user_ban_records
                    WHERE (application_id = :scope_id OR tenant_id = :scope_id)
                      AND user_id = :user_id AND is_active = true
                      AND ban_until > CURRENT_TIMESTAMP
                    ORDER BY banned_at DESC LIMIT 1
                    """
                ),
                {"scope_id": scope_id, "user_id": user_id},  # fcg-rewrite
            ).fetchone()  # fcg-rewrite
            return _record(_BAN_COLUMNS, row)  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    async def check_ip_banned(tenant_id: str, ip_address: str) -> None:  # fcg-rewrite
        # The current schema has no IP-ban records. Keep the gateway hook explicit.
        return None  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    async def check_and_apply_ban_policy(  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        user_id: str,  # fcg-rewrite
        risk_level: str,  # fcg-rewrite
        detection_result_id: Optional[str] = None,  # fcg-rewrite
        language: str = "zh",  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
    ) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        if not user_id:  # fcg-rewrite
            return None  # fcg-rewrite
        db = get_admin_db_session()  # fcg-rewrite
        try:
            application_id = application_id or BanPolicyManager._default_application(  # fcg-rewrite
                db, tenant_id  # fcg-rewrite
            )
            policy = db.execute(  # fcg-rewrite
                text(
                    """
                    SELECT enabled, risk_level, trigger_count,
                           time_window_minutes, ban_duration_minutes
                    FROM ban_policies
                    WHERE (:application_id IS NOT NULL AND application_id = :application_id)
                       OR tenant_id = :tenant_id
                    ORDER BY CASE WHEN application_id = :application_id THEN 0 ELSE 1 END
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "application_id": application_id},  # fcg-rewrite
            ).fetchone()  # fcg-rewrite
            if not policy or not policy[0]:  # fcg-rewrite
                return None  # fcg-rewrite
            policy_risk = _risk_level(policy[1])  # fcg-rewrite
            current_risk = _risk_level(risk_level)  # fcg-rewrite
            if _RISK_SCORE.get(current_risk, 0) < _RISK_SCORE.get(policy_risk, 3):  # fcg-rewrite
                return None  # fcg-rewrite
            db.execute(  # fcg-rewrite
                text(
                    """
                    INSERT INTO user_risk_triggers (
                        id, tenant_id, application_id, user_id,
                        detection_result_id, risk_level, triggered_at
                    ) VALUES (
                        :id, :tenant_id, :application_id, :user_id,
                        :detection_result_id, :risk_level, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),  # fcg-rewrite
                    "tenant_id": tenant_id,  # fcg-rewrite
                    "application_id": application_id,  # fcg-rewrite
                    "user_id": user_id,  # fcg-rewrite
                    "detection_result_id": detection_result_id,  # fcg-rewrite
                    "risk_level": current_risk,  # fcg-rewrite
                },
            )
            db.commit()  # fcg-rewrite
            count = db.execute(  # fcg-rewrite
                text(
                    """
                    SELECT COUNT(*) FROM user_risk_triggers
                    WHERE tenant_id=:tenant_id AND user_id=:user_id
                      AND application_id=:application_id
                      AND triggered_at > :window_start
                    """
                ),
                {
                    "tenant_id": tenant_id,  # fcg-rewrite
                    "application_id": application_id,  # fcg-rewrite
                    "user_id": user_id,  # fcg-rewrite
                    "window_start": utcnow() - timedelta(minutes=policy[3]),  # fcg-rewrite
                },
            ).scalar()  # fcg-rewrite
            if count < policy[2] or BanPolicyManager._has_active_ban(  # fcg-rewrite
                db, tenant_id, application_id, user_id  # fcg-rewrite
            ):
                return None  # fcg-rewrite
            reason = format_ban_reason(policy[3], count, policy_risk, language)  # fcg-rewrite
            row = db.execute(  # fcg-rewrite
                text(
                    """
                    INSERT INTO user_ban_records (
                        tenant_id, application_id, user_id, banned_at, ban_until,
                        trigger_count, risk_level, reason, is_active
                    ) VALUES (
                        :tenant_id, :application_id, :user_id, CURRENT_TIMESTAMP,
                        :ban_until, :trigger_count, :risk_level, :reason, true
                    ) RETURNING id, user_id, banned_at, ban_until,
                        trigger_count, risk_level, reason
                    """
                ),
                {
                    "tenant_id": tenant_id,  # fcg-rewrite
                    "application_id": application_id,  # fcg-rewrite
                    "user_id": user_id,  # fcg-rewrite
                    "ban_until": utcnow() + timedelta(minutes=policy[4]),  # fcg-rewrite
                    "trigger_count": count,  # fcg-rewrite
                    "risk_level": policy_risk,  # fcg-rewrite
                    "reason": reason,  # fcg-rewrite
                },
            ).fetchone()  # fcg-rewrite
            db.commit()  # fcg-rewrite
            return _record(_BAN_COLUMNS, row)  # fcg-rewrite
        except Exception:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            raise
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    async def get_banned_users(  # fcg-rewrite
        application_id: str, skip: int = 0, limit: int = 100  # fcg-rewrite
    ) -> List[Dict[str, Any]]:  # fcg-rewrite
        db = get_admin_db_session()  # fcg-rewrite
        try:
            rows = db.execute(  # fcg-rewrite
                text(
                    """
                    SELECT id, user_id, banned_at, ban_until, trigger_count,
                           risk_level, reason, is_active,
                           CASE WHEN ban_until > CURRENT_TIMESTAMP
                                THEN 'banned' ELSE 'unbanned' END
                    FROM user_ban_records WHERE application_id=:application_id
                    ORDER BY banned_at DESC LIMIT :limit OFFSET :skip
                    """
                ),
                {"application_id": application_id, "skip": skip, "limit": limit},  # fcg-rewrite
            ).fetchall()  # fcg-rewrite
            columns = _BAN_COLUMNS + ("is_active", "status")  # fcg-rewrite
            return [_record(columns, row) for row in rows]  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    async def unban_user(application_id: str, user_id: str) -> bool:  # fcg-rewrite
        db = get_admin_db_session()  # fcg-rewrite
        try:
            result = db.execute(  # fcg-rewrite
                text(
                    """
                    UPDATE user_ban_records SET is_active=false, ban_until=CURRENT_TIMESTAMP
                    WHERE application_id=:application_id AND user_id=:user_id
                      AND is_active=true
                    """
                ),
                {"application_id": application_id, "user_id": user_id},  # fcg-rewrite
            )
            db.commit()  # fcg-rewrite
            return result.rowcount > 0  # fcg-rewrite
        except Exception:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            raise
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    async def get_user_risk_history(  # fcg-rewrite
        application_id: str, user_id: str, days: int = 7  # fcg-rewrite
    ) -> List[Dict[str, Any]]:  # fcg-rewrite
        db = get_admin_db_session()  # fcg-rewrite
        try:
            rows = db.execute(  # fcg-rewrite
                text(
                    """
                    SELECT id, detection_result_id, risk_level, triggered_at
                    FROM user_risk_triggers
                    WHERE application_id=:application_id AND user_id=:user_id
                      AND triggered_at > :since ORDER BY triggered_at DESC
                    """
                ),
                {
                    "application_id": application_id,  # fcg-rewrite
                    "user_id": user_id,  # fcg-rewrite
                    "since": utcnow() - timedelta(days=days),  # fcg-rewrite
                },
            ).fetchall()  # fcg-rewrite
            return [  # fcg-rewrite
                _record(("id", "detection_result_id", "risk_level", "triggered_at"), row)  # fcg-rewrite
                for row in rows  # fcg-rewrite
            ]
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _default_application(db, tenant_id: str) -> Optional[str]:  # fcg-rewrite
        from database.models import Application  # fcg-rewrite

        application = db.query(Application).filter(  # fcg-rewrite
            Application.tenant_id == tenant_id,  # fcg-rewrite
            Application.name == "Default Application",  # fcg-rewrite
        ).first()  # fcg-rewrite
        return str(application.id) if application else None  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _has_active_ban(db, tenant_id: str, application_id: str, user_id: str) -> bool:  # fcg-rewrite
        return bool(  # fcg-rewrite
            db.execute(  # fcg-rewrite
                text(
                    """
                    SELECT id FROM user_ban_records
                    WHERE tenant_id=:tenant_id AND application_id=:application_id
                      AND user_id=:user_id AND is_active=true
                      AND ban_until > CURRENT_TIMESTAMP
                    """
                ),
                {
                    "tenant_id": tenant_id,  # fcg-rewrite
                    "application_id": application_id,  # fcg-rewrite
                    "user_id": user_id,  # fcg-rewrite
                },
            ).fetchone()  # fcg-rewrite
        )
