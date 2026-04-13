"""
MCP Scanner policy API routes + dedicated scan endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from database.connection import get_admin_db
from database.models import McpScannerPolicy, Application
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import logging

from pydantic import BaseModel

from plugins_builtin.mcp_scanner.models import (
    McpScannerPolicyUpdate,
    McpScannerPolicyResponse,
    McpServerScanRequest,
    McpServerScanResponse,
)


class DirectoryScanRequest(BaseModel):
    directory: str

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["mcp-scanner"])


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

@router.get("/config/mcp-scanner-policy")
async def get_mcp_scanner_policy(
    request: Request,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Get MCP scanner policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    policy = db.query(McpScannerPolicy).filter(
        McpScannerPolicy.application_id == app_uuid
    ).first()

    if not policy:
        tenant_id = get_tenant_id(request)
        policy = McpScannerPolicy(
            tenant_id=uuid.UUID(tenant_id),
            application_id=app_uuid,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)

    return McpScannerPolicyResponse(
        id=str(policy.id),
        application_id=str(policy.application_id),
        enabled=policy.enabled,
        enable_yara_rules=policy.enable_yara_rules,
        enable_llm_semantic=policy.enable_llm_semantic,
        enable_behavior_analysis=policy.enable_behavior_analysis,
        llm_auto_trigger_on_medium=policy.llm_auto_trigger_on_medium,
        enable_tool_scan=policy.enable_tool_scan,
        enable_prompt_scan=policy.enable_prompt_scan,
        enable_resource_scan=policy.enable_resource_scan,
        enable_instruction_scan=policy.enable_instruction_scan,
        enable_supply_chain=policy.enable_supply_chain,
        policy_mode=policy.policy_mode,
        critical_action=policy.critical_action,
        high_action=policy.high_action,
        medium_action=policy.medium_action,
        low_action=policy.low_action,
        custom_yara_rules=policy.custom_yara_rules or [],
        trusted_servers=policy.trusted_servers or [],
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.put("/config/mcp-scanner-policy")
async def update_mcp_scanner_policy(
    request: Request,
    policy_data: McpScannerPolicyUpdate,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Update MCP scanner policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    policy = db.query(McpScannerPolicy).filter(
        McpScannerPolicy.application_id == app_uuid
    ).first()

    if not policy:
        tenant_id = get_tenant_id(request)
        policy = McpScannerPolicy(
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
        from plugins_builtin.mcp_scanner.cache import mcp_scanner_cache
        await mcp_scanner_cache.invalidate(application_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate MCP scanner cache: {e}")

    return {
        "success": True,
        "message": "MCP scanner policy updated",
        "policy": McpScannerPolicyResponse(
            id=str(policy.id),
            application_id=str(policy.application_id),
            enabled=policy.enabled,
            enable_yara_rules=policy.enable_yara_rules,
            enable_llm_semantic=policy.enable_llm_semantic,
            enable_behavior_analysis=policy.enable_behavior_analysis,
            llm_auto_trigger_on_medium=policy.llm_auto_trigger_on_medium,
            enable_tool_scan=policy.enable_tool_scan,
            enable_prompt_scan=policy.enable_prompt_scan,
            enable_resource_scan=policy.enable_resource_scan,
            enable_instruction_scan=policy.enable_instruction_scan,
            enable_supply_chain=policy.enable_supply_chain,
            policy_mode=policy.policy_mode,
            critical_action=policy.critical_action,
            high_action=policy.high_action,
            medium_action=policy.medium_action,
            low_action=policy.low_action,
            custom_yara_rules=policy.custom_yara_rules or [],
            trusted_servers=policy.trusted_servers or [],
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        ),
    }


# ── Dedicated Scan Endpoint ──────────────────────────────────────────────────

@router.post("/mcp-scanner/scan")
async def scan_mcp_servers(
    request: Request,
    scan_request: McpServerScanRequest,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Scan MCP server data for security issues (standalone batch scan)"""
    if not scan_request.servers:
        raise HTTPException(status_code=400, detail="No servers provided for scanning")

    if len(scan_request.servers) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 servers per scan request")

    # Build policy: use application policy or defaults
    from plugins_builtin.mcp_scanner.cache import mcp_scanner_cache
    policy = await mcp_scanner_cache.get_policy(application_id)

    if not policy:
        from plugins_builtin.mcp_scanner.cache import _PolicySnapshot
        policy = _PolicySnapshot(
            enabled=True,
            enable_yara_rules=True,
            enable_llm_semantic=scan_request.enable_llm if scan_request.enable_llm is not None else False,
            enable_behavior_analysis=True,
            llm_auto_trigger_on_medium=True,
            enable_tool_scan=True,
            enable_prompt_scan=True,
            enable_resource_scan=True,
            enable_instruction_scan=True,
            enable_supply_chain=False,
            policy_mode=scan_request.policy_mode or 'balanced',
            critical_action='block',
            high_action='warn',
            medium_action='log',
            low_action='log',
            custom_yara_rules=[],
            trusted_servers=[],
        )

    force_llm = scan_request.enable_llm if scan_request.enable_llm is not None else False

    from plugins_builtin.mcp_scanner.service import mcp_scanner_service
    result = await mcp_scanner_service.scan_mcp_server_data(
        servers=scan_request.servers,
        policy=policy,
        force_llm=force_llm,
    )

    request_id = str(uuid.uuid4())

    return McpServerScanResponse(
        request_id=request_id,
        result=result,
        scan_timestamp=datetime.utcnow(),
    )


# ── Directory Scan Endpoint (SSE Streaming) ──────────────────────────────────

@router.post("/mcp-scanner/scan-directory")
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
        from plugins_builtin.mcp_scanner.extractors import scan_directory
        try:
            all_servers, servers_by_agent, all_agents = scan_directory(directory)
        except Exception as e:
            yield sse("error", {"message": f"Extraction failed: {str(e)}"})
            return

        agent_summary = {}
        # Only emit agents that have MCP configs
        for agent_name, servers in sorted(servers_by_agent.items()):
            agent_info = {
                "servers_count": len(servers),
                "server_names": [s["name"] for s in servers],
            }
            agent_summary[agent_name] = agent_info
            yield sse("agent_discovered", {
                "agent": agent_name,
                "servers_count": len(servers),
                "server_names": [s["name"] for s in servers],
            })

        yield sse("discovery_complete", {
            "agents_scanned": len(all_agents),
            "total_with_mcp": len(servers_by_agent),
            "servers_extracted": len(all_servers),
        })

        if not all_servers:
            elapsed_ms = (time.time() - start_time) * 1000
            yield sse("complete", {
                "request_id": str(uuid.uuid4()),
                "agents_scanned": len(all_agents), "servers_extracted": 0,
                "servers_by_agent": agent_summary,
                "result": {"findings": [], "servers_scanned": 0, "servers_flagged": 0,
                           "max_severity": "info", "scan_duration_ms": round(elapsed_ms, 1), "engine_summary": {}},
            })
            return

        # ── Phase 2: Static scanning (per-agent) ──────────────────────────
        yield sse("phase", {"phase": "scanning", "message": "正在运行静态安全引擎..."})

        from plugins_builtin.mcp_scanner.cache import mcp_scanner_cache, _PolicySnapshot
        policy = await mcp_scanner_cache.get_policy(application_id)
        if not policy:
            policy = _PolicySnapshot(
                enabled=True, enable_yara_rules=True,
                enable_llm_semantic=False, enable_behavior_analysis=True,
                llm_auto_trigger_on_medium=True,
                enable_tool_scan=True, enable_prompt_scan=True,
                enable_resource_scan=True, enable_instruction_scan=True,
                enable_supply_chain=False,
                policy_mode='strict', critical_action='block', high_action='warn',
                medium_action='log', low_action='log',
                custom_yara_rules=[], trusted_servers=[],
            )

        from plugins_builtin.mcp_scanner.service import mcp_scanner_service

        all_findings = []
        total_scanned = 0
        total_flagged = 0
        engine_summary = {}

        agent_names_sorted = sorted(servers_by_agent.keys())
        for agent_idx, agent_name in enumerate(agent_names_sorted):
            agent_servers = servers_by_agent[agent_name]

            yield sse("scan_progress", {
                "agent": agent_name,
                "agent_index": agent_idx,
                "agents_total": len(agent_names_sorted),
                "servers_count": len(agent_servers),
            })

            formatted = []
            for s in agent_servers:
                formatted.append({
                    "name": s["name"],
                    "tools": s.get("tools", []),
                    "prompts": s.get("prompts", []),
                    "resources": s.get("resources", []),
                    "instructions": s.get("instructions", ""),
                })

            result = await mcp_scanner_service.scan_mcp_server_data(
                servers=formatted, policy=policy, force_llm=False,
            )

            agent_findings = [f.model_dump() for f in result.findings]
            all_findings.extend(agent_findings)
            total_scanned += result.servers_scanned
            total_flagged += result.servers_flagged
            for k, v in (result.engine_summary or {}).items():
                engine_summary[k] = engine_summary.get(k, 0) + v

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
        yield sse("phase", {"phase": "llm_analysis", "message": "AI 正在分析 MCP 安全发现..."})

        if all_findings:
            try:
                from plugins_builtin.mcp_scanner.engines.llm_semantic import enrich_findings_with_llm_streaming

                enriched_count = 0
                async for event in enrich_findings_with_llm_streaming(all_findings, all_servers):
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
                logger.warning(f"MCP LLM enrichment failed: {e}")
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
            "agents_scanned": len(all_agents),
            "servers_extracted": len(all_servers),
            "servers_by_agent": agent_summary,
            "result": {
                "findings": all_findings,
                "servers_scanned": total_scanned,
                "servers_flagged": total_flagged,
                "max_severity": max_sev,
                "scan_duration_ms": round(elapsed_ms, 1),
                "engine_summary": engine_summary,
            },
        })

    return EventSourceResponse(event_generator())
