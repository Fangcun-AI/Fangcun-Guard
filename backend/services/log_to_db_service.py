"""Incremental JSONL audit-log importer with single-process file locking."""

import asyncio  # fcg-rewrite
import fcntl  # fcg-rewrite
import json  # fcg-rewrite
import pickle  # fcg-rewrite
import uuid  # fcg-rewrite
from datetime import datetime, timezone  # fcg-rewrite
from pathlib import Path  # fcg-rewrite
from typing import Dict, Optional  # fcg-rewrite

from sqlalchemy.orm import Session  # fcg-rewrite

from database.connection import get_admin_db_session  # fcg-rewrite
from database.models import DetectionResult  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class AuditLogWriter:  # fcg-rewrite
    def __init__(self):  # fcg-rewrite
        self.running = False  # fcg-rewrite
        self.task = None  # fcg-rewrite
        self.processed_files: Dict[str, int] = {}  # fcg-rewrite
        self._state_file = None  # fcg-rewrite
        self._lock_file = None  # fcg-rewrite
        self._lock_fd = None  # fcg-rewrite

    async def start(self):  # fcg-rewrite
        if self.running:  # fcg-rewrite
            return
        from config import settings  # fcg-rewrite

        root = Path(settings.data_dir)  # fcg-rewrite
        self._state_file = root / "log_to_db_service_state.pkl"  # fcg-rewrite
        self._lock_file = root / "log_to_db_service.lock"  # fcg-rewrite
        if not self._acquire_lock():  # fcg-rewrite
            return
        await self._load_processed_files_state()  # fcg-rewrite
        self.running = True  # fcg-rewrite
        self.task = asyncio.create_task(self._process_logs_loop())  # fcg-rewrite

    async def stop(self):  # fcg-rewrite
        if not self.running:  # fcg-rewrite
            return
        self.running = False  # fcg-rewrite
        if self.task:  # fcg-rewrite
            self.task.cancel()  # fcg-rewrite
            try:
                await self.task  # fcg-rewrite
            except asyncio.CancelledError:  # fcg-rewrite
                pass
            self.task = None  # fcg-rewrite
        await self._save_processed_files_state()  # fcg-rewrite
        self._release_lock()  # fcg-rewrite

    async def _process_logs_loop(self):  # fcg-rewrite
        while self.running:  # fcg-rewrite
            try:
                await self._process_log_files()  # fcg-rewrite
                await asyncio.sleep(5)  # fcg-rewrite
            except asyncio.CancelledError:  # fcg-rewrite
                return
            except Exception as exc:  # fcg-rewrite
                logger.error(f"Log processing error: {exc}")  # fcg-rewrite
                await asyncio.sleep(60)  # fcg-rewrite

    async def _process_log_files(self):  # fcg-rewrite
        for path in self._log_files():  # fcg-rewrite
            total = self._count_lines(path)  # fcg-rewrite
            offset = self.processed_files.get(path.name, 0)  # fcg-rewrite
            if total > offset:  # fcg-rewrite
                self.processed_files[path.name] = offset + await self._process_single_log_file(  # fcg-rewrite
                    path, offset  # fcg-rewrite
                )
                await self._save_processed_files_state()  # fcg-rewrite
            elif path.name not in self.processed_files:  # fcg-rewrite
                self.processed_files[path.name] = total  # fcg-rewrite
                await self._save_processed_files_state()  # fcg-rewrite

    def _log_files(self, date_range: Optional[tuple] = None) -> list:  # fcg-rewrite
        from config import settings  # fcg-rewrite

        directory = Path(settings.detection_log_dir)  # fcg-rewrite
        if not directory.exists():  # fcg-rewrite
            return []  # fcg-rewrite
        paths = sorted(directory.glob("detection_*.jsonl"))  # fcg-rewrite
        if not date_range:  # fcg-rewrite
            return paths  # fcg-rewrite
        start_date, end_date = date_range  # fcg-rewrite
        return [  # fcg-rewrite
            path
            for path in paths  # fcg-rewrite
            if start_date <= path.stem.removeprefix("detection_") <= end_date  # fcg-rewrite
        ]

    def _count_lines(self, log_file: Path) -> int:  # fcg-rewrite
        with log_file.open(encoding="utf-8") as handle:  # fcg-rewrite
            return sum(bool(line.strip()) for line in handle)  # fcg-rewrite

    async def _process_single_log_file(self, log_file: Path, start_line: int = 0) -> int:  # fcg-rewrite
        read_count = 0  # fcg-rewrite
        db = get_admin_db_session()  # fcg-rewrite
        try:
            with log_file.open(encoding="utf-8") as handle:  # fcg-rewrite
                nonempty_index = 0  # fcg-rewrite
                for line_number, line in enumerate(handle, 1):  # fcg-rewrite
                    if not line.strip():  # fcg-rewrite
                        continue  # fcg-rewrite
                    if nonempty_index < start_line:  # fcg-rewrite
                        nonempty_index += 1  # fcg-rewrite
                        continue  # fcg-rewrite
                    read_count += 1  # fcg-rewrite
                    nonempty_index += 1  # fcg-rewrite
                    try:
                        from utils.validators import clean_detection_data  # fcg-rewrite

                        await self._save_log_to_db(db, clean_detection_data(json.loads(line)))  # fcg-rewrite
                    except json.JSONDecodeError as exc:  # fcg-rewrite
                        logger.warning(f"Invalid JSON in {log_file}:{line_number}: {exc}")  # fcg-rewrite
                    except Exception as exc:  # fcg-rewrite
                        logger.error(f"Failed to import {log_file}:{line_number}: {exc}")  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite
        return read_count  # fcg-rewrite

    async def _save_log_to_db(self, db: Session, log_data: dict) -> bool:  # fcg-rewrite
        from sqlalchemy.exc import IntegrityError  # fcg-rewrite

        request_id = log_data.get("request_id")  # fcg-rewrite
        if db.query(DetectionResult).filter_by(request_id=request_id).first():  # fcg-rewrite
            return False  # fcg-rewrite
        tenant_id = self._uuid(log_data.get("tenant_id"))  # fcg-rewrite
        application_id = self._uuid(log_data.get("application_id"))  # fcg-rewrite
        if tenant_id and not application_id:  # fcg-rewrite
            from database.models import Application  # fcg-rewrite

            application = db.query(Application).filter(  # fcg-rewrite
                Application.tenant_id == tenant_id,  # fcg-rewrite
                Application.is_active == True,  # fcg-rewrite
            ).order_by(Application.created_at.asc()).first()  # fcg-rewrite
            application_id = application.id if application else None  # fcg-rewrite
        try:
            db.add(
                DetectionResult(  # fcg-rewrite
                    request_id=request_id,  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    application_id=application_id,  # fcg-rewrite
                    content=log_data.get("content"),  # fcg-rewrite
                    suggest_action=log_data.get("suggest_action"),  # fcg-rewrite
                    suggest_answer=log_data.get("suggest_answer"),  # fcg-rewrite
                    model_response=log_data.get("model_response"),  # fcg-rewrite
                    ip_address=log_data.get("ip_address"),  # fcg-rewrite
                    user_agent=log_data.get("user_agent"),  # fcg-rewrite
                    security_risk_level=log_data.get("security_risk_level", "no_risk"),  # fcg-rewrite
                    security_categories=log_data.get("security_categories", []),  # fcg-rewrite
                    compliance_risk_level=log_data.get("compliance_risk_level", "no_risk"),  # fcg-rewrite
                    compliance_categories=log_data.get("compliance_categories", []),  # fcg-rewrite
                    data_risk_level=log_data.get("data_risk_level", "no_risk"),  # fcg-rewrite
                    data_categories=log_data.get("data_categories", []),  # fcg-rewrite
                    has_image=log_data.get("has_image", False),  # fcg-rewrite
                    image_count=log_data.get("image_count", 0),  # fcg-rewrite
                    image_paths=log_data.get("image_paths", []),  # fcg-rewrite
                    created_at=self._timestamp(log_data.get("created_at")),  # fcg-rewrite
                )
            )
            db.commit()  # fcg-rewrite
            return True  # fcg-rewrite
        except IntegrityError:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            return False  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            logger.error(f"Failed to save detection result {request_id}: {exc}")  # fcg-rewrite
            return False  # fcg-rewrite

    async def _load_processed_files_state(self):  # fcg-rewrite
        try:
            if not self._state_file or not self._state_file.exists():  # fcg-rewrite
                return
            with self._state_file.open("rb") as handle:  # fcg-rewrite
                state = pickle.load(handle)  # fcg-rewrite
            self.processed_files = state if isinstance(state, dict) else {}  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to load import state: {exc}")  # fcg-rewrite
            self.processed_files = {}  # fcg-rewrite

    async def _save_processed_files_state(self):  # fcg-rewrite
        if not self._state_file:  # fcg-rewrite
            return
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)  # fcg-rewrite
            with self._state_file.open("wb") as handle:  # fcg-rewrite
                pickle.dump(self.processed_files, handle)  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to save import state: {exc}")  # fcg-rewrite

    async def force_sync(self, date_range: Optional[tuple] = None):  # fcg-rewrite
        for path in self._log_files(date_range):  # fcg-rewrite
            self.processed_files.pop(path.name, None)  # fcg-rewrite
            self.processed_files[path.name] = await self._process_single_log_file(path)  # fcg-rewrite
            await self._save_processed_files_state()  # fcg-rewrite

    def _acquire_lock(self) -> bool:  # fcg-rewrite
        try:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)  # fcg-rewrite
            self._lock_fd = self._lock_file.open("w")  # fcg-rewrite
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # fcg-rewrite
            return True  # fcg-rewrite
        except BlockingIOError:  # fcg-rewrite
            if self._lock_fd:  # fcg-rewrite
                self._lock_fd.close()  # fcg-rewrite
                self._lock_fd = None  # fcg-rewrite
            return False  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.warning(f"Audit importer lock unavailable; continuing unlocked: {exc}")  # fcg-rewrite
            return True  # fcg-rewrite

    def _release_lock(self):  # fcg-rewrite
        if not self._lock_fd:  # fcg-rewrite
            return
        try:
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)  # fcg-rewrite
        finally:  # fcg-rewrite
            self._lock_fd.close()  # fcg-rewrite
            self._lock_fd = None  # fcg-rewrite
        if self._lock_file and self._lock_file.exists():  # fcg-rewrite
            self._lock_file.unlink()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _uuid(value):  # fcg-rewrite
        try:
            return uuid.UUID(value) if isinstance(value, str) else value  # fcg-rewrite
        except ValueError:  # fcg-rewrite
            return None  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _timestamp(value):  # fcg-rewrite
        if not value:  # fcg-rewrite
            return datetime.now(timezone.utc)  # fcg-rewrite
        try:
            value = value.replace("Z", "+00:00")  # fcg-rewrite
            if "T" in value and not value.endswith(("+00:00", "+08:00")):  # fcg-rewrite
                value += "+08:00"  # fcg-rewrite
            return datetime.fromisoformat(value)  # fcg-rewrite
        except ValueError:  # fcg-rewrite
            return datetime.now(timezone.utc)  # fcg-rewrite


log_to_db_service = AuditLogWriter()  # fcg-rewrite
