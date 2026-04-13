"""
Plugin management API — list, query, enable/disable plugins for Tool Center.
Also provides skills, batch-configure, and status endpoints for the
compatibility_agent (deployment agent) integration.
"""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from database.connection import get_admin_db
from database.models import (
    Application,
    BasicGuardPolicy,
    SkillScannerPolicy,
    AgentSafetyPolicy,
    HallucinationPolicy,
    McpScannerPolicy,
)
from sqlalchemy.orm import Session
from plugins.registry import plugin_registry
from plugins.base import DetectionPlugin
from utils.logger import setup_logger
import uuid

logger = setup_logger()

router = APIRouter(prefix="/api/v1/plugins", tags=["Plugins"])

# SKILLS.md directory (relative to backend/)
_PLUGINS_BUILTIN_DIR = Path(__file__).parent.parent / "plugins_builtin"


# ── Response Models ───────────────────────────────────────────────────────────

class PluginHookInfo(BaseModel):
    """Which hooks a plugin implements"""
    on_input_check: bool = False
    on_output_check: bool = False
    on_detection_check: bool = False
    on_stream_complete: bool = False


class PluginInfo(BaseModel):
    """Plugin information for Tool Center display"""
    name: str
    version: str
    description: str
    author: str
    plugin_type: str
    deployment_mode: str
    priority: int
    display_name: str
    display_name_en: str
    icon: str
    category: str
    tags: List[str]
    documentation: str
    enabled: bool
    hooks: Optional[PluginHookInfo] = None


class PluginListResponse(BaseModel):
    """Response for plugin listing"""
    total: int
    plugins: List[PluginInfo]


class PluginSkillInfo(BaseModel):
    """Plugin info with SKILLS.md content for LLM analysis"""
    name: str
    display_name: str
    display_name_en: str
    skills_content: str
    enabled_by_default: bool
    category: str
    tags: List[str]


class PluginSkillsResponse(BaseModel):
    """Response for /plugins/skills endpoint"""
    plugins: List[PluginSkillInfo]


class BatchConfigureRequest(BaseModel):
    """Request body for batch plugin configuration"""
    application_id: str
    plugins: Dict[str, Dict[str, Any]]


class BatchConfigureResponse(BaseModel):
    """Response for batch plugin configuration"""
    configured: List[str]
    skipped: List[str]
    errors: Dict[str, str]


class PluginStatusEntry(BaseModel):
    """Status of a single plugin for an application"""
    enabled: bool
    policy_exists: bool
    key_config: Optional[Dict[str, Any]] = None


class PluginStatusResponse(BaseModel):
    """Response for /plugins/status endpoint"""
    application_id: str
    plugins: Dict[str, PluginStatusEntry]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_tenant_id(request: Request) -> str:
    """Extract tenant_id from auth context"""
    auth_context = getattr(request.state, 'auth_context', None)
    if not auth_context:
        raise HTTPException(status_code=401, detail="Not authenticated")
    tenant_id = auth_context['data'].get('tenant_id')
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant ID not found")
    return str(tenant_id)


def _plugin_to_info(name: str, plugin) -> PluginInfo:
    """Convert a plugin instance to PluginInfo for API response"""
    meta = plugin.get_metadata()

    # Detect which hooks are implemented (non-default)
    hooks = None
    if isinstance(plugin, DetectionPlugin):
        hooks = PluginHookInfo(
            on_input_check=type(plugin).on_input_check is not DetectionPlugin.on_input_check,
            on_output_check=type(plugin).on_output_check is not DetectionPlugin.on_output_check,
            on_detection_check=type(plugin).on_detection_check is not DetectionPlugin.on_detection_check,
            on_stream_complete=type(plugin).on_stream_complete is not DetectionPlugin.on_stream_complete,
        )

    return PluginInfo(
        name=meta.name,
        version=meta.version,
        description=meta.description,
        author=meta.author,
        plugin_type=meta.plugin_type.value,
        deployment_mode=meta.deployment_mode.value,
        priority=meta.priority,
        display_name=meta.display_name or meta.name,
        display_name_en=meta.display_name_en or meta.name,
        icon=meta.icon,
        category=meta.category,
        tags=meta.tags,
        documentation=meta.documentation,
        enabled=True,  # Currently all loaded plugins are enabled
        hooks=hooks,
    )


# Plugin name → (ORM model, default "enabled" value, key config fields)
_PLUGIN_POLICY_MAP: Dict[str, tuple] = {
    "basic_guard": (BasicGuardPolicy, True, [
        "enable_content_pattern_check", "enable_reasoning_divergence_check",
        "enable_output_anomaly_check", "violation_action",
    ]),
    "skill_scanner": (SkillScannerPolicy, False, [
        "enable_static_pattern", "enable_structural_validation",
        "enable_capability_risk", "enable_llm_semantic", "policy_mode",
    ]),
    "agent_safety": (AgentSafetyPolicy, False, [
        "enable_argument_inspection", "enable_reasoning_safety",
        "tool_violation_action", "reasoning_violation_action",
    ]),
    "hallucination_detection": (HallucinationPolicy, False, [
        "enable_groundedness", "enable_consistency",
        "groundedness_threshold", "consistency_threshold", "violation_action",
    ]),
    "mcp_scanner": (McpScannerPolicy, False, [
        "enable_yara_rules", "enable_llm_semantic", "enable_behavior_analysis",
        "enable_tool_scan", "enable_prompt_scan", "enable_resource_scan",
        "enable_instruction_scan", "enable_supply_chain", "policy_mode",
    ]),
}


# ── Existing Endpoints ────────────────────────────────────────────────────────

@router.get("", response_model=PluginListResponse)
async def list_plugins():
    """List all loaded plugins"""
    all_plugins = plugin_registry.get_all()
    plugins = [_plugin_to_info(name, plugin) for name, plugin in all_plugins.items()]
    return PluginListResponse(total=len(plugins), plugins=plugins)


# NOTE: /skills, /status, /batch-configure are registered BEFORE /{plugin_name}
# to avoid FastAPI treating "skills" etc. as a plugin_name path parameter.

# ── Skills Endpoint (for deployment agent LLM analysis) ──────────────────────

@router.get("/skills", response_model=PluginSkillsResponse)
async def get_plugin_skills():
    """Return SKILLS.md content for all registered plugins.

    The deployment agent reads these to let an LLM recommend which plugins
    to enable for a target project.
    """
    all_plugins = plugin_registry.get_all()
    result: List[PluginSkillInfo] = []

    for name, plugin in all_plugins.items():
        meta = plugin.get_metadata()
        skills_path = _PLUGINS_BUILTIN_DIR / name / "SKILLS.md"
        skills_content = ""
        if skills_path.exists():
            try:
                skills_content = skills_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to read SKILLS.md for plugin '{name}': {e}")

        # Determine default enabled state from policy map
        enabled_by_default = _PLUGIN_POLICY_MAP.get(name, (None, False, []))[1]

        result.append(PluginSkillInfo(
            name=name,
            display_name=meta.display_name or name,
            display_name_en=meta.display_name_en or name,
            skills_content=skills_content,
            enabled_by_default=enabled_by_default,
            category=meta.category,
            tags=meta.tags,
        ))

    return PluginSkillsResponse(plugins=result)


# ── Plugin Status Endpoint ────────────────────────────────────────────────────

@router.get("/status", response_model=PluginStatusResponse)
async def get_plugin_status(
    application_id: str = Query(..., description="Application UUID"),
    db: Session = Depends(get_admin_db),
):
    """Query per-application plugin enabled status and key config."""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application_id format")

    # Verify application exists
    app = db.query(Application).filter(Application.id == app_uuid).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    plugins_status: Dict[str, PluginStatusEntry] = {}

    for plugin_name, (model_cls, default_enabled, key_fields) in _PLUGIN_POLICY_MAP.items():
        policy = db.query(model_cls).filter(
            model_cls.application_id == app_uuid
        ).first()

        if policy:
            key_config = {}
            for field in key_fields:
                val = getattr(policy, field, None)
                key_config[field] = val
            plugins_status[plugin_name] = PluginStatusEntry(
                enabled=policy.enabled,
                policy_exists=True,
                key_config=key_config,
            )
        else:
            plugins_status[plugin_name] = PluginStatusEntry(
                enabled=default_enabled,
                policy_exists=False,
                key_config=None,
            )

    return PluginStatusResponse(
        application_id=application_id,
        plugins=plugins_status,
    )


# ── Batch Configure Endpoint ─────────────────────────────────────────────────

@router.post("/batch-configure", response_model=BatchConfigureResponse)
async def batch_configure_plugins(
    request: Request,
    body: BatchConfigureRequest,
    db: Session = Depends(get_admin_db),
):
    """Batch configure plugin policies for an application.

    The deployment agent calls this after LLM-based plugin recommendation
    to enable/configure the recommended set of plugins in one request.
    """
    try:
        app_uuid = uuid.UUID(body.application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application_id format")

    # Verify application exists
    app = db.query(Application).filter(Application.id == app_uuid).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    tenant_id = _get_tenant_id(request)
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")

    configured: List[str] = []
    skipped: List[str] = []
    errors: Dict[str, str] = {}

    for plugin_name, config in body.plugins.items():
        if plugin_name not in _PLUGIN_POLICY_MAP:
            skipped.append(plugin_name)
            continue

        model_cls = _PLUGIN_POLICY_MAP[plugin_name][0]

        try:
            policy = db.query(model_cls).filter(
                model_cls.application_id == app_uuid
            ).first()

            if not policy:
                policy = model_cls(
                    tenant_id=tenant_uuid,
                    application_id=app_uuid,
                )
                db.add(policy)

            # Apply config fields
            for field, value in config.items():
                if hasattr(policy, field):
                    setattr(policy, field, value)

            configured.append(plugin_name)
        except Exception as e:
            errors[plugin_name] = str(e)
            logger.error(f"Failed to configure plugin '{plugin_name}': {e}")

    # Commit all changes in one transaction
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database commit failed: {e}")

    # Invalidate caches for configured plugins
    _cache_map = {
        "basic_guard": "plugins_builtin.basic_guard.cache:basic_guard_cache",
        "skill_scanner": "plugins_builtin.skill_scanner.cache:skill_scanner_cache",
        "agent_safety": "plugins_builtin.agent_safety.cache:agent_safety_cache",
        "hallucination_detection": "plugins_builtin.hallucination_detection.cache:hallucination_cache",
        "mcp_scanner": "plugins_builtin.mcp_scanner.cache:mcp_scanner_cache",
    }
    for plugin_name in configured:
        cache_ref = _cache_map.get(plugin_name)
        if cache_ref:
            try:
                module_path, attr_name = cache_ref.split(":")
                import importlib
                mod = importlib.import_module(module_path)
                cache_instance = getattr(mod, attr_name)
                await cache_instance.invalidate(body.application_id)
            except Exception as e:
                logger.warning(f"Failed to invalidate cache for '{plugin_name}': {e}")

    return BatchConfigureResponse(
        configured=configured,
        skipped=skipped,
        errors=errors,
    )


# ── Single Plugin Detail (must be LAST to avoid capturing other paths) ────────

@router.get("/{plugin_name}", response_model=PluginInfo)
async def get_plugin(plugin_name: str):
    """Get details of a specific plugin"""
    plugin = plugin_registry.get(plugin_name)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")
    return _plugin_to_info(plugin_name, plugin)
