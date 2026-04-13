"""
Cross-Server Trust Boundary Engine — analyzes MULTI-SERVER capability
combinations and trust boundary violations.

Skill Scanner already handles single-tool and same-request cross-tool
capability risk.  This engine focuses on what Skill Scanner CANNOT see:
  - Capabilities spread across DIFFERENT MCP servers
  - Trust boundary violations (trusted server A + untrusted server B)
  - Server-level capability aggregation and attack surface assessment

Only meaningful when scanning 2+ MCP servers simultaneously.
"""

import re
from typing import List, Dict, Any, Set
from plugins_builtin.mcp_scanner.engines import McpScanEngine
from plugins_builtin.mcp_scanner.models import McpFinding


# Capability detection (regex-based, applied to tool name + description)
CAPABILITY_PATTERNS: Dict[str, re.Pattern] = {
    'filesystem':       re.compile(r'(?:read|write|create|delete|list|move|copy)\s+(?:file|directory|folder|path)|(?:file_system|filesystem|fs_|upload|download)\s+file', re.I),
    'network':          re.compile(r'(?:http|https|fetch|request|api|curl|wget|send|receive|connect|socket|webhook|url|endpoint)', re.I),
    'code_execution':   re.compile(r'(?:execute|run|eval|exec|interpret)\s+(?:code|script|command|shell|program)|(?:python|javascript|bash|shell|terminal|subprocess)', re.I),
    'database':         re.compile(r'(?:query|select|insert|update|delete|sql|database|db|postgres|mysql|sqlite|mongo|redis)', re.I),
    'authentication':   re.compile(r'(?:login|logout|auth|token|credential|password|oauth|jwt|session|api.key|access.token)', re.I),
    'system_admin':     re.compile(r'(?:install|configure|deploy|restart|kill|process|admin|root|sudo|privilege|permission|chmod|env)', re.I),
    'email':            re.compile(r'(?:send|receive|compose)\s+(?:email|mail|message)|(?:smtp|imap)', re.I),
    'browser':          re.compile(r'(?:browse|navigate|click|screenshot|scrape|crawl|browser|puppeteer|selenium|playwright)', re.I),
}

# Cross-server dangerous combinations
CROSS_SERVER_CHAINS = [
    {
        'caps': ('filesystem', 'network'),
        'title': 'Cross-server data exfiltration: server A reads files, server B sends data',
        'severity': 'critical',
        'category': 'cross_tool_attack_chain',
        'description': 'Separate MCP servers provide filesystem read and network send capabilities. '
                       'An attacker could chain them: read sensitive files via server A, exfiltrate via server B.',
    },
    {
        'caps': ('code_execution', 'network'),
        'title': 'Cross-server RCE: server A fetches payload, server B executes',
        'severity': 'critical',
        'category': 'cross_tool_attack_chain',
        'description': 'Separate MCP servers provide network access and code execution. '
                       'An attacker could download malicious code from one and execute via the other.',
    },
    {
        'caps': ('authentication', 'code_execution'),
        'title': 'Cross-server privilege escalation: server A manages auth, server B executes code',
        'severity': 'critical',
        'category': 'cross_tool_attack_chain',
        'description': 'Separate MCP servers provide credential access and code execution. '
                       'Stolen credentials from one server could enable unauthorized code execution.',
    },
    {
        'caps': ('database', 'network'),
        'title': 'Cross-server DB exfiltration: server A queries data, server B transmits',
        'severity': 'high',
        'category': 'cross_tool_attack_chain',
        'description': 'Separate MCP servers provide database access and network transmission. '
                       'An attacker could query sensitive data and exfiltrate it externally.',
    },
    {
        'caps': ('filesystem', 'code_execution'),
        'title': 'Cross-server persistence: server A writes files, server B executes',
        'severity': 'high',
        'category': 'cross_tool_attack_chain',
        'description': 'Separate MCP servers provide file write and code execution. '
                       'An attacker could write malicious files and then execute them.',
    },
    {
        'caps': ('system_admin', 'network'),
        'title': 'Cross-server lateral movement: server A configures system, server B has network access',
        'severity': 'high',
        'category': 'cross_tool_attack_chain',
        'description': 'Separate MCP servers provide system admin and network capabilities. '
                       'Could enable lateral movement across infrastructure.',
    },
]


def _detect_server_capabilities(tools: List[Dict[str, Any]]) -> Set[str]:
    """Detect aggregate capabilities across all tools from one server."""
    capabilities = set()
    for tool in tools:
        func = tool.get('function', tool)
        text = f"{func.get('name', '')} {func.get('description', '')}"
        for cap_name, pattern in CAPABILITY_PATTERNS.items():
            if pattern.search(text):
                capabilities.add(cap_name)
    return capabilities


class BehaviorAnalysisEngine(McpScanEngine):
    """Cross-server trust boundary and capability combination analysis.

    Only produces findings when 2+ servers are scanned together, since
    single-server capability risk is already covered by Skill Scanner.
    """

    @property
    def name(self) -> str:
        return "cross_server_analysis"

    async def scan(self, items: List[Dict[str, Any]], policy) -> List[McpFinding]:
        # Group tools by server
        servers: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            if item.get('_item_type') != 'tool':
                continue
            server = item.get('_server_name', 'unknown')
            servers.setdefault(server, []).append(item)

        # Need 2+ servers to detect cross-server issues
        if len(servers) < 2:
            return []

        findings = []

        # Compute per-server capabilities
        server_caps: Dict[str, Set[str]] = {}
        for server_name, tools in servers.items():
            server_caps[server_name] = _detect_server_capabilities(tools)

        # ── Cross-server attack chain detection ──
        for chain in CROSS_SERVER_CHAINS:
            cap_a, cap_b = chain['caps']
            servers_with_a = [s for s, caps in server_caps.items() if cap_a in caps]
            servers_with_b = [s for s, caps in server_caps.items() if cap_b in caps]

            if not servers_with_a or not servers_with_b:
                continue

            # Only flag if DIFFERENT servers provide the two capabilities
            # (same-server is Skill Scanner's job)
            cross_pairs = [
                (sa, sb) for sa in servers_with_a for sb in servers_with_b if sa != sb
            ]
            if not cross_pairs:
                continue

            # Report one finding per unique chain
            server_a, server_b = cross_pairs[0]
            findings.append(McpFinding(
                server_name=f"{server_a} + {server_b}",
                item_name=f"cross-server ({cap_a} + {cap_b})",
                item_type='tool',
                engine=self.name,
                category=chain['category'],
                severity=chain['severity'],
                title=chain['title'],
                description=f"{chain['description']} "
                            f"Server '{server_a}' provides {cap_a}; "
                            f"server '{server_b}' provides {cap_b}.",
                remediation='Consider whether both servers need to be active simultaneously. '
                            'Apply least-privilege by limiting tool availability per conversation.',
                confidence=0.8,
            ))

        # ── High aggregate attack surface ──
        total_caps = set()
        for caps in server_caps.values():
            total_caps.update(caps)

        if len(total_caps) >= 5:
            findings.append(McpFinding(
                server_name='all servers',
                item_name='aggregate attack surface',
                item_type='tool',
                engine=self.name,
                category='cross_tool_attack_chain',
                severity='medium',
                title=f'High aggregate attack surface: {len(total_caps)} capability categories across {len(servers)} servers',
                description=f"Combined MCP servers expose {len(total_caps)} capability categories: "
                            f"{', '.join(sorted(total_caps))}. "
                            f"Servers: {', '.join(sorted(servers.keys()))}. "
                            f"Large attack surface increases risk of multi-step attacks.",
                remediation='Review whether all servers need to be connected simultaneously. '
                            'Consider dynamic tool selection to reduce per-request attack surface.',
                confidence=0.7,
            ))

        return findings
