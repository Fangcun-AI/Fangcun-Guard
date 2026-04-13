"""
Capability Risk Engine — classifies tool capabilities and detects dangerous cross-tool combinations.
"""

from typing import List, Dict, Any, Set, Tuple
from plugins_builtin.skill_scanner.engines import ScanEngine
from plugins_builtin.skill_scanner.models import Finding

# Capability classification keywords (matched against tool name + description)
CAPABILITY_KEYWORDS: Dict[str, List[str]] = {
    "filesystem": [
        "file", "read_file", "write_file", "directory", "path", "folder",
        "disk", "storage", "upload", "download", "open_file", "save_file",
        "list_dir", "mkdir", "rmdir", "rename_file", "copy_file", "move_file",
    ],
    "network": [
        "http", "request", "fetch", "api", "url", "webhook", "socket",
        "connect", "download", "upload", "curl", "get_url", "post_url",
        "send_request", "web_request", "browse",
    ],
    "code_execution": [
        "execute", "eval", "run", "compile", "interpret", "script",
        "shell", "bash", "python", "command", "exec", "invoke",
        "run_code", "run_script", "code_interpreter",
    ],
    "database": [
        "sql", "query", "database", "db", "table", "insert", "update",
        "delete", "select", "mongo", "redis", "postgres", "mysql",
    ],
    "authentication": [
        "login", "password", "token", "credential", "auth", "session",
        "key", "secret", "oauth", "jwt", "api_key", "access_token",
    ],
    "system": [
        "process", "system", "os", "env", "environment", "config",
        "admin", "root", "sudo", "service", "daemon", "registry",
    ],
    "email": [
        "email", "mail", "smtp", "send_message", "notify", "notification",
        "send_email", "compose_email",
    ],
    "browser": [
        "browser", "navigate", "click", "scrape", "screenshot", "dom",
        "page", "web_page", "selenium", "playwright", "puppeteer",
    ],
}

# Cross-tool dangerous combinations
# Format: (source_caps, sink_caps, category, severity, description)
DANGEROUS_COMBINATIONS: List[Tuple[Set[str], Set[str], str, str, str]] = [
    (
        {"filesystem", "database", "authentication"},
        {"network", "email"},
        "data_exfiltration",
        "high",
        "工具集同时具备数据访问和外部传输能力，存在数据泄露链风险",
    ),
    (
        {"code_execution"},
        {"network"},
        "code_execution",
        "high",
        "工具集可实现远程代码执行（代码执行 + 网络访问）",
    ),
    (
        {"authentication"},
        {"code_execution", "system"},
        "privilege_escalation",
        "critical",
        "工具集可实现权限提升（认证 + 代码/系统访问）",
    ),
    (
        {"filesystem"},
        {"code_execution"},
        "command_injection",
        "high",
        "工具集可实现持久化代码篡改（文件系统 + 代码执行）",
    ),
    (
        {"database"},
        {"code_execution"},
        "command_injection",
        "high",
        "工具集可实现 SQL 到代码的攻击链（数据库 + 代码执行）",
    ),
]


def _classify_tool_capabilities(
    tool_name: str, description: str, extra_keywords: List[str] = None,
) -> Set[str]:
    """Classify a single tool's capabilities based on name and description."""
    text = f"{tool_name} {description}".lower()
    capabilities = set()

    for cap_name, keywords in CAPABILITY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                capabilities.add(cap_name)
                break

    # Check extra keywords from policy
    if extra_keywords:
        for kw in extra_keywords:
            if kw.lower() in text:
                capabilities.add("dangerous_custom")
                break

    return capabilities


class CapabilityRiskEngine(ScanEngine):
    """Classifies tool capabilities and detects dangerous cross-tool combinations"""

    @property
    def name(self) -> str:
        return "capability_risk"

    async def scan(self, tools: List[Dict[str, Any]], policy) -> List[Finding]:
        findings = []

        extra_keywords = getattr(policy, 'dangerous_capability_keywords', []) or []

        # Phase 1: Classify each tool individually
        tool_capabilities: Dict[str, Set[str]] = {}
        for tool in tools:
            func = tool.get('function', tool)
            tool_name = func.get('name', 'unknown')
            description = func.get('description', '')

            caps = _classify_tool_capabilities(tool_name, description, extra_keywords)
            tool_capabilities[tool_name] = caps

            # Single-tool risk assessment
            findings.extend(self._assess_single_tool(tool_name, caps))

        # Phase 2: Cross-tool combination analysis
        if len(tools) > 1:
            findings.extend(self._assess_cross_tool(tool_capabilities))

        return findings

    def _assess_single_tool(self, tool_name: str, caps: Set[str]) -> List[Finding]:
        """Assess risk from a single tool's capabilities"""
        findings = []

        if "code_execution" in caps and "system" in caps:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='privilege_escalation',
                severity='high',
                title='工具同时具备系统访问和代码执行能力',
                description=f"工具 '{tool_name}' 同时拥有系统访问和代码执行权限，存在权限提升风险",
                remediation='建议将系统管理和代码执行拆分为独立的、权限受限的工具。',
            ))
        elif "code_execution" in caps:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='code_execution',
                severity='medium',
                title='工具具备代码执行能力',
                description=f"工具 '{tool_name}' 具备代码执行能力，需确保已实施适当的沙箱隔离。",
                remediation='建议实施沙箱化执行，限制权限和资源使用。',
            ))

        if "dangerous_custom" in caps:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='hidden_functionality',
                severity='medium',
                title='工具匹配自定义危险关键词',
                description=f"工具 '{tool_name}' 匹配了用户定义的危险能力关键词",
                remediation='请根据您的安全策略审查此工具定义。',
            ))

        if len(caps - {"dangerous_custom"}) > 3:
            cap_names = {
                'filesystem': '文件系统', 'network': '网络', 'code_execution': '代码执行',
                'database': '数据库', 'authentication': '认证', 'system': '系统',
                'email': '邮件', 'browser': '浏览器',
            }
            cap_display = ', '.join(cap_names.get(c, c) for c in sorted(caps))
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='excessive_scope',
                severity='medium',
                title='工具能力范围过大',
                description=f"工具 '{tool_name}' 横跨 {len(caps)} 个能力类别：{cap_display}",
                remediation='建议按照最小权限原则，将此工具拆分为更小的、单一用途的工具。',
            ))

        return findings

    def _assess_cross_tool(self, tool_capabilities: Dict[str, Set[str]]) -> List[Finding]:
        """Detect dangerous capability combinations across all tools"""
        findings = []

        # Aggregate all capabilities across tools
        all_caps = set()
        cap_to_tools: Dict[str, List[str]] = {}
        for tool_name, caps in tool_capabilities.items():
            all_caps.update(caps)
            for cap in caps:
                cap_to_tools.setdefault(cap, []).append(tool_name)

        category_names = {
            'data_exfiltration': '数据泄露', 'code_execution': '代码执行',
            'privilege_escalation': '权限提升', 'command_injection': '命令注入',
        }

        # Check each dangerous combination
        for source_caps, sink_caps, category, severity, description in DANGEROUS_COMBINATIONS:
            has_source = source_caps & all_caps
            has_sink = sink_caps & all_caps
            if has_source and has_sink:
                # Find involved tools
                source_tools = set()
                for cap in has_source:
                    source_tools.update(cap_to_tools.get(cap, []))
                sink_tools = set()
                for cap in has_sink:
                    sink_tools.update(cap_to_tools.get(cap, []))

                # Only flag if different tools provide source and sink
                if source_tools != sink_tools or len(source_tools) > 1:
                    involved = sorted(source_tools | sink_tools)
                    cat_name = category_names.get(category, category)
                    findings.append(Finding(
                        tool_name=', '.join(involved),
                        engine=self.name,
                        category=category,
                        severity=severity,
                        title=f'危险的跨工具组合：{cat_name}',
                        description=f"{description}。涉及工具：{', '.join(involved)}",
                        remediation='请评估这些工具是否需要共存，考虑按上下文限制工具的可用性。',
                    ))

        return findings
