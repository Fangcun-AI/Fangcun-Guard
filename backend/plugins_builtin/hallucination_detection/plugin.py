"""
Hallucination Detection Plugin — groundedness checking and consistency analysis.

References:
- AWS Bedrock Guardrails: Contextual Grounding scoring concept
- Arthur AI Engine (MIT): Groundedness + consistency dual-dimension methodology
- NeMo Guardrails (NVIDIA, Apache 2.0): Fact-checking rail pipeline integration
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from plugins.base import DetectionPlugin, PluginMetadata, PluginType, DeploymentMode
from plugins.hooks import HookContext, HookResult, HookPhase
from utils.logger import setup_logger

logger = setup_logger()


class PluginClass(DetectionPlugin):
    """Hallucination Detection plugin"""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="hallucination_detection",
            version="1.0.0",
            description="Hallucination detection: groundedness checking and consistency analysis",
            author="FangcunGuard",
            plugin_type=PluginType.DETECTION,
            deployment_mode=DeploymentMode.BOTH,
            priority=200,
            display_name="幻觉检测",
            display_name_en="Hallucination Detection",
            icon="search-check",
            category="analysis",
            tags=["hallucination", "groundedness", "consistency", "fact-check"],
            documentation=(
                "## 幻觉检测\n\n"
                "对 LLM 输出进行事实依据和内部一致性双维度检测，识别潜在幻觉内容。\n\n"
                "### 核心能力\n\n"
                "- **事实依据检测（Groundedness）**：对比 LLM 输出与参考上下文，"
                "评估每个声明是否有据可依，返回 0.0-1.0 评分\n"
                "- **内部一致性检测（Consistency）**：检查 LLM 输出内部是否存在自相矛盾，"
                "返回 0.0-1.0 评分\n"
                "- **可配置阈值**：通过策略配置调整检测灵敏度\n\n"
                "### 部署模式\n\n"
                "黑盒 + 白盒（同时支持检测 API 5001 和安全网关 5002）\n\n"
                "### 上下文来源\n\n"
                "- System Message（RAG 场景）\n"
                "- extra_body.context（API 参数传入）\n"
                "- extra_body.documents（文档列表传入）\n\n"
                "### 参考设计\n\n"
                "- AWS Bedrock Guardrails: Contextual Grounding 评分理念\n"
                "- Arthur AI Engine (MIT): Groundedness + Consistency 双维度方法论\n"
                "- NeMo Guardrails (NVIDIA, Apache 2.0): Fact-checking rail 管道化集成"
            ),
        )

    async def initialize(self, app_context: Dict[str, Any]) -> None:
        logger.info("Hallucination detection plugin initialized")

    async def shutdown(self) -> None:
        logger.info("Hallucination detection plugin shut down")

    def get_routers(self) -> list:
        from plugins_builtin.hallucination_detection.router import router
        return [router]

    def get_migrations_dir(self) -> Optional[Path]:
        migrations_dir = Path(__file__).parent / "migrations"
        return migrations_dir if migrations_dir.exists() else None

    # ===================== Hooks =====================

    async def on_output_check(self, ctx: HookContext) -> Optional[HookResult]:
        """Hallucination detection on non-streaming proxy output"""
        if not ctx.application_id or not ctx.content or ctx.output_blocked:
            return None

        return await self._run_detection(ctx)

    async def on_detection_check(self, ctx: HookContext) -> Optional[HookResult]:
        """Hallucination detection via Detection API (output direction)"""
        if not ctx.application_id or ctx.detection_direction != "output":
            return None
        if not ctx.content:
            return None

        return await self._run_detection(ctx)

    async def _run_detection(self, ctx: HookContext) -> Optional[HookResult]:
        """Shared detection logic for both output and detection hooks"""
        from plugins_builtin.hallucination_detection.cache import hallucination_cache
        policy = await hallucination_cache.get_policy(str(ctx.application_id))
        if not policy or not policy.enabled:
            return None

        from plugins_builtin.hallucination_detection.service import hallucination_detection_service

        # Extract source context
        messages_as_dicts = []
        if ctx.messages:
            for msg in ctx.messages:
                if isinstance(msg, dict):
                    messages_as_dicts.append(msg)
                else:
                    messages_as_dicts.append({
                        "role": getattr(msg, 'role', ''),
                        "content": getattr(msg, 'content', '') if isinstance(getattr(msg, 'content', ''), str) else str(getattr(msg, 'content', ''))
                    })

        source_context = hallucination_detection_service.extract_source_context(
            messages=messages_as_dicts,
            extra_body=ctx.extra_body,
            policy=policy,
        )

        # Extract assistant output content for evaluation
        output_content = ctx.content
        if not output_content and messages_as_dicts:
            for msg in reversed(messages_as_dicts):
                if msg.get('role') == 'assistant':
                    output_content = msg.get('content', '')
                    break

        if not output_content:
            return None

        result = await hallucination_detection_service.detect(
            output_content=output_content,
            source_context=source_context,
            policy=policy,
        )

        if result.risk_level == 'no_risk':
            return None

        action = None
        blocked_message = None
        if policy.violation_action == 'block':
            action = 'block'
            blocked_message = "Response blocked due to potential hallucination detected."
        elif policy.violation_action in ('flag', 'warn'):
            action = 'warn'
        else:
            action = 'log'

        return HookResult(
            risk_level=result.risk_level,
            categories=result.categories,
            action=action,
            blocked_message=blocked_message,
            metadata={
                "groundedness_score": result.groundedness_score,
                "consistency_score": result.consistency_score,
                "flagged_claims": result.flagged_claims,
            },
        )
