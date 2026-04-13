"""
SKILL.md Structural Validation Engine — checks skill definition quality and conventions.

Unlike the JSON Schema structural engine (used by Agent Safety for OpenAI tool definitions),
this engine validates SKILL.md format: YAML frontmatter (name, description, allowed-tools)
+ Markdown instruction body.
"""

import re
from typing import List, Dict, Any
from plugins_builtin.skill_scanner.engines import ScanEngine
from plugins_builtin.skill_scanner.models import Finding

# Tool names that indicate dangerous capabilities
DANGEROUS_TOOL_NAMES = re.compile(
    r'^(execute_shell|run_command|eval_code|exec_script|shell_exec|'
    r'system_command|run_shell|bash_exec|code_eval|raw_exec)$',
    re.IGNORECASE,
)

# Dangerous tools that should not appear in allowed-tools
DANGEROUS_ALLOWED_TOOLS = re.compile(
    r'^(Bash|shell|terminal|exec|run_command|execute|system|subprocess|'
    r'code_interpreter|dangerous_tool)$',
    re.IGNORECASE,
)


class SkillStructuralEngine(ScanEngine):
    """Validates SKILL.md definition quality: name, description, allowed-tools, instruction body."""

    @property
    def name(self) -> str:
        return "structural"

    async def scan(self, tools: List[Dict[str, Any]], policy) -> List[Finding]:
        findings = []
        for tool in tools:
            tool_name = tool.get('name', 'unknown')
            findings.extend(self._check_name(tool, tool_name))
            findings.extend(self._check_description(tool, tool_name))
            findings.extend(self._check_allowed_tools(tool, tool_name))
            findings.extend(self._check_instruction_body(tool, tool_name))
        return findings

    def _check_name(self, tool: Dict, tool_name: str) -> List[Finding]:
        """Check skill name for issues"""
        findings = []

        if not tool_name or tool_name == 'unknown':
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='schema_violation',
                severity='medium',
                title='缺少技能名称',
                description='SKILL.md 定义缺少 name 字段',
                field_path='name',
                remediation='请在 YAML frontmatter 中添加 name 字段。',
            ))
            return findings

        if len(tool_name) > 64:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='schema_violation',
                severity='low',
                title='技能名称过长',
                description=f"技能名称长度为 {len(tool_name)} 个字符（建议最大 64 个字符）",
                field_path='name',
                remediation='请使用更短、更具描述性的技能名称。',
            ))

        if DANGEROUS_TOOL_NAMES.match(tool_name):
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='code_execution',
                severity='medium',
                title='技能名称暗示危险能力',
                description=f"技能名称 '{tool_name}' 匹配已知的危险执行模式",
                field_path='name',
                remediation='建议重命名技能，使用描述具体功能的名称，而非通用的执行能力名称。',
            ))

        return findings

    def _check_description(self, tool: Dict, tool_name: str) -> List[Finding]:
        """Check description quality"""
        findings = []
        desc = tool.get('description', '')

        if not desc:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='poor_description',
                severity='medium',
                title='缺少技能描述',
                description=f"技能 '{tool_name}' 没有描述信息，这会增加审计难度并可能导致误用。",
                field_path='description',
                remediation='请在 YAML frontmatter 中添加 description 字段，说明技能的功能及适用场景。',
            ))
        elif len(desc) < 10:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='poor_description',
                severity='low',
                title='技能描述过短',
                description=f"技能 '{tool_name}' 的描述仅 {len(desc)} 个字符，可能不足以安全使用。",
                field_path='description',
                remediation='请提供更详细的描述（建议 20 字符以上），说明技能行为。',
            ))
        elif len(desc) > 1000:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='excessive_scope',
                severity='low',
                title='技能描述异常冗长',
                description=f"技能 '{tool_name}' 的描述长达 {len(desc)} 个字符，过长的描述可能隐藏恶意指令。",
                field_path='description',
                remediation='请保持技能描述简洁（建议 500 字符以内），详细说明应放在 instruction body 中。',
            ))

        return findings

    def _check_allowed_tools(self, tool: Dict, tool_name: str) -> List[Finding]:
        """Check allowed-tools list for dangerous tools and overly broad permissions"""
        findings = []
        allowed_tools = tool.get('allowed_tools', [])

        if not allowed_tools:
            return findings

        # Check for wildcard / overly broad patterns
        for at in allowed_tools:
            if not isinstance(at, str):
                continue
            if at.strip() in ('*', '**', 'all'):
                findings.append(Finding(
                    tool_name=tool_name,
                    engine=self.name,
                    category='overly_permissive',
                    severity='high',
                    title='allowed-tools 使用通配符',
                    description=f"技能 '{tool_name}' 的 allowed-tools 包含 '{at.strip()}'，授予了所有工具权限",
                    field_path='allowed-tools',
                    remediation='请明确列出需要使用的工具，不要使用通配符。',
                ))

            if DANGEROUS_ALLOWED_TOOLS.match(at.strip()):
                findings.append(Finding(
                    tool_name=tool_name,
                    engine=self.name,
                    category='code_execution',
                    severity='high',
                    title=f'allowed-tools 包含危险工具 "{at.strip()}"',
                    description=f"技能 '{tool_name}' 的 allowed-tools 列表包含 '{at.strip()}'，"
                                f"该工具具有代码/命令执行能力",
                    field_path='allowed-tools',
                    remediation=f'请评估是否确实需要 "{at.strip()}" 工具，如果需要，请确保 instruction body 中有足够的安全约束。',
                ))

        # Too many allowed tools
        if len(allowed_tools) > 20:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='excessive_scope',
                severity='medium',
                title=f'allowed-tools 数量过多 ({len(allowed_tools)} 个)',
                description=f"技能 '{tool_name}' 声明了 {len(allowed_tools)} 个允许使用的工具，权限范围过大",
                field_path='allowed-tools',
                remediation='请遵循最小权限原则，只声明技能实际需要的工具。',
            ))

        return findings

    def _check_instruction_body(self, tool: Dict, tool_name: str) -> List[Finding]:
        """Check instruction body quality"""
        findings = []
        body = tool.get('instruction_body', '')

        if not body or len(body.strip()) < 10:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='poor_description',
                severity='low',
                title='instruction body 内容过少',
                description=f"技能 '{tool_name}' 的指令正文为空或过短，缺少具体的执行指导",
                field_path='instruction_body',
                remediation='请在 YAML frontmatter 之后添加详细的 Markdown 指令，说明技能的执行步骤和约束。',
            ))

        # Check for excessively long instruction body (potential prompt stuffing)
        if len(body) > 10000:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='excessive_scope',
                severity='medium',
                title=f'instruction body 异常冗长 ({len(body)} 字符)',
                description=f"技能 '{tool_name}' 的指令正文长达 {len(body)} 字符，过长的指令可能隐藏恶意内容",
                field_path='instruction_body',
                remediation='请精简指令正文，将通用逻辑抽取到独立文档或代码中。',
            ))

        return findings
