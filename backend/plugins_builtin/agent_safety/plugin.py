"""
Agent Safety Plugin — tool call monitoring, argument inspection, reasoning safety audit.

References:
- LlamaFirewall (Meta, MIT): AlignmentCheck CoT audit architecture
- NeMo Guardrails (NVIDIA, Apache 2.0): Tool call safety rail design
- OWASP Top 10 for LLM: 11 built-in injection detection patterns
"""

import time
from pathlib import Path
from typing import Optional, Dict, Any
from plugins.base import DetectionPlugin, PluginMetadata, PluginType, DeploymentMode
from plugins.hooks import HookContext, HookResult, HookPhase
from utils.logger import setup_logger

logger = setup_logger()


class PluginClass(DetectionPlugin):
    """Agent Safety detection plugin"""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="agent_safety",
            version="1.0.0",
            description="Agent safety: tool definition scanning, tool call monitoring, argument inspection, reasoning CoT audit",
            author="FangcunGuard",
            plugin_type=PluginType.DETECTION,
            deployment_mode=DeploymentMode.WHITE_BOX,
            priority=100,
            display_name="Agent 安全防护",
            display_name_en="Agent Safety",
            icon="shield-check",
            category="security",
            tags=["agent", "tool-call", "tool-definition", "reasoning", "injection"],
            documentation=(
                "## Agent 安全防护\n\n"
                "为 AI Agent 的工具定义、工具调用和推理过程提供全方位安全防护。\n\n"
                "### 核心能力\n\n"
                "- **工具定义安全扫描**：对 JSON 工具定义进行安全审计（提示注入、命令注入、数据泄露、混淆、结构缺陷、能力风险）\n"
                "- **工具定义白名单/黑名单**：控制 Agent 可以使用哪些工具\n"
                "- **工具调用参数检测**：19 种内置正则模式检测注入攻击（Shell 注入、路径遍历、SQL 注入等）\n"
                "- **推理链安全审计**：检测思维链中的目标劫持、注入影响、对齐偏离、数据窃取\n\n"
                "### 与 SKILL.md 安全扫描的区别\n\n"
                "- **Agent 安全防护**: 运行时 JSON 工具定义扫描 + 工具调用监控 + 参数注入检测 + 推理链审计\n"
                "- **SKILL.md 安全扫描**: SKILL.md 技能定义文件审计（目录扫描模式）\n\n"
                "### 部署模式\n\n"
                "白盒模式（需通过安全网关 5002 端口接管流量）\n\n"
                "### 参考设计\n\n"
                "- LlamaFirewall (Meta, MIT): AlignmentCheck 思维链审计架构\n"
                "- NeMo Guardrails (NVIDIA, Apache 2.0): 工具调用安全 rail 设计\n"
                "- Cisco AI Defense skill-scanner (Apache 2.0): 多引擎工具定义分析\n"
                "- OWASP Top 10 for LLM: 工具参数注入检测模式"
            ),
        )

    async def initialize(self, app_context: Dict[str, Any]) -> None:
        # Validate database availability
        try:
            from database.connection import get_db
            db = next(get_db())
            db.close()
            logger.info("Agent safety plugin: database connection OK")
        except Exception as e:
            logger.error(f"Agent safety plugin: database unavailable: {e}")
            raise RuntimeError(f"Agent safety plugin requires database: {e}") from e

        # Validate model service configuration (warn, don't fail — reasoning audit will fail-close)
        from config import settings
        if not settings.guardrails_model_api_url:
            logger.warning("Agent safety: GUARDRAILS_MODEL_API_URL not set — reasoning audit will fail-close")
        if not settings.guardrails_model_api_key:
            logger.warning("Agent safety: GUARDRAILS_MODEL_API_KEY not set — reasoning audit will fail-close")

        logger.info("Agent safety plugin initialized")

    async def shutdown(self) -> None:
        logger.info("Agent safety plugin shut down")

    def get_routers(self) -> list:
        from plugins_builtin.agent_safety.router import router
        return [router]

    def get_migrations_dir(self) -> Optional[Path]:
        migrations_dir = Path(__file__).parent / "migrations"
        return migrations_dir if migrations_dir.exists() else None

    # ===================== Hooks =====================

    async def on_input_check(self, ctx: HookContext) -> Optional[HookResult]:
        """Pre-flight tool definition validation + tool definition security scan"""
        if not ctx.application_id or not ctx.tools:
            return None

        from plugins_builtin.agent_safety.cache import agent_safety_cache
        policy = await agent_safety_cache.get_policy(str(ctx.application_id))
        if not policy or not policy.enabled:
            return None

        from plugins_builtin.agent_safety.service import agent_safety_service

        # Phase 1: Whitelist/blacklist check
        result = await agent_safety_service.check_tool_definitions(ctx.tools, policy)

        if result.risk_level != 'no_risk':
            action = None
            blocked_message = None
            if policy.tool_violation_action == 'block':
                action = 'block'
                blocked_message = (
                    f"Tool definition blocked by agent safety policy. "
                    f"Blocked tools: {', '.join(result.blocked_tools)}"
                )
            elif policy.tool_violation_action == 'warn':
                action = 'warn'
            else:
                action = 'log'

            return HookResult(
                risk_level=result.risk_level,
                categories=result.categories,
                action=action,
                blocked_message=blocked_message,
                metadata={
                    "tool_call_count": result.tool_call_count,
                    "blocked_tools": result.blocked_tools,
                },
            )

        # Phase 2: Tool definition security scanning (static patterns, structural, capability risk)
        if getattr(policy, 'enable_tool_definition_scan', True):
            scan_result = await agent_safety_service.check_tool_definition_security(ctx.tools, policy)

            if scan_result.risk_level != 'no_risk':
                scan_action = getattr(policy, 'tool_definition_scan_action', 'warn')
                blocked_message = None
                if scan_action == 'block':
                    blocked_message = (
                        f"Tool definitions blocked by security scan. "
                        f"Found {len(scan_result.definition_scan_findings)} issue(s). "
                        f"Categories: {', '.join(scan_result.categories)}"
                    )

                return HookResult(
                    risk_level=scan_result.risk_level,
                    categories=scan_result.categories,
                    action=scan_action,
                    blocked_message=blocked_message,
                    metadata={
                        "tool_call_count": scan_result.tool_call_count,
                        "definition_scan_findings": scan_result.definition_scan_findings[:20],
                    },
                )

        return None

    async def on_output_check(self, ctx: HookContext) -> Optional[HookResult]:
        """Tool call monitoring (non-streaming output)"""
        if not ctx.application_id or not ctx.tool_calls:
            return None

        from plugins_builtin.agent_safety.cache import agent_safety_cache
        policy = await agent_safety_cache.get_policy(str(ctx.application_id))
        if not policy or not policy.enabled:
            return None

        from plugins_builtin.agent_safety.service import agent_safety_service
        result = await agent_safety_service.check_tool_calls(
            tool_calls=ctx.tool_calls,
            policy=policy,
            application_id=str(ctx.application_id),
        )

        if result.risk_level == 'no_risk':
            return None

        action = None
        blocked_message = None
        if policy.tool_violation_action == 'block':
            action = 'block'
            blocked_message = (
                f"Tool call blocked by agent safety policy. "
                f"Categories: {', '.join(result.categories)}"
            )
        elif policy.tool_violation_action == 'warn':
            action = 'warn'
        else:
            action = 'log'

        return HookResult(
            risk_level=result.risk_level,
            categories=result.categories,
            action=action,
            blocked_message=blocked_message,
            metadata={
                "tool_call_count": result.tool_call_count,
                "blocked_tools": result.blocked_tools,
                "suspicious_arguments": result.suspicious_arguments,
            },
        )

    async def on_stream_complete(self, ctx: HookContext) -> Optional[HookResult]:
        """Reasoning safety audit at stream end"""
        if not ctx.application_id or not ctx.reasoning_content:
            return None

        from plugins_builtin.agent_safety.cache import agent_safety_cache
        policy = await agent_safety_cache.get_policy(str(ctx.application_id))
        if not policy or not policy.enabled or not policy.enable_reasoning_safety:
            return None

        # Extract original user message from messages
        user_message = ""
        if ctx.messages:
            for msg in ctx.messages:
                role = msg.get('role', '') if isinstance(msg, dict) else getattr(msg, 'role', '')
                content = msg.get('content', '') if isinstance(msg, dict) else getattr(msg, 'content', '')
                if role == 'user' and content:
                    user_message = content[:500]
                    break

        from plugins_builtin.agent_safety.service import agent_safety_service
        result = await agent_safety_service.check_reasoning_safety(
            reasoning_content=ctx.reasoning_content,
            original_user_message=user_message,
            tenant_id=ctx.tenant_id,
            application_id=str(ctx.application_id),
        )

        if result.risk_level == 'no_risk':
            return None

        action = None
        blocked_message = None
        if policy.reasoning_violation_action == 'block':
            action = 'block'
            blocked_message = "Response blocked due to reasoning safety concerns."
        elif policy.reasoning_violation_action == 'warn':
            action = 'warn'
        else:
            action = 'log'

        return HookResult(
            risk_level=result.risk_level,
            categories=result.categories,
            action=action,
            blocked_message=blocked_message,
            metadata={"source": "reasoning_audit"},
        )
