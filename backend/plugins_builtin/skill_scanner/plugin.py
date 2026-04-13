"""
Skill Scanner Plugin — SKILL.md definition security auditor.

Scans AI Agent SKILL.md files (YAML frontmatter + Markdown instructions)
for security vulnerabilities. For JSON tool definition scanning at runtime,
see the Agent Safety plugin.

References:
- Cisco AI Defense skill-scanner (Apache 2.0): Multi-engine analysis architecture
- OWASP Top 10 for LLM: Tool definition security best practices
"""

from pathlib import Path
from typing import Optional, Dict, Any
from plugins.base import DetectionPlugin, PluginMetadata, PluginType, DeploymentMode
from utils.logger import setup_logger

logger = setup_logger()


class PluginClass(DetectionPlugin):
    """Skill Scanner plugin — audits SKILL.md definitions for security vulnerabilities"""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="skill_scanner",
            version="2.0.0",
            description="SKILL.md 安全审计：检测技能定义中的提示注入、危险能力、混淆和结构缺陷",
            author="FangcunGuard",
            plugin_type=PluginType.DETECTION,
            deployment_mode=DeploymentMode.BOTH,
            priority=90,
            display_name="SKILL.md 安全扫描",
            display_name_en="SKILL.md Scanner",
            icon="scan-search",
            category="security",
            tags=["skill", "skill-md", "audit", "prompt-injection", "supply-chain"],
            documentation=(
                "## SKILL.md 安全扫描\n\n"
                "专注于 AI Agent 的 SKILL.md 技能定义文件安全审计。\n"
                "SKILL.md 是 Claude Code、Cursor、GitHub Copilot、LobeChat 等使用的标准技能格式。\n\n"
                "### 与 Agent 安全防护的区别\n\n"
                "- **Agent 安全防护**: 运行时 JSON 工具定义扫描 + 工具调用监控 + 参数注入检测\n"
                "- **SKILL.md 安全扫描**: 技能定义文件审计（提示注入、危险能力、混淆、结构缺陷）\n\n"
                "### 使用方式\n\n"
                "通过目录扫描 API 扫描客户 Agent 项目中的 SKILL.md 文件。\n"
                "当客户 Agent 的 SKILL.md 更新或新增时，调用扫描接口进行安全审计。\n\n"
                "### 检测引擎（两阶段流水线）\n\n"
                "**Phase 1（非 LLM，并行执行，< 50ms）**:\n"
                "- 静态模式引擎：31 条正则模式检测提示注入、命令注入、数据泄露、混淆、占位符注入、同形字符\n"
                "- 结构验证引擎：描述质量、名称检查\n"
                "- 能力风险引擎：危险能力分类、跨工具风险链检测\n\n"
                "**Phase 2（LLM 语义，可选）**:\n"
                "- 深度语义分析 + Phase 1 假阳性过滤\n\n"
                "### 参考设计\n\n"
                "- Cisco AI Defense skill-scanner (Apache 2.0): 多引擎分析架构\n"
                "- OWASP Top 10 for LLM: 工具定义安全最佳实践"
            ),
        )

    async def initialize(self, app_context: Dict[str, Any]) -> None:
        logger.info("Skill scanner plugin initialized (SKILL.md only)")

    async def shutdown(self) -> None:
        logger.info("Skill scanner plugin shut down")

    def get_routers(self) -> list:
        from plugins_builtin.skill_scanner.router import router
        return [router]

    def get_migrations_dir(self) -> Optional[Path]:
        migrations_dir = Path(__file__).parent / "migrations"
        return migrations_dir if migrations_dir.exists() else None
