#!/usr/bin/env python3
"""Start the admin API after a best-effort migration pass."""

import uvicorn

from config import settings
from utils.logger import setup_logger

logger = setup_logger()


def run_migrations():
    try:
        from migrations.run_migrations import run_migrations as migrate

        executed, failed = migrate(dry_run=False)
        if failed:
            raise RuntimeError(f"{failed} migration(s) failed")
        logger.info(f"Migration check complete: {executed} applied")
    except Exception as exc:
        logger.warning(f"Migration check failed; continuing startup: {exc}")


if __name__ == "__main__":
    run_migrations()
    uvicorn.run(
        "admin_service:app",
        host=settings.host,
        port=settings.admin_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        workers=1 if settings.debug else settings.admin_uvicorn_workers,
    )
