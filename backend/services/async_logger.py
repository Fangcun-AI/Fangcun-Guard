"""Queued JSONL writer for detection audit events."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles

from utils.logger import setup_logger

logger = setup_logger()


class AsyncDetectionRecorder:
    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            from config import settings

            log_dir = settings.detection_log_dir
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._queue: Optional[asyncio.Queue] = None
        self._writer_task: Optional[asyncio.Task] = None
        self._running = False

    def _ensure_queue(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    async def start(self):
        if not self._running:
            self._running = True
            self._ensure_queue()
            self._writer_task = asyncio.create_task(self._writer_loop())
            logger.info("Async detection logger started")

    async def stop(self):
        if not self._running:
            return
        self._running = False
        await self._ensure_queue().put(None)
        if self._writer_task:
            await self._writer_task
            self._writer_task = None
        logger.info("Async detection logger stopped")

    async def log_detection(self, detection_data: Dict[str, Any]):
        if not self._running:
            await self.start()
        from utils.validators import clean_detection_data

        cleaned = clean_detection_data(detection_data.copy())
        cleaned["logged_at"] = datetime.now(timezone.utc).isoformat()
        await self._ensure_queue().put(cleaned)

    async def _writer_loop(self):
        current_date = None
        current_file = None
        try:
            while True:
                data = await self._ensure_queue().get()
                if data is None:
                    break
                today = datetime.now().strftime("%Y%m%d")
                if today != current_date:
                    if current_file:
                        await current_file.close()
                    current_date = today
                    current_file = await aiofiles.open(
                        self.log_dir / f"detection_{today}.jsonl",
                        "a",
                        encoding="utf-8",
                    )
                await self._flush_batch([data], current_date, current_file)
        except Exception as exc:
            logger.error(f"Async detection logger failed: {exc}")
        finally:
            if current_file:
                await current_file.close()

    async def _flush_batch(self, batch: list, current_date: str, current_file):
        if batch and current_file:
            lines = "".join(
                f"{json.dumps(data, ensure_ascii=False)}\n" for data in batch
            )
            await current_file.write(lines)
            await current_file.flush()

    def get_log_files(self, date_range: Optional[tuple] = None) -> list:
        files = sorted(self.log_dir.glob("detection_*.jsonl"))
        if not date_range:
            return files
        start_date, end_date = date_range
        return [
            path
            for path in files
            if start_date <= path.stem.removeprefix("detection_") <= end_date
        ]


async_detection_logger = AsyncDetectionRecorder()
