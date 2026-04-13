"""
Static Pattern Engine — regex-based detection of dangerous patterns in tool definitions.
Inspired by Cisco skill-scanner's static analyzer + YARA-style pattern matching.
"""

import re
from typing import List, Dict, Any, Tuple
from plugins_builtin.skill_scanner.engines import ScanEngine
from plugins_builtin.skill_scanner.models import Finding


# Pattern format: (compiled_regex, category, title, severity, remediation)
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


# ── Prompt Injection Patterns ──────────────────────────────────────────────────

_PROMPT_INJECTION_RAW = [
    (
        r'(?:you\s+(?:must|should|need\s+to|are\s+required\s+to))\s+(?:always|never|ignore|forget|disregard)',
        'prompt_injection',
        '工具描述中包含命令式指令',
        'critical',
        '请移除工具描述中的行为指令。描述应仅说明工具的功能，不应指示 LLM 的行为。',
    ),
    (
        r'ignore\s+(?:all\s+)?(?:previous|prior|other)\s+(?:instructions|rules|constraints|guidelines)',
        'prompt_injection',
        '检测到系统提示词覆盖攻击',
        'critical',
        '请移除试图覆盖系统指令的文本，这是经典的提示词注入模式。',
    ),
    (
        r'(?:IMPORTANT|NOTE|CRITICAL|SYSTEM|WARNING)\s*:\s*.{20,}',
        'description_manipulation',
        '描述中嵌入了指令块',
        'high',
        '避免在工具描述中使用大写指令块，保持描述客观中立。',
    ),
    (
        r'(?:you\s+are\s+(?:a|an|now)\s+\w+|act\s+as\s+(?:a|an)\s+\w+|pretend\s+to\s+be)',
        'prompt_injection',
        '工具描述中包含角色扮演指令',
        'high',
        '工具描述不应为 LLM 分配角色，请移除角色/人设指令。',
    ),
    (
        r'(?:include|embed|attach|send|return|output)\s+(?:the\s+)?(?:system\s+prompt|instructions|conversation|chat\s+history|previous\s+messages)',
        'data_exfiltration',
        '描述中包含数据提取指令',
        'critical',
        '请移除要求获取系统提示词、对话历史或其他内部数据的指令。',
    ),
    (
        r'(?:DAN|jailbreak|developer\s+mode|unrestricted|no\s+(?:limits|restrictions|rules))',
        'prompt_injection',
        '检测到越狱关键词',
        'critical',
        '请移除工具定义中的越狱相关关键词。',
    ),
    (
        r'[\u200b\u200c\u200d\u2060\ufeff]',
        'obfuscation',
        '检测到零宽字符（可能隐藏文本）',
        'high',
        '请移除零宽 Unicode 字符，这些字符可在工具定义中隐藏不可见的指令。',
    ),
    (
        r'<(?:script|iframe|img\s+onerror|svg\s+onload)[^>]*>',
        'prompt_injection',
        '工具描述中包含 HTML/脚本注入',
        'critical',
        '请移除工具描述中的 HTML 标签，描述应仅为纯文本。',
    ),
]

# ── Command/Code Injection Patterns ────────────────────────────────────────────

_COMMAND_INJECTION_RAW = [
    (
        r'(?:eval|exec)\s*\(',
        'command_injection',
        '引用了 eval/exec 函数',
        'high',
        '避免在工具描述中引用 eval/exec。如工具需执行代码，应使用沙箱化方式描述。',
    ),
    (
        r'(?:os\.(?:system|popen|exec)|subprocess\.(?:run|call|Popen|check_output))',
        'code_execution',
        '引用了 OS/subprocess 执行函数',
        'high',
        '避免直接引用操作系统命令执行函数，如需执行请使用沙箱化方式。',
    ),
    (
        r'(?:sh\s+-c|bash\s+-c|/bin/(?:sh|bash|zsh))',
        'command_injection',
        '检测到 Shell 执行模式',
        'high',
        '请移除 Shell 执行模式。如需 Shell 访问，请使用受限接口。',
    ),
    (
        r'(?:curl|wget|nc\s+-|netcat)\s+',
        'network_access',
        '工具定义中包含网络命令',
        'medium',
        '请明确记录网络访问需求，并限制为必要的端点。',
    ),
    (
        r'\$\{[^}]+\}|\$\([^)]+\)|`[^`]+`',
        'command_injection',
        '检测到 Shell 变量展开/命令替换',
        'high',
        '请移除工具定义中的 Shell 变量展开和命令替换语法。',
    ),
    (
        r'(?:import\s+(?:os|sys|subprocess|shutil|socket|ctypes))',
        'code_execution',
        '引用了危险的 Python 模块',
        'medium',
        '避免在工具描述中引用危险的 Python 模块。',
    ),
    (
        r'(?:DROP\s+TABLE|DELETE\s+FROM|TRUNCATE|ALTER\s+TABLE|GRANT\s+ALL)',
        'command_injection',
        '定义中包含 SQL DDL/DML 命令',
        'high',
        '请移除工具定义中的破坏性 SQL 命令，应使用参数化查询。',
    ),
    (
        r'(?:rm\s+-rf|chmod\s+777|chown\s+root|mkfs|dd\s+if=)',
        'command_injection',
        '检测到破坏性系统命令',
        'critical',
        '请移除破坏性系统命令，这些命令不应出现在工具定义中。',
    ),
]

# ── Data Exfiltration Patterns ─────────────────────────────────────────────────

_DATA_EXFILTRATION_RAW = [
    (
        r'(?:send|post|upload|transmit|forward)\s+(?:to|data|file|content)\s+(?:external|remote|http|url|webhook)',
        'data_exfiltration',
        '描述中包含外部数据传输指令',
        'high',
        '请将出站数据传输限制为已记录且已批准的端点。',
    ),
    (
        r'(?:api[_\-]?key|secret[_\-]?key|password|access[_\-]?token|private[_\-]?key|auth[_\-]?token)',
        'sensitive_data_access',
        '定义中引用了敏感凭证',
        'high',
        '避免在工具描述中引用凭证字段，请使用安全的凭证管理方式。',
    ),
    (
        r'(?:\.env|config\.json|credentials|\.aws|\.ssh|id_rsa|\.kube)',
        'sensitive_data_access',
        '定义中引用了敏感文件',
        'high',
        '请勿在工具定义中引用敏感配置文件。',
    ),
    (
        r'(?:base64\.(?:b64encode|encode)|binascii\.hexlify|codecs\.encode)',
        'obfuscation',
        '引用了编码函数（可能用于数据混淆）',
        'medium',
        '请确保编码操作用于合法的数据格式化，而非混淆目的。',
    ),
    (
        r'(?:webhook|callback\s*url|exfil|phone\s*home|beacon)',
        'data_exfiltration',
        '检测到数据外传关键词',
        'high',
        '请移除数据外传相关关键词，所有出站通信应明确记录。',
    ),
]

# ── Obfuscation Patterns ──────────────────────────────────────────────────────

_OBFUSCATION_RAW = [
    (
        r'[A-Za-z0-9+/]{60,}={0,2}',
        'obfuscation',
        '定义中可能包含 Base64 编码内容',
        'medium',
        '避免在工具定义中使用 Base64 编码内容，应使用纯文本描述。',
    ),
    (
        r'(?:0x[0-9a-fA-F]{2}[\s,]*){10,}',
        'obfuscation',
        '定义中包含十六进制编码内容',
        'medium',
        '请移除工具定义中的十六进制编码内容，使用纯文本。',
    ),
    (
        r'(?:\\u[0-9a-fA-F]{4}){4,}',
        'obfuscation',
        '检测到 Unicode 转义序列链',
        'medium',
        '请将 Unicode 转义序列替换为可读文本。',
    ),
    (
        r'(?:rot13|base64|hex|cipher|encrypt|decrypt)\s*\(',
        'obfuscation',
        '定义中调用了编码/加密函数',
        'medium',
        '请确保编码函数有合理用途且已记录。如用于混淆，应予以移除。',
    ),
]

# ── Placeholder Injection Patterns ───────────────────────────────────────────

_PLACEHOLDER_INJECTION_RAW = [
    (
        r'\{(?:system_instructions|system_prompt|system_message|internal_prompt|admin_prompt)\}',
        'prompt_injection',
        '检测到系统指令占位符注入',
        'critical',
        '请移除引用系统指令的模板占位符，这可能导致系统提示词泄露。',
    ),
    (
        r'\{\{(?:system|admin|config|secret|internal|root|sudo)[^}]*\}\}',
        'prompt_injection',
        '检测到特权模板变量',
        'high',
        '请移除引用特权或内部配置的模板变量。',
    ),
    (
        r'\{%.*(?:import|exec|eval|system|popen).*%\}',
        'code_execution',
        '模板表达式中包含代码执行',
        'critical',
        '请移除模板表达式中的代码执行调用。',
    ),
]

# ── Homoglyph / Confusable Character Patterns ────────────────────────────────

_HOMOGLYPH_RAW = [
    (
        r'[\u0430\u0435\u043e\u0440\u0441\u0445\u0456\u0458]',
        'obfuscation',
        '检测到西里尔字母同形字符（可能伪装为拉丁字母）',
        'high',
        '请将西里尔同形字符替换为对应的 ASCII 拉丁字母，这些字符可能用于绕过关键词检测。',
    ),
    (
        r'[\u03bf\u03b1\u03b5\u03b9\u03ba\u03bd\u03c1\u03c4]',
        'obfuscation',
        '检测到希腊字母同形字符（可能伪装为拉丁字母）',
        'high',
        '请将希腊同形字符替换为对应的 ASCII 拉丁字母。',
    ),
    (
        r'[\uff21-\uff3a\uff41-\uff5a]{3,}',
        'obfuscation',
        '检测到全角 ASCII 字母序列',
        'medium',
        '请将全角 ASCII 字母替换为标准半角字母，全角字符可能用于绕过模式匹配。',
    ),
]

# Compile all patterns
PROMPT_INJECTION_PATTERNS = _compile_patterns(_PROMPT_INJECTION_RAW)
COMMAND_INJECTION_PATTERNS = _compile_patterns(_COMMAND_INJECTION_RAW)
DATA_EXFILTRATION_PATTERNS = _compile_patterns(_DATA_EXFILTRATION_RAW)
OBFUSCATION_PATTERNS = _compile_patterns(_OBFUSCATION_RAW)
PLACEHOLDER_INJECTION_PATTERNS = _compile_patterns(_PLACEHOLDER_INJECTION_RAW)
HOMOGLYPH_PATTERNS = _compile_patterns(_HOMOGLYPH_RAW)

ALL_PATTERNS = (
    PROMPT_INJECTION_PATTERNS
    + COMMAND_INJECTION_PATTERNS
    + DATA_EXFILTRATION_PATTERNS
    + OBFUSCATION_PATTERNS
    + PLACEHOLDER_INJECTION_PATTERNS
    + HOMOGLYPH_PATTERNS
)


def _extract_tool_text(tool: Dict[str, Any]) -> Dict[str, str]:
    """Extract scannable text fields from a tool definition.
    Supports both nested {"type":"function","function":{...}} and flat format.
    Returns dict mapping field_path -> text.
    """
    fields = {}
    func = tool.get('function', tool)
    name = func.get('name', '')
    desc = func.get('description', '')

    fields['function.name'] = name
    fields['function.description'] = desc

    # SKILL.md specific fields
    instruction_body = func.get('instruction_body', '')
    if instruction_body:
        fields['instruction_body'] = instruction_body

    allowed_tools = func.get('allowed_tools', [])
    if allowed_tools and isinstance(allowed_tools, list):
        fields['allowed_tools'] = ' '.join(str(t) for t in allowed_tools)

    # JSON tool definition fields (used by Agent Safety)
    params = func.get('parameters', {})
    properties = params.get('properties', {})
    for param_name, param_def in properties.items():
        if isinstance(param_def, dict):
            pdesc = param_def.get('description', '')
            if pdesc:
                fields[f'function.parameters.properties.{param_name}.description'] = pdesc
            enum_vals = param_def.get('enum', [])
            if enum_vals:
                fields[f'function.parameters.properties.{param_name}.enum'] = ' '.join(str(v) for v in enum_vals)

    return fields


class StaticPatternEngine(ScanEngine):
    """Regex-based detection of dangerous patterns in tool definitions"""

    @property
    def name(self) -> str:
        return "static_pattern"

    async def scan(self, tools: List[Dict[str, Any]], policy) -> List[Finding]:
        findings = []

        # Combine built-in patterns with any custom patterns from policy
        patterns = list(ALL_PATTERNS)
        custom_patterns = getattr(policy, 'custom_patterns', []) or []
        for cp in custom_patterns:
            try:
                compiled = re.compile(cp, re.IGNORECASE)
                patterns.append((
                    compiled, 'prompt_injection', f'自定义规则匹配：{cp[:50]}',
                    'medium', '请审查此自定义规则的匹配结果。',
                ))
            except re.error:
                pass

        for tool in tools:
            func = tool.get('function', tool)
            tool_name = func.get('name', 'unknown')
            text_fields = _extract_tool_text(tool)

            for field_path, text in text_fields.items():
                if not text:
                    continue
                for regex, category, title, severity, remediation in patterns:
                    match = regex.search(text)
                    if match:
                        evidence = match.group(0)[:200]
                        findings.append(Finding(
                            tool_name=tool_name,
                            engine=self.name,
                            category=category,
                            severity=severity,
                            title=title,
                            description=f"在工具 '{tool_name}' 的 {field_path} 字段中匹配到危险模式",
                            evidence=evidence,
                            remediation=remediation,
                            confidence=1.0,
                            field_path=field_path,
                        ))

        return findings
