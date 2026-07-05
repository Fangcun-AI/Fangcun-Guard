# Data Leakage Prevention Guide <!-- fcg-rewrite -->

> Comprehensive guide for configuring and using Fangcun Guard's data leakage prevention system. <!-- fcg-rewrite -->

## Table of Contents <!-- fcg-rewrite -->

- [Overview](#overview) <!-- fcg-rewrite -->
- [Architecture](#architecture) <!-- fcg-rewrite -->
- [Quick Start](#quick-start) <!-- fcg-rewrite -->
- [Private Model Configuration](#private-model-configuration) <!-- fcg-rewrite -->
- [Policy Configuration](#policy-configuration) <!-- fcg-rewrite -->
- [Format Detection](#format-detection) <!-- fcg-rewrite -->
- [Smart Segmentation](#smart-segmentation) <!-- fcg-rewrite -->
- [Disposal Strategies](#disposal-strategies) <!-- fcg-rewrite -->
- [Best Practices](#best-practices) <!-- fcg-rewrite -->
- [Troubleshooting](#troubleshooting) <!-- fcg-rewrite -->
- [API Integration](#api-integration) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Overview <!-- fcg-rewrite -->

Fangcun Guard's Data Leakage Prevention (DLP) system provides **multi-layer protection** against sensitive data exposure when using AI models. The system automatically: <!-- fcg-rewrite -->

1. **Detects sensitive data** in user prompts (ID cards, phone numbers, addresses, etc.) <!-- fcg-rewrite -->
2. **Assesses risk levels** (High/Medium/Low) based on entity types and context <!-- fcg-rewrite -->
3. **Applies disposal strategies** based on configured policies <!-- fcg-rewrite -->
4. **Protects data** through blocking, model switching, or anonymization <!-- fcg-rewrite -->

### Key Features <!-- fcg-rewrite -->

- **Format-Aware Detection**: Automatically identifies JSON, YAML, CSV, Markdown, or plain text <!-- fcg-rewrite -->
- **Smart Segmentation**: Splits content intelligently based on format for parallel processing <!-- fcg-rewrite -->
- **Three Disposal Methods**: Block, switch to private model, or anonymize <!-- fcg-rewrite -->
- **Application-Level Policies**: Customize strategies per application <!-- fcg-rewrite -->
- **Private Model Priority System**: Flexible fallback model selection <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Architecture <!-- fcg-rewrite -->

### Detection Flow <!-- fcg-rewrite -->

``` <!-- fcg-rewrite -->
┌─────────────────────────────────────────────────────────────────┐ <!-- fcg-rewrite -->
│ 1. User Request                                                  │ <!-- fcg-rewrite -->
│    - Text prompt with potential sensitive data                   │ <!-- fcg-rewrite -->
└────────────────────┬────────────────────────────────────────────┘ <!-- fcg-rewrite -->
                     │ <!-- fcg-rewrite -->
                     ▼ <!-- fcg-rewrite -->
┌─────────────────────────────────────────────────────────────────┐ <!-- fcg-rewrite -->
│ 2. Format Detection (if enabled)                                 │ <!-- fcg-rewrite -->
│    - JSON: Detect by parsing                                     │ <!-- fcg-rewrite -->
│    - YAML: Detect by YAML syntax                                 │ <!-- fcg-rewrite -->
│    - CSV: Detect by comma/tab patterns                           │ <!-- fcg-rewrite -->
│    - Markdown: Detect by headers/lists                           │ <!-- fcg-rewrite -->
│    - Plain Text: Fallback                                        │ <!-- fcg-rewrite -->
└────────────────────┬────────────────────────────────────────────┘ <!-- fcg-rewrite -->
                     │ <!-- fcg-rewrite -->
                     ▼ <!-- fcg-rewrite -->
┌─────────────────────────────────────────────────────────────────┐ <!-- fcg-rewrite -->
│ 3. Smart Segmentation (if enabled)                               │ <!-- fcg-rewrite -->
│    - JSON: Split by top-level objects                            │ <!-- fcg-rewrite -->
│    - YAML: Split by top-level keys                               │ <!-- fcg-rewrite -->
│    - CSV: Split by rows                                          │ <!-- fcg-rewrite -->
│    - Markdown: Split by sections (## headers)                    │ <!-- fcg-rewrite -->
│    - Plain Text: Process as single segment                       │ <!-- fcg-rewrite -->
└────────────────────┬────────────────────────────────────────────┘ <!-- fcg-rewrite -->
                     │ <!-- fcg-rewrite -->
                     ▼ <!-- fcg-rewrite -->
┌─────────────────────────────────────────────────────────────────┐ <!-- fcg-rewrite -->
│ 4. Parallel Entity Detection                                     │ <!-- fcg-rewrite -->
│    ┌──────────────────┐  ┌──────────────────┐                   │ <!-- fcg-rewrite -->
│    │ Regex Entities   │  │ GenAI Entities   │                   │ <!-- fcg-rewrite -->
│    │ - Full text only │  │ - Per segment    │                   │ <!-- fcg-rewrite -->
│    │ - ID cards       │  │ - Context-aware  │                   │ <!-- fcg-rewrite -->
│    │ - Phone numbers  │  │ - Parallel async │                   │ <!-- fcg-rewrite -->
│    └──────────────────┘  └──────────────────┘                   │ <!-- fcg-rewrite -->
└────────────────────┬────────────────────────────────────────────┘ <!-- fcg-rewrite -->
                     │ <!-- fcg-rewrite -->
                     ▼ <!-- fcg-rewrite -->
┌─────────────────────────────────────────────────────────────────┐ <!-- fcg-rewrite -->
│ 5. Risk Aggregation                                              │ <!-- fcg-rewrite -->
│    - Aggregate results from all segments                         │ <!-- fcg-rewrite -->
│    - Highest risk level wins                                     │ <!-- fcg-rewrite -->
│    - Merge all detected entities                                 │ <!-- fcg-rewrite -->
└────────────────────┬────────────────────────────────────────────┘ <!-- fcg-rewrite -->
                     │ <!-- fcg-rewrite -->
                     ▼ <!-- fcg-rewrite -->
┌─────────────────────────────────────────────────────────────────┐ <!-- fcg-rewrite -->
│ 6. Policy-Based Disposal                                         │ <!-- fcg-rewrite -->
│    ┌─────────────┬──────────────┬───────────────┐               │ <!-- fcg-rewrite -->
│    │ High Risk   │ Medium Risk  │ Low Risk      │               │ <!-- fcg-rewrite -->
│    │ → Block     │ → Private Model │ → Anonymize   │ (defaults)    │ <!-- fcg-rewrite -->
│    └─────────────┴──────────────┴───────────────┘               │ <!-- fcg-rewrite -->
└────────────────────┬────────────────────────────────────────────┘ <!-- fcg-rewrite -->
                     │ <!-- fcg-rewrite -->
                     ▼ <!-- fcg-rewrite -->
┌─────────────────────────────────────────────────────────────────┐ <!-- fcg-rewrite -->
│ 7. Action Execution                                              │ <!-- fcg-rewrite -->
│    - Block: Return error, log incident                           │ <!-- fcg-rewrite -->
│    - Switch Model: Forward to private model, log switch             │ <!-- fcg-rewrite -->
│    - Anonymize: Replace entities, forward to original model      │ <!-- fcg-rewrite -->
│    - Pass: Allow request, log detection                          │ <!-- fcg-rewrite -->
└─────────────────────────────────────────────────────────────────┘ <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Component Architecture <!-- fcg-rewrite -->

``` <!-- fcg-rewrite -->
┌─────────────────────────────────────────────────────────────────┐ <!-- fcg-rewrite -->
│ Proxy Service (Port 5002)                                        │ <!-- fcg-rewrite -->
│ - Receives /v1/chat/completions requests                         │ <!-- fcg-rewrite -->
│ - Calls DataLeakageDisposalService                               │ <!-- fcg-rewrite -->
└────────────────────┬────────────────────────────────────────────┘ <!-- fcg-rewrite -->
                     │ <!-- fcg-rewrite -->
                     ▼ <!-- fcg-rewrite -->
┌─────────────────────────────────────────────────────────────────┐ <!-- fcg-rewrite -->
│ DataLeakageDisposalService                                       │ <!-- fcg-rewrite -->
│ - Fetches policy for application                                 │ <!-- fcg-rewrite -->
│ - Coordinates disposal based on risk level                       │ <!-- fcg-rewrite -->
└────────────────────┬────────────────────────────────────────────┘ <!-- fcg-rewrite -->
                     │ <!-- fcg-rewrite -->
                     ├─────────────────────┬──────────────────────┐ <!-- fcg-rewrite -->
                     ▼                     ▼                      ▼ <!-- fcg-rewrite -->
┌──────────────────────────┐ ┌──────────────────┐ ┌──────────────┐ <!-- fcg-rewrite -->
│ FormatDetectionService   │ │ SegmentationSvc  │ │ DataSecSvc   │ <!-- fcg-rewrite -->
│ - Detect content format  │ │ - Smart split    │ │ - Entity det │ <!-- fcg-rewrite -->
└──────────────────────────┘ └──────────────────┘ └──────────────┘ <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Quick Start <!-- fcg-rewrite -->

### Step 1: Configure Private Models <!-- fcg-rewrite -->

1. Navigate to **Config > Proxy Models** <!-- fcg-rewrite -->
2. Create or edit a model configuration <!-- fcg-rewrite -->
3. Enable **"Data Safety Attributes"**: <!-- fcg-rewrite -->
   - **Is Data Safe**: Mark as safe (e.g., on-premise, private deployment) <!-- fcg-rewrite -->
   - **Is Default Private Model**: Set as tenant-wide default <!-- fcg-rewrite -->
   - **Private Model Priority**: Set priority (0-100, higher = preferred) <!-- fcg-rewrite -->

**Example**: Enterprise private deployment <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
Model: gpt-4o (Private) <!-- fcg-rewrite -->
Provider: Azure OpenAI <!-- fcg-rewrite -->
Is Data Safe: ✓ Enabled <!-- fcg-rewrite -->
Is Default Private Model: ✓ Enabled <!-- fcg-rewrite -->
Private Model Priority: 90 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Step 2: Configure Data Leakage Policy <!-- fcg-rewrite -->

1. Navigate to **Config > Data Leakage Policy** <!-- fcg-rewrite -->
2. Configure **Risk Level Actions**: <!-- fcg-rewrite -->
   - **High Risk**: Choose disposal action (default: Block) <!-- fcg-rewrite -->
   - **Medium Risk**: Choose disposal action (default: Switch Private Model) <!-- fcg-rewrite -->
   - **Low Risk**: Choose disposal action (default: Anonymize) <!-- fcg-rewrite -->
3. Select **Private Model** (or leave as "Current Private Model - Default") <!-- fcg-rewrite -->
4. Enable **Feature Toggles**: <!-- fcg-rewrite -->
   - **Format Detection**: Recommended ✓ <!-- fcg-rewrite -->
   - **Smart Segmentation**: Recommended ✓ <!-- fcg-rewrite -->
5. Click **Save Policy** <!-- fcg-rewrite -->

### Step 3: Test Protection <!-- fcg-rewrite -->

Send a test request with sensitive data: <!-- fcg-rewrite -->

```bash <!-- fcg-rewrite -->
curl -X POST http://localhost:5002/v1/chat/completions \ <!-- fcg-rewrite -->
  -H "Authorization: Bearer sk-xxai-your-proxy-key" \ <!-- fcg-rewrite -->
  -H "Content-Type: application/json" \ <!-- fcg-rewrite -->
  -d '{ <!-- fcg-rewrite -->
    "model": "gpt-4o", <!-- fcg-rewrite -->
    "messages": [ <!-- fcg-rewrite -->
      { <!-- fcg-rewrite -->
        "role": "user", <!-- fcg-rewrite -->
        "content": "My ID card number is 110101199001011234, can you help me?" <!-- fcg-rewrite -->
      } <!-- fcg-rewrite -->
    ] <!-- fcg-rewrite -->
  }' <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Expected Behavior** (with default high-risk = block): <!-- fcg-rewrite -->
- Request is blocked <!-- fcg-rewrite -->
- Error response returned <!-- fcg-rewrite -->
- Incident logged in detection results <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Private Model Configuration <!-- fcg-rewrite -->

### What is a Private Model? <!-- fcg-rewrite -->

A **private model** is a model marked as **data-safe** for handling sensitive information. Common examples: <!-- fcg-rewrite -->

- **On-Premise Models**: Self-hosted models (Ollama, vLLM, etc.) <!-- fcg-rewrite -->
- **Private Cloud**: Enterprise Azure OpenAI, AWS Bedrock with private endpoints <!-- fcg-rewrite -->
- **Air-Gapped Models**: Fully isolated deployments <!-- fcg-rewrite -->
- **Compliance-Certified**: Models meeting specific regulatory requirements (GDPR, HIPAA, etc.) <!-- fcg-rewrite -->

### Safety Attributes <!-- fcg-rewrite -->

#### `is_data_safe` (Boolean) <!-- fcg-rewrite -->

Marks the model as safe for sensitive data. <!-- fcg-rewrite -->

**When to enable**: <!-- fcg-rewrite -->
- ✅ Enterprise private deployment <!-- fcg-rewrite -->
- ✅ On-premise/self-hosted <!-- fcg-rewrite -->
- ✅ Air-gapped environment <!-- fcg-rewrite -->
- ✅ Compliance-certified endpoint <!-- fcg-rewrite -->
- ❌ Public cloud APIs (OpenAI, Anthropic, etc.) <!-- fcg-rewrite -->

#### `is_default_private_model` (Boolean) <!-- fcg-rewrite -->

Sets this model as the **tenant-wide default** for private model switching. <!-- fcg-rewrite -->

**Rules**: <!-- fcg-rewrite -->
- Only **one model per tenant** should have this enabled <!-- fcg-rewrite -->
- Used when policy doesn't specify a `private_model_id` <!-- fcg-rewrite -->
- Overrides priority-based selection <!-- fcg-rewrite -->

#### `private_model_priority` (Integer 0-100) <!-- fcg-rewrite -->

Sets selection priority when multiple private models exist. <!-- fcg-rewrite -->

**Priority Rules**: <!-- fcg-rewrite -->
1. Higher number = higher priority <!-- fcg-rewrite -->
2. Used when no default private model is set <!-- fcg-rewrite -->
3. Ties are broken by creation time (newest first) <!-- fcg-rewrite -->

**Recommended Ranges**: <!-- fcg-rewrite -->
- **90-100**: Production-grade, fully compliant <!-- fcg-rewrite -->
- **70-89**: Standard private models <!-- fcg-rewrite -->
- **50-69**: Testing/staging private models <!-- fcg-rewrite -->
- **0-49**: Low-priority fallbacks <!-- fcg-rewrite -->

### Private Model Selection Priority <!-- fcg-rewrite -->

When the disposal action is **"switch_private_model"**, the system selects a model using this priority: <!-- fcg-rewrite -->

``` <!-- fcg-rewrite -->
1. Application Policy Private Model (private_model_id in policy) <!-- fcg-rewrite -->
   ↓ (if null) <!-- fcg-rewrite -->
2. Tenant Default Private Model (is_default_private_model = true) <!-- fcg-rewrite -->
   ↓ (if none) <!-- fcg-rewrite -->
3. Highest Priority Private Model (private_model_priority DESC) <!-- fcg-rewrite -->
   ↓ (if none) <!-- fcg-rewrite -->
4. ERROR: No private model available <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Configuration Examples <!-- fcg-rewrite -->

#### Example 1: Single Private Model <!-- fcg-rewrite -->

``` <!-- fcg-rewrite -->
Model: llama-3-70b-local <!-- fcg-rewrite -->
Provider: Ollama <!-- fcg-rewrite -->
API Base URL: http://local-ollama:11434 <!-- fcg-rewrite -->
Is Data Safe: ✓ Enabled <!-- fcg-rewrite -->
Is Default Private Model: ✓ Enabled <!-- fcg-rewrite -->
Private Model Priority: 80 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Result**: This model is always selected for "switch_private_model" actions. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Example 2: Multi-Tier Private Models <!-- fcg-rewrite -->

**Production Model**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
Model: gpt-4o-azure-private <!-- fcg-rewrite -->
Provider: Azure OpenAI <!-- fcg-rewrite -->
Is Data Safe: ✓ Enabled <!-- fcg-rewrite -->
Is Default Private Model: ✓ Enabled (tenant default) <!-- fcg-rewrite -->
Private Model Priority: 95 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Staging Model**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
Model: gpt-4o-mini-azure-private <!-- fcg-rewrite -->
Provider: Azure OpenAI <!-- fcg-rewrite -->
Is Data Safe: ✓ Enabled <!-- fcg-rewrite -->
Is Default Private Model: ✗ Disabled <!-- fcg-rewrite -->
Private Model Priority: 70 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Fallback Model**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
Model: llama-3-8b-local <!-- fcg-rewrite -->
Provider: Ollama <!-- fcg-rewrite -->
Is Data Safe: ✓ Enabled <!-- fcg-rewrite -->
Is Default Private Model: ✗ Disabled <!-- fcg-rewrite -->
Private Model Priority: 50 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Result**: gpt-4o-azure-private is selected by default (default flag overrides priority). <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Example 3: Application-Specific Private Model <!-- fcg-rewrite -->

**Tenant Default**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
Model: gpt-4o-mini-safe <!-- fcg-rewrite -->
Is Default Private Model: ✓ Enabled <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**High-Security Application Policy**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
Application: HIPAA-Compliant-App <!-- fcg-rewrite -->
Private Model ID: llama-3-70b-airgap (explicitly configured) <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Result**: HIPAA app uses llama-3-70b-airgap; other apps use gpt-4o-mini-safe. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Policy Configuration <!-- fcg-rewrite -->

### Risk Level Actions <!-- fcg-rewrite -->

Configure disposal actions for each risk level: <!-- fcg-rewrite -->

#### High Risk (Default: Block) <!-- fcg-rewrite -->

**Recommended Action**: **Block** <!-- fcg-rewrite -->

Entities typically classified as high risk: <!-- fcg-rewrite -->
- ID card numbers (exact patterns) <!-- fcg-rewrite -->
- Credit card numbers <!-- fcg-rewrite -->
- Social security numbers <!-- fcg-rewrite -->
- Bank account numbers <!-- fcg-rewrite -->
- Passport numbers <!-- fcg-rewrite -->

**Alternative Actions**: <!-- fcg-rewrite -->
- **Switch Private Model**: If you have a compliant model that can handle these <!-- fcg-rewrite -->
- **Anonymize**: For testing environments only (not recommended for production) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Medium Risk (Default: Switch Private Model) <!-- fcg-rewrite -->

**Recommended Action**: **Switch Private Model** <!-- fcg-rewrite -->

Entities typically classified as medium risk: <!-- fcg-rewrite -->
- Full names with context <!-- fcg-rewrite -->
- Detailed addresses <!-- fcg-rewrite -->
- Company internal information <!-- fcg-rewrite -->
- Medical record IDs <!-- fcg-rewrite -->
- License plate numbers <!-- fcg-rewrite -->

**Alternative Actions**: <!-- fcg-rewrite -->
- **Block**: For zero-tolerance policies <!-- fcg-rewrite -->
- **Anonymize**: For development/testing <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Low Risk (Default: Anonymize) <!-- fcg-rewrite -->

**Recommended Action**: **Anonymize** <!-- fcg-rewrite -->

Entities typically classified as low risk: <!-- fcg-rewrite -->
- Phone numbers (generic patterns) <!-- fcg-rewrite -->
- Email addresses <!-- fcg-rewrite -->
- Partial addresses (city names only) <!-- fcg-rewrite -->
- Organization names <!-- fcg-rewrite -->
- Generic personal information <!-- fcg-rewrite -->

**Alternative Actions**: <!-- fcg-rewrite -->
- **Pass**: For audit-only mode <!-- fcg-rewrite -->
- **Switch Private Model**: For maximum protection <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Pass (Allow) <!-- fcg-rewrite -->

**Use Case**: Audit-only mode <!-- fcg-rewrite -->

When set to **Pass**: <!-- fcg-rewrite -->
- Request is allowed to proceed unchanged <!-- fcg-rewrite -->
- Detection result is logged for audit <!-- fcg-rewrite -->
- No protective action taken <!-- fcg-rewrite -->
- Useful for monitoring before enforcement <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Private Model Selection in Policy <!-- fcg-rewrite -->

#### Option 1: Use Current Private Model (Default) <!-- fcg-rewrite -->

```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "private_model_id": null <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Behavior**: Use tenant's default private model or highest priority private model. <!-- fcg-rewrite -->

**Use When**: <!-- fcg-rewrite -->
- Standard protection is sufficient <!-- fcg-rewrite -->
- Tenant has one primary private model <!-- fcg-rewrite -->
- Centralized management is preferred <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Option 2: Specify Application-Specific Private Model <!-- fcg-rewrite -->

```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "private_model_id": "uuid-of-private-model" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Behavior**: Always use this specific model for this application. <!-- fcg-rewrite -->

**Use When**: <!-- fcg-rewrite -->
- Application has specific compliance requirements <!-- fcg-rewrite -->
- Different apps need different private models <!-- fcg-rewrite -->
- Multi-tier protection strategy <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Feature Toggles <!-- fcg-rewrite -->

#### Enable Format Detection <!-- fcg-rewrite -->

**Default**: Enabled (Recommended) <!-- fcg-rewrite -->

**When Enabled**: <!-- fcg-rewrite -->
- Automatically detects JSON, YAML, CSV, Markdown, Plain Text <!-- fcg-rewrite -->
- Enables format-aware smart segmentation <!-- fcg-rewrite -->
- Improves detection accuracy for structured data <!-- fcg-rewrite -->

**When to Disable**: <!-- fcg-rewrite -->
- All content is plain text <!-- fcg-rewrite -->
- Performance is critical (saves ~5-10ms per request) <!-- fcg-rewrite -->
- Testing legacy behavior <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Enable Smart Segmentation <!-- fcg-rewrite -->

**Default**: Enabled (Recommended) <!-- fcg-rewrite -->

**Requires**: Format Detection enabled <!-- fcg-rewrite -->

**When Enabled**: <!-- fcg-rewrite -->
- Splits content based on format structure <!-- fcg-rewrite -->
- Processes segments in parallel (faster) <!-- fcg-rewrite -->
- Improves context accuracy for GenAI entities <!-- fcg-rewrite -->

**When to Disable**: <!-- fcg-rewrite -->
- Content is always short (< 500 chars) <!-- fcg-rewrite -->
- Only using regex entities (segmentation not needed) <!-- fcg-rewrite -->
- Testing legacy behavior <!-- fcg-rewrite -->

**Performance Impact**: <!-- fcg-rewrite -->
- **Small content (< 1KB)**: Negligible <!-- fcg-rewrite -->
- **Medium content (1-10KB)**: 20-40% faster (parallel processing) <!-- fcg-rewrite -->
- **Large content (> 10KB)**: 40-60% faster <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Format Detection <!-- fcg-rewrite -->

### Supported Formats <!-- fcg-rewrite -->

| Format      | Detection Method                  | Confidence Threshold | <!-- fcg-rewrite -->
|-------------|-----------------------------------|----------------------| <!-- fcg-rewrite -->
| JSON        | `json.loads()` parsing            | 100% (parse success) | <!-- fcg-rewrite -->
| YAML        | YAML syntax patterns              | 70%+                 | <!-- fcg-rewrite -->
| CSV         | Comma/tab delimiters, row count   | 60%+                 | <!-- fcg-rewrite -->
| Markdown    | Headers, lists, code blocks       | 60%+                 | <!-- fcg-rewrite -->
| Plain Text  | Fallback (no structure detected)  | N/A                  | <!-- fcg-rewrite -->

### Format Detection Examples <!-- fcg-rewrite -->

#### JSON Detection <!-- fcg-rewrite -->

**Input**: <!-- fcg-rewrite -->
```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "user": { <!-- fcg-rewrite -->
    "name": "张三", <!-- fcg-rewrite -->
    "id_card": "110101199001011234", <!-- fcg-rewrite -->
    "phone": "13800138000" <!-- fcg-rewrite -->
  } <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Detection Result**: `json` (confidence: 100%) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### YAML Detection <!-- fcg-rewrite -->

**Input**: <!-- fcg-rewrite -->
```yaml <!-- fcg-rewrite -->
user: <!-- fcg-rewrite -->
  name: 张三 <!-- fcg-rewrite -->
  id_card: 110101199001011234 <!-- fcg-rewrite -->
  phone: 13800138000 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Detection Result**: `yaml` (confidence: 85%) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### CSV Detection <!-- fcg-rewrite -->

**Input**: <!-- fcg-rewrite -->
```csv <!-- fcg-rewrite -->
name,id_card,phone <!-- fcg-rewrite -->
张三,110101199001011234,13800138000 <!-- fcg-rewrite -->
李四,110101199001015678,13900139000 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Detection Result**: `csv` (confidence: 90%) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Markdown Detection <!-- fcg-rewrite -->

**Input**: <!-- fcg-rewrite -->
```markdown <!-- fcg-rewrite -->
## User Information <!-- fcg-rewrite -->

- Name: 张三 <!-- fcg-rewrite -->
- ID Card: 110101199001011234 <!-- fcg-rewrite -->
- Phone: 13800138000 <!-- fcg-rewrite -->

## Contact Details <!-- fcg-rewrite -->

Email: zhangsan@example.com <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Detection Result**: `markdown` (confidence: 80%) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Plain Text (Fallback) <!-- fcg-rewrite -->

**Input**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
My name is 张三, ID card: 110101199001011234, phone: 13800138000 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Detection Result**: `plain_text` (confidence: 100%, fallback) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Smart Segmentation <!-- fcg-rewrite -->

### Segmentation Strategies <!-- fcg-rewrite -->

#### JSON Segmentation <!-- fcg-rewrite -->

**Strategy**: Split by top-level objects/arrays <!-- fcg-rewrite -->

**Example Input**: <!-- fcg-rewrite -->
```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "user1": { <!-- fcg-rewrite -->
    "name": "张三", <!-- fcg-rewrite -->
    "id_card": "110101199001011234" <!-- fcg-rewrite -->
  }, <!-- fcg-rewrite -->
  "user2": { <!-- fcg-rewrite -->
    "name": "李四", <!-- fcg-rewrite -->
    "id_card": "110101199001015678" <!-- fcg-rewrite -->
  } <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Segments** (2): <!-- fcg-rewrite -->
1. `{"user1": {"name": "张三", "id_card": "110101199001011234"}}` <!-- fcg-rewrite -->
2. `{"user2": {"name": "李四", "id_card": "110101199001015678"}}` <!-- fcg-rewrite -->

**Benefit**: Each user's data is processed independently with full context. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### YAML Segmentation <!-- fcg-rewrite -->

**Strategy**: Split by top-level keys <!-- fcg-rewrite -->

**Example Input**: <!-- fcg-rewrite -->
```yaml <!-- fcg-rewrite -->
user1: <!-- fcg-rewrite -->
  name: 张三 <!-- fcg-rewrite -->
  id_card: 110101199001011234 <!-- fcg-rewrite -->
user2: <!-- fcg-rewrite -->
  name: 李四 <!-- fcg-rewrite -->
  id_card: 110101199001015678 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Segments** (2): <!-- fcg-rewrite -->
1. `user1:\n  name: 张三\n  id_card: 110101199001011234` <!-- fcg-rewrite -->
2. `user2:\n  name: 李四\n  id_card: 110101199001015678` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### CSV Segmentation <!-- fcg-rewrite -->

**Strategy**: Split by rows (keep header) <!-- fcg-rewrite -->

**Example Input**: <!-- fcg-rewrite -->
```csv <!-- fcg-rewrite -->
name,id_card,phone <!-- fcg-rewrite -->
张三,110101199001011234,13800138000 <!-- fcg-rewrite -->
李四,110101199001015678,13900139000 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Segments** (2): <!-- fcg-rewrite -->
1. `name,id_card,phone\n张三,110101199001011234,13800138000` <!-- fcg-rewrite -->
2. `name,id_card,phone\n李四,110101199001015678,13900139000` <!-- fcg-rewrite -->

**Benefit**: Each row retains column headers for context. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Markdown Segmentation <!-- fcg-rewrite -->

**Strategy**: Split by ## sections <!-- fcg-rewrite -->

**Example Input**: <!-- fcg-rewrite -->
```markdown <!-- fcg-rewrite -->
## User 1 <!-- fcg-rewrite -->

Name: 张三 <!-- fcg-rewrite -->
ID Card: 110101199001011234 <!-- fcg-rewrite -->

## User 2 <!-- fcg-rewrite -->

Name: 李四 <!-- fcg-rewrite -->
ID Card: 110101199001015678 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Segments** (2): <!-- fcg-rewrite -->
1. `## User 1\n\nName: 张三\nID Card: 110101199001011234` <!-- fcg-rewrite -->
2. `## User 2\n\nName: 李四\nID Card: 110101199001015678` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Plain Text (No Segmentation) <!-- fcg-rewrite -->

**Strategy**: Process as single segment <!-- fcg-rewrite -->

**Example Input**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
My name is 张三, ID: 110101199001011234. My friend 李四's ID is 110101199001015678. <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Segments** (1): <!-- fcg-rewrite -->
1. (entire text as single segment) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Segmentation Limits <!-- fcg-rewrite -->

| Format      | Max Segments | Max Segment Size | Behavior if Exceeded        | <!-- fcg-rewrite -->
|-------------|--------------|------------------|-----------------------------| <!-- fcg-rewrite -->
| JSON        | 50           | 10,000 chars     | Fallback to full text       | <!-- fcg-rewrite -->
| YAML        | 50           | 10,000 chars     | Fallback to full text       | <!-- fcg-rewrite -->
| CSV         | 100          | 5,000 chars/row  | Fallback to full text       | <!-- fcg-rewrite -->
| Markdown    | 30           | 15,000 chars     | Fallback to full text       | <!-- fcg-rewrite -->
| Plain Text  | 1            | Unlimited        | N/A                         | <!-- fcg-rewrite -->

**Fallback Behavior**: If segmentation exceeds limits, process entire content as single segment (plain text mode). <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Disposal Strategies <!-- fcg-rewrite -->

### Block <!-- fcg-rewrite -->

**Action**: Reject request completely <!-- fcg-rewrite -->

**Use Case**: <!-- fcg-rewrite -->
- High-risk data detected <!-- fcg-rewrite -->
- Zero-tolerance policies <!-- fcg-rewrite -->
- Compliance requirements <!-- fcg-rewrite -->

**Implementation**: <!-- fcg-rewrite -->
1. Stop request processing <!-- fcg-rewrite -->
2. Return error response to client <!-- fcg-rewrite -->
3. Log incident with detected entities <!-- fcg-rewrite -->
4. Optionally trigger alerts <!-- fcg-rewrite -->

**Response Example**: <!-- fcg-rewrite -->
```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "error": { <!-- fcg-rewrite -->
    "message": "Request blocked due to data leakage risk: High risk entities detected (ID card, credit card)", <!-- fcg-rewrite -->
    "type": "data_leakage_blocked", <!-- fcg-rewrite -->
    "code": "high_risk_detected" <!-- fcg-rewrite -->
  } <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Logging**: <!-- fcg-rewrite -->
- Risk level: HIGH <!-- fcg-rewrite -->
- Action taken: BLOCK <!-- fcg-rewrite -->
- Detected entities: [list of entity types] <!-- fcg-rewrite -->
- Tenant ID, Application ID, User ID <!-- fcg-rewrite -->
- Timestamp, request hash <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Switch Private Model <!-- fcg-rewrite -->

**Action**: Redirect request to data-private model <!-- fcg-rewrite -->

**Use Case**: <!-- fcg-rewrite -->
- Medium/high-risk data detected <!-- fcg-rewrite -->
- Private model available <!-- fcg-rewrite -->
- Maintain user experience while protecting data <!-- fcg-rewrite -->

**Implementation**: <!-- fcg-rewrite -->
1. Fetch private model using priority logic <!-- fcg-rewrite -->
2. Replace `model` parameter in request <!-- fcg-rewrite -->
3. Forward to private model API <!-- fcg-rewrite -->
4. Return response to client <!-- fcg-rewrite -->
5. Log model switch <!-- fcg-rewrite -->

**Example Flow**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
User Request: <!-- fcg-rewrite -->
  model: gpt-4o (public API) <!-- fcg-rewrite -->
  content: "My ID is 110101199001011234" <!-- fcg-rewrite -->

↓ Detection: Medium Risk <!-- fcg-rewrite -->

↓ Policy: switch_private_model <!-- fcg-rewrite -->

Private Model Selection: <!-- fcg-rewrite -->
  gpt-4o-azure-private (is_default_private_model) <!-- fcg-rewrite -->

Modified Request: <!-- fcg-rewrite -->
  model: gpt-4o-azure-private <!-- fcg-rewrite -->
  content: "My ID is 110101199001011234" (unchanged) <!-- fcg-rewrite -->

↓ Forward to Azure Private Endpoint <!-- fcg-rewrite -->

Response: (from private model) <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Logging**: <!-- fcg-rewrite -->
- Risk level: MEDIUM <!-- fcg-rewrite -->
- Action taken: SWITCH_private_model <!-- fcg-rewrite -->
- Original model: gpt-4o <!-- fcg-rewrite -->
- Private model used: gpt-4o-azure-private <!-- fcg-rewrite -->
- Detected entities: [list] <!-- fcg-rewrite -->

**Error Handling**: <!-- fcg-rewrite -->
- If no private model available → fallback to BLOCK <!-- fcg-rewrite -->
- If private model API fails → return original error + log incident <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Anonymize <!-- fcg-rewrite -->

**Action**: Replace sensitive entities with placeholders <!-- fcg-rewrite -->

**Use Case**: <!-- fcg-rewrite -->
- Low-risk data detected <!-- fcg-rewrite -->
- Model needs context but not exact values <!-- fcg-rewrite -->
- Development/testing environments <!-- fcg-rewrite -->

**Implementation**: <!-- fcg-rewrite -->
1. Detect sensitive entities <!-- fcg-rewrite -->
2. Generate placeholders (e.g., `[ID_CARD_1]`, `[PHONE_NUMBER_1]`) <!-- fcg-rewrite -->
3. Replace entities in content <!-- fcg-rewrite -->
4. Forward anonymized request to original model <!-- fcg-rewrite -->
5. Return response (with placeholders) <!-- fcg-rewrite -->
6. Log anonymization <!-- fcg-rewrite -->

**Anonymization Examples**: <!-- fcg-rewrite -->

**Original**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
My name is 张三, ID card: 110101199001011234, phone: 13800138000 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Anonymized**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
My name is 张三, ID card: [ID_CARD_1], phone: [PHONE_NUMBER_1] <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Original (JSON)**: <!-- fcg-rewrite -->
```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "user": "张三", <!-- fcg-rewrite -->
  "id_card": "110101199001011234", <!-- fcg-rewrite -->
  "credit_card": "6222021234567890123" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Anonymized**: <!-- fcg-rewrite -->
```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "user": "张三", <!-- fcg-rewrite -->
  "id_card": "[ID_CARD_1]", <!-- fcg-rewrite -->
  "credit_card": "[CREDIT_CARD_1]" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Placeholder Format**: <!-- fcg-rewrite -->
- Pattern: `[{ENTITY_TYPE}_{INDEX}]` <!-- fcg-rewrite -->
- Preserves structure (e.g., JSON remains valid JSON) <!-- fcg-rewrite -->
- Reversible (for response processing, if needed) <!-- fcg-rewrite -->

**Logging**: <!-- fcg-rewrite -->
- Risk level: LOW <!-- fcg-rewrite -->
- Action taken: ANONYMIZE <!-- fcg-rewrite -->
- Entities anonymized: count by type <!-- fcg-rewrite -->
- Original content hash (for audit) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Pass (Audit Only) <!-- fcg-rewrite -->

**Action**: Allow request unchanged, log detection <!-- fcg-rewrite -->

**Use Case**: <!-- fcg-rewrite -->
- Monitoring before enforcement <!-- fcg-rewrite -->
- Audit trails <!-- fcg-rewrite -->
- Low-sensitivity applications <!-- fcg-rewrite -->

**Implementation**: <!-- fcg-rewrite -->
1. Run detection as normal <!-- fcg-rewrite -->
2. Log results <!-- fcg-rewrite -->
3. Forward request unchanged <!-- fcg-rewrite -->
4. Return response unchanged <!-- fcg-rewrite -->

**Logging**: <!-- fcg-rewrite -->
- Risk level: (detected level) <!-- fcg-rewrite -->
- Action taken: PASS <!-- fcg-rewrite -->
- Detected entities: [list] <!-- fcg-rewrite -->
- Note: "Audit-only mode" <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Best Practices <!-- fcg-rewrite -->

### Policy Configuration <!-- fcg-rewrite -->

#### 1. Start with Default Strategy <!-- fcg-rewrite -->

**Recommended Initial Configuration**: <!-- fcg-rewrite -->
- High Risk → Block <!-- fcg-rewrite -->
- Medium Risk → Switch Private Model <!-- fcg-rewrite -->
- Low Risk → Anonymize <!-- fcg-rewrite -->
- Format Detection: Enabled <!-- fcg-rewrite -->
- Smart Segmentation: Enabled <!-- fcg-rewrite -->

**Why**: This provides strong protection while maintaining usability. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 2. Use Audit Mode Before Enforcement <!-- fcg-rewrite -->

**Workflow**: <!-- fcg-rewrite -->
1. Set all actions to **Pass** initially <!-- fcg-rewrite -->
2. Monitor detection results for 1-2 weeks <!-- fcg-rewrite -->
3. Review false positives/negatives <!-- fcg-rewrite -->
4. Adjust entity types or thresholds <!-- fcg-rewrite -->
5. Enable enforcement (Block/Switch/Anonymize) <!-- fcg-rewrite -->

**Benefit**: Prevents disrupting users with false positives. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 3. Configure Private Models First <!-- fcg-rewrite -->

**Before enabling "Switch Private Model"**: <!-- fcg-rewrite -->
1. ✅ Configure at least one private model <!-- fcg-rewrite -->
2. ✅ Test private model API connectivity <!-- fcg-rewrite -->
3. ✅ Set default private model or priorities <!-- fcg-rewrite -->
4. ✅ Document private model selection logic <!-- fcg-rewrite -->

**Why**: Prevents errors when policy tries to switch but no private model exists. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 4. Tier Policies by Application Sensitivity <!-- fcg-rewrite -->

**Example**: <!-- fcg-rewrite -->

**Public Chatbot** (low sensitivity): <!-- fcg-rewrite -->
- High → Anonymize <!-- fcg-rewrite -->
- Medium → Anonymize <!-- fcg-rewrite -->
- Low → Pass <!-- fcg-rewrite -->

**Internal HR System** (high sensitivity): <!-- fcg-rewrite -->
- High → Block <!-- fcg-rewrite -->
- Medium → Switch Private Model <!-- fcg-rewrite -->
- Low → Anonymize <!-- fcg-rewrite -->

**Compliance-Critical App** (maximum sensitivity): <!-- fcg-rewrite -->
- High → Block <!-- fcg-rewrite -->
- Medium → Block <!-- fcg-rewrite -->
- Low → Switch Private Model <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Private Model Management <!-- fcg-rewrite -->

#### 1. Maintain Model Redundancy <!-- fcg-rewrite -->

**Recommendation**: Configure at least **2 private models** per priority tier. <!-- fcg-rewrite -->

**Example**: <!-- fcg-rewrite -->
- Primary: Azure OpenAI Private (priority 95) <!-- fcg-rewrite -->
- Secondary: AWS Bedrock Private (priority 90) <!-- fcg-rewrite -->
- Fallback: Local Ollama (priority 70) <!-- fcg-rewrite -->

**Benefit**: Ensures availability even if primary private model fails. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 2. Test Private Models Regularly <!-- fcg-rewrite -->

**Monthly Checklist**: <!-- fcg-rewrite -->
- [ ] Test API connectivity <!-- fcg-rewrite -->
- [ ] Verify authentication tokens <!-- fcg-rewrite -->
- [ ] Check rate limits <!-- fcg-rewrite -->
- [ ] Test with sample sensitive data <!-- fcg-rewrite -->
- [ ] Review performance metrics <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 3. Document Model Capabilities <!-- fcg-rewrite -->

**For each private model, document**: <!-- fcg-rewrite -->
- Model name and version <!-- fcg-rewrite -->
- Provider and endpoint <!-- fcg-rewrite -->
- Data residency (region, country) <!-- fcg-rewrite -->
- Compliance certifications (GDPR, HIPAA, SOC2, etc.) <!-- fcg-rewrite -->
- Performance characteristics (latency, throughput) <!-- fcg-rewrite -->
- Cost per request <!-- fcg-rewrite -->
- Maintenance windows <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Detection Tuning <!-- fcg-rewrite -->

#### 1. Review Detection Results Weekly <!-- fcg-rewrite -->

**Metrics to Monitor**: <!-- fcg-rewrite -->
- Total detections by risk level <!-- fcg-rewrite -->
- False positive rate (user reports) <!-- fcg-rewrite -->
- Blocked requests (High risk) <!-- fcg-rewrite -->
- Model switches (Medium risk) <!-- fcg-rewrite -->
- Anonymizations (Low risk) <!-- fcg-rewrite -->

**Action Items**: <!-- fcg-rewrite -->
- Whitelist known false positives <!-- fcg-rewrite -->
- Adjust entity type sensitivities <!-- fcg-rewrite -->
- Update regex patterns if needed <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 2. Balance Security and Usability <!-- fcg-rewrite -->

**Signs of Over-Blocking**: <!-- fcg-rewrite -->
- High user complaint rate <!-- fcg-rewrite -->
- Many legitimate requests blocked <!-- fcg-rewrite -->
- Users bypass system (direct API calls) <!-- fcg-rewrite -->

**Solution**: <!-- fcg-rewrite -->
- Lower high-risk thresholds <!-- fcg-rewrite -->
- Move some entities from high → medium risk <!-- fcg-rewrite -->
- Use anonymize instead of block for borderline cases <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 3. Use Format Detection for Structured Data <!-- fcg-rewrite -->

**When to Enable**: <!-- fcg-rewrite -->
- Users submit JSON/YAML/CSV frequently <!-- fcg-rewrite -->
- API integrations (structured payloads) <!-- fcg-rewrite -->
- Batch data processing <!-- fcg-rewrite -->

**When to Disable**: <!-- fcg-rewrite -->
- 100% plain text chatbot <!-- fcg-rewrite -->
- Performance-critical (latency < 50ms required) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Security Hardening <!-- fcg-rewrite -->

#### 1. Rotate API Keys for Private Models <!-- fcg-rewrite -->

**Recommendation**: Rotate every 90 days <!-- fcg-rewrite -->

**Process**: <!-- fcg-rewrite -->
1. Generate new API key in provider console <!-- fcg-rewrite -->
2. Update private model configuration <!-- fcg-rewrite -->
3. Test connectivity <!-- fcg-rewrite -->
4. Revoke old key after 7-day overlap <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 2. Monitor for Data Leakage Incidents <!-- fcg-rewrite -->

**Set up alerts for**: <!-- fcg-rewrite -->
- High-risk detections (immediate alert) <!-- fcg-rewrite -->
- Blocked requests exceeding threshold (hourly) <!-- fcg-rewrite -->
- Private model switch failures (immediate) <!-- fcg-rewrite -->
- Unusually high detection rate (daily) <!-- fcg-rewrite -->

**Alert Channels**: <!-- fcg-rewrite -->
- Email: Security team <!-- fcg-rewrite -->
- Slack/Teams: On-call engineer <!-- fcg-rewrite -->
- SIEM: Log aggregation system <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 3. Implement Rate Limits <!-- fcg-rewrite -->

**Recommendation**: <!-- fcg-rewrite -->
- Set rate limits on proxy keys <!-- fcg-rewrite -->
- Separate limits for high-risk vs. normal requests <!-- fcg-rewrite -->
- Block users exceeding limits temporarily <!-- fcg-rewrite -->

**Example**: <!-- fcg-rewrite -->
- Normal requests: 100/minute <!-- fcg-rewrite -->
- High-risk detections: 10/minute (triggers alert if exceeded) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### 4. Audit Logs Retention <!-- fcg-rewrite -->

**Recommendation**: <!-- fcg-rewrite -->
- Retain detection logs for **90 days** minimum <!-- fcg-rewrite -->
- Archive critical incidents for **1 year** <!-- fcg-rewrite -->
- Anonymize logs older than retention period <!-- fcg-rewrite -->

**Compliance**: <!-- fcg-rewrite -->
- GDPR: Right to erasure (delete user data on request) <!-- fcg-rewrite -->
- HIPAA: 6-year retention requirement <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Troubleshooting <!-- fcg-rewrite -->

### Common Issues <!-- fcg-rewrite -->

#### Issue 1: "No private model available" Error <!-- fcg-rewrite -->

**Symptom**: <!-- fcg-rewrite -->
```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "error": "No private model available for switching" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Cause**: Policy is set to "switch_private_model", but no private models are configured. <!-- fcg-rewrite -->

**Solution**: <!-- fcg-rewrite -->
1. Navigate to **Config > Proxy Models** <!-- fcg-rewrite -->
2. Edit an existing model or create a new one <!-- fcg-rewrite -->
3. Enable **"Is Data Safe"** <!-- fcg-rewrite -->
4. Set **"Is Default Private Model"** or assign a priority <!-- fcg-rewrite -->
5. Save and test again <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Issue 2: Private Model Switch Not Working <!-- fcg-rewrite -->

**Symptom**: Medium-risk data detected, but request still goes to original model. <!-- fcg-rewrite -->

**Possible Causes**: <!-- fcg-rewrite -->

**Cause 1**: Policy action is not set to "switch_private_model" <!-- fcg-rewrite -->
- **Solution**: Check **Config > Data Leakage Policy** → Medium Risk Action <!-- fcg-rewrite -->

**Cause 2**: Private model API is failing <!-- fcg-rewrite -->
- **Solution**: Check logs for private model API errors, verify connectivity <!-- fcg-rewrite -->

**Cause 3**: Private model is marked inactive <!-- fcg-rewrite -->
- **Solution**: Navigate to **Proxy Models** → ensure "Is Active" is enabled <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Issue 3: Format Detection Not Working <!-- fcg-rewrite -->

**Symptom**: JSON content is processed as plain text. <!-- fcg-rewrite -->

**Possible Causes**: <!-- fcg-rewrite -->

**Cause 1**: Format detection is disabled <!-- fcg-rewrite -->
- **Solution**: Enable **"Enable Format Detection"** in policy <!-- fcg-rewrite -->

**Cause 2**: JSON is invalid <!-- fcg-rewrite -->
- **Solution**: Validate JSON syntax (use `jq` or online validator) <!-- fcg-rewrite -->

**Cause 3**: Content is too small (< 50 chars) <!-- fcg-rewrite -->
- **Solution**: Format detection requires minimum content length <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Issue 4: Smart Segmentation Causing Errors <!-- fcg-rewrite -->

**Symptom**: Error "Segmentation failed" or "Maximum segments exceeded". <!-- fcg-rewrite -->

**Possible Causes**: <!-- fcg-rewrite -->

**Cause 1**: Content exceeds segmentation limits (50 objects, 100 rows, etc.) <!-- fcg-rewrite -->
- **Solution**: System should fallback to full text automatically; check logs <!-- fcg-rewrite -->

**Cause 2**: Malformed content (e.g., unclosed JSON objects) <!-- fcg-rewrite -->
- **Solution**: Validate content structure before sending <!-- fcg-rewrite -->

**Solution**: Disable smart segmentation temporarily: <!-- fcg-rewrite -->
1. Navigate to **Config > Data Leakage Policy** <!-- fcg-rewrite -->
2. Disable **"Enable Smart Segmentation"** <!-- fcg-rewrite -->
3. Save and test <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Issue 5: High False Positive Rate <!-- fcg-rewrite -->

**Symptom**: Legitimate requests are blocked or anonymized incorrectly. <!-- fcg-rewrite -->

**Examples**: <!-- fcg-rewrite -->
- Generic IDs (e.g., "ORDER-123456") detected as ID cards <!-- fcg-rewrite -->
- Phone-like numbers (e.g., "40404040") detected as phone numbers <!-- fcg-rewrite -->

**Solutions**: <!-- fcg-rewrite -->

**Solution 1**: Adjust entity type sensitivity <!-- fcg-rewrite -->
- Navigate to **Config > Data Security** → Entity Types <!-- fcg-rewrite -->
- Lower sensitivity or disable problematic entity types <!-- fcg-rewrite -->

**Solution 2**: Use whitelist patterns <!-- fcg-rewrite -->
- Add known false-positive patterns to whitelist <!-- fcg-rewrite -->
- Example: `ORDER-\d+` for order IDs <!-- fcg-rewrite -->

**Solution 3**: Use "Pass" action temporarily <!-- fcg-rewrite -->
- Set action to "Pass" (audit-only) <!-- fcg-rewrite -->
- Review logs for patterns <!-- fcg-rewrite -->
- Create whitelist rules <!-- fcg-rewrite -->
- Re-enable enforcement <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

#### Issue 6: Performance Degradation <!-- fcg-rewrite -->

**Symptom**: Requests are slow (> 2 seconds) with format detection/segmentation enabled. <!-- fcg-rewrite -->

**Possible Causes**: <!-- fcg-rewrite -->

**Cause 1**: Very large content (> 50KB) <!-- fcg-rewrite -->
- **Solution**: Consider disabling segmentation for large content <!-- fcg-rewrite -->

**Cause 2**: Too many segments (> 50) <!-- fcg-rewrite -->
- **Solution**: System should fallback automatically; verify in logs <!-- fcg-rewrite -->

**Cause 3**: Private model API is slow <!-- fcg-rewrite -->
- **Solution**: Monitor private model latency; consider faster model <!-- fcg-rewrite -->

**Performance Optimization**: <!-- fcg-rewrite -->
1. Disable format detection if all content is plain text <!-- fcg-rewrite -->
2. Disable smart segmentation for short content (< 1KB) <!-- fcg-rewrite -->
3. Use faster private models (e.g., gpt-4o-mini instead of gpt-4o) <!-- fcg-rewrite -->
4. Increase proxy service worker count <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Debug Mode <!-- fcg-rewrite -->

#### Enable Debug Logging <!-- fcg-rewrite -->

**Method 1**: Environment variable <!-- fcg-rewrite -->
```bash <!-- fcg-rewrite -->
export LOG_LEVEL=DEBUG <!-- fcg-rewrite -->
docker compose restart fangcunguard-admin fangcunguard-proxy <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Method 2**: Runtime flag (development) <!-- fcg-rewrite -->
```python <!-- fcg-rewrite -->
# In proxy_service.py or admin_service.py <!-- fcg-rewrite -->
import logging <!-- fcg-rewrite -->
logging.getLogger("fangcunguard").setLevel(logging.DEBUG) <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

#### View Debug Logs <!-- fcg-rewrite -->

```bash <!-- fcg-rewrite -->
# Proxy service logs (disposal logic) <!-- fcg-rewrite -->
docker logs -f fangcunguard-proxy | grep -i "data_leakage" <!-- fcg-rewrite -->

# Admin service logs (policy configuration) <!-- fcg-rewrite -->
docker logs -f fangcunguard-admin | grep -i "policy" <!-- fcg-rewrite -->

# Database queries (if needed) <!-- fcg-rewrite -->
docker logs -f fangcunguard-postgres <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

#### Key Log Messages <!-- fcg-rewrite -->

**Format Detection**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
DEBUG - Format detected: json (confidence: 95%) <!-- fcg-rewrite -->
DEBUG - Segmentation enabled: True, format: json <!-- fcg-rewrite -->
DEBUG - Segments created: 5 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Entity Detection**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
DEBUG - Regex entities detected: ['ID_CARD'] in full text <!-- fcg-rewrite -->
DEBUG - GenAI entities detected in segment 1: ['PHONE_NUMBER', 'ADDRESS'] <!-- fcg-rewrite -->
DEBUG - Aggregated risk: MEDIUM (highest from 5 segments) <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Disposal Action**: <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
INFO - Data leakage risk: MEDIUM, action: SWITCH_private_model <!-- fcg-rewrite -->
DEBUG - Private model selected: gpt-4o-azure-private (priority: 95) <!-- fcg-rewrite -->
DEBUG - Request forwarded to private model <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## API Integration <!-- fcg-rewrite -->

### Using the Proxy Gateway (Recommended) <!-- fcg-rewrite -->

**Endpoint**: `POST http://localhost:5002/v1/chat/completions` <!-- fcg-rewrite -->

**Authentication**: Proxy API Key (`sk-xxai-...`) <!-- fcg-rewrite -->

**Example Request**: <!-- fcg-rewrite -->
```bash <!-- fcg-rewrite -->
curl -X POST http://localhost:5002/v1/chat/completions \ <!-- fcg-rewrite -->
  -H "Authorization: Bearer sk-xxai-your-proxy-key" \ <!-- fcg-rewrite -->
  -H "Content-Type: application/json" \ <!-- fcg-rewrite -->
  -d '{ <!-- fcg-rewrite -->
    "model": "gpt-4o", <!-- fcg-rewrite -->
    "messages": [ <!-- fcg-rewrite -->
      { <!-- fcg-rewrite -->
        "role": "user", <!-- fcg-rewrite -->
        "content": "{\"user\": \"张三\", \"id_card\": \"110101199001011234\"}" <!-- fcg-rewrite -->
      } <!-- fcg-rewrite -->
    ] <!-- fcg-rewrite -->
  }' <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Automatic Protection**: <!-- fcg-rewrite -->
1. Request is intercepted by proxy <!-- fcg-rewrite -->
2. Content is analyzed for data leakage <!-- fcg-rewrite -->
3. Disposal action is applied (block/switch/anonymize) <!-- fcg-rewrite -->
4. Response is returned <!-- fcg-rewrite -->

**Advantages**: <!-- fcg-rewrite -->
- **Zero code changes**: Works with OpenAI SDK <!-- fcg-rewrite -->
- **Automatic protection**: No manual API calls <!-- fcg-rewrite -->
- **Transparent**: Users don't see protection layer <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Direct Detection API (Advanced) <!-- fcg-rewrite -->

**Endpoint**: `POST http://localhost:5001/v1/guardrails` <!-- fcg-rewrite -->

**Authentication**: Proxy API Key (`sk-xxai-...`) <!-- fcg-rewrite -->

**Use Case**: Custom workflows, manual control over disposal <!-- fcg-rewrite -->

**Example Request**: <!-- fcg-rewrite -->
```bash <!-- fcg-rewrite -->
curl -X POST http://localhost:5001/v1/guardrails \ <!-- fcg-rewrite -->
  -H "Authorization: Bearer sk-xxai-your-proxy-key" \ <!-- fcg-rewrite -->
  -H "Content-Type: application/json" \ <!-- fcg-rewrite -->
  -d '{ <!-- fcg-rewrite -->
    "messages": [ <!-- fcg-rewrite -->
      { <!-- fcg-rewrite -->
        "role": "user", <!-- fcg-rewrite -->
        "content": "My ID card is 110101199001011234" <!-- fcg-rewrite -->
      } <!-- fcg-rewrite -->
    ] <!-- fcg-rewrite -->
  }' <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Response**: <!-- fcg-rewrite -->
```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "is_safe": false, <!-- fcg-rewrite -->
  "highest_risk_level": "MEDIUM", <!-- fcg-rewrite -->
  "data_risks": [ <!-- fcg-rewrite -->
    { <!-- fcg-rewrite -->
      "detected": true, <!-- fcg-rewrite -->
      "risk_level": "MEDIUM", <!-- fcg-rewrite -->
      "detected_entity_types": ["ID_CARD"], <!-- fcg-rewrite -->
      "risk_details": ["ID card number detected: 110101..."], <!-- fcg-rewrite -->
      "suggested_action": "SWITCH_private_model" <!-- fcg-rewrite -->
    } <!-- fcg-rewrite -->
  ] <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Client-Side Disposal**: <!-- fcg-rewrite -->
```python <!-- fcg-rewrite -->
response = requests.post( <!-- fcg-rewrite -->
    "http://localhost:5001/v1/guardrails", <!-- fcg-rewrite -->
    headers={"Authorization": "Bearer sk-xxai-your-key"}, <!-- fcg-rewrite -->
    json={"messages": messages, "enable_data_detection": True} <!-- fcg-rewrite -->
) <!-- fcg-rewrite -->

result = response.json() <!-- fcg-rewrite -->

if not result["is_safe"]: <!-- fcg-rewrite -->
    action = result["data_risks"][0]["suggested_action"] <!-- fcg-rewrite -->

    if action == "BLOCK": <!-- fcg-rewrite -->
        return {"error": "Request blocked due to data leakage risk"} <!-- fcg-rewrite -->

    elif action == "SWITCH_private_model": <!-- fcg-rewrite -->
        # Switch to private model manually <!-- fcg-rewrite -->
        messages_safe = messages  # Send to private model <!-- fcg-rewrite -->
        safe_response = openai.ChatCompletion.create( <!-- fcg-rewrite -->
            model="gpt-4o-azure-private", <!-- fcg-rewrite -->
            messages=messages_safe <!-- fcg-rewrite -->
        ) <!-- fcg-rewrite -->
        return safe_response <!-- fcg-rewrite -->

    elif action == "ANONYMIZE": <!-- fcg-rewrite -->
        # Anonymize manually (simplified) <!-- fcg-rewrite -->
        anonymized_content = anonymize_entities(messages, result["data_risks"][0]["detected_entity_types"]) <!-- fcg-rewrite -->
        safe_response = openai.ChatCompletion.create( <!-- fcg-rewrite -->
            model="gpt-4o", <!-- fcg-rewrite -->
            messages=anonymized_content <!-- fcg-rewrite -->
        ) <!-- fcg-rewrite -->
        return safe_response <!-- fcg-rewrite -->

else: <!-- fcg-rewrite -->
    # Safe, proceed normally <!-- fcg-rewrite -->
    response = openai.ChatCompletion.create(model="gpt-4o", messages=messages) <!-- fcg-rewrite -->
    return response <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Programmatic Policy Management <!-- fcg-rewrite -->

#### Get Current Policy <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
import requests <!-- fcg-rewrite -->

response = requests.get( <!-- fcg-rewrite -->
    "http://localhost:5000/api/v1/config/data-leakage-policy", <!-- fcg-rewrite -->
    headers={ <!-- fcg-rewrite -->
        "Authorization": "Bearer <JWT_TOKEN>", <!-- fcg-rewrite -->
        "X-Application-ID": "<APPLICATION_ID>" <!-- fcg-rewrite -->
    } <!-- fcg-rewrite -->
) <!-- fcg-rewrite -->

policy = response.json() <!-- fcg-rewrite -->
print(policy["high_risk_action"])  # e.g., "block" <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

#### Update Policy <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
import requests <!-- fcg-rewrite -->

requests.put( <!-- fcg-rewrite -->
    "http://localhost:5000/api/v1/config/data-leakage-policy", <!-- fcg-rewrite -->
    headers={ <!-- fcg-rewrite -->
        "Authorization": "Bearer <JWT_TOKEN>", <!-- fcg-rewrite -->
        "X-Application-ID": "<APPLICATION_ID>" <!-- fcg-rewrite -->
    }, <!-- fcg-rewrite -->
    json={ <!-- fcg-rewrite -->
        "high_risk_action": "block", <!-- fcg-rewrite -->
        "medium_risk_action": "switch_private_model", <!-- fcg-rewrite -->
        "low_risk_action": "anonymize", <!-- fcg-rewrite -->
        "private_model_id": "uuid-of-private-model",  # or null for default <!-- fcg-rewrite -->
        "enable_format_detection": True, <!-- fcg-rewrite -->
        "enable_smart_segmentation": True <!-- fcg-rewrite -->
    } <!-- fcg-rewrite -->
) <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

#### List Available Private Models <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
response = requests.get( <!-- fcg-rewrite -->
    "http://localhost:5000/api/v1/config/private-models", <!-- fcg-rewrite -->
    headers={"Authorization": "Bearer <JWT_TOKEN>"} <!-- fcg-rewrite -->
) <!-- fcg-rewrite -->

private_models = response.json() <!-- fcg-rewrite -->
for model in private_models: <!-- fcg-rewrite -->
    print(f"{model['config_name']}: priority {model['private_model_priority']}") <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## FAQ <!-- fcg-rewrite -->

### General Questions <!-- fcg-rewrite -->

**Q: What happens if I don't configure any private models?** <!-- fcg-rewrite -->

A: If a disposal action is set to "switch_private_model" and no private models are configured, the system will **fallback to BLOCK** and return an error. Configure at least one private model before enabling "switch_private_model" actions. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

**Q: Can I use multiple private models for different risk levels?** <!-- fcg-rewrite -->

A: Not directly. The system uses a single private model selection per request. However, you can: <!-- fcg-rewrite -->
1. Configure application-specific policies with different `private_model_id` values <!-- fcg-rewrite -->
2. Use priority to prefer different models for different applications <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

**Q: Does anonymization preserve JSON/YAML structure?** <!-- fcg-rewrite -->

A: **Yes**. The anonymization service preserves content structure: <!-- fcg-rewrite -->
- Valid JSON remains valid JSON <!-- fcg-rewrite -->
- YAML structure is maintained <!-- fcg-rewrite -->
- CSV rows remain valid CSV <!-- fcg-rewrite -->

Placeholders are inserted in place of sensitive values (e.g., `"id_card": "[ID_CARD_1]"`). <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

**Q: What is the performance impact of format detection and segmentation?** <!-- fcg-rewrite -->

A: <!-- fcg-rewrite -->
- **Format Detection**: ~5-10ms per request <!-- fcg-rewrite -->
- **Smart Segmentation**: ~10-20ms per request <!-- fcg-rewrite -->
- **Parallel Processing Gain**: 20-60% faster for large content (> 1KB) <!-- fcg-rewrite -->

**Net impact**: Slight overhead for small content, significant speedup for large content. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Configuration Questions <!-- fcg-rewrite -->

**Q: Should I enable format detection for plain text chatbots?** <!-- fcg-rewrite -->

A: **No**. If all content is plain text, format detection is unnecessary and adds minimal overhead. Disable it for best performance. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

**Q: Can I set different policies for different applications?** <!-- fcg-rewrite -->

A: **Yes**. Policies are configured per-application using the `X-Application-ID` header. Each application can have unique risk actions and private models. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

**Q: What happens if the private model API fails?** <!-- fcg-rewrite -->

A: The system logs the error and **falls back to BLOCK** to prevent data leakage. Configure redundant private models to minimize failures. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Detection Questions <!-- fcg-rewrite -->

**Q: Why are some ID cards detected as low risk instead of high risk?** <!-- fcg-rewrite -->

A: Risk level depends on: <!-- fcg-rewrite -->
1. **Entity type**: ID cards are typically high risk <!-- fcg-rewrite -->
2. **Detection confidence**: Low confidence may reduce risk level <!-- fcg-rewrite -->
3. **Context**: Partial or obfuscated IDs may be medium/low risk <!-- fcg-rewrite -->

Check detection logs to see specific risk assignments. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

**Q: Can I customize entity types (e.g., add "Employee ID")?** <!-- fcg-rewrite -->

A: **Yes**. Navigate to **Config > Data Security > Entity Type Management** to add custom entity types with regex or GenAI-based detection. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

**Q: How do I test data leakage protection without affecting users?** <!-- fcg-rewrite -->

A: Use **audit-only mode**: <!-- fcg-rewrite -->
1. Set all risk actions to **"Pass"** <!-- fcg-rewrite -->
2. Monitor detection results for 1-2 weeks <!-- fcg-rewrite -->
3. Review logs to identify false positives <!-- fcg-rewrite -->
4. Enable enforcement after tuning <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Compliance Questions <!-- fcg-rewrite -->

**Q: Is the system GDPR-compliant?** <!-- fcg-rewrite -->

A: Fangcun Guard provides **technical controls** for data protection (detection, blocking, anonymization). GDPR compliance depends on: <!-- fcg-rewrite -->
1. **Data residency**: Use on-premise or EU-region private models <!-- fcg-rewrite -->
2. **Data retention**: Configure log retention policies <!-- fcg-rewrite -->
3. **User rights**: Implement data deletion on request <!-- fcg-rewrite -->

Consult legal counsel for full compliance. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

**Q: Does anonymization meet HIPAA "de-identification" requirements?** <!-- fcg-rewrite -->

A: Anonymization **reduces risk** but may not meet HIPAA Safe Harbor or Expert Determination standards. For HIPAA: <!-- fcg-rewrite -->
1. Use **"Block"** action for high-risk PHI <!-- fcg-rewrite -->
2. Use **private models** with BAAs (Business Associate Agreements) <!-- fcg-rewrite -->
3. Conduct formal de-identification review <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

**Q: Can I use the system for PCI DSS compliance?** <!-- fcg-rewrite -->

A: **Yes**, for detecting credit card numbers. Recommended configuration: <!-- fcg-rewrite -->
- High Risk (credit cards) → **Block** <!-- fcg-rewrite -->
- Medium Risk → **Switch Private Model** (PCI-compliant endpoint) <!-- fcg-rewrite -->
- Private Model: Tokenization gateway or PCI-certified API <!-- fcg-rewrite -->

**Note**: Full PCI DSS requires additional controls (encryption, access control, logging). <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Appendix <!-- fcg-rewrite -->

### Disposal Action Decision Matrix <!-- fcg-rewrite -->

| Risk Level | Default Action       | Alternative Actions              | Use Case                          | <!-- fcg-rewrite -->
|------------|----------------------|----------------------------------|-----------------------------------| <!-- fcg-rewrite -->
| **High**   | Block                | Switch Private Model, Anonymize     | Critical data (ID, credit cards)  | <!-- fcg-rewrite -->
| **Medium** | Switch Private Model    | Block, Anonymize, Pass           | Sensitive data (names, addresses) | <!-- fcg-rewrite -->
| **Low**    | Anonymize            | Pass, Switch Private Model, Block   | Generic PII (phone, email)        | <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Entity Type Risk Mapping <!-- fcg-rewrite -->

| Entity Type          | Typical Risk Level | Regex-Based | GenAI-Based | <!-- fcg-rewrite -->
|----------------------|--------------------|-------------|-------------| <!-- fcg-rewrite -->
| ID Card              | High               | ✓           | ✓           | <!-- fcg-rewrite -->
| Credit Card          | High               | ✓           | ✗           | <!-- fcg-rewrite -->
| Social Security #    | High               | ✓           | ✓           | <!-- fcg-rewrite -->
| Bank Account         | High               | ✓           | ✓           | <!-- fcg-rewrite -->
| Passport Number      | High               | ✓           | ✓           | <!-- fcg-rewrite -->
| Full Name            | Medium             | ✗           | ✓           | <!-- fcg-rewrite -->
| Address              | Medium             | ✗           | ✓           | <!-- fcg-rewrite -->
| Medical Record ID    | Medium             | ✓           | ✓           | <!-- fcg-rewrite -->
| License Plate        | Medium             | ✓           | ✓           | <!-- fcg-rewrite -->
| Phone Number         | Low                | ✓           | ✓           | <!-- fcg-rewrite -->
| Email Address        | Low                | ✓           | ✓           | <!-- fcg-rewrite -->
| Organization Name    | Low                | ✗           | ✓           | <!-- fcg-rewrite -->

**Note**: Risk levels are configurable per-entity type in **Config > Data Security**. <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Glossary <!-- fcg-rewrite -->

- **Data Leakage Prevention (DLP)**: System for detecting and protecting sensitive data <!-- fcg-rewrite -->
- **Private Model**: Model marked as data-safe for handling sensitive information <!-- fcg-rewrite -->
- **Disposal Strategy**: Action taken when data leakage is detected (block, switch, anonymize, pass) <!-- fcg-rewrite -->
- **Format Detection**: Automatic identification of content structure (JSON, YAML, etc.) <!-- fcg-rewrite -->
- **Smart Segmentation**: Format-aware content splitting for parallel processing <!-- fcg-rewrite -->
- **Regex Entity**: Entity detected using regular expressions (e.g., ID card patterns) <!-- fcg-rewrite -->
- **GenAI Entity**: Entity detected using AI models (e.g., names, addresses) <!-- fcg-rewrite -->
- **Risk Aggregation**: Combining detection results from multiple segments <!-- fcg-rewrite -->
- **Application Policy**: Per-application configuration for disposal strategies <!-- fcg-rewrite -->
- **Private Model Priority**: Ranking system for selecting private models <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

### Support <!-- fcg-rewrite -->

**Documentation**: <!-- fcg-rewrite -->
- [Deployment Guide](../getting-started/DEPLOYMENT.md) <!-- fcg-rewrite -->

**Community**: <!-- fcg-rewrite -->
- [GitHub Issues](https://github.com/Fangcun-AI/Fangcun-Guard/issues) <!-- fcg-rewrite -->
