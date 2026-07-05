"""
Skill Scanner Service — orchestrates the two-phase scanning pipeline.
"""

import asyncio
import time
from typing import List, Dict, Any
from plugins_builtin.skill_scanner.models import Finding, FindingSeverity, SkillScannerResult
from plugins_builtin.skill_scanner.engines.static_pattern import StaticPatternEngine
from plugins_builtin.skill_scanner.engines.skill_structural import SkillStructuralEngine
from plugins_builtin.skill_scanner.engines.capability_risk import CapabilityRiskScorer
from plugins_builtin.skill_scanner.engines.llm_semantic import LlmSemanticAnalyzer
from utils.logger import setup_logger

logger = setup_logger()

SEVERITY_ORDER = {
    'critical': 4,
    'high': 3,
    'medium': 2,
    'low': 1,
    'info': 0,
}
SEVERITY_REVERSE = {v: k for k, v in SEVERITY_ORDER.items()}


class SkillScannerService:
    """Orchestrates the two-phase skill scanning pipeline"""

    def __init__(self):
        self.static_engine = StaticPatternEngine()
        self.structural_engine = SkillStructuralEngine()
        self.capability_engine = CapabilityRiskScorer()
        self.llm_engine = LlmSemanticAnalyzer()

    async def scan_tools(
        self,
        tools: List[Dict[str, Any]],
        policy,
        force_llm: bool = False,
    ) -> SkillScannerResult:
        """Full two-phase scan pipeline"""
        if not tools:
            return SkillScannerResult()

        # Cap tool count
        tools = tools[:100]
        start_time = time.monotonic()

        # ── Phase 1: Parallel non-LLM engines ──────────────────────────────

        phase1_tasks = []
        task_names = []

        if getattr(policy, 'enable_static_pattern', True):
            phase1_tasks.append(self.static_engine.scan(tools, policy))
            task_names.append('static_pattern')

        if getattr(policy, 'enable_structural_validation', True):
            phase1_tasks.append(self.structural_engine.scan(tools, policy))
            task_names.append('structural')

        if getattr(policy, 'enable_capability_risk', True):
            phase1_tasks.append(self.capability_engine.scan(tools, policy))
            task_names.append('capability_risk')

        all_findings: List[Finding] = []
        engine_summary: Dict[str, int] = {}

        if phase1_tasks:
            phase1_results = await asyncio.gather(*phase1_tasks, return_exceptions=True)
            for i, result in enumerate(phase1_results):
                engine_name = task_names[i]
                if isinstance(result, Exception):
                    logger.error(f"Engine {engine_name} failed: {result}")
                    engine_summary[engine_name] = 0
                    continue
                all_findings.extend(result)
                engine_summary[engine_name] = len(result)

        phase1_count = len(all_findings)

        # ── Phase 2: LLM semantic (conditional) ────────────────────────────

        should_run_llm = force_llm or (
            getattr(policy, 'enable_llm_semantic', False) and (
                not getattr(policy, 'llm_auto_trigger_on_medium', True) or
                any(f.severity in ('critical', 'high', 'medium') for f in all_findings)
            )
        )

        phase2_count = 0
        if should_run_llm:
            try:
                llm_findings, false_positive_indices = await self.llm_engine.scan(
                    tools, policy, phase1_findings=all_findings,
                )
                # Apply meta-filtering: downgrade false positives
                for idx in false_positive_indices:
                    if 0 <= idx < len(all_findings):
                        all_findings[idx] = all_findings[idx].model_copy(update={
                            'severity': FindingSeverity.INFO,
                            'description': all_findings[idx].description + ' [LLM meta-filter: likely false positive]',
                        })

                all_findings.extend(llm_findings)
                phase2_count = len(llm_findings)
                engine_summary['llm_semantic'] = phase2_count
            except Exception as e:
                logger.error(f"LLM semantic engine failed: {e}")

        # ── Aggregate ───────────────────────────────────────────────────────

        duration_ms = (time.monotonic() - start_time) * 1000
        return self._aggregate_result(
            all_findings, len(tools), duration_ms,
            phase1_count, phase2_count, engine_summary,
        )

    def _aggregate_result(
        self,
        findings: List[Finding],
        tools_count: int,
        duration_ms: float,
        phase1_count: int,
        phase2_count: int,
        engine_summary: Dict[str, int],
    ) -> SkillScannerResult:
        """Aggregate findings into SkillScannerResult"""
        # Filter out INFO-level for risk assessment
        actionable = [f for f in findings if f.severity != FindingSeverity.INFO]

        max_sev_val = max(
            (SEVERITY_ORDER.get(f.severity, 0) for f in findings),
            default=0,
        )
        max_severity_str = SEVERITY_REVERSE.get(max_sev_val, 'info')

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

        flagged_tools = len(set(f.tool_name for f in actionable))
        categories = list(set(f.category for f in actionable))

        return SkillScannerResult(
            risk_level=risk_level,
            categories=categories,
            findings=findings,
            tools_scanned=tools_count,
            tools_flagged=flagged_tools,
            max_severity=max_severity_str,
            scan_duration_ms=round(duration_ms, 2),
            phase1_findings=phase1_count,
            phase2_findings=phase2_count,
            engine_summary=engine_summary,
        )


# Global singleton
skill_scanner_service = SkillScannerService()
