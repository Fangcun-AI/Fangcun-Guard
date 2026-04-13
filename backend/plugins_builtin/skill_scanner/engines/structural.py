"""
Structural Validation Engine — checks tool definition schema compliance and parameter constraints.
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

# Parameter names that are sensitive and need constraints
SENSITIVE_PARAM_NAMES = re.compile(
    r'^(command|cmd|query|sql|code|script|shell|eval|exec|expression|'
    r'program|source|input|raw_input|payload|body)$',
    re.IGNORECASE,
)


class StructuralValidationEngine(ScanEngine):
    """Validates tool definition schema quality and parameter constraints"""

    @property
    def name(self) -> str:
        return "structural"

    async def scan(self, tools: List[Dict[str, Any]], policy) -> List[Finding]:
        findings = []

        for tool in tools:
            func = tool.get('function', tool)
            tool_name = func.get('name', 'unknown')

            findings.extend(self._check_schema(tool, tool_name))
            findings.extend(self._check_description(func, tool_name))
            findings.extend(self._check_parameters(func, tool_name))
            findings.extend(self._check_name(func, tool_name))

        return findings

    def _check_schema(self, tool: Dict, tool_name: str) -> List[Finding]:
        """Check basic schema compliance"""
        findings = []
        func = tool.get('function', tool)

        if 'function' in tool and tool.get('type') != 'function':
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='schema_violation',
                severity='low',
                title='工具类型无效',
                description=f"工具 '{tool_name}' 的 type='{tool.get('type')}'，但期望为 'function'",
                field_path='type',
                remediation='请将 type 设为 "function"。',
            ))

        if not func.get('name'):
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='schema_violation',
                severity='medium',
                title='缺少工具名称',
                description='工具定义缺少 name 字段',
                field_path='function.name',
                remediation='请为工具定义添加一个描述性名称。',
            ))

        return findings

    def _check_description(self, func: Dict, tool_name: str) -> List[Finding]:
        """Check description quality"""
        findings = []
        desc = func.get('description', '')

        if not desc:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='poor_description',
                severity='medium',
                title='缺少工具描述',
                description=f"工具 '{tool_name}' 没有描述信息，这会增加审计难度并可能导致误用。",
                field_path='function.description',
                remediation='请添加清晰简洁的描述，说明工具的功能及预期的输入/输出。',
            ))
        elif len(desc) < 10:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='poor_description',
                severity='low',
                title='工具描述过短',
                description=f"工具 '{tool_name}' 的描述仅 {len(desc)} 个字符，可能不足以安全使用。",
                field_path='function.description',
                remediation='请提供更详细的描述（建议 20 字符以上），说明工具行为。',
            ))
        elif len(desc) > 1000:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='excessive_scope',
                severity='low',
                title='工具描述异常冗长',
                description=f"工具 '{tool_name}' 的描述长达 {len(desc)} 个字符，过长的描述可能隐藏恶意指令。",
                field_path='function.description',
                remediation='请保持工具描述简洁（建议 500 字符以内），详细文档应放在其他地方。',
            ))

        return findings

    def _check_parameters(self, func: Dict, tool_name: str) -> List[Finding]:
        """Check parameter type constraints"""
        findings = []
        params = func.get('parameters', {})
        properties = params.get('properties', {})

        if params.get('additionalProperties', False) is True:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='overly_permissive',
                severity='medium',
                title='启用了 additionalProperties',
                description=f"工具 '{tool_name}' 允许参数中传入任意附加属性",
                field_path='function.parameters.additionalProperties',
                remediation='请将 additionalProperties 设为 false，防止未经验证的输入。',
            ))

        # Check required field
        required = params.get('required', None)
        if properties and required is not None:
            if isinstance(required, list) and len(required) == 0:
                findings.append(Finding(
                    tool_name=tool_name,
                    engine=self.name,
                    category='missing_validation',
                    severity='medium',
                    title='required 数组为空',
                    description=f"工具 '{tool_name}' 声明了参数但 required 为空数组，允许调用时不传任何参数",
                    field_path='function.parameters.required',
                    remediation='请在 required 中列出必填参数，或移除 required 字段。',
                ))

        # Check deep nesting (DoS risk)
        max_depth = self._measure_nesting_depth(params)
        if max_depth > 5:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='overly_permissive',
                severity='medium',
                title=f'参数嵌套深度过大 ({max_depth} 层)',
                description=f"工具 '{tool_name}' 的参数定义嵌套 {max_depth} 层，过深的嵌套可能导致 DoS 或解析问题",
                field_path='function.parameters',
                remediation='请将参数嵌套深度控制在 5 层以内。',
            ))

        for param_name, param_def in properties.items():
            if not isinstance(param_def, dict):
                continue

            field_path = f'function.parameters.properties.{param_name}'
            param_type = param_def.get('type', '')

            # Missing type
            if not param_type:
                findings.append(Finding(
                    tool_name=tool_name,
                    engine=self.name,
                    category='missing_validation',
                    severity='medium',
                    title=f'参数 "{param_name}" 缺少类型定义',
                    description=f"工具 '{tool_name}' 的参数 '{param_name}' 没有类型规范",
                    field_path=field_path,
                    remediation='请为此参数指定类型（string、number、boolean 等）。',
                ))

            # String without constraints
            if param_type == 'string':
                has_enum = bool(param_def.get('enum'))
                has_pattern = bool(param_def.get('pattern'))
                has_max_length = 'maxLength' in param_def

                if SENSITIVE_PARAM_NAMES.match(param_name):
                    if not has_enum and not has_pattern:
                        findings.append(Finding(
                            tool_name=tool_name,
                            engine=self.name,
                            category='overly_permissive',
                            severity='high',
                            title=f'敏感参数 "{param_name}" 缺少约束',
                            description=f"参数 '{param_name}'（敏感的执行相关名称）类型为 'string'，但没有 enum、pattern 或 maxLength 约束",
                            field_path=field_path,
                            remediation=f'请为 "{param_name}" 添加 enum、pattern 或 maxLength 约束以防止注入攻击。',
                        ))
                elif not has_enum and not has_pattern and not has_max_length:
                    findings.append(Finding(
                        tool_name=tool_name,
                        engine=self.name,
                        category='overly_permissive',
                        severity='low',
                        title=f'字符串参数 "{param_name}" 无约束',
                        description=f"参数 '{param_name}' 类型为 'string'，但没有任何验证约束",
                        field_path=field_path,
                        remediation='建议添加 enum、pattern 或 maxLength 来约束输入。',
                    ))

            # Very large maxLength
            max_len = param_def.get('maxLength')
            if isinstance(max_len, (int, float)) and max_len > 10000:
                findings.append(Finding(
                    tool_name=tool_name,
                    engine=self.name,
                    category='overly_permissive',
                    severity='low',
                    title=f'参数 "{param_name}" 的 maxLength 过大',
                    description=f"参数 '{param_name}' 允许最多 {max_len} 个字符",
                    field_path=field_path,
                    remediation='请将 maxLength 减小到合理的限制范围。',
                ))

            # Object with additionalProperties
            if param_type == 'object' and param_def.get('additionalProperties', False) is True:
                findings.append(Finding(
                    tool_name=tool_name,
                    engine=self.name,
                    category='overly_permissive',
                    severity='medium',
                    title=f'对象参数 "{param_name}" 允许附加属性',
                    description=f"参数 '{param_name}' 是一个 additionalProperties=true 的对象",
                    field_path=field_path,
                    remediation='请将 additionalProperties 设为 false，或明确定义允许的属性。',
                ))

        return findings

    @staticmethod
    def _measure_nesting_depth(schema: Dict, current_depth: int = 0, max_depth: int = 20) -> int:
        """Recursively measure the maximum nesting depth of a JSON schema."""
        if current_depth >= max_depth or not isinstance(schema, dict):
            return current_depth
        deepest = current_depth
        properties = schema.get('properties', {})
        if isinstance(properties, dict):
            for prop_def in properties.values():
                if isinstance(prop_def, dict):
                    child_depth = StructuralValidationEngine._measure_nesting_depth(
                        prop_def, current_depth + 1, max_depth
                    )
                    deepest = max(deepest, child_depth)
        # Also check items for array types
        items = schema.get('items', {})
        if isinstance(items, dict):
            child_depth = StructuralValidationEngine._measure_nesting_depth(
                items, current_depth + 1, max_depth
            )
            deepest = max(deepest, child_depth)
        return deepest

    def _check_name(self, func: Dict, tool_name: str) -> List[Finding]:
        """Check tool name for issues"""
        findings = []

        if len(tool_name) > 64:
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='schema_violation',
                severity='low',
                title='工具名称过长',
                description=f"工具名称长度为 {len(tool_name)} 个字符（建议最大 64 个字符）",
                field_path='function.name',
                remediation='请使用更短、更具描述性的工具名称。',
            ))

        if DANGEROUS_TOOL_NAMES.match(tool_name):
            findings.append(Finding(
                tool_name=tool_name,
                engine=self.name,
                category='code_execution',
                severity='medium',
                title='工具名称暗示危险能力',
                description=f"工具名称 '{tool_name}' 匹配已知的危险执行模式",
                field_path='function.name',
                remediation='建议重命名工具，使用描述具体功能的名称，而非通用的执行能力名称。',
            ))

        return findings
