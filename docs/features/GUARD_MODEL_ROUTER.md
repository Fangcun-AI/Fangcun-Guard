# Fangcun Guard Router

Fangcun Guard Router is Fangcun Guard's multi-model safety detection dispatch system. It uses a classification router to automatically identify the relevant safety dimension for each input and dispatches it to the corresponding detection model.

Users configure detection models for each dimension by simply providing an API Key. It supports self-deployed models, third-party APIs, and any OpenAI-compatible endpoint. You can also use the Fangcun Guard backend service as a detection model.

## Workflow

```
User Input
  │
  ▼
Classification Router ── Automatically categorize content into safety dimensions (e.g., prompt injection, jailbreak, toxicity)
  │
  ▼
Query Dimension Config ── Which detection model is assigned to this dimension?
  │
  ▼
Call the Corresponding Model for Detection → Return Result
```

## Safety Dimensions

The system includes 15 predefined safety dimensions. The classification router automatically categorizes each input:

| # | Dimension | Description |
|---|-----------|-------------|
| 1 | Chinese Safety | Politically sensitive, violent, pornographic content, etc. |
| 2 | English Safety | MLCommons standard safety taxonomy |
| 3 | Prompt Injection | Direct/indirect injection attacks |
| 4 | Jailbreak Detection | Adversarial jailbreak attacks |
| 5 | Toxicity Detection | Insults, threats, hate speech, profanity |
| 6 | PII Detection | Personal information, credentials, financial data |
| 7 | Hallucination Detection | Factuality verification in RAG scenarios |
| 8 | Code Safety | Code vulnerabilities, secret key leaks |
| 9 | Image Safety | Violent/NSFW/dangerous behavior images |
| 10 | Commercial Compliance | Illegal ads, false claims, financial fraud scripts |
| 11 | Self-Harm Detection | Suicide/self-harm content |
| 12 | Child Protection | CSAM/grooming detection |
| 13 | Multilingual Safety | Safety detection for 40+ languages |
| 14 | Copyright Detection | Reproduction of copyrighted text |
| 15 | Quick Screening | Fast pass-through for low-risk content |

Users can assign a detection model to any dimension by configuring the corresponding API endpoint and key.

## Enabling

Set in `.env`:

```bash
GUARD_MODELS_CONFIG_PATH=guard_models.yaml
```

Restart the service for changes to take effect.

## Configuration

Edit `backend/guard_models.yaml`, which contains two sections:

### 1. Model Pool

Register available detection models. Any OpenAI-compatible endpoint is supported:

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

### 2. Dimension-Model Assignment

Assign detection models to the dimensions you need:

```yaml
dimensions:
  english_safety:
    model: "my-guard-model"          # English Safety

  jailbreak:
    model: "my-guard-model"          # Jailbreak Detection

  multilingual_safety:
    model: "my-guard-model"          # Multilingual Safety
```

Dimensions without configuration are automatically skipped by the router.
