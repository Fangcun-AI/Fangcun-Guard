"""
Basic Guard Plugin — core safety protection suite.

Provides streaming output safety detection:
  - Content pattern detection (system prompt leakage, jailbreak indicators)
  - Reasoning divergence detection
  - Output anomaly detection (repetition loops)

Prompt injection detection (L1 static regex + L2 Prompt Guard + L3 Qwen3Guard S9)
runs in the core pipeline (detection_guardrail_service.py), NOT in plugin hooks.

The core guardrail features (content safety model detection, DLP,
blacklist/whitelist, ban policy, response templates) run independently
in guardrail_service.py — this plugin REPRESENTS them in the UI and
provides ACTIVE streaming output detection capabilities.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from plugins.base import DetectionPlugin, PluginMetadata, PluginType, DeploymentMode
from plugins.hooks import HookContext, HookResult
from utils.logger import setup_logger

logger = setup_logger()


class PluginClass(DetectionPlugin):
    """Fangcun Core Shield — core safety protection plugin"""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="basic_guard",
            version="1.0.0",
            description="Core safety: prompt injection detection, content safety (19 categories), DLP, blacklist/whitelist, ban policy, response templates, streaming output safety",
            author="FangcunGuard",
            plugin_type=PluginType.DETECTION,
            deployment_mode=DeploymentMode.BOTH,
            priority=50,
            display_name="方寸安全基座",
            display_name_en="Fangcun Core Shield",
            icon="shield",
            category="security",
            tags=["core", "content-safety", "prompt-injection", "dlp", "blacklist", "streaming", "output-safety"],
            documentation=(
                "## 基础安全防护\n\n"
                "FangcunGuard 核心安全防护套件，提供全方位的 AI 安全基座能力。\n\n"
                "### 核心能力\n\n"
                "#### 0. 提示注入检测（Prompt Injection Guard）\n"
                "基于 Llama Prompt Guard 2（86M DeBERTa 模型，<10ms 推理延迟）：\n"
                "- **直接注入/越狱**：角色扮演攻击、忽略指令、DAN 越狱等\n"
                "- **间接注入**：RAG 检索内容、工具返回内容中的隐藏指令\n"
                "- 三分类输出：BENIGN / INJECTION / JAILBREAK\n\n"
                "#### 1. 内容安全检测（19 风险类别）\n"
                "基于 Qwen3Guard-Gen-8B 模型，覆盖：\n"
                "- **高风险**：敏感政治(S2)、暴力犯罪(S3)、提示攻击(S5)、大规模杀伤性武器(S9)、性犯罪(S15)、敏感政治(S17)\n"
                "- **中风险**：未成年人伤害(S4)、非暴力犯罪(S6)、色情内容(S7)、自残自杀(S16)\n"
                "- **低风险**：一般政治(S1)、仇恨言论(S8)、脏话(S10)、隐私(S11)、商业(S12)、知识产权(S13)、骚扰(S14)、威胁(S18)、专业建议(S19)\n\n"
                "#### 2. 数据泄露防护（DLP）\n"
                "- 格式感知检测（JSON/YAML/CSV/Markdown/纯文本）\n"
                "- 智能分段并行处理\n"
                "- 正则实体检测（身份证、信用卡等）\n"
                "- GenAI 实体检测\n"
                "- 处置策略：阻断 / 匿名化 / 切换私有模型 / 放行\n\n"
                "#### 3. 黑名单 / 白名单\n"
                "- 关键词白名单：命中即放行\n"
                "- 关键词黑名单：命中即拦截\n\n"
                "#### 4. 封禁策略\n"
                "- 自动封禁规则（阈值、时长）\n"
                "- IP / 用户维度封禁\n\n"
                "#### 5. 响应模板\n"
                "- 知识库问答（向量相似度匹配）\n"
                "- 自定义风险类别响应模板\n\n"
                "#### 6. 流式输出安全检测\n"
                "- **内容安全模式检测**：检测系统提示泄露、越狱指示器、指令覆盖确认、编码混淆输出\n"
                "- **推理链偏离检测**：检测意图重解释、安全绕过意图、角色扮演偏离\n"
                "- **输出异常检测**：检测重复循环输出等异常模式\n\n"
                "### 部署模式\n\n"
                "黑盒 + 白盒（核心检测支持检测 API 5001；流式检测需安全网关 5002）\n\n"
                "### 检测阶段\n\n"
                "- **流式完成阶段**：Token 输出完毕后对完整内容进行安全回扫\n"
                "- **输出阶段**：非流式响应同样进行输出内容安全检查"
            ),
        )

    async def initialize(self, app_context: Dict[str, Any]) -> None:
        logger.info("Basic guard plugin initialized")
        # Check if Prompt Guard server is reachable
        from plugins_builtin.basic_guard.prompt_guard_service import prompt_injection_service
        healthy = await prompt_injection_service.health_check()
        if healthy:
            logger.info("Prompt Guard server is reachable")
        else:
            logger.warning("Prompt Guard server is NOT reachable — PI detection will fail-open")

    async def shutdown(self) -> None:
        from plugins_builtin.basic_guard.prompt_guard_service import prompt_injection_service
        await prompt_injection_service.close()
        logger.info("Basic guard plugin shut down")

    def get_routers(self) -> list:
        from plugins_builtin.basic_guard.router import router
        return [router]

    def get_migrations_dir(self) -> Optional[Path]:
        migrations_dir = Path(__file__).parent / "migrations"
        return migrations_dir if migrations_dir.exists() else None

    # ===================== Hooks =====================
    # NOTE: Prompt injection detection (L1 regex + L2 Prompt Guard + L3 Qwen3Guard S9)
    # is handled entirely by the core pipeline (detection_guardrail_service.py).
    # This plugin only handles streaming/output safety checks.

    async def on_stream_complete(self, ctx: HookContext) -> Optional[HookResult]:
        """Audit streaming output after all tokens are received"""
        if not ctx.application_id:
            return None
        if not ctx.content and not ctx.reasoning_content:
            return None

        from plugins_builtin.basic_guard.cache import basic_guard_cache
        policy = await basic_guard_cache.get_policy(str(ctx.application_id))
        if not policy or not policy.enabled:
            return None

        user_message = ""
        if ctx.messages:
            for msg in ctx.messages:
                role = msg.get('role', '') if isinstance(msg, dict) else getattr(msg, 'role', '')
                content = msg.get('content', '') if isinstance(msg, dict) else getattr(msg, 'content', '')
                if role == 'user' and content:
                    user_message = content[:500]
                    break

        from plugins_builtin.basic_guard.service import basic_guard_service
        result = await basic_guard_service.check_streaming_output(
            content=ctx.content or "",
            reasoning_content=ctx.reasoning_content or "",
            user_message=user_message,
            policy=policy,
        )

        if result.risk_level == 'no_risk':
            return None

        action = policy.violation_action
        blocked_message = None
        if action == 'block':
            blocked_message = "Response blocked due to streaming output safety concerns."

        return HookResult(
            risk_level=result.risk_level,
            categories=result.categories,
            action=action,
            blocked_message=blocked_message,
            metadata={
                "source": "basic_guard",
                "content_length": result.content_length,
                "reasoning_length": result.reasoning_length,
                "details": [d for d in result.details],
            },
        )

    async def on_output_check(self, ctx: HookContext) -> Optional[HookResult]:
        """Check non-streaming output content"""
        if not ctx.application_id or not ctx.content:
            return None
        if ctx.output_blocked:
            return None

        from plugins_builtin.basic_guard.cache import basic_guard_cache
        policy = await basic_guard_cache.get_policy(str(ctx.application_id))
        if not policy or not policy.enabled:
            return None

        from plugins_builtin.basic_guard.service import basic_guard_service
        result = await basic_guard_service.check_streaming_output(
            content=ctx.content,
            reasoning_content="",
            user_message="",
            policy=policy,
        )

        if result.risk_level == 'no_risk':
            return None

        action = policy.violation_action
        blocked_message = None
        if action == 'block':
            blocked_message = "Response blocked due to output safety concerns."

        return HookResult(
            risk_level=result.risk_level,
            categories=result.categories,
            action=action,
            blocked_message=blocked_message,
            metadata={
                "source": "basic_guard_output",
                "content_length": result.content_length,
                "details": [d for d in result.details],
            },
        )
