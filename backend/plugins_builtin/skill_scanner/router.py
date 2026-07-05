"""
Skill Scanner policy API routes + SKILL.md directory scan endpoint.

JSON tool definition scanning has been moved to the Agent Safety plugin.
"""

from fastapi import APIRouter, Depends, HTTPException, Request  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from database.models import SkillScannerPolicy, Application  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite
import uuid  # fcg-rewrite
import logging  # fcg-rewrite

from pydantic import BaseModel  # fcg-rewrite

from plugins_builtin.skill_scanner.models import (  # fcg-rewrite
    SkillScannerPolicyUpdate,  # fcg-rewrite
    SkillScannerPolicyResponse,  # fcg-rewrite
)


class DirectoryScanRequest(BaseModel):  # fcg-rewrite
    directory: str  # fcg-rewrite
    max_tools: int = 500  # fcg-rewrite

logger = logging.getLogger(__name__)  # fcg-rewrite

router = APIRouter(prefix="/api/v1", tags=["skill-scanner"])  # fcg-rewrite


def get_current_application_id(request: Request, db: Session = Depends(get_admin_db)) -> str:  # fcg-rewrite
    """Get current application ID from request context"""
    header_app_id = request.headers.get('x-application-id') or request.headers.get('X-Application-ID')  # fcg-rewrite
    if header_app_id:  # fcg-rewrite
        try:
            header_app_uuid = uuid.UUID(str(header_app_id))  # fcg-rewrite
            app = db.query(Application).filter(  # fcg-rewrite
                Application.id == header_app_uuid,  # fcg-rewrite
                Application.is_active == True  # fcg-rewrite
            ).first()  # fcg-rewrite
            if app:
                return str(app.id)  # fcg-rewrite
        except (ValueError, AttributeError):  # fcg-rewrite
            pass

    auth_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
    if not auth_context:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite

    application_id = auth_context['data'].get('application_id')  # fcg-rewrite
    if application_id:  # fcg-rewrite
        return str(application_id)  # fcg-rewrite

    tenant_id = auth_context['data'].get('tenant_id')  # fcg-rewrite
    if not tenant_id:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Tenant ID not found in auth context")  # fcg-rewrite

    try:
        tenant_uuid = uuid.UUID(str(tenant_id))  # fcg-rewrite
        default_app = db.query(Application).filter(  # fcg-rewrite
            Application.tenant_id == tenant_uuid,  # fcg-rewrite
            Application.is_active == True  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not default_app:  # fcg-rewrite
            raise HTTPException(status_code=404, detail="No active application found for user")  # fcg-rewrite
        return str(default_app.id)  # fcg-rewrite
    except ValueError:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")  # fcg-rewrite


def get_tenant_id(request: Request) -> str:  # fcg-rewrite
    """Get tenant ID from request auth context"""
    auth_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
    if not auth_context:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite
    tenant_id = auth_context['data'].get('tenant_id')  # fcg-rewrite
    if not tenant_id:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Tenant ID not found")  # fcg-rewrite
    return str(tenant_id)  # fcg-rewrite


# ── Policy Configuration Endpoints ─────────────────────────────────────────────

@router.get("/config/skill-scanner-policy")  # fcg-rewrite
async def get_skill_scanner_policy(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    application_id: str = Depends(get_current_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    """Get skill scanner policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)  # fcg-rewrite
    except ValueError:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Invalid application ID")  # fcg-rewrite

    policy = db.query(SkillScannerPolicy).filter(  # fcg-rewrite
        SkillScannerPolicy.application_id == app_uuid  # fcg-rewrite
    ).first()  # fcg-rewrite

    if not policy:  # fcg-rewrite
        tenant_id = get_tenant_id(request)  # fcg-rewrite
        policy = SkillScannerPolicy(  # fcg-rewrite
            tenant_id=uuid.UUID(tenant_id),  # fcg-rewrite
            application_id=app_uuid,  # fcg-rewrite
        )
        db.add(policy)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        db.refresh(policy)  # fcg-rewrite

    return SkillScannerPolicyResponse(  # fcg-rewrite
        id=str(policy.id),  # fcg-rewrite
        application_id=str(policy.application_id),  # fcg-rewrite
        enabled=policy.enabled,  # fcg-rewrite
        enable_static_pattern=policy.enable_static_pattern,  # fcg-rewrite
        enable_structural_validation=policy.enable_structural_validation,  # fcg-rewrite
        enable_capability_risk=policy.enable_capability_risk,  # fcg-rewrite
        enable_llm_semantic=policy.enable_llm_semantic,  # fcg-rewrite
        llm_auto_trigger_on_medium=policy.llm_auto_trigger_on_medium,  # fcg-rewrite
        policy_mode=policy.policy_mode,  # fcg-rewrite
        critical_action=policy.critical_action,  # fcg-rewrite
        high_action=policy.high_action,  # fcg-rewrite
        medium_action=policy.medium_action,  # fcg-rewrite
        low_action=policy.low_action,  # fcg-rewrite
        custom_patterns=policy.custom_patterns or [],  # fcg-rewrite
        dangerous_capability_keywords=policy.dangerous_capability_keywords or [],  # fcg-rewrite
        created_at=policy.created_at,  # fcg-rewrite
        updated_at=policy.updated_at,  # fcg-rewrite
    )


@router.put("/config/skill-scanner-policy")  # fcg-rewrite
async def update_skill_scanner_policy(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    policy_data: SkillScannerPolicyUpdate,  # fcg-rewrite
    application_id: str = Depends(get_current_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    """Update skill scanner policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)  # fcg-rewrite
    except ValueError:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Invalid application ID")  # fcg-rewrite

    policy = db.query(SkillScannerPolicy).filter(  # fcg-rewrite
        SkillScannerPolicy.application_id == app_uuid  # fcg-rewrite
    ).first()  # fcg-rewrite

    if not policy:  # fcg-rewrite
        tenant_id = get_tenant_id(request)  # fcg-rewrite
        policy = SkillScannerPolicy(  # fcg-rewrite
            tenant_id=uuid.UUID(tenant_id),  # fcg-rewrite
            application_id=app_uuid,  # fcg-rewrite
        )
        db.add(policy)  # fcg-rewrite

    for field, value in policy_data.model_dump().items():  # fcg-rewrite
        setattr(policy, field, value)  # fcg-rewrite

    db.commit()  # fcg-rewrite
    db.refresh(policy)  # fcg-rewrite

    # Invalidate cache
    try:
        from plugins_builtin.skill_scanner.cache import skill_scanner_cache  # fcg-rewrite
        await skill_scanner_cache.invalidate(application_id)  # fcg-rewrite
    except Exception as e:  # fcg-rewrite
        logger.warning(f"Failed to invalidate skill scanner cache: {e}")  # fcg-rewrite

    return {  # fcg-rewrite
        "success": True,  # fcg-rewrite
        "message": "Skill scanner policy updated",  # fcg-rewrite
        "policy": SkillScannerPolicyResponse(  # fcg-rewrite
            id=str(policy.id),  # fcg-rewrite
            application_id=str(policy.application_id),  # fcg-rewrite
            enabled=policy.enabled,  # fcg-rewrite
            enable_static_pattern=policy.enable_static_pattern,  # fcg-rewrite
            enable_structural_validation=policy.enable_structural_validation,  # fcg-rewrite
            enable_capability_risk=policy.enable_capability_risk,  # fcg-rewrite
            enable_llm_semantic=policy.enable_llm_semantic,  # fcg-rewrite
            llm_auto_trigger_on_medium=policy.llm_auto_trigger_on_medium,  # fcg-rewrite
            policy_mode=policy.policy_mode,  # fcg-rewrite
            critical_action=policy.critical_action,  # fcg-rewrite
            high_action=policy.high_action,  # fcg-rewrite
            medium_action=policy.medium_action,  # fcg-rewrite
            low_action=policy.low_action,  # fcg-rewrite
            custom_patterns=policy.custom_patterns or [],  # fcg-rewrite
            dangerous_capability_keywords=policy.dangerous_capability_keywords or [],  # fcg-rewrite
            created_at=policy.created_at,  # fcg-rewrite
            updated_at=policy.updated_at,  # fcg-rewrite
        ),
    }


# ── Directory Scan Endpoint (SSE Streaming) ──────────────────────────────────

@router.post("/skill-scanner/scan-directory")  # fcg-rewrite
async def scan_directory_endpoint(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    body: DirectoryScanRequest,  # fcg-rewrite
    application_id: str = Depends(get_current_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    """Scan a directory of agent projects — streams SSE events for real-time UI."""
    import os  # fcg-rewrite
    import json as _json  # fcg-rewrite
    from sse_starlette.sse import EventSourceResponse  # fcg-rewrite

    directory = body.directory.strip()  # fcg-rewrite
    if not os.path.isdir(directory) and os.path.isdir("/mnt/scan_targets"):  # fcg-rewrite
        directory = "/mnt/scan_targets"  # fcg-rewrite
    if not os.path.isdir(directory):  # fcg-rewrite
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {directory}")  # fcg-rewrite

    async def event_generator():  # fcg-rewrite
        import time  # fcg-rewrite
        start_time = time.time()  # fcg-rewrite

        def sse(event: str, data: dict):  # fcg-rewrite
            return {"event": event, "data": _json.dumps(data, ensure_ascii=False)}  # fcg-rewrite

        # ── Phase 1: Discovery ───────────────────────────────────────────
        from plugins_builtin.skill_scanner.extractors import scan_directory  # fcg-rewrite
        try:
            all_tools, tools_by_agent = scan_directory(directory)  # fcg-rewrite
        except Exception as e:  # fcg-rewrite
            yield sse("error", {"message": f"Extraction failed: {str(e)}"})  # fcg-rewrite
            return

        # Stream each agent discovery
        agent_summary = {}  # fcg-rewrite
        for agent_name, tools in sorted(tools_by_agent.items()):  # fcg-rewrite
            agent_info = {  # fcg-rewrite
                "tools_count": len(tools),  # fcg-rewrite
                "tool_names": [t["name"] for t in tools],  # fcg-rewrite
            }
            agent_summary[agent_name] = agent_info  # fcg-rewrite
            yield sse("agent_discovered", {  # fcg-rewrite
                "agent": agent_name,  # fcg-rewrite
                "tools_count": len(tools),  # fcg-rewrite
                "tool_names": [t["name"] for t in tools],  # fcg-rewrite
            })

        yield sse("discovery_complete", {  # fcg-rewrite
            "agents_scanned": len(tools_by_agent),  # fcg-rewrite
            "tools_extracted": len(all_tools),  # fcg-rewrite
        })

        if not all_tools:  # fcg-rewrite
            yield sse("complete", {  # fcg-rewrite
                "request_id": str(uuid.uuid4()),  # fcg-rewrite
                "agents_scanned": 0, "tools_extracted": 0,  # fcg-rewrite
                "tools_by_agent": {},  # fcg-rewrite
                "result": {"findings": [], "tools_scanned": 0, "tools_flagged": 0,  # fcg-rewrite
                           "max_severity": "info", "scan_duration_ms": 0, "engine_summary": {}},  # fcg-rewrite
            })
            return

        scan_tools = all_tools[:body.max_tools]  # fcg-rewrite

        # ── Phase 2: Static scanning (per-agent) ──────────────────────────
        yield sse("phase", {"phase": "scanning", "message": "正在运行静态安全引擎..."})  # fcg-rewrite

        from plugins_builtin.skill_scanner.cache import skill_scanner_cache, _PolicySnapshot  # fcg-rewrite
        policy = await skill_scanner_cache.get_policy(application_id)  # fcg-rewrite
        if not policy:  # fcg-rewrite
            policy = _PolicySnapshot(  # fcg-rewrite
                enabled=True, enable_static_pattern=True,  # fcg-rewrite
                enable_structural_validation=True, enable_capability_risk=True,  # fcg-rewrite
                enable_llm_semantic=False, llm_auto_trigger_on_medium=True,  # fcg-rewrite
                policy_mode='strict', critical_action='block', high_action='warn',  # fcg-rewrite
                medium_action='log', low_action='log',  # fcg-rewrite
                custom_patterns=[], dangerous_capability_keywords=[],  # fcg-rewrite
            )

        from plugins_builtin.skill_scanner.service import skill_scanner_service  # fcg-rewrite

        all_findings = []  # fcg-rewrite
        total_scanned = 0  # fcg-rewrite
        total_flagged = 0  # fcg-rewrite
        engine_summary = {}  # fcg-rewrite

        # Scan per-agent for real-time progress
        agent_names_sorted = sorted(tools_by_agent.keys())  # fcg-rewrite
        for agent_idx, agent_name in enumerate(agent_names_sorted):  # fcg-rewrite
            agent_tools = tools_by_agent[agent_name]  # fcg-rewrite

            yield sse("scan_progress", {  # fcg-rewrite
                "agent": agent_name,  # fcg-rewrite
                "agent_index": agent_idx,  # fcg-rewrite
                "agents_total": len(agent_names_sorted),  # fcg-rewrite
                "tools_count": len(agent_tools),  # fcg-rewrite
            })

            batch_formatted = []  # fcg-rewrite
            for t in agent_tools:  # fcg-rewrite
                tool_entry = {"name": t["name"], "description": t.get("description", "")}  # fcg-rewrite
                for key in ("inputSchema", "instruction_body", "allowed_tools", "skill_type"):  # fcg-rewrite
                    if key in t:  # fcg-rewrite
                        tool_entry[key] = t[key]  # fcg-rewrite
                batch_formatted.append(tool_entry)  # fcg-rewrite

            result = await skill_scanner_service.scan_tools(  # fcg-rewrite
                tools=batch_formatted, policy=policy, force_llm=False,  # fcg-rewrite
            )

            agent_findings = [f.model_dump() for f in result.findings]  # fcg-rewrite
            all_findings.extend(agent_findings)  # fcg-rewrite
            total_scanned += result.tools_scanned  # fcg-rewrite
            total_flagged += result.tools_flagged  # fcg-rewrite
            for k, v in (result.engine_summary or {}).items():  # fcg-rewrite
                engine_summary[k] = engine_summary.get(k, 0) + v  # fcg-rewrite

            # Stream findings for this agent immediately
            for f in agent_findings:  # fcg-rewrite
                yield sse("finding", f)  # fcg-rewrite

            if agent_findings:  # fcg-rewrite
                yield sse("agent_scan_done", {  # fcg-rewrite
                    "agent": agent_name,  # fcg-rewrite
                    "findings_count": len(agent_findings),  # fcg-rewrite
                })

        yield sse("static_complete", {  # fcg-rewrite
            "findings_count": len(all_findings),  # fcg-rewrite
            "engine_summary": engine_summary,  # fcg-rewrite
        })

        # ── Phase 3: LLM Analysis (streaming) ───────────────────────────
        yield sse("phase", {"phase": "llm_analysis", "message": "AI analyzing security findings..."})  # fcg-rewrite

        if all_findings:  # fcg-rewrite
            try:
                from plugins_builtin.skill_scanner.engines.llm_semantic import enrich_findings_with_llm_streaming  # fcg-rewrite

                enriched_count = 0  # fcg-rewrite
                async for event in enrich_findings_with_llm_streaming(all_findings, scan_tools):  # fcg-rewrite
                    yield sse("llm_progress", event)  # fcg-rewrite
                    if event.get("type") == "enriched":  # fcg-rewrite
                        idx = event.get("index", -1)  # fcg-rewrite
                        if 0 <= idx < len(all_findings):  # fcg-rewrite
                            if event.get("description"):  # fcg-rewrite
                                all_findings[idx]["description"] = event["description"]  # fcg-rewrite
                            if event.get("evidence"):  # fcg-rewrite
                                all_findings[idx]["evidence"] = event["evidence"]  # fcg-rewrite
                            if event.get("remediation"):  # fcg-rewrite
                                all_findings[idx]["remediation"] = event["remediation"]  # fcg-rewrite
                            enriched_count += 1  # fcg-rewrite
                engine_summary['llm_semantic'] = enriched_count  # fcg-rewrite
            except Exception as e:  # fcg-rewrite
                logger.warning(f"LLM enrichment failed: {e}")  # fcg-rewrite
                yield sse("llm_progress", {"type": "error", "message": str(e)})  # fcg-rewrite

        # ── Complete ─────────────────────────────────────────────────────
        elapsed_ms = (time.time() - start_time) * 1000  # fcg-rewrite
        sev_order = ['info', 'low', 'medium', 'high', 'critical']  # fcg-rewrite
        max_sev = 'info'  # fcg-rewrite
        for f in all_findings:  # fcg-rewrite
            s = f.get('severity', 'info')  # fcg-rewrite
            if s in sev_order and sev_order.index(s) > sev_order.index(max_sev):  # fcg-rewrite
                max_sev = s  # fcg-rewrite

        yield sse("complete", {  # fcg-rewrite
            "request_id": str(uuid.uuid4()),  # fcg-rewrite
            "agents_scanned": len(tools_by_agent),  # fcg-rewrite
            "tools_extracted": len(all_tools),  # fcg-rewrite
            "tools_by_agent": agent_summary,  # fcg-rewrite
            "result": {  # fcg-rewrite
                "findings": all_findings,  # fcg-rewrite
                "tools_scanned": total_scanned,  # fcg-rewrite
                "tools_flagged": total_flagged,  # fcg-rewrite
                "max_severity": max_sev,  # fcg-rewrite
                "scan_duration_ms": round(elapsed_ms, 1),  # fcg-rewrite
                "engine_summary": engine_summary,  # fcg-rewrite
            },
        })

    return EventSourceResponse(event_generator())  # fcg-rewrite
