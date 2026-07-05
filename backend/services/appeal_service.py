"""False-positive appeal orchestration."""

import uuid  # fcg-rewrite
from datetime import datetime, timezone  # fcg-rewrite
from typing import Optional  # fcg-rewrite

from sqlalchemy import desc  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite
from sqlalchemy.orm.attributes import flag_modified  # fcg-rewrite

from database.connection import get_db_session  # fcg-rewrite
from database.models import AppealConfig, AppealRecord, Application, DetectionResult, Whitelist  # fcg-rewrite
from services.appeal_context_service import AppealContextService  # fcg-rewrite
from services.appeal_review_engine import AppealReviewEngine, compute_content_hash, t  # fcg-rewrite
from services.appeal_whitelist_service import AppealWhitelistService  # fcg-rewrite
from services.keyword_cache import keyword_cache  # fcg-rewrite
from utils.email import send_appeal_review_email  # fcg-rewrite
from utils.i18n_loader import get_translation  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
_RISK_ORDER = ("high_risk", "medium_risk", "low_risk", "no_risk")  # fcg-rewrite


class AppealReviewer:  # fcg-rewrite
    def __init__(self):  # fcg-rewrite
        self.context_service = AppealContextService()  # fcg-rewrite
        self.review_engine = AppealReviewEngine()  # fcg-rewrite
        self.whitelist_service = AppealWhitelistService()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _open_session(db: Session):  # fcg-rewrite
        return (db, False) if db is not None else (get_db_session(), True)  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _serialize_config(config: AppealConfig) -> Optional[dict]:  # fcg-rewrite
        if not config:  # fcg-rewrite
            return None  # fcg-rewrite
        return {  # fcg-rewrite
            "id": str(config.id), "enabled": config.enabled,  # fcg-rewrite
            "message_template": config.message_template, "appeal_base_url": config.appeal_base_url,  # fcg-rewrite
            "final_reviewer_email": config.final_reviewer_email,  # fcg-rewrite
            "created_at": config.created_at.isoformat() if config.created_at else None,  # fcg-rewrite
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,  # fcg-rewrite
        }

    async def get_config(self, application_id: str, db: Session = None) -> Optional[dict]:  # fcg-rewrite
        db, owned = self._open_session(db)  # fcg-rewrite
        try:
            return self._serialize_config(await self.get_config_with_db(application_id, db))  # fcg-rewrite
        finally:  # fcg-rewrite
            if owned:  # fcg-rewrite
                db.close()  # fcg-rewrite

    async def get_config_with_db(self, application_id: str, db: Session) -> Optional[AppealConfig]:  # fcg-rewrite
        return db.query(AppealConfig).filter(AppealConfig.application_id == uuid.UUID(application_id)).first()  # fcg-rewrite

    async def update_config(self, application_id: str, tenant_id: str, config_data: dict, db: Session = None) -> dict:  # fcg-rewrite
        db, owned = self._open_session(db)  # fcg-rewrite
        try:
            config = await self.get_config_with_db(application_id, db)  # fcg-rewrite
            if not config:  # fcg-rewrite
                config = AppealConfig(  # fcg-rewrite
                    tenant_id=uuid.UUID(tenant_id), application_id=uuid.UUID(application_id),  # fcg-rewrite
                    enabled=config_data.get("enabled", False),  # fcg-rewrite
                    message_template=config_data.get("message_template")  # fcg-rewrite
                    or get_translation("en", "appealPage", "defaultMessageTemplate"),  # fcg-rewrite
                    appeal_base_url=config_data.get("appeal_base_url", ""),  # fcg-rewrite
                    final_reviewer_email=config_data.get("final_reviewer_email"),  # fcg-rewrite
                )
                db.add(config)  # fcg-rewrite
            else:
                for field in ("enabled", "message_template", "appeal_base_url", "final_reviewer_email"):  # fcg-rewrite
                    if field in config_data:  # fcg-rewrite
                        setattr(config, field, config_data[field])  # fcg-rewrite
            db.commit()  # fcg-rewrite
            db.refresh(config)  # fcg-rewrite
            return self._serialize_config(config)  # fcg-rewrite
        finally:  # fcg-rewrite
            if owned:  # fcg-rewrite
                db.close()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _existing_response(record: AppealRecord, language: str, reviewer: Optional[str]) -> dict:  # fcg-rewrite
        if record.status == "approved":  # fcg-rewrite
            return {"success": True, "already_processed": True, "status": "approved", "message": t(language, "alreadyApproved")}  # fcg-rewrite
        result = {"success": False, "already_processed": True, "status": record.status}  # fcg-rewrite
        if record.status == "rejected":  # fcg-rewrite
            result.update(message=t(language, "alreadyRejected"), reason=record.ai_review_result or record.processor_reason)  # fcg-rewrite
        elif record.status == "pending_review":  # fcg-rewrite
            result.update(message=t(language, "pendingReviewMessage"), final_reviewer_email=reviewer)  # fcg-rewrite
        else:
            result["message"] = t(language, "processingMessage")  # fcg-rewrite
        return result  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _categories(detection) -> list:  # fcg-rewrite
        fields = ("security_categories", "compliance_categories", "data_categories")  # fcg-rewrite
        return [category for field in fields for category in (getattr(detection, field, None) or [])]  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _risk_level(detection) -> str:  # fcg-rewrite
        levels = [  # fcg-rewrite
            getattr(detection, field, None)  # fcg-rewrite
            for field in ("security_risk_level", "compliance_risk_level", "data_risk_level")  # fcg-rewrite
        ]
        return min((level for level in levels if level in _RISK_ORDER), key=_RISK_ORDER.index, default="no_risk")  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _duplicate_content_response(record: AppealRecord, config: dict, language: str) -> dict:  # fcg-rewrite
        status_key = {  # fcg-rewrite
            "approved": "duplicateApproved", "rejected": "duplicateRejected",  # fcg-rewrite
            "pending_review": "duplicatePendingReview",  # fcg-rewrite
        }.get(record.status, "duplicateProcessing")  # fcg-rewrite
        return {  # fcg-rewrite
            "success": False, "error": "duplicate_content", "status": record.status,  # fcg-rewrite
            "message": f"{t(language, 'duplicateContent')}，{t(language, status_key)}",  # fcg-rewrite
            "previous_appeal_id": str(record.id), "previous_request_id": record.request_id,  # fcg-rewrite
            "final_reviewer_email": config.get("final_reviewer_email") if record.status == "pending_review" else None,  # fcg-rewrite
        }

    async def process_appeal(  # fcg-rewrite
        self, request_id: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None,  # fcg-rewrite
        language: str = "zh", db: Session = None,  # fcg-rewrite
    ) -> dict:  # fcg-rewrite
        db, owned = self._open_session(db)  # fcg-rewrite
        try:
            detection = db.query(DetectionResult).filter(DetectionResult.request_id == request_id).first()  # fcg-rewrite
            if not detection:  # fcg-rewrite
                return {"success": False, "error": "detection_not_found", "message": t(language, "detectionNotFound")}  # fcg-rewrite
            application_id, tenant_id = str(detection.application_id), str(detection.tenant_id)  # fcg-rewrite
            config = await self.get_config(application_id, db)  # fcg-rewrite
            if not config or not config.get("enabled"):  # fcg-rewrite
                return {"success": False, "error": "appeal_disabled", "message": t(language, "appealDisabled")}  # fcg-rewrite
            existing = db.query(AppealRecord).filter(AppealRecord.request_id == request_id).first()  # fcg-rewrite
            if existing:  # fcg-rewrite
                return self._existing_response(existing, language, config.get("final_reviewer_email"))  # fcg-rewrite
            content_hash = compute_content_hash(detection.content)  # fcg-rewrite
            duplicate = db.query(AppealRecord).filter(  # fcg-rewrite
                AppealRecord.application_id == uuid.UUID(application_id),  # fcg-rewrite
                AppealRecord.content_hash == content_hash, AppealRecord.request_id != request_id,  # fcg-rewrite
            ).first()  # fcg-rewrite
            if duplicate:  # fcg-rewrite
                return self._duplicate_content_response(duplicate, config, language)  # fcg-rewrite
            user_id = getattr(detection, "user_id", None)  # fcg-rewrite
            context = await self._gather_user_context(application_id, user_id, db)  # fcg-rewrite
            categories, risk = self._categories(detection), self._risk_level(detection)  # fcg-rewrite
            record = AppealRecord(  # fcg-rewrite
                tenant_id=uuid.UUID(tenant_id), application_id=uuid.UUID(application_id),  # fcg-rewrite
                request_id=request_id, user_id=user_id, original_content=detection.content,  # fcg-rewrite
                original_risk_level=risk, original_categories=categories,  # fcg-rewrite
                original_suggest_action=detection.suggest_action or "unknown", status="reviewing",  # fcg-rewrite
                user_recent_requests=context.get("recent_requests"), user_ban_history=context.get("ban_history"),  # fcg-rewrite
                ip_address=ip_address, user_agent=user_agent, content_hash=content_hash,  # fcg-rewrite
            )
            db.add(record)  # fcg-rewrite
            db.commit()  # fcg-rewrite
            try:
                approved, reasoning = await self._ai_review_appeal(  # fcg-rewrite
                    detection.content, categories, risk, detection.suggest_action, context, language  # fcg-rewrite
                )
            except Exception as error:  # fcg-rewrite
                record.status, record.ai_review_result = "pending", f"AI审核失败: {error}"  # fcg-rewrite
                db.commit()  # fcg-rewrite
                return {"success": False, "error": "ai_review_failed", "message": t(language, "aiReviewFailed")}  # fcg-rewrite
            now = datetime.now(timezone.utc)  # fcg-rewrite
            record.ai_approved, record.ai_review_result, record.ai_reviewed_at = approved, reasoning, now  # fcg-rewrite
            if approved:  # fcg-rewrite
                await self._approve_record(record, application_id, tenant_id, detection.content, language, db, "agent")  # fcg-rewrite
                return {"success": True, "status": "approved", "message": t(language, "approvedMessage"), "reason": reasoning}  # fcg-rewrite
            return self._reject_or_escalate(record, config, context, request_id, user_id, detection.content, risk, categories, reasoning, language, db, now)  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Appeal processing failed: %s", error)  # fcg-rewrite
            return {"success": False, "error": "processing_error", "message": t(language, "systemError")}  # fcg-rewrite
        finally:  # fcg-rewrite
            if owned:  # fcg-rewrite
                db.close()  # fcg-rewrite

    async def _approve_record(self, record, application_id, tenant_id, content, language, db, processor):  # fcg-rewrite
        try:
            record.whitelist_id, record.whitelist_keyword = await self._add_to_appeal_whitelist(  # fcg-rewrite
                application_id, tenant_id, content, language, db  # fcg-rewrite
            )
        except Exception as error:  # fcg-rewrite
            logger.error("Unable to update appeal whitelist: %s", error)  # fcg-rewrite
            record.ai_review_result = f"{record.ai_review_result or ''}\n\nWhitelist update failed: {error}"  # fcg-rewrite
        record.status, record.processor_type, record.processed_at = "approved", processor, datetime.now(timezone.utc)  # fcg-rewrite
        db.commit()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _reject_or_escalate(record, config, context, request_id, user_id, content, risk, categories, reasoning, language, db, now):  # fcg-rewrite
        reviewer = config.get("final_reviewer_email")  # fcg-rewrite
        if not reviewer:  # fcg-rewrite
            record.status, record.processor_type, record.processed_at = "rejected", "agent", now  # fcg-rewrite
            db.commit()  # fcg-rewrite
            return {"success": False, "status": "rejected", "message": t(language, "rejectedMessage"), "reason": reasoning}  # fcg-rewrite
        record.status = "pending_review"  # fcg-rewrite
        try:
            send_appeal_review_email(  # fcg-rewrite
                to_email=reviewer,  # fcg-rewrite
                appeal_data={  # fcg-rewrite
                    "request_id": request_id, "user_id": user_id, "original_content": content,  # fcg-rewrite
                    "original_risk_level": risk, "original_categories": categories,  # fcg-rewrite
                    "ai_approved": False, "ai_review_result": reasoning,  # fcg-rewrite
                },
                user_context=context, language="zh",  # fcg-rewrite
            )
        except Exception as error:  # fcg-rewrite
            logger.error("Unable to notify appeal reviewer: %s", error)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        return {  # fcg-rewrite
            "success": False, "status": "pending_review", "message": t(language, "pendingReviewAiRejected"),  # fcg-rewrite
            "reason": reasoning, "final_reviewer_email": reviewer,  # fcg-rewrite
        }

    async def _gather_user_context(self, application_id: str, user_id: Optional[str], db: Session) -> dict:  # fcg-rewrite
        return await self.context_service.gather_user_context(application_id, user_id, db)  # fcg-rewrite

    async def _ai_review_appeal(self, original_content, categories, risk_level, suggest_action, user_context, language="zh"):  # fcg-rewrite
        return await self.review_engine.review_appeal(original_content, categories, risk_level, suggest_action, user_context, language)  # fcg-rewrite

    async def _add_to_appeal_whitelist(self, application_id, tenant_id, content, language, db):  # fcg-rewrite
        return await self.whitelist_service.add_to_appeal_whitelist(application_id, tenant_id, content, language, db)  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _record_item(record, app_names) -> dict:  # fcg-rewrite
        content = record.original_content  # fcg-rewrite
        return {  # fcg-rewrite
            "id": str(record.id), "request_id": record.request_id, "user_id": record.user_id,  # fcg-rewrite
            "application_id": str(record.application_id) if record.application_id else None,  # fcg-rewrite
            "application_name": app_names.get(record.application_id), "original_content": content[:200] + "..." if len(content) > 200 else content,  # fcg-rewrite
            "original_risk_level": record.original_risk_level, "original_categories": record.original_categories,  # fcg-rewrite
            "status": record.status, "ai_approved": record.ai_approved, "ai_review_result": record.ai_review_result,  # fcg-rewrite
            "processor_type": record.processor_type, "processor_id": record.processor_id,  # fcg-rewrite
            "processor_reason": record.processor_reason,  # fcg-rewrite
            "created_at": record.created_at.isoformat() if record.created_at else None,  # fcg-rewrite
            "ai_reviewed_at": record.ai_reviewed_at.isoformat() if record.ai_reviewed_at else None,  # fcg-rewrite
            "processed_at": record.processed_at.isoformat() if record.processed_at else None,  # fcg-rewrite
        }

    async def get_appeal_records(self, application_id: str, status: Optional[str] = None, page: int = 1, page_size: int = 20, db: Session = None) -> dict:  # fcg-rewrite
        db, owned = self._open_session(db)  # fcg-rewrite
        try:
            query = db.query(AppealRecord).filter(AppealRecord.application_id == uuid.UUID(application_id))  # fcg-rewrite
            if status:  # fcg-rewrite
                query = query.filter(AppealRecord.status == status)  # fcg-rewrite
            total = query.count()  # fcg-rewrite
            records = query.order_by(desc(AppealRecord.created_at)).offset((page - 1) * page_size).limit(page_size).all()  # fcg-rewrite
            app_ids = {record.application_id for record in records if record.application_id}  # fcg-rewrite
            names = {app.id: app.name for app in db.query(Application).filter(Application.id.in_(app_ids)).all()} if app_ids else {}  # fcg-rewrite
            return {"items": [self._record_item(record, names) for record in records], "total": total, "page": page, "page_size": page_size, "pages": (total + page_size - 1) // page_size}  # fcg-rewrite
        finally:  # fcg-rewrite
            if owned:  # fcg-rewrite
                db.close()  # fcg-rewrite

    async def manual_review_appeal(self, appeal_id: str, action: str, reviewer_email: str, reason: Optional[str] = None, language: str = "zh", db: Session = None) -> dict:  # fcg-rewrite
        db, owned = self._open_session(db)  # fcg-rewrite
        try:
            record = db.query(AppealRecord).filter(AppealRecord.id == uuid.UUID(appeal_id)).first()  # fcg-rewrite
            if not record:  # fcg-rewrite
                return {"success": False, "error": "appeal_not_found", "message": "Appeal record not found"}  # fcg-rewrite
            reviewer = reviewer_email.split("@")[0]  # fcg-rewrite
            if action == "approve":  # fcg-rewrite
                await self._approve_record(record, str(record.application_id), str(record.tenant_id), record.original_content, language, db, "human")  # fcg-rewrite
                record.processor_id, record.processor_reason = reviewer, reason  # fcg-rewrite
                db.commit()  # fcg-rewrite
                return {"success": True, "status": "approved", "message": "Appeal approved and content added to whitelist"}  # fcg-rewrite
            if action != "reject":  # fcg-rewrite
                return {"success": False, "error": "invalid_action", "message": f"Invalid action: {action}. Must be 'approve' or 'reject'"}  # fcg-rewrite
            if record.status == "approved" and record.whitelist_id:  # fcg-rewrite
                whitelist = db.query(Whitelist).filter(Whitelist.id == record.whitelist_id).first()  # fcg-rewrite
                if whitelist and record.whitelist_keyword in (whitelist.keywords or []):  # fcg-rewrite
                    whitelist.keywords.remove(record.whitelist_keyword)  # fcg-rewrite
                    flag_modified(whitelist, "keywords")  # fcg-rewrite
                    await keyword_cache.invalidate_cache()  # fcg-rewrite
            record.status, record.processor_type, record.processor_id = "rejected", "human", reviewer  # fcg-rewrite
            record.processor_reason, record.processed_at = reason, datetime.now(timezone.utc)  # fcg-rewrite
            record.whitelist_id, record.whitelist_keyword = None, None  # fcg-rewrite
            db.commit()  # fcg-rewrite
            return {"success": True, "status": "rejected", "message": "Appeal rejected"}  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Manual appeal review failed: %s", error)  # fcg-rewrite
            return {"success": False, "error": "processing_error", "message": f"Error processing manual review: {error}"}  # fcg-rewrite
        finally:  # fcg-rewrite
            if owned:  # fcg-rewrite
                db.close()  # fcg-rewrite

    async def generate_appeal_link(self, request_id: str, application_id: str, language: str = "zh", db: Session = None) -> Optional[str]:  # fcg-rewrite
        config = await self.get_config(application_id, db)  # fcg-rewrite
        base = (config or {}).get("appeal_base_url", "").rstrip("/")  # fcg-rewrite
        if not config or not config.get("enabled") or not base:  # fcg-rewrite
            return None  # fcg-rewrite
        url = f"{base}/v1/appeal/{request_id}?lang={language}"  # fcg-rewrite
        template = config.get("message_template") or "If you think this is a false positive, please click the following link to appeal: {appeal_url}"  # fcg-rewrite
        return template.replace("{appeal_url}", url)  # fcg-rewrite


appeal_service = AppealReviewer()  # fcg-rewrite
