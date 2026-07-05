"""
MCP Scanner Plugin — pre-deployment security auditor for MCP servers.

Positioned as a **standalone / on-demand** scanner for MCP servers, NOT a
runtime proxy hook.  Runtime tool-definition scanning is handled by
Skill Scanner; runtime tool-call monitoring is handled by Agent Safety.

MCP Scanner covers dimensions that those plugins cannot:
  - MCP prompt templates
  - MCP resources & URI safety
  - MCP server instructions (initialization directives)
  - Cross-server trust boundary analysis

Invocation paths:
  1. POST /api/v1/mcp-scanner/scan  (standalone batch scan)
  2. Detection API extra_body.mcp_servers  (on_detection_check hook)

References:
- Cisco AI Defense mcp-scanner (Apache 2.0)
- OWASP Top 10 for LLM: MCP server security best practices
"""

from pathlib import Path
from typing import Optional, Dict, Any
from plugins.base import DetectionPlugin, PluginMetadata, PluginType, DeploymentMode
from plugins.hooks import HookContext, HookResult
from utils.logger import setup_logger

logger = setup_logger()


class PluginClass(DetectionPlugin):
    """MCP Scanner plugin — pre-deployment auditor for MCP servers.

    Does NOT hook on_input_check (Skill Scanner already covers runtime
    tool definitions).  Only responds to explicit scan requests.
    """

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mcp_scanner",
            version="1.0.0",
            description="MCP server pre-deployment scanner: audits prompts, resources, instructions, and cross-server trust boundaries",
            author="FangcunGuard",
            plugin_type=PluginType.DETECTION,
            deployment_mode=DeploymentMode.BOTH,
            priority=85,
            display_name="MCP 安全审计",
            display_name_en="MCP Security Audit",
            icon="network",
            category="security",
            tags=["mcp", "tool-poisoning", "prompt-injection", "supply-chain", "server-audit"],
            documentation=(
                "## MCP 服务器安全扫描\n\n"
                "对 AI 应用连接的 MCP 服务器进行 **部署前 / 按需** 安全审计。\n\n"
                "### 定位（与其他插件零重叠）\n\n"
                "| 插件 | 职责 |\n"
                "|------|------|\n"
                "| **Skill Scanner** | 运行时扫描所有 tool 定义（on_input_check） |\n"
                "| **Agent Safety** | 运行时监控 tool 调用参数 + 推理链 |\n"
                "| **MCP Scanner** | 部署前审计 MCP 服务器的 prompts / resources / instructions |\n\n"
                "### MCP 独有扫描维度\n\n"
                "1. **提示词模板扫描**: MCP prompts/list 返回的模板注入检测\n"
                "2. **资源安全扫描**: URI 安全（SSRF、file://）、MIME 类型验证、敏感数据暴露\n"
                "3. **服务器指令分析**: 初始化指令中的行为操纵、权限提升、安全绕过\n"
                "4. **跨服务器信任边界**: 多 MCP 服务器间的组合攻击链分析\n\n"
                "### 调用方式\n\n"
                "- `POST /api/v1/mcp-scanner/scan` — 独立批量扫描\n"
                "- Detection API `extra_body.mcp_servers` — 通过检测 API 调用\n\n"
                "### 检测引擎\n\n"
                "- **YARA 规则引擎**: MCP 特有模式（URI 攻击、服务器指令、提示模板注入），< 50ms\n"
                "- **LLM 语义引擎**: 深度语义分析，500-2000ms（条件触发）\n"
                "- **跨服务器分析引擎**: 信任边界 + 能力组合风险，< 100ms\n\n"
                "### 参考设计\n\n"
                "- Cisco AI Defense mcp-scanner (Apache 2.0)\n"
                "- OWASP Top 10 for LLM"
            ),
        )

    async def initialize(self, app_context: Dict[str, Any]) -> None:
        logger.info("MCP Scanner plugin initialized")

    async def shutdown(self) -> None:
        logger.info("MCP Scanner plugin shut down")

    def get_routers(self) -> list:
        from plugins_builtin.mcp_scanner.router import router
        return [router]

    def get_migrations_dir(self) -> Optional[Path]:
        migrations_dir = Path(__file__).parent / "migrations"
        return migrations_dir if migrations_dir.exists() else None

    # ===================== Hooks =====================
    #
    # NOTE: on_input_check is intentionally NOT implemented.
    # Runtime tool-definition scanning is Skill Scanner's job.
    # MCP Scanner only responds to explicit scan requests.

    async def on_detection_check(self, ctx: HookContext) -> Optional[HookResult]:
        """Scan MCP servers when explicitly provided via Detection API.

        Expects extra_body.mcp_servers — a list of MCP server descriptors:
        [{"name": "...", "tools": [...], "prompts": [...],
          "resources": [...], "instructions": "..."}]
        """
        if not ctx.application_id:
            return None

        mcp_servers = None
        if ctx.extra_body and isinstance(ctx.extra_body, dict):
            mcp_servers = ctx.extra_body.get('mcp_servers')

        if not mcp_servers or not isinstance(mcp_servers, list):
            return None

        from plugins_builtin.mcp_scanner.cache import mcp_scanner_cache
        policy = await mcp_scanner_cache.get_policy(str(ctx.application_id))
        if not policy or not policy.enabled:
            return None

        from plugins_builtin.mcp_scanner.service import mcp_scanner_service
        result = await mcp_scanner_service.scan_mcp_server_data(mcp_servers, policy)

        if result.risk_level == 'no_risk':
            return None

        action = self._severity_to_action(result.max_severity, policy)
        blocked_message = None
        if action == 'block':
            blocked_message = (
                f"MCP servers blocked by MCP Scanner. "
                f"Found {len(result.findings)} issue(s) across "
                f"{result.servers_flagged} server(s). "
                f"Max severity: {result.max_severity}."
            )

        return HookResult(
            risk_level=result.risk_level,
            categories=result.categories,
            action=action,
            blocked_message=blocked_message,
            metadata=self._build_metadata(result),
        )

    def _severity_to_action(self, max_severity: str, policy) -> str:
        severity_action_map = {
            'critical': getattr(policy, 'critical_action', 'block'),
            'high': getattr(policy, 'high_action', 'warn'),
            'medium': getattr(policy, 'medium_action', 'log'),
            'low': getattr(policy, 'low_action', 'log'),
        }
        return severity_action_map.get(max_severity, 'log')

    def _build_metadata(self, result) -> dict:
        return {
            "findings_count": len(result.findings),
            "servers_scanned": result.servers_scanned,
            "servers_flagged": result.servers_flagged,
            "tools_scanned": result.tools_scanned,
            "prompts_scanned": result.prompts_scanned,
            "resources_scanned": result.resources_scanned,
            "max_severity": result.max_severity,
            "scan_duration_ms": result.scan_duration_ms,
            "engine_summary": result.engine_summary,
            "findings_summary": [
                {
                    "server": f.server_name,
                    "item": f.item_name,
                    "item_type": f.item_type,
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                }
                for f in result.findings[:20]
            ],
        }
