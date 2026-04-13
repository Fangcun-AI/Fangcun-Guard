<div align="center">
  <h1>Fangcun Guard</h1>
  <p>Open-Source AI Guardrails Platform</p>
  <p><a href="README_zh.md">简体中文</a></p>
  <p>
    <a href="https://github.com/Fangcun-AI"><img src="./skillward-badge.svg" alt="Fangcun AI" height="20" /></a>
    <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
    <img src="https://img.shields.io/badge/version-1.0.0-green.svg" alt="Version">
  </p>
</div>

Fangcun Guard is an open-source AI security platform that provides protection for AI applications across content safety, prompt attacks, data leakage, agent behavior security, and more.

## Highlights

- **Guard Model Router**: 15 predefined safety dimensions with a classification router that automatically identifies the relevant dimension for each input and dispatches it to the corresponding detection model. Users can freely choose which model to use for each dimension.
- **Defense in Depth**: Content safety, prompt injection, data leakage, agent behavior, hallucination detection — all covered by one unified platform.
- **Quick to Deploy**: One-command Docker deployment — configure your detection model URL and go.
- **Platform Management**: Web UI for all configuration, multi-tenant isolation, real-time dashboard monitoring.

## Core Capabilities

### Guard Model Router

Fangcun Guard predefines 15 safety dimensions (content safety, prompt injection, jailbreak, toxicity, PII, code security, image safety, etc.). The classification router automatically identifies the relevant dimension for each input and dispatches it to the corresponding detection model for parallel execution. Users configure a detection model for each dimension — just provide the API URL. Supports self-hosted models, third-party APIs, and any OpenAI-compatible endpoint.

See [Guard Model Router docs](docs/features/GUARD_MODEL_ROUTER.md)

### Data Leakage Prevention (DLP)

Multi-path sensitive data detection (LLM semantic recognition + regex matching + keyword matching). Four disposal strategies upon detection: block directly, anonymize before sending and restore in response, automatically switch to a private model, or pass through with logging.

### Agent Safety

Security audit of agent tool calls — detects 19 attack patterns including shell injection, SQL injection, and path traversal, with tool whitelist and blacklist support. Also audits reasoning chains (CoT) for goal hijacking and data exfiltration intent.

### Hallucination Detection

Detects factual consistency between LLM output and reference context, verifies whether output content is grounded in source material, and checks for internal contradictions within the context. Suitable for output quality control in RAG scenarios.

## Quick Start

Requires Docker and an OpenAI-compatible detection model API.

```bash
pip install fangcunguard
fangcunguard init
fangcunguard up
```

For detailed deployment steps, see the [Quick Start & Deployment Guide](docs/getting-started/QUICK_START.md).

## Documentation

- [Quick Start & Deployment](docs/getting-started/QUICK_START.md) — Deployment, model configuration, local development
- [Guard Model Router](docs/features/GUARD_MODEL_ROUTER.md) — Multi-model routing configuration
- [Basic Guard](docs/features/BASIC_GUARD_OVERVIEW.md) — Core safety capabilities
- [Agent Safety](docs/features/AGENT_SAFETY_OVERVIEW.md) — Agent protection

## License

[Apache License 2.0](LICENSE)
