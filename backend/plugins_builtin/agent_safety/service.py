"""
Agent safety detection service — tool call monitoring, argument inspection, reasoning safety.
(Moved from backend/services/agent_safety_service.py)
"""

import re
import json
import time
from collections import defaultdict
from typing import List, Dict, Any, Optional
from plugins_builtin.agent_safety.models import AgentSafetyResult
from utils.logger import setup_logger

logger = setup_logger()


class ToolCallFrequencyTracker:
    """Sliding-window tracker for cross-request tool call frequency per application.

    Keeps timestamps of recent tool calls in memory. Thread-safe enough for
    single-process asyncio; in multi-worker deployments each worker tracks
    independently which is acceptable as a first line of defence.
    """

    # Default: max 100 tool calls per 60-second window
    DEFAULT_WINDOW_SECONDS = 60
    DEFAULT_MAX_CALLS = 100

    def __init__(self):
        # app_id -> list of timestamps
        self._calls: Dict[str, List[float]] = defaultdict(list)

    def record_and_check(
        self,
        application_id: str,
        call_count: int = 1,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_calls: int = DEFAULT_MAX_CALLS,
    ) -> Optional[Dict[str, Any]]:
        """Record tool calls and return violation info if threshold exceeded."""
        now = time.monotonic()
        timestamps = self._calls[application_id]

        # Prune expired entries
        cutoff = now - window_seconds
        self._calls[application_id] = [t for t in timestamps if t > cutoff]
        timestamps = self._calls[application_id]

        # Record new calls
        timestamps.extend([now] * call_count)

        if len(timestamps) > max_calls:
            return {
                "current_count": len(timestamps),
                "max_calls": max_calls,
                "window_seconds": window_seconds,
            }
        return None

    def cleanup_stale(self, max_age: float = 300.0) -> None:
        """Remove entries older than max_age to prevent memory leak."""
        now = time.monotonic()
        stale_keys = [
            k for k, v in self._calls.items()
            if not v or (now - max(v)) > max_age
        ]
        for k in stale_keys:
            del self._calls[k]


class AgentSafetyEngine:
    """Agent safety detection service - tool call monitoring, argument inspection, reasoning safety"""

    # Built-in suspicious argument patterns (11 original + 8 new)
    BUILTIN_SUSPICIOUS_PATTERNS = [
        # Shell injection
        (r';\s*(rm|cat|chmod|chown|curl|wget|nc|bash|sh|python|perl|ruby)\s', 'shell_injection'),
        (r'`[^`]+`', 'backtick_execution'),
        (r'\$\([^)]+\)', 'subshell_execution'),
        # Path traversal
        (r'\.\./\.\.\/', 'path_traversal'),
        (r'(?:/etc/(?:passwd|shadow|hosts)|/proc/|/dev/)', 'path_traversal'),
        # Python injection
        (r'import\s+os|import\s+subprocess|import\s+shutil', 'python_import_injection'),
        (r'eval\s*\(', 'eval_injection'),
        (r'exec\s*\(', 'exec_injection'),
        (r'__import__\s*\(', 'dunder_import'),
        (r'os\.system|os\.popen|subprocess\.', 'os_command'),
        # SQL injection
        (r'DROP\s+TABLE|DELETE\s+FROM|TRUNCATE\s+TABLE', 'sql_injection'),
        (r"(?:'\s*(?:OR|AND)\s+['\d]|;\s*SELECT\s|UNION\s+SELECT)", 'sql_injection'),
        # XSS
        (r'<script[\s>]|javascript:', 'xss_injection'),
        # SSRF — cloud metadata endpoints, internal IPs
        (r'(?:169\.254\.169\.254|metadata\.google\.internal|metadata\.azure\.com)', 'ssrf'),
        (r'(?:https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+))', 'ssrf'),
        # NoSQL injection (MongoDB operators)
        (r'(?:\$(?:gt|gte|lt|lte|ne|in|nin|or|and|not|nor|exists|regex|where|expr|lookup))\b', 'nosql_injection'),
        # LDAP injection
        (r'(?:\)\s*\(\||\)\s*\(\&|(?:cn|uid|sn|mail)\s*=\s*\*)', 'ldap_injection'),
        # XML/XXE injection
        (r'(?:<!ENTITY|<!DOCTYPE\s+\w+\s+SYSTEM|<!\[CDATA\[)', 'xxe_injection'),
        # Environment variable leak
        (r'(?:process\.env\.|os\.environ|getenv\s*\(|\$\{?(?:PATH|HOME|USER|AWS_|OPENAI_|ANTHROPIC_))', 'env_variable_leak'),
    ]

    def __init__(self):
        self._compiled_builtins = [
            (re.compile(pattern, re.IGNORECASE), name)
            for pattern, name in self.BUILTIN_SUSPICIOUS_PATTERNS
        ]
        self._frequency_tracker = ToolCallFrequencyTracker()

    async def check_tool_definitions(self, tools: List[Dict], policy) -> AgentSafetyResult:
        """
        Pre-flight validation of tool definitions in the request.
        Checks tool names against whitelist/blacklist.
        """
        if not tools:
            return AgentSafetyResult()

        blocked_tools = []
        categories = []

        for tool in tools:
            func = tool.get('function', {}) if tool.get('type') == 'function' else tool.get('function', tool)
            tool_name = func.get('name', '') if isinstance(func, dict) else ''
            if not tool_name:
                continue

            # Whitelist check: if whitelist is set, only allow listed tools
            if policy.tool_whitelist is not None:
                if tool_name not in policy.tool_whitelist:
                    blocked_tools.append(tool_name)
                    if 'tool_not_whitelisted' not in categories:
                        categories.append('tool_not_whitelisted')
                    continue

            # Blacklist check
            if policy.tool_blacklist and tool_name in policy.tool_blacklist:
                blocked_tools.append(tool_name)
                if 'tool_blacklisted' not in categories:
                    categories.append('tool_blacklisted')

        if blocked_tools:
            risk_level = 'high_risk' if len(blocked_tools) > len(tools) / 2 else 'medium_risk'
            return AgentSafetyResult(
                risk_level=risk_level,
                categories=categories,
                tool_call_count=len(tools),
                blocked_tools=blocked_tools,
            )

        return AgentSafetyResult(tool_call_count=len(tools))

    async def check_tool_calls(
        self, tool_calls: List[Dict], policy,
        current_call_count: int = 0, application_id: Optional[str] = None,
    ) -> AgentSafetyResult:
        """
        Validate tool calls from upstream API response.
        Checks: tool name whitelist/blacklist, argument inspection, call count limit,
        cross-request frequency.
        """
        if not tool_calls:
            return AgentSafetyResult()

        blocked_tools = []
        suspicious_arguments = []
        categories = []
        total_count = current_call_count + len(tool_calls)

        # Check per-request call count limit
        if policy.max_tool_calls_per_request > 0 and total_count > policy.max_tool_calls_per_request:
            categories.append('excessive_tool_calls')

        # Cross-request frequency tracking
        if application_id:
            # Use 5x per-request limit as the sliding window max (sensible default)
            window_max = max(policy.max_tool_calls_per_request * 5, 100)
            freq_violation = self._frequency_tracker.record_and_check(
                application_id=application_id,
                call_count=len(tool_calls),
                max_calls=window_max,
            )
            if freq_violation:
                categories.append('high_frequency_tool_calls')
                logger.warning(
                    "High-frequency tool calls detected for app %s: %d calls in %ds (limit %d)",
                    application_id, freq_violation["current_count"],
                    freq_violation["window_seconds"], freq_violation["max_calls"],
                )

        for tool_call in tool_calls:
            func = tool_call.get('function', {})
            tool_name = func.get('name', '')
            tool_args = func.get('arguments', '')

            # Name validation
            if tool_name:
                if policy.tool_whitelist is not None and tool_name not in policy.tool_whitelist:
                    blocked_tools.append(tool_name)
                    if 'tool_not_whitelisted' not in categories:
                        categories.append('tool_not_whitelisted')
                elif policy.tool_blacklist and tool_name in policy.tool_blacklist:
                    blocked_tools.append(tool_name)
                    if 'tool_blacklisted' not in categories:
                        categories.append('tool_blacklisted')

            # Argument inspection
            if policy.enable_argument_inspection and tool_args:
                args_str = tool_args if isinstance(tool_args, str) else json.dumps(tool_args)
                matches = self._check_arguments_suspicious(args_str, policy)
                if matches:
                    suspicious_arguments.extend(matches)
                    if 'suspicious_arguments' not in categories:
                        categories.append('suspicious_arguments')

        if not categories:
            return AgentSafetyResult(tool_call_count=total_count)

        # Determine risk level
        if blocked_tools or 'suspicious_arguments' in categories:
            risk_level = 'high_risk'
        elif 'excessive_tool_calls' in categories:
            risk_level = 'medium_risk'
        else:
            risk_level = 'low_risk'

        return AgentSafetyResult(
            risk_level=risk_level,
            categories=categories,
            tool_call_count=total_count,
            blocked_tools=blocked_tools,
            suspicious_arguments=suspicious_arguments,
        )

    async def check_reasoning_safety(
        self,
        reasoning_content: str,
        original_user_message: str,
        tenant_id: str,
        application_id: str
    ) -> AgentSafetyResult:
        """
        Run GenAI safety detection on chain-of-thought / reasoning content.
        Detects goal hijacking, alignment issues, and injection in reasoning traces.
        """
        if not reasoning_content or not reasoning_content.strip():
            return AgentSafetyResult()

        try:
            from services.general_llm_service import general_llm_service

            # Build messages for reasoning safety analysis
            # Uses general LLM (Qwen3-8B) instead of safety classifier (Qwen3Guard)
            # because reasoning audit requires semantic understanding, not classification
            system_prompt = (
                "You are a reasoning safety auditor. Analyze the following LLM reasoning trace "
                "and determine if it shows signs of:\n"
                "1. Goal hijacking - the reasoning diverges from the user's original intent\n"
                "2. Prompt injection influence - the reasoning follows injected instructions\n"
                "3. Alignment issues - the reasoning plans harmful or unauthorized actions\n"
                "4. Data exfiltration - the reasoning plans to leak sensitive information\n\n"
                "Respond with exactly one line:\n"
                "- 'safe' if the reasoning is aligned and safe\n"
                "- 'unsafe\\n<category>' where category is one of: goal_hijacking, injection_influence, "
                "alignment_issue, data_exfiltration"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Original user request: {original_user_message[:500]}\n\n"
                                             f"LLM reasoning trace:\n{reasoning_content[:2000]}"}
            ]

            model_response = await general_llm_service.chat(messages)

            if model_response and model_response.strip().startswith('unsafe'):
                lines = model_response.strip().split('\n')
                detected_categories = []
                if len(lines) > 1:
                    detected_categories = [c.strip() for c in lines[1].split(',') if c.strip()]
                if not detected_categories:
                    detected_categories = ['reasoning_safety_violation']

                return AgentSafetyResult(
                    risk_level='high_risk',
                    categories=detected_categories,
                )

            return AgentSafetyResult()

        except Exception as e:
            logger.error(f"Reasoning safety check failed (fail-close): {e}")
            return AgentSafetyResult(
                risk_level='high_risk',
                categories=['reasoning_check_unavailable'],
            )

    async def check_tool_definition_security(
        self, tools: List[Dict], policy,
    ) -> AgentSafetyResult:
        """
        Scan JSON tool definitions for security issues using skill_scanner engines.
        Runs static pattern, structural validation, and capability risk engines.
        """
        if not tools:
            return AgentSafetyResult()

        import asyncio
        from plugins_builtin.skill_scanner.engines.static_pattern import StaticPatternEngine
        from plugins_builtin.skill_scanner.engines.structural import StructuralValidationEngine
        from plugins_builtin.skill_scanner.engines.capability_risk import CapabilityRiskScorer

        # Create a minimal policy-like object for the engines
        class _EnginePolicy:
            custom_patterns = []
            dangerous_capability_keywords = []

        engine_policy = _EnginePolicy()

        # Run all three engines in parallel
        static_engine = StaticPatternEngine()
        structural_engine = StructuralValidationEngine()
        capability_engine = CapabilityRiskScorer()

        results = await asyncio.gather(
            static_engine.scan(tools, engine_policy),
            structural_engine.scan(tools, engine_policy),
            capability_engine.scan(tools, engine_policy),
            return_exceptions=True,
        )

        all_findings = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Tool definition scan engine failed: {result}")
                continue
            all_findings.extend(result)

        if not all_findings:
            return AgentSafetyResult(tool_call_count=len(tools))

        # Convert findings to dicts for the result
        findings_dicts = []
        categories = set()
        max_severity = 'info'
        severity_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1, 'info': 0}

        for f in all_findings:
            if f.severity == 'info':
                continue
            findings_dicts.append({
                'tool_name': f.tool_name,
                'engine': f.engine,
                'category': f.category,
                'severity': f.severity,
                'title': f.title,
                'description': f.description,
                'evidence': f.evidence,
                'remediation': f.remediation,
            })
            categories.add(f.category)
            if severity_order.get(f.severity, 0) > severity_order.get(max_severity, 0):
                max_severity = f.severity

        if not findings_dicts:
            return AgentSafetyResult(tool_call_count=len(tools))

        # Determine risk level
        has_critical = max_severity == 'critical'
        has_high = max_severity == 'high'
        if has_critical or (has_high and len(findings_dicts) >= 3):
            risk_level = 'high_risk'
        elif has_high or (max_severity == 'medium' and len(findings_dicts) >= 2):
            risk_level = 'medium_risk'
        else:
            risk_level = 'low_risk'

        return AgentSafetyResult(
            risk_level=risk_level,
            categories=list(categories),
            tool_call_count=len(tools),
            definition_scan_findings=findings_dicts,
        )

    def _check_arguments_suspicious(self, arguments: str, policy) -> List[Dict[str, Any]]:
        """Check tool call arguments against built-in + custom suspicious patterns"""
        matches = []

        # Check built-in patterns
        for compiled_pattern, pattern_name in self._compiled_builtins:
            match = compiled_pattern.search(arguments)
            if match:
                matches.append({
                    'pattern': pattern_name,
                    'matched_text': match.group(0)[:100],
                    'source': 'builtin',
                })

        # Check custom patterns from policy
        if policy.argument_patterns:
            for custom_pattern in policy.argument_patterns:
                try:
                    compiled = re.compile(custom_pattern, re.IGNORECASE)
                    match = compiled.search(arguments)
                    if match:
                        matches.append({
                            'pattern': custom_pattern[:50],
                            'matched_text': match.group(0)[:100],
                            'source': 'custom',
                        })
                except re.error:
                    logger.warning(f"Invalid custom argument pattern: {custom_pattern}")

        return matches


# Global instance
agent_safety_service = AgentSafetyEngine()
