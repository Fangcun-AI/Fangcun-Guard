#!/usr/bin/env python3
"""Start the OpenAI-compatible proxy API."""

import uvicorn

from config import settings


if __name__ == "__main__":
    uvicorn.run(
        "proxy_service:app",
        host=settings.host,
        port=settings.proxy_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        workers=1 if settings.debug else settings.proxy_uvicorn_workers,
        access_log=True,
    )
