# Guard Model Router

Guard Model Router 是 Fangcun Guard 的多模型安全检测调度系统。它通过分类路由将输入内容识别为不同的安全维度，再分发到对应的检测模型执行检测。

用户为每个维度配置检测模型，只需提供 API Key 即可接入。支持自部署模型、第三方 API、任何 OpenAI 兼容接口。也可以使用 Fangcun Guard 后端服务作为检测模型。

## 工作流程

```
用户输入
  │
  ▼
分类路由 ── 将内容自动归类到安全维度（如：提示词注入、越狱、毒性等）
  │
  ▼
查询维度配置 ── 该维度指定了哪个检测模型？
  │
  ▼
调用对应模型执行检测 → 返回结果
```

## 安全维度

系统预定义 15 个安全维度，分类路由自动将输入归类：

| # | 维度 | 说明 |
|---|------|------|
| 1 | 中文安全 | 政治敏感、暴力、色情等 |
| 2 | 英文安全 | MLCommons 标准安全分类 |
| 3 | 提示词注入 | 直接/间接注入攻击 |
| 4 | 越狱检测 | 对抗性越狱攻击 |
| 5 | 毒性检测 | 侮辱、威胁、仇恨、亵渎 |
| 6 | PII 检测 | 个人信息、凭证、金融数据 |
| 7 | 幻觉检测 | RAG 场景事实性验证 |
| 8 | 代码安全 | 代码漏洞、密钥泄露 |
| 9 | 图片安全 | 暴力/NSFW/危险行为图片 |
| 10 | 商业合规 | 违规广告、虚假宣传、金融诈骗话术 |
| 11 | 自残检测 | 自杀/自残内容 |
| 12 | 儿童保护 | CSAM/诱导检测 |
| 13 | 多语言安全 | 40+ 小语种安全检测 |
| 14 | 版权检测 | 受版权保护文本的复述 |
| 15 | 快速筛查 | 低风险内容快速放行 |

用户可以为任意维度指定检测模型，只需配置对应的 API 地址和 Key。

## 启用

在 `.env` 中设置：

```bash
GUARD_MODELS_CONFIG_PATH=guard_models.yaml
```

重启服务后生效。

## 配置

编辑 `backend/guard_models.yaml`，包含两部分：

### 1. 模型池

注册可用的检测模型。支持任何 OpenAI 兼容接口：

```yaml
models:
  my-guard-model:
    name: "Your Guard Model"
    api_url: "${YOUR_MODEL_API_URL}"
    api_key: "${YOUR_MODEL_API_KEY}"
    model_name: "your-model-name"
    api_type: "chat_completion"       # chat_completion | classification | moderation | ner | custom
    max_context_length: 8192
```

### 2. 维度模型分配

为需要的维度指定检测模型：

```yaml
dimensions:
  english_safety:
    model: "my-guard-model"          # 英文安全

  jailbreak:
    model: "my-guard-model"          # 越狱检测

  multilingual_safety:
    model: "my-guard-model"          # 多语言安全
```

不需要的维度不配置即可，路由器会自动跳过。
