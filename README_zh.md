<div align="center">
  <h1>Fangcun Guard</h1>
  <p>开源 AI 安全护栏平台</p>
  <p><a href="README.md">English</a></p>
  <p>
    <a href="https://github.com/Fangcun-AI"><img src="./skillward-badge.svg" alt="Fangcun AI" height="20" /></a>
    <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
    <img src="https://img.shields.io/badge/version-1.0.0-green.svg" alt="Version">
  </p>
</div>

Fangcun Guard 是一个开源 AI 安全平台，为 AI 应用提供内容安全、提示词攻击、数据泄漏、Agent 行为安全等方面的防护。

## 产品亮点

- **Guard Model Router**：系统预定义 15 个安全维度，分类路由自动识别输入内容所属维度并分发给对应的检测模型，用户可为每个维度自由选择模型。
- **多层纵深防御**：内容安全、提示词注入、数据泄漏、Agent 行为、幻觉检测，同一套平台统一覆盖。
- **快速部署**：Docker 一键部署，配置检测模型地址即可使用。
- **平台化管理**：Web 界面配置一切，多租户隔离，仪表盘实时监控。

## 核心能力

### Guard Model Router

系统预定义了 15 个安全维度（内容安全、提示词注入、越狱、毒性、PII、代码安全、图片安全等），通过分类路由自动识别输入内容所属的维度，并分发给对应的检测模型并行执行。用户为每个维度配置检测模型，只需提供 API 地址即可接入。支持自部署模型、第三方 API、任何 OpenAI 兼容接口。

详见 [Guard Model Router 文档](docs/features/GUARD_MODEL_ROUTER_zh.md)

### 数据防泄漏（DLP）

多路识别敏感数据（LLM 语义识别 + 正则匹配 + 关键词匹配），检测到敏感数据后支持四种处置策略：直接拦截、脱敏后发送并在响应中还原、自动切换到私有模型、放行并记录日志。

### Agent 安全

对 Agent 的工具调用进行安全审计，检测 Shell 注入、SQL 注入、路径穿越等 19 种攻击模式，支持工具白名单和黑名单。同时对推理链（CoT）进行安全审计，检测目标劫持和数据外泄意图。

### 幻觉检测

检测 LLM 输出与参考上下文之间的事实一致性，验证输出内容是否有来源依据，以及上下文是否自相矛盾。适用于 RAG 场景的输出质量把控。

## 快速开始

需要 Docker 和一个 OpenAI 兼容的检测模型 API。

```bash
pip install fangcunguard
fangcunguard init
fangcunguard up
```

详细部署步骤见 [快速开始与部署文档](docs/getting-started/QUICK_START_zh.md)。

## 文档

- [快速开始与部署](docs/getting-started/QUICK_START_zh.md) — 部署、模型配置、本地开发
- [Guard Model Router](docs/features/GUARD_MODEL_ROUTER_zh.md) — 多模型路由配置
- [Basic Guard](docs/features/BASIC_GUARD_OVERVIEW_zh.md) — 安全基座能力
- [Agent Safety](docs/features/AGENT_SAFETY_OVERVIEW_zh.md) — Agent 防护

## 开源协议

[Apache License 2.0](LICENSE)
