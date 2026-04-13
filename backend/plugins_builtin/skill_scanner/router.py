"""
Skill Scanner policy API routes + SKILL.md directory scan endpoint.

JSON tool definition scanning has been moved to the Agent Safety plugin.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from database.connection import get_admin_db
from database.models import SkillScannerPolicy, Application
from sqlalchemy.orm import Session
import uuid
import logging

from pydantic import BaseModel

from plugins_builtin.skill_scanner.models import (
    SkillScannerPolicyUpdate,
    SkillScannerPolicyResponse,
)


class DirectoryScanRequest(BaseModel):
    directory: str
    max_tools: int = 500

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["skill-scanner"])


def get_current_application_id(request: Request, db: Session = Depends(get_admin_db)) -> str:
    """Get current application ID from request context"""
    header_app_id = request.headers.get('x-application-id') or request.headers.get('X-Application-ID')
    if header_app_id:
        try:
            header_app_uuid = uuid.UUID(str(header_app_id))
            app = db.query(Application).filter(
                Application.id == header_app_uuid,
                Application.is_active == True
            ).first()
            if app:
                return str(app.id)
        except (ValueError, AttributeError):
            pass

    auth_context = getattr(request.state, 'auth_context', None)
    if not auth_context:
        raise HTTPException(status_code=401, detail="Not authenticated")

    application_id = auth_context['data'].get('application_id')
    if application_id:
        return str(application_id)

    tenant_id = auth_context['data'].get('tenant_id')
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant ID not found in auth context")

    try:
        tenant_uuid = uuid.UUID(str(tenant_id))
        default_app = db.query(Application).filter(
            Application.tenant_id == tenant_uuid,
            Application.is_active == True
        ).first()
        if not default_app:
            raise HTTPException(status_code=404, detail="No active application found for user")
        return str(default_app.id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")


def get_tenant_id(request: Request) -> str:
    """Get tenant ID from request auth context"""
    auth_context = getattr(request.state, 'auth_context', None)
    if not auth_context:
        raise HTTPException(status_code=401, detail="Not authenticated")
    tenant_id = auth_context['data'].get('tenant_id')
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant ID not found")
    return str(tenant_id)


# ── Policy Configuration Endpoints ─────────────────────────────────────────────

@router.get("/config/skill-scanner-policy")
async def get_skill_scanner_policy(
    request: Request,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Get skill scanner policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    policy = db.query(SkillScannerPolicy).filter(
        SkillScannerPolicy.application_id == app_uuid
    ).first()

    if not policy:
        tenant_id = get_tenant_id(request)
        policy = SkillScannerPolicy(
            tenant_id=uuid.UUID(tenant_id),
            application_id=app_uuid,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)

    return SkillScannerPolicyResponse(
        id=str(policy.id),
        application_id=str(policy.application_id),
        enabled=policy.enabled,
        enable_static_pattern=policy.enable_static_pattern,
        enable_structural_validation=policy.enable_structural_validation,
        enable_capability_risk=policy.enable_capability_risk,
        enable_llm_semantic=policy.enable_llm_semantic,
        llm_auto_trigger_on_medium=policy.llm_auto_trigger_on_medium,
        policy_mode=policy.policy_mode,
        critical_action=policy.critical_action,
        high_action=policy.high_action,
        medium_action=policy.medium_action,
        low_action=policy.low_action,
        custom_patterns=policy.custom_patterns or [],
        dangerous_capability_keywords=policy.dangerous_capability_keywords or [],
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.put("/config/skill-scanner-policy")
async def update_skill_scanner_policy(
    request: Request,
    policy_data: SkillScannerPolicyUpdate,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Update skill scanner policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    policy = db.query(SkillScannerPolicy).filter(
        SkillScannerPolicy.application_id == app_uuid
    ).first()

    if not policy:
        tenant_id = get_tenant_id(request)
        policy = SkillScannerPolicy(
            tenant_id=uuid.UUID(tenant_id),
            application_id=app_uuid,
        )
        db.add(policy)

    for field, value in policy_data.model_dump().items():
        setattr(policy, field, value)

    db.commit()
    db.refresh(policy)

    # Invalidate cache
    try:
        from plugins_builtin.skill_scanner.cache import skill_scanner_cache
        await skill_scanner_cache.invalidate(application_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate skill scanner cache: {e}")

    return {
        "success": True,
        "message": "Skill scanner policy updated",
        "policy": SkillScannerPolicyResponse(
            id=str(policy.id),
            application_id=str(policy.application_id),
            enabled=policy.enabled,
            enable_static_pattern=policy.enable_static_pattern,
            enable_structural_validation=policy.enable_structural_validation,
            enable_capability_risk=policy.enable_capability_risk,
            enable_llm_semantic=policy.enable_llm_semantic,
            llm_auto_trigger_on_medium=policy.llm_auto_trigger_on_medium,
            policy_mode=policy.policy_mode,
            critical_action=policy.critical_action,
            high_action=policy.high_action,
            medium_action=policy.medium_action,
            low_action=policy.low_action,
            custom_patterns=policy.custom_patterns or [],
            dangerous_capability_keywords=policy.dangerous_capability_keywords or [],
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        ),
    }


# ── Directory Scan Endpoint (SSE Streaming) ──────────────────────────────────

@router.post("/skill-scanner/scan-directory")
async def scan_directory_endpoint(
    request: Request,
    body: DirectoryScanRequest,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Scan a directory of agent projects — streams SSE events for real-time UI."""
    import os
    import json as _json
    from sse_starlette.sse import EventSourceResponse

    directory = body.directory.strip()
    if not os.path.isdir(directory) and os.path.isdir("/mnt/scan_targets"):
        directory = "/mnt/scan_targets"
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {directory}")

    async def event_generator():
        import time
        start_time = time.time()

        def sse(event: str, data: dict):
            return {"event": event, "data": _json.dumps(data, ensure_ascii=False)}

        # ── Phase 1: Discovery ───────────────────────────────────────────
        from plugins_builtin.skill_scanner.extractors import scan_directory
        try:
            all_tools, tools_by_agent = scan_directory(directory)
        except Exception as e:
            yield sse("error", {"message": f"Extraction failed: {str(e)}"})
            return

        # Stream each agent discovery
        agent_summary = {}
        for agent_name, tools in sorted(tools_by_agent.items()):
            agent_info = {
                "tools_count": len(tools),
                "tool_names": [t["name"] for t in tools],
            }
            agent_summary[agent_name] = agent_info
            yield sse("agent_discovered", {
                "agent": agent_name,
                "tools_count": len(tools),
                "tool_names": [t["name"] for t in tools],
            })

        yield sse("discovery_complete", {
            "agents_scanned": len(tools_by_agent),
            "tools_extracted": len(all_tools),
        })

        if not all_tools:
            yield sse("complete", {
                "request_id": str(uuid.uuid4()),
                "agents_scanned": 0, "tools_extracted": 0,
                "tools_by_agent": {},
                "result": {"findings": [], "tools_scanned": 0, "tools_flagged": 0,
                           "max_severity": "info", "scan_duration_ms": 0, "engine_summary": {}},
            })
            return

        scan_tools = all_tools[:body.max_tools]

        # ── Phase 2: Static scanning (per-agent) ──────────────────────────
        yield sse("phase", {"phase": "scanning", "message": "正在运行静态安全引擎..."})

        from plugins_builtin.skill_scanner.cache import skill_scanner_cache, _PolicySnapshot
        policy = await skill_scanner_cache.get_policy(application_id)
        if not policy:
            policy = _PolicySnapshot(
                enabled=True, enable_static_pattern=True,
                enable_structural_validation=True, enable_capability_risk=True,
                enable_llm_semantic=False, llm_auto_trigger_on_medium=True,
                policy_mode='strict', critical_action='block', high_action='warn',
                medium_action='log', low_action='log',
                custom_patterns=[], dangerous_capability_keywords=[],
            )

        from plugins_builtin.skill_scanner.service import skill_scanner_service

        all_findings = []
        total_scanned = 0
        total_flagged = 0
        engine_summary = {}

        # Scan per-agent for real-time progress
        agent_names_sorted = sorted(tools_by_agent.keys())
        for agent_idx, agent_name in enumerate(agent_names_sorted):
            agent_tools = tools_by_agent[agent_name]

            yield sse("scan_progress", {
                "agent": agent_name,
                "agent_index": agent_idx,
                "agents_total": len(agent_names_sorted),
                "tools_count": len(agent_tools),
            })

            batch_formatted = []
            for t in agent_tools:
                tool_entry = {"name": t["name"], "description": t.get("description", "")}
                for key in ("inputSchema", "instruction_body", "allowed_tools", "skill_type"):
                    if key in t:
                        tool_entry[key] = t[key]
                batch_formatted.append(tool_entry)

            result = await skill_scanner_service.scan_tools(
                tools=batch_formatted, policy=policy, force_llm=False,
            )

            agent_findings = [f.model_dump() for f in result.findings]
            all_findings.extend(agent_findings)
            total_scanned += result.tools_scanned
            total_flagged += result.tools_flagged
            for k, v in (result.engine_summary or {}).items():
                engine_summary[k] = engine_summary.get(k, 0) + v

            # Stream findings for this agent immediately
            for f in agent_findings:
                yield sse("finding", f)

            if agent_findings:
                yield sse("agent_scan_done", {
                    "agent": agent_name,
                    "findings_count": len(agent_findings),
                })

        yield sse("static_complete", {
            "findings_count": len(all_findings),
            "engine_summary": engine_summary,
        })

        # ── Phase 3: LLM Analysis (streaming) ───────────────────────────
        yield sse("phase", {"phase": "llm_analysis", "message": "AI analyzing security findings..."})

        if all_findings:
            try:
                from plugins_builtin.skill_scanner.engines.llm_semantic import enrich_findings_with_llm_streaming

                enriched_count = 0
                async for event in enrich_findings_with_llm_streaming(all_findings, scan_tools):
                    yield sse("llm_progress", event)
                    if event.get("type") == "enriched":
                        idx = event.get("index", -1)
                        if 0 <= idx < len(all_findings):
                            if event.get("description"):
                                all_findings[idx]["description"] = event["description"]
                            if event.get("evidence"):
                                all_findings[idx]["evidence"] = event["evidence"]
                            if event.get("remediation"):
                                all_findings[idx]["remediation"] = event["remediation"]
                            enriched_count += 1
                engine_summary['llm_semantic'] = enriched_count
            except Exception as e:
                logger.warning(f"LLM enrichment failed: {e}")
                yield sse("llm_progress", {"type": "error", "message": str(e)})

        # ── Complete ─────────────────────────────────────────────────────
        elapsed_ms = (time.time() - start_time) * 1000
        sev_order = ['info', 'low', 'medium', 'high', 'critical']
        max_sev = 'info'
        for f in all_findings:
            s = f.get('severity', 'info')
            if s in sev_order and sev_order.index(s) > sev_order.index(max_sev):
                max_sev = s

        yield sse("complete", {
            "request_id": str(uuid.uuid4()),
            "agents_scanned": len(tools_by_agent),
            "tools_extracted": len(all_tools),
            "tools_by_agent": agent_summary,
            "result": {
                "findings": all_findings,
                "tools_scanned": total_scanned,
                "tools_flagged": total_flagged,
                "max_severity": max_sev,
                "scan_duration_ms": round(elapsed_ms, 1),
                "engine_summary": engine_summary,
            },
        })

    return EventSourceResponse(event_generator())
