"""
DEPRECATED: This module has been split into:
  - plugins_builtin/agent_safety/router.py
  - plugins_builtin/hallucination_detection/router.py
This file provides backward compatibility by combining both routers.
"""
from fastapi import APIRouter

# Create a combined router for backward compatibility
# Plugin system now handles route registration, but this file ensures
# any direct imports of `agent_safety_api.router` still work.
from plugins_builtin.agent_safety.router import router as _agent_safety_router
from plugins_builtin.hallucination_detection.router import router as _hallucination_router

# Use the agent safety router as the primary (since it has the same prefix)
router = APIRouter()

# Re-export routes from both plugins
for route in _agent_safety_router.routes:
    router.routes.append(route)
for route in _hallucination_router.routes:
    router.routes.append(route)
