"""
YARA Rules Engine — MCP-specific pattern detection.

This engine ONLY contains patterns for MCP-unique constructs that
Skill Scanner does NOT cover:
  - MCP prompt template injection
  - MCP resource URI attacks
  - MCP server instruction manipulation
  - MCP tool-poisoning patterns specific to the MCP protocol
    (e.g. behavioral manipulation via "before/after calling this tool")

Generic tool-definition patterns (eval/exec, shell injection, base64
obfuscation, etc.) are handled by Skill Scanner and intentionally
NOT duplicated here.
"""

import re
from typing import List, Dict, Any, Tuple
from plugins_builtin.mcp_scanner.engines import McpScanEngine
from plugins_builtin.mcp_scanner.models import McpFinding


def _compile_patterns(raw_patterns: List[Tuple[str, str, str, str, str]]):
    compiled = []
    for pattern_str, category, title, severity, remediation in raw_patterns:
        try:
            compiled.append((
                re.compile(pattern_str, re.IGNORECASE),
                category, title, severity, remediation,
            ))
        except re.error:
            pass
    return compiled


# ══════════════════════════════════════════════════════════════════════════════
# MCP Tool Poisoning — patterns UNIQUE to MCP that Skill Scanner misses
# (Skill Scanner covers generic prompt injection; these target MCP-specific
#  behavioral manipulation that only makes sense in a multi-tool MCP context)
# ══════════════════════════════════════════════════════════════════════════════

_MCP_TOOL_POISONING_RAW = [
    (
        r'(?:before|after)\s+(?:calling|using|running|executing)\s+this\s+tool.*(?:first|also|always|must)',
        'tool_poisoning',
        'MCP tool behavioral manipulation (cross-tool workflow hijacking)',
        'high',
        'MCP tool descriptions should not dictate workflow. Remove instructions that manipulate tool call ordering.',
    ),
    (
        r'(?:do\s+not|never)\s+(?:tell|inform|show|reveal|display)\s+(?:the\s+)?user',
        'tool_poisoning',
        'User deception instruction in MCP tool',
        'critical',
        'Remove instructions that hide information from users.',
    ),
    (
        r'(?:instead\s+of|rather\s+than)\s+(?:using|calling)\s+\w+.*(?:use|call)\s+this\s+tool',
        'tool_poisoning',
        'MCP tool shadowing (replaces other tools)',
        'high',
        'MCP tools should not redirect away from other tools. This may indicate tool shadowing.',
    ),
    (
        r'(?:this\s+tool\s+(?:replaces|overrides|supersedes)|use\s+this\s+(?:instead|in\s+place)\s+of)',
        'tool_poisoning',
        'MCP tool replacement claim',
        'high',
        'Tools should not claim to replace other tools.',
    ),
    (
        r'(?:silently|quietly|without\s+(?:telling|informing|notifying))',
        'tool_poisoning',
        'Stealth operation instruction in MCP tool',
        'critical',
        'Remove stealth-operation instructions from MCP tool definitions.',
    ),
]

# ══════════════════════════════════════════════════════════════════════════════
# MCP Prompt Template Injection — ONLY applies to MCP prompts/list items
# ══════════════════════════════════════════════════════════════════════════════

_PROMPT_TEMPLATE_RAW = [
    (
        r'(?:override|replace|modify)\s+(?:the\s+)?(?:system|base|default)\s+(?:prompt|instructions|behavior)',
        'context_pollution',
        'System prompt override in MCP prompt template',
        'critical',
        'Prompt templates should not override system instructions.',
    ),
    (
        r'\{\{[^}]*(?:system|admin|root|secret|password|token)[^}]*\}\}',
        'parameter_injection',
        'Privileged template variable in MCP prompt',
        'high',
        'Review template variables for injection of privileged data.',
    ),
    (
        r'(?:{{|{%|<%).*(?:exec|eval|import|require|system).*(?:}}|%}|%>)',
        'prompt_injection',
        'Code execution in MCP prompt template expression',
        'critical',
        'Remove code execution from prompt template expressions.',
    ),
    (
        r'(?:include|embed|inject|insert)\s+(?:the\s+)?(?:following|this|these)\s+(?:instructions|rules|directives)',
        'context_pollution',
        'Directive injection in MCP prompt template',
        'high',
        'Prompt templates should provide context, not inject behavioral directives.',
    ),
    (
        r'(?:when\s+(?:this|the)\s+prompt\s+is\s+(?:used|called|invoked)).*(?:always|must|should)',
        'context_pollution',
        'Conditional behavioral manipulation in MCP prompt template',
        'medium',
        'Prompt templates should not contain conditional behavioral instructions.',
    ),
]

# ══════════════════════════════════════════════════════════════════════════════
# MCP Resource URI Patterns — SSRF, local file access, dangerous schemes
# ══════════════════════════════════════════════════════════════════════════════

_RESOURCE_URI_RAW = [
    (
        r'file://(?:/etc/(?:passwd|shadow|hosts|sudoers)|/proc/|/sys/|/dev/|/root/|/home/\w+/\.ssh)',
        'malicious_uri',
        'Sensitive system file URI in MCP resource',
        'critical',
        'MCP resources should not reference sensitive system files.',
    ),
    (
        r'(?:127\.0\.0\.1|localhost|0\.0\.0\.0|::1|169\.254\.169\.254|metadata\.google\.internal|metadata\.azure)',
        'malicious_uri',
        'Internal/cloud-metadata URI in MCP resource (SSRF)',
        'high',
        'MCP resources should not reference internal or cloud metadata addresses.',
    ),
    (
        r'data:(?:text/html|application/javascript|application/x-javascript)',
        'malicious_uri',
        'Executable data URI in MCP resource',
        'high',
        'Avoid executable data URIs in MCP resources.',
    ),
    (
        r'(?:ftp|gopher|dict|ldap|telnet|tftp)://',
        'malicious_uri',
        'Uncommon/dangerous protocol URI in MCP resource',
        'medium',
        'Review uncommon protocol URIs for security implications.',
    ),
    (
        r'file://.*(?:\.env|\.git/|\.ssh/|\.aws/|\.kube/|credentials|secrets)',
        'sensitive_data_exposure',
        'Sensitive config file reference in MCP resource URI',
        'high',
        'Do not expose sensitive configuration files through MCP resources.',
    ),
    # URL-encoded bypass patterns
    (
        r'(?:%2e%2e|%252e%252e|%2f%2e%2e|%c0%ae)',
        'malicious_uri',
        'URL-encoded path traversal bypass in MCP resource URI',
        'high',
        'Detect and block URL-encoded path traversal attempts (double-encoding, overlong UTF-8).',
    ),
    (
        r'(?:%66%69%6c%65|%46%49%4c%45)(?:%3a|:)//',
        'malicious_uri',
        'URL-encoded file:// protocol bypass in MCP resource URI',
        'high',
        'Detect URL-encoded file:// scheme bypass attempts.',
    ),
    # Additional cloud metadata endpoints (ECS task metadata, IPv6 link-local)
    (
        r'(?:100\.100\.100\.200|169\.254\.170\.2|fd00::)',
        'malicious_uri',
        'Additional cloud metadata/container endpoint in MCP resource',
        'high',
        'Block access to cloud container metadata endpoints.',
    ),
    # Punycode/IDN domain bypass (homograph attacks)
    (
        r'xn--[a-z0-9]+\.',
        'malicious_uri',
        'Punycode (IDN) domain in MCP resource URI — potential homograph attack',
        'medium',
        'Review Punycode domains for potential homograph attacks.',
    ),
]

# ══════════════════════════════════════════════════════════════════════════════
# MCP Resource Content Patterns — sensitive data in resource bodies
# ══════════════════════════════════════════════════════════════════════════════

_RESOURCE_CONTENT_RAW = [
    (
        r'(?:api[_\-]?key|secret[_\-]?key|password|access[_\-]?token|private[_\-]?key)\s*[=:]\s*\S+',
        'sensitive_data_exposure',
        'Credential value exposed in MCP resource content',
        'critical',
        'Remove embedded credentials from MCP resource content.',
    ),
    (
        r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----',
        'sensitive_data_exposure',
        'Private key exposed in MCP resource content',
        'critical',
        'Never expose private keys through MCP resources.',
    ),
]

# ══════════════════════════════════════════════════════════════════════════════
# MCP Server Instruction Patterns — initialization directive manipulation
# ══════════════════════════════════════════════════════════════════════════════

_SERVER_INSTRUCTION_RAW = [
    (
        r'(?:this\s+server|this\s+mcp)\s+(?:has|requires|needs)\s+(?:full|admin|root|elevated|unrestricted)\s+(?:access|permissions|privileges)',
        'privilege_escalation',
        'Privilege escalation claim in MCP server instruction',
        'critical',
        'MCP servers should not claim elevated privileges.',
    ),
    (
        r'(?:disable|bypass|skip|turn\s+off|ignore)\s+(?:security|safety|validation|verification|authentication|guardrails)',
        'behavior_manipulation',
        'Security bypass instruction from MCP server',
        'critical',
        'MCP server instructions should not disable security checks.',
    ),
    (
        r'(?:always|automatically)\s+(?:approve|allow|grant|execute|run|trust)\s+(?:all|any|every)',
        'behavior_manipulation',
        'Auto-approve instruction from MCP server',
        'high',
        'MCP server instructions should not auto-approve all actions.',
    ),
    (
        r'(?:do\s+not|never)\s+(?:ask|prompt|confirm|verify|check)\s+(?:the\s+)?(?:user|human|operator)',
        'behavior_manipulation',
        'User confirmation bypass in MCP server instruction',
        'high',
        'MCP servers should not bypass user confirmations.',
    ),
    (
        r'(?:you\s+are|act\s+as|pretend\s+to\s+be|your\s+role\s+is)\s+(?:a|an|the)\s+\w+',
        'instruction_injection',
        'Role assignment in MCP server instruction',
        'high',
        'MCP servers should not assign roles to the LLM via instructions.',
    ),
    (
        r'(?:ignore|forget|disregard)\s+(?:all\s+)?(?:previous|prior|other|user)\s+(?:instructions|rules|requests|messages)',
        'instruction_injection',
        'Instruction override in MCP server initialization',
        'critical',
        'MCP servers should not override prior instructions.',
    ),
    (
        r'(?:prioritize|prefer|favor)\s+(?:this|my|our)\s+(?:server|tools?|instructions?)\s+(?:over|above|before)',
        'behavior_manipulation',
        'Priority manipulation in MCP server instruction',
        'high',
        'MCP servers should not self-elevate priority over other servers or user instructions.',
    ),
]

# ══════════════════════════════════════════════════════════════════════════════
# Obfuscation — zero-width characters (applies to ALL MCP item types)
# ══════════════════════════════════════════════════════════════════════════════

_OBFUSCATION_RAW = [
    (
        r'[\u200b\u200c\u200d\u2060\ufeff]',
        'obfuscation',
        'Zero-width characters in MCP definition (hidden text)',
        'high',
        'Remove zero-width Unicode characters that can hide instructions.',
    ),
]


# ── Compile ──────────────────────────────────────────────────────────────────

MCP_TOOL_POISONING = _compile_patterns(_MCP_TOOL_POISONING_RAW)
PROMPT_TEMPLATE = _compile_patterns(_PROMPT_TEMPLATE_RAW)
RESOURCE_URI = _compile_patterns(_RESOURCE_URI_RAW)
RESOURCE_CONTENT = _compile_patterns(_RESOURCE_CONTENT_RAW)
SERVER_INSTRUCTION = _compile_patterns(_SERVER_INSTRUCTION_RAW)
OBFUSCATION = _compile_patterns(_OBFUSCATION_RAW)

# Per item-type pattern sets
PATTERNS_BY_TYPE = {
    'tool': MCP_TOOL_POISONING + OBFUSCATION,
    'prompt': PROMPT_TEMPLATE + OBFUSCATION,
    'resource': RESOURCE_URI + RESOURCE_CONTENT + OBFUSCATION,
    'instruction': SERVER_INSTRUCTION + OBFUSCATION,
}


# ── Text extraction helpers ──────────────────────────────────────────────────

def _extract_tool_text(tool: Dict[str, Any]) -> Dict[str, str]:
    func = tool.get('function', tool)
    fields = {
        'name': func.get('name', ''),
        'description': func.get('description', ''),
    }
    input_schema = func.get('inputSchema', func.get('parameters', {}))
    if isinstance(input_schema, dict):
        for param_name, param_def in input_schema.get('properties', {}).items():
            if isinstance(param_def, dict) and param_def.get('description'):
                fields[f'inputSchema.{param_name}.description'] = param_def['description']
    return fields


def _extract_prompt_text(prompt: Dict[str, Any]) -> Dict[str, str]:
    fields = {
        'name': prompt.get('name', ''),
        'description': prompt.get('description', ''),
    }
    for arg in prompt.get('arguments', []):
        if isinstance(arg, dict) and arg.get('description'):
            fields[f'arguments.{arg.get("name", "")}.description'] = arg['description']
    return fields


def _extract_resource_text(resource: Dict[str, Any]) -> Dict[str, str]:
    return {
        'uri': resource.get('uri', ''),
        'name': resource.get('name', ''),
        'description': resource.get('description', ''),
        'mimeType': resource.get('mimeType', ''),
        'content': resource.get('content', ''),
    }


def _extract_instruction_text(item: Dict[str, Any]) -> Dict[str, str]:
    return {'instruction': item.get('instruction', '')}


_EXTRACTOR = {
    'tool': _extract_tool_text,
    'prompt': _extract_prompt_text,
    'resource': _extract_resource_text,
    'instruction': _extract_instruction_text,
}


class YaraRulesEngine(McpScanEngine):
    """YARA-style pattern matching for MCP-specific threats only."""

    @property
    def name(self) -> str:
        return "yara_rules"

    async def scan(self, items: List[Dict[str, Any]], policy) -> List[McpFinding]:
        findings = []

        # Custom YARA rules from policy
        custom_compiled = []
        for rule in (getattr(policy, 'custom_yara_rules', None) or []):
            try:
                compiled = re.compile(rule, re.IGNORECASE)
                custom_compiled.append((
                    compiled, 'tool_poisoning', f'Custom rule: {rule[:50]}',
                    'medium', 'Review this custom rule match.',
                ))
            except re.error:
                pass

        for item in items:
            server_name = item.get('_server_name', 'unknown')
            item_type = item.get('_item_type', 'tool')

            patterns = list(PATTERNS_BY_TYPE.get(item_type, [])) + custom_compiled
            extractor = _EXTRACTOR.get(item_type, _extract_tool_text)
            text_fields = extractor(item)
            item_name = text_fields.get('name', item.get('name', 'unknown'))

            for field_path, text in text_fields.items():
                if not text:
                    continue
                for regex, category, title, severity, remediation in patterns:
                    match = regex.search(text)
                    if match:
                        findings.append(McpFinding(
                            server_name=server_name,
                            item_name=item_name,
                            item_type=item_type,
                            engine=self.name,
                            category=category,
                            severity=severity,
                            title=title,
                            description=f"In {field_path} of {item_type} '{item_name}' from server '{server_name}'",
                            evidence=match.group(0)[:200],
                            remediation=remediation,
                            confidence=1.0,
                            field_path=field_path,
                        ))

        return findings
