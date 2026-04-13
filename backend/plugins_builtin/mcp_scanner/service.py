"""
MCP Scanner Service — orchestrates the scanning pipeline for MCP server data.

Only exposes scan_mcp_server_data() — no runtime tool scanning
(that is Skill Scanner's job).
"""

import asyncio
import time
from typing import List, Dict, Any
from plugins_builtin.mcp_scanner.models import McpFinding, FindingSeverity, McpScannerResult
from plugins_builtin.mcp_scanner.engines.yara_rules import YaraRulesEngine
from plugins_builtin.mcp_scanner.engines.llm_semantic import LLMSemanticEngine
from plugins_builtin.mcp_scanner.engines.behavior_analysis import BehaviorAnalysisEngine
from utils.logger import setup_logger

logger = setup_logger()

SEVERITY_ORDER = {
    'critical': 4, 'high': 3, 'medium': 2, 'low': 1, 'info': 0,
}
SEVERITY_REVERSE = {v: k for k, v in SEVERITY_ORDER.items()}


class McpScannerService:
    """Orchestrates the MCP server scanning pipeline."""

    def __init__(self):
        self.yara_engine = YaraRulesEngine()
        self.llm_engine = LLMSemanticEngine()
        self.cross_server_engine = BehaviorAnalysisEngine()

    async def scan_mcp_server_data(
        self,
        servers: List[Dict[str, Any]],
        policy,
        force_llm: bool = False,
    ) -> McpScannerResult:
        """Scan complete MCP server descriptors.

        Expected format per server:
        {
            "name": "server-name",
            "tools": [...],           # MCP tool definitions
            "prompts": [...],         # MCP prompt templates (optional)
            "resources": [...],       # MCP resources (optional)
            "instructions": "...",    # Server instructions (optional)
        }
        """
        if not servers:
            return McpScannerResult()

        # Flatten all items with annotations
        all_items: List[Dict[str, Any]] = []
        servers_count = 0
        tools_count = 0
        prompts_count = 0
        resources_count = 0

        trusted = set(getattr(policy, 'trusted_servers', None) or [])

        for server in servers[:50]:
            server_name = server.get('name', f'server_{servers_count}')
            if server_name in trusted:
                continue
            servers_count += 1

            # Tools (MCP-specific poisoning patterns only; generic tool
            # scanning is Skill Scanner's job)
            if getattr(policy, 'enable_tool_scan', True):
                for tool in server.get('tools', [])[:200]:
                    t = dict(tool) if isinstance(tool, dict) else {'name': str(tool)}
                    t['_server_name'] = server_name
                    t['_item_type'] = 'tool'
                    all_items.append(t)
                    tools_count += 1

            # Prompts — MCP-unique, not covered by other plugins
            if getattr(policy, 'enable_prompt_scan', True):
                for prompt in server.get('prompts', [])[:50]:
                    p = dict(prompt) if isinstance(prompt, dict) else {'name': str(prompt)}
                    p['_server_name'] = server_name
                    p['_item_type'] = 'prompt'
                    all_items.append(p)
                    prompts_count += 1

            # Resources — MCP-unique, not covered by other plugins
            if getattr(policy, 'enable_resource_scan', True):
                for resource in server.get('resources', [])[:100]:
                    r = dict(resource) if isinstance(resource, dict) else {'uri': str(resource)}
                    r['_server_name'] = server_name
                    r['_item_type'] = 'resource'
                    all_items.append(r)
                    resources_count += 1

            # Server instructions — MCP-unique, not covered by other plugins
            if getattr(policy, 'enable_instruction_scan', True):
                instructions = server.get('instructions', '')
                if instructions:
                    all_items.append({
                        '_server_name': server_name,
                        '_item_type': 'instruction',
                        'name': f'{server_name}_instructions',
                        'instruction': instructions,
                    })

        result = await self._run_pipeline(all_items, policy, force_llm)
        result.servers_scanned = servers_count
        result.tools_scanned = tools_count
        result.prompts_scanned = prompts_count
        result.resources_scanned = resources_count
        return result

    async def _run_pipeline(
        self,
        items: List[Dict[str, Any]],
        policy,
        force_llm: bool = False,
    ) -> McpScannerResult:
        """Run the scanning pipeline."""
        start_time = time.monotonic()

        # ── Phase 1: Parallel non-LLM engines ──
        phase1_tasks = []
        task_names = []

        if getattr(policy, 'enable_yara_rules', True):
            phase1_tasks.append(self.yara_engine.scan(items, policy))
            task_names.append('yara_rules')

        # Cross-server analysis (only meaningful with 2+ servers)
        server_names = set(i.get('_server_name', '') for i in items)
        if len(server_names) >= 2:
            phase1_tasks.append(self.cross_server_engine.scan(items, policy))
            task_names.append('cross_server_analysis')

        all_findings: List[McpFinding] = []
        engine_summary: Dict[str, int] = {}

        if phase1_tasks:
            phase1_results = await asyncio.gather(*phase1_tasks, return_exceptions=True)
            for i, result in enumerate(phase1_results):
                engine_name = task_names[i]
                if isinstance(result, Exception):
                    logger.error(f"MCP Scanner engine {engine_name} failed: {result}")
                    engine_summary[engine_name] = 0
                    continue
                all_findings.extend(result)
                engine_summary[engine_name] = len(result)

        # ── Phase 2: LLM semantic (conditional) ──
        should_run_llm = force_llm or (
            getattr(policy, 'enable_llm_semantic', False) and (
                not getattr(policy, 'llm_auto_trigger_on_medium', True) or
                any(f.severity in ('critical', 'high', 'medium') for f in all_findings)
            )
        )

        if should_run_llm:
            try:
                llm_findings, false_positive_indices = await self.llm_engine.scan(
                    items, policy, phase1_findings=all_findings,
                )
                for idx in false_positive_indices:
                    if 0 <= idx < len(all_findings):
                        all_findings[idx] = McpFinding(
                            **{
                                **all_findings[idx].model_dump(),
                                'severity': FindingSeverity.INFO,
                                'description': all_findings[idx].description + ' [LLM: likely false positive]',
                            }
                        )
                all_findings.extend(llm_findings)
                engine_summary['llm_semantic'] = len(llm_findings)
            except Exception as e:
                logger.error(f"MCP Scanner LLM engine failed: {e}")

        # ── Aggregate ──
        duration_ms = (time.monotonic() - start_time) * 1000
        return self._aggregate(all_findings, items, duration_ms, engine_summary)

    def _aggregate(
        self,
        findings: List[McpFinding],
        items: List[Dict[str, Any]],
        duration_ms: float,
        engine_summary: Dict[str, int],
    ) -> McpScannerResult:
        actionable = [f for f in findings if f.severity != FindingSeverity.INFO]

        max_sev_val = max(
            (SEVERITY_ORDER.get(f.severity, 0) for f in findings),
            default=0,
        )

        has_critical = any(f.severity == 'critical' for f in actionable)
        has_high = any(f.severity == 'high' for f in actionable)
        has_medium = any(f.severity == 'medium' for f in actionable)

        if has_critical or (has_high and len(actionable) >= 3):
            risk_level = 'high_risk'
        elif has_high or (has_medium and len(actionable) >= 2):
            risk_level = 'medium_risk'
        elif actionable:
            risk_level = 'low_risk'
        else:
            risk_level = 'no_risk'

        return McpScannerResult(
            risk_level=risk_level,
            categories=list(set(f.category for f in actionable)),
            findings=findings,
            servers_scanned=len(set(i.get('_server_name', '') for i in items)),
            servers_flagged=len(set(f.server_name for f in actionable)),
            tools_scanned=len([i for i in items if i.get('_item_type') == 'tool']),
            prompts_scanned=len([i for i in items if i.get('_item_type') == 'prompt']),
            resources_scanned=len([i for i in items if i.get('_item_type') == 'resource']),
            max_severity=SEVERITY_REVERSE.get(max_sev_val, 'info'),
            scan_duration_ms=round(duration_ms, 2),
            engine_summary=engine_summary,
        )


# Global singleton
mcp_scanner_service = McpScannerService()
