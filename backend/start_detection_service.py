#!/usr/bin/env python3
"""Start the detection API."""

import uvicorn

from config import settings


if __name__ == "__main__":
    uvicorn.run(
        "detection_service:app",
        host=settings.host,
        port=settings.detection_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        workers=1 if settings.debug else settings.detection_uvicorn_workers,
    )
