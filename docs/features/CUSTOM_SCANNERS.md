# Custom Scanners Guide <!-- fcg-rewrite -->

> Build custom detection logic tailored to your business needs <!-- fcg-rewrite -->

## Table of Contents <!-- fcg-rewrite -->

- [Overview](#overview) <!-- fcg-rewrite -->
- [Scanner Package System](#scanner-package-system) <!-- fcg-rewrite -->
- [Scanner Types](#scanner-types) <!-- fcg-rewrite -->
- [Creating Custom Scanners](#creating-custom-scanners) <!-- fcg-rewrite -->
- [Managing Scanners](#managing-scanners) <!-- fcg-rewrite -->
- [Best Practices](#best-practices) <!-- fcg-rewrite -->
- [Examples](#examples) <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Overview <!-- fcg-rewrite -->

**Custom Scanners** are one of FangcunGuard' most powerful features, allowing you to create domain-specific detection logic without code changes. <!-- fcg-rewrite -->

### Why Custom Scanners? <!-- fcg-rewrite -->

Traditional guardrails have **fixed, hardcoded risk types** (e.g., S1-S21). This creates problems: <!-- fcg-rewrite -->

- ❌ Can't add new detection rules without code changes <!-- fcg-rewrite -->
- ❌ Can't tailor detection to your specific business <!-- fcg-rewrite -->
- ❌ Can't implement industry-specific compliance rules <!-- fcg-rewrite -->
- ❌ Requires database migrations for new risk types <!-- fcg-rewrite -->

**FangcunGuard' Scanner System solves this:** <!-- fcg-rewrite -->

- ✅ **Unlimited custom scanners** - create as many as you need <!-- fcg-rewrite -->
- ✅ **No code changes** - add scanners via API or UI <!-- fcg-rewrite -->
- ✅ **No database migrations** - dynamic scanner system <!-- fcg-rewrite -->
- ✅ **Business-specific** - tailor to your exact use case <!-- fcg-rewrite -->
- ✅ **Application-scoped** - different scanners per application <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Scanner Package System <!-- fcg-rewrite -->

FangcunGuard uses a flexible **three-tier scanner architecture**: <!-- fcg-rewrite -->

### 📦 Three Types of Scanner Packages <!-- fcg-rewrite -->

#### 1. 🔧 **Built-in Official Packages** <!-- fcg-rewrite -->
System packages that come pre-installed: <!-- fcg-rewrite -->
- **Tags**: S1-S21 <!-- fcg-rewrite -->
- **Examples**: Violent Crime (S5), Prompt Injection (S9), Data Leak (S11) <!-- fcg-rewrite -->
- **Management**: Managed through scanner package system <!-- fcg-rewrite -->
- **Configuration**: Can enable/disable, adjust risk levels <!-- fcg-rewrite -->

#### 2. 🛒 **Purchasable Official Packages** <!-- fcg-rewrite -->
Premium scanner packages from FangcunGuard team: <!-- fcg-rewrite -->
- **Tags**: S22-S99 (reserved) <!-- fcg-rewrite -->
- **Examples**: Healthcare Compliance, Financial Regulations, Legal Industry <!-- fcg-rewrite -->
- **Management**: Purchase through admin marketplace <!-- fcg-rewrite -->
- **Updates**: Regular updates from FangcunGuard team <!-- fcg-rewrite -->

#### 3. ✨ **Custom Scanners (S100+)** <!-- fcg-rewrite -->
User-defined scanners for business-specific needs: <!-- fcg-rewrite -->
- **Tags**: S100, S101, S102... (automatically assigned) <!-- fcg-rewrite -->
- **Scope**: Application-specific (not tenant-wide) <!-- fcg-rewrite -->
- **Types**: GenAI, Regex, Keyword <!-- fcg-rewrite -->
- **Flexibility**: Unlimited creation, full control <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Scanner Types <!-- fcg-rewrite -->

FangcunGuard supports three scanner implementation types: <!-- fcg-rewrite -->

### 1. GenAI Scanner (Intelligent) <!-- fcg-rewrite -->

**Best for**: Complex concepts, contextual understanding <!-- fcg-rewrite -->

**How it works**: Uses Qwen3Guard-Gen-8B model for intelligent detection <!-- fcg-rewrite -->

**Examples**: <!-- fcg-rewrite -->
- Medical advice detection <!-- fcg-rewrite -->
- Financial advice screening <!-- fcg-rewrite -->
- Brand reputation monitoring <!-- fcg-rewrite -->
- Complex policy violations <!-- fcg-rewrite -->

**Performance**: ~100-200ms per detection (model call required) <!-- fcg-rewrite -->

**Accuracy**: High - understands context and nuance <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "scanner_type": "genai", <!-- fcg-rewrite -->
  "name": "Medical Advice Detection", <!-- fcg-rewrite -->
  "definition": "Detect medical advice, diagnosis, or treatment recommendations that should only come from licensed professionals", <!-- fcg-rewrite -->
  "risk_level": "high_risk" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### 2. Regex Scanner (Pattern-Based) <!-- fcg-rewrite -->

**Best for**: Structured data, pattern matching <!-- fcg-rewrite -->

**How it works**: Python regex pattern matching <!-- fcg-rewrite -->

**Examples**: <!-- fcg-rewrite -->
- Credit card numbers <!-- fcg-rewrite -->
- Social security numbers <!-- fcg-rewrite -->
- API keys / credentials <!-- fcg-rewrite -->
- Email patterns <!-- fcg-rewrite -->
- URLs matching specific domains <!-- fcg-rewrite -->

**Performance**: <1ms per detection (instant) <!-- fcg-rewrite -->

**Accuracy**: Perfect for structured data <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "scanner_type": "regex", <!-- fcg-rewrite -->
  "name": "Credit Card Detection", <!-- fcg-rewrite -->
  "pattern": r"\b(?:\d{4}[-\s]?){3}\d{4}\b", <!-- fcg-rewrite -->
  "risk_level": "high_risk" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### 3. Keyword Scanner (Simple) <!-- fcg-rewrite -->

**Best for**: Simple blocking, keyword lists <!-- fcg-rewrite -->

**How it works**: Comma-separated keyword matching <!-- fcg-rewrite -->

**Examples**: <!-- fcg-rewrite -->
- Competitor brand names <!-- fcg-rewrite -->
- Prohibited terminology <!-- fcg-rewrite -->
- Banned product names <!-- fcg-rewrite -->
- Internal codenames <!-- fcg-rewrite -->

**Performance**: <1ms per detection (instant) <!-- fcg-rewrite -->

**Accuracy**: Exact match only <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "scanner_type": "keyword", <!-- fcg-rewrite -->
  "name": "Competitor Brands", <!-- fcg-rewrite -->
  "keywords": "CompetitorA, CompetitorB, CompetitorC", <!-- fcg-rewrite -->
  "risk_level": "low_risk" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Creating Custom Scanners <!-- fcg-rewrite -->

### Via API <!-- fcg-rewrite -->

#### Example 1: Banking Fraud Detection (GenAI) <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
import requests <!-- fcg-rewrite -->

response = requests.post( <!-- fcg-rewrite -->
    "http://localhost:5000/api/v1/custom-scanners", <!-- fcg-rewrite -->
    headers={"Authorization": "Bearer your-jwt-token"}, <!-- fcg-rewrite -->
    json={ <!-- fcg-rewrite -->
        "scanner_type": "genai", <!-- fcg-rewrite -->
        "name": "Bank Fraud Detection", <!-- fcg-rewrite -->
        "definition": "Detect banking fraud attempts, financial scams, illegal financial advice, and money laundering instructions", <!-- fcg-rewrite -->
        "risk_level": "high_risk", <!-- fcg-rewrite -->
        "scan_prompt": True, <!-- fcg-rewrite -->
        "scan_response": True, <!-- fcg-rewrite -->
        "notes": "Custom scanner for financial applications" <!-- fcg-rewrite -->
    } <!-- fcg-rewrite -->
) <!-- fcg-rewrite -->

scanner = response.json() <!-- fcg-rewrite -->
print(f"Created scanner: {scanner['tag']}")  # Output: S100 <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

#### Example 2: Internal Codename Protection (Keyword) <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
response = requests.post( <!-- fcg-rewrite -->
    "http://localhost:5000/api/v1/custom-scanners", <!-- fcg-rewrite -->
    headers={"Authorization": "Bearer your-jwt-token"}, <!-- fcg-rewrite -->
    json={ <!-- fcg-rewrite -->
        "scanner_type": "keyword", <!-- fcg-rewrite -->
        "name": "Internal Codename Protection", <!-- fcg-rewrite -->
        "keywords": "ProjectPhoenix, ProjectTitan, AlphaBuild", <!-- fcg-rewrite -->
        "risk_level": "medium_risk", <!-- fcg-rewrite -->
        "scan_prompt": False, <!-- fcg-rewrite -->
        "scan_response": True, <!-- fcg-rewrite -->
        "notes": "Prevent leaking internal project codenames" <!-- fcg-rewrite -->
    } <!-- fcg-rewrite -->
) <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

#### Example 3: API Key Detection (Regex) <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
response = requests.post( <!-- fcg-rewrite -->
    "http://localhost:5000/api/v1/custom-scanners", <!-- fcg-rewrite -->
    headers={"Authorization": "Bearer your-jwt-token"}, <!-- fcg-rewrite -->
    json={ <!-- fcg-rewrite -->
        "scanner_type": "regex", <!-- fcg-rewrite -->
        "name": "API Key Detection", <!-- fcg-rewrite -->
        "pattern": r"(sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36,}|AIza[a-zA-Z0-9]{35})", <!-- fcg-rewrite -->
        "risk_level": "high_risk", <!-- fcg-rewrite -->
        "scan_prompt": True, <!-- fcg-rewrite -->
        "scan_response": True, <!-- fcg-rewrite -->
        "notes": "Detect OpenAI, GitHub, Google API keys" <!-- fcg-rewrite -->
    } <!-- fcg-rewrite -->
) <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Via Python SDK <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
from fangcunguard import FangcunGuard <!-- fcg-rewrite -->

client = FangcunGuard(api_key="sk-xxai-your-key") <!-- fcg-rewrite -->

# Create custom scanner <!-- fcg-rewrite -->
scanner = client.create_custom_scanner( <!-- fcg-rewrite -->
    scanner_type="genai", <!-- fcg-rewrite -->
    name="Healthcare Compliance", <!-- fcg-rewrite -->
    definition="Detect medical advice, HIPAA violations, or protected health information", <!-- fcg-rewrite -->
    risk_level="high_risk", <!-- fcg-rewrite -->
    scan_prompt=True, <!-- fcg-rewrite -->
    scan_response=True <!-- fcg-rewrite -->
) <!-- fcg-rewrite -->

print(f"Created scanner: {scanner.tag}") <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Via Web UI <!-- fcg-rewrite -->

1. Navigate to `/platform/config/custom-scanners` <!-- fcg-rewrite -->
2. Click "Create Custom Scanner" <!-- fcg-rewrite -->
3. Fill in the form: <!-- fcg-rewrite -->
   - **Scanner Type**: GenAI / Regex / Keyword <!-- fcg-rewrite -->
   - **Name**: Descriptive name <!-- fcg-rewrite -->
   - **Definition/Pattern/Keywords**: Detection logic <!-- fcg-rewrite -->
   - **Risk Level**: high_risk / medium_risk / low_risk <!-- fcg-rewrite -->
   - **Scan Prompt**: Enable input scanning <!-- fcg-rewrite -->
   - **Scan Response**: Enable output scanning <!-- fcg-rewrite -->
4. Click "Save" <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Managing Scanners <!-- fcg-rewrite -->

### List Custom Scanners <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
GET /api/v1/custom-scanners <!-- fcg-rewrite -->
Authorization: Bearer your-jwt-token <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Response:** <!-- fcg-rewrite -->
```json <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
  "scanners": [ <!-- fcg-rewrite -->
    { <!-- fcg-rewrite -->
      "id": "scanner_xxx", <!-- fcg-rewrite -->
      "tag": "S100", <!-- fcg-rewrite -->
      "scanner_type": "genai", <!-- fcg-rewrite -->
      "name": "Bank Fraud Detection", <!-- fcg-rewrite -->
      "definition": "...", <!-- fcg-rewrite -->
      "risk_level": "high_risk", <!-- fcg-rewrite -->
      "enabled": true, <!-- fcg-rewrite -->
      "scan_prompt": true, <!-- fcg-rewrite -->
      "scan_response": true, <!-- fcg-rewrite -->
      "created_at": "2025-01-15T10:30:00Z" <!-- fcg-rewrite -->
    } <!-- fcg-rewrite -->
  ] <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Update Scanner <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
PUT /api/v1/custom-scanners/{scanner_id} <!-- fcg-rewrite -->
Authorization: Bearer your-jwt-token <!-- fcg-rewrite -->

{ <!-- fcg-rewrite -->
  "enabled": false, <!-- fcg-rewrite -->
  "risk_level": "medium_risk" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Delete Scanner <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
DELETE /api/v1/custom-scanners/{scanner_id} <!-- fcg-rewrite -->
Authorization: Bearer your-jwt-token <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Using Scanners in Detection <!-- fcg-rewrite -->

Custom scanners are **automatically used** in detection requests: <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
from fangcunguard import FangcunGuard <!-- fcg-rewrite -->

client = FangcunGuard("sk-xxai-your-key") <!-- fcg-rewrite -->

# Detection automatically uses all enabled scanners (including custom) <!-- fcg-rewrite -->
response = client.check_prompt( <!-- fcg-rewrite -->
    "How can I launder money through my bank account?", <!-- fcg-rewrite -->
    application_id="your-banking-app-id" <!-- fcg-rewrite -->
) <!-- fcg-rewrite -->

print(f"Risk level: {response.overall_risk_level}") <!-- fcg-rewrite -->
print(f"Matched scanners: {response.matched_scanner_tags}") <!-- fcg-rewrite -->
# Output: "high_risk" and "S5,S100" (Violent Crime + Bank Fraud Detection) <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Best Practices <!-- fcg-rewrite -->

### 1. Choose the Right Scanner Type <!-- fcg-rewrite -->

| Scenario | Recommended Type | Reason | <!-- fcg-rewrite -->
|----------|-----------------|---------| <!-- fcg-rewrite -->
| Complex business rules | GenAI | Understands context and nuance | <!-- fcg-rewrite -->
| Structured data patterns | Regex | Fast and precise | <!-- fcg-rewrite -->
| Simple keyword blocking | Keyword | Instant and straightforward | <!-- fcg-rewrite -->
| Policy interpretation | GenAI | Can understand natural language policies | <!-- fcg-rewrite -->
| Format validation | Regex | Perfect for structured formats | <!-- fcg-rewrite -->

### 2. Write Clear Definitions (GenAI) <!-- fcg-rewrite -->

**Good GenAI Definition:** <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
Detect attempts to manipulate stock prices through false information, <!-- fcg-rewrite -->
pump-and-dump schemes, or insider trading discussions. Include both <!-- fcg-rewrite -->
explicit trading advice and subtle market manipulation tactics. <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

**Bad GenAI Definition:** <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->
Bad trading stuff <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### 3. Test Your Scanners <!-- fcg-rewrite -->

Always test scanners with: <!-- fcg-rewrite -->
- **Positive cases** (should detect) <!-- fcg-rewrite -->
- **Negative cases** (should not detect) <!-- fcg-rewrite -->
- **Edge cases** (boundary conditions) <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
test_cases = [ <!-- fcg-rewrite -->
    # Positive (should detect) <!-- fcg-rewrite -->
    "How do I avoid paying taxes on my investment gains?", <!-- fcg-rewrite -->
    "Let's discuss ways to manipulate the market price", <!-- fcg-rewrite -->

    # Negative (should not detect) <!-- fcg-rewrite -->
    "What is the difference between stocks and bonds?", <!-- fcg-rewrite -->
    "Can you explain how capital gains tax works?", <!-- fcg-rewrite -->
] <!-- fcg-rewrite -->

for test in test_cases: <!-- fcg-rewrite -->
    result = client.check_prompt(test) <!-- fcg-rewrite -->
    print(f"{test}: {result.overall_risk_level}") <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### 4. Use Application Scoping <!-- fcg-rewrite -->

Custom scanners are **application-specific**. Create different scanners for different applications: <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
# Banking app scanners <!-- fcg-rewrite -->
- S100: Bank Fraud Detection <!-- fcg-rewrite -->
- S101: Money Laundering Detection <!-- fcg-rewrite -->
- S102: Credit Card Fraud <!-- fcg-rewrite -->

# Healthcare app scanners <!-- fcg-rewrite -->
- S100: HIPAA Violation Detection <!-- fcg-rewrite -->
- S101: Medical Malpractice Advice <!-- fcg-rewrite -->
- S102: Prescription Drug Abuse <!-- fcg-rewrite -->

# E-commerce app scanners <!-- fcg-rewrite -->
- S100: Price Manipulation Detection <!-- fcg-rewrite -->
- S101: Fake Review Detection <!-- fcg-rewrite -->
- S102: Prohibited Product Detection <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### 5. Performance Considerations <!-- fcg-rewrite -->

- **GenAI scanners**: ~100-200ms each (run in parallel) <!-- fcg-rewrite -->
- **Regex/Keyword scanners**: <1ms each (negligible) <!-- fcg-rewrite -->
- **Total latency**: Typically <10% increase with custom scanners <!-- fcg-rewrite -->

**Optimization tips:** <!-- fcg-rewrite -->
- Use regex/keyword for simple patterns <!-- fcg-rewrite -->
- Combine multiple keywords into one scanner <!-- fcg-rewrite -->
- Disable scanners you don't need <!-- fcg-rewrite -->
- Use application scoping to limit active scanners <!-- fcg-rewrite -->

### 6. Risk Level Guidelines <!-- fcg-rewrite -->

**high_risk**: Violations require immediate blocking <!-- fcg-rewrite -->
- Security threats <!-- fcg-rewrite -->
- Legal violations <!-- fcg-rewrite -->
- Financial fraud <!-- fcg-rewrite -->
- Data breaches <!-- fcg-rewrite -->

**medium_risk**: Violations may require review or substitution <!-- fcg-rewrite -->
- Policy violations <!-- fcg-rewrite -->
- Inappropriate content <!-- fcg-rewrite -->
- Competitor mentions <!-- fcg-rewrite -->
- Off-topic content <!-- fcg-rewrite -->

**low_risk**: Violations for monitoring only <!-- fcg-rewrite -->
- Minor policy breaches <!-- fcg-rewrite -->
- Borderline cases <!-- fcg-rewrite -->
- Informational tracking <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Examples <!-- fcg-rewrite -->

### Example 1: Healthcare Compliance Scanner <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
    "scanner_type": "genai", <!-- fcg-rewrite -->
    "name": "HIPAA Violation Detection", <!-- fcg-rewrite -->
    "definition": """ <!-- fcg-rewrite -->
    Detect violations of HIPAA (Health Insurance Portability and Accountability Act): <!-- fcg-rewrite -->
    - Requests for patient medical records without authorization <!-- fcg-rewrite -->
    - Sharing of protected health information (PHI) without consent <!-- fcg-rewrite -->
    - Discussions of patient cases with identifying information <!-- fcg-rewrite -->
    - Unauthorized access to medical databases <!-- fcg-rewrite -->
    - Improper disclosure of health information <!-- fcg-rewrite -->

    Focus on privacy violations, not general medical discussions. <!-- fcg-rewrite -->
    """, <!-- fcg-rewrite -->
    "risk_level": "high_risk", <!-- fcg-rewrite -->
    "scan_prompt": True, <!-- fcg-rewrite -->
    "scan_response": True <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Example 2: Brand Competitor Monitor <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
    "scanner_type": "keyword", <!-- fcg-rewrite -->
    "name": "Competitor Brand Mentions", <!-- fcg-rewrite -->
    "keywords": "CompetitorA, CompetitorB, CompetitorC, RivalProduct, AlternativeSolution", <!-- fcg-rewrite -->
    "risk_level": "low_risk", <!-- fcg-rewrite -->
    "scan_prompt": False, <!-- fcg-rewrite -->
    "scan_response": True, <!-- fcg-rewrite -->
    "notes": "Monitor but don't block competitor mentions in responses" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Example 3: Internal Secret Detection <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
    "scanner_type": "regex", <!-- fcg-rewrite -->
    "name": "AWS Access Key Detection", <!-- fcg-rewrite -->
    "pattern": r"(AKIA[0-9A-Z]{16})", <!-- fcg-rewrite -->
    "risk_level": "high_risk", <!-- fcg-rewrite -->
    "scan_prompt": True, <!-- fcg-rewrite -->
    "scan_response": True, <!-- fcg-rewrite -->
    "notes": "Detect AWS access keys to prevent credential leakage" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Example 4: Financial Advice Compliance <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
    "scanner_type": "genai", <!-- fcg-rewrite -->
    "name": "Unlicensed Financial Advice", <!-- fcg-rewrite -->
    "definition": """ <!-- fcg-rewrite -->
    Detect providing specific investment advice, stock picks, or financial planning <!-- fcg-rewrite -->
    recommendations that should only come from licensed financial advisors: <!-- fcg-rewrite -->
    - Specific stock buy/sell recommendations <!-- fcg-rewrite -->
    - Portfolio allocation advice <!-- fcg-rewrite -->
    - Tax optimization strategies <!-- fcg-rewrite -->
    - Retirement planning recommendations <!-- fcg-rewrite -->

    Do NOT flag general financial education or publicly available information. <!-- fcg-rewrite -->
    """, <!-- fcg-rewrite -->
    "risk_level": "medium_risk", <!-- fcg-rewrite -->
    "scan_prompt": False, <!-- fcg-rewrite -->
    "scan_response": True <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Example 5: Off-Topic Detector <!-- fcg-rewrite -->

```python <!-- fcg-rewrite -->
{ <!-- fcg-rewrite -->
    "scanner_type": "genai", <!-- fcg-rewrite -->
    "name": "Customer Support Scope", <!-- fcg-rewrite -->
    "definition": """ <!-- fcg-rewrite -->
    This is a customer support chatbot for TechProduct Inc. Detect requests that are: <!-- fcg-rewrite -->
    - Completely unrelated to our products or services <!-- fcg-rewrite -->
    - Personal advice (relationship, health, legal) <!-- fcg-rewrite -->
    - Requests to perform tasks outside our product scope <!-- fcg-rewrite -->
    - Entertainment or general conversation <!-- fcg-rewrite -->

    Valid topics: Product features, troubleshooting, billing, account management. <!-- fcg-rewrite -->
    """, <!-- fcg-rewrite -->
    "risk_level": "low_risk", <!-- fcg-rewrite -->
    "scan_prompt": True, <!-- fcg-rewrite -->
    "scan_response": False <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Migration from Risk Types <!-- fcg-rewrite -->

### Automatic Migration <!-- fcg-rewrite -->

Existing S1-S21 risk type configurations are **automatically migrated** to the scanner package system on upgrade - no manual intervention required. <!-- fcg-rewrite -->

### Custom Scanner Tag Allocation <!-- fcg-rewrite -->

- **S1-S21**: Built-in official packages (pre-installed) <!-- fcg-rewrite -->
- **S22-S99**: Purchasable official packages (reserved) <!-- fcg-rewrite -->
- **S100+**: Custom user-defined scanners (auto-assigned) <!-- fcg-rewrite -->

When you create a custom scanner, tags are automatically assigned: <!-- fcg-rewrite -->
- First custom scanner: S100 <!-- fcg-rewrite -->
- Second custom scanner: S101 <!-- fcg-rewrite -->
- And so on... <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Management Interface <!-- fcg-rewrite -->

### Web UI Pages <!-- fcg-rewrite -->

- **Official Scanners** (`/platform/config/official-scanners`): <!-- fcg-rewrite -->
  - View and configure S1-S21 built-in packages <!-- fcg-rewrite -->
  - Enable/disable official scanners <!-- fcg-rewrite -->
  - Adjust risk levels <!-- fcg-rewrite -->

- **Custom Scanners** (`/platform/config/custom-scanners`): <!-- fcg-rewrite -->
  - Create new custom scanners <!-- fcg-rewrite -->
  - Edit existing custom scanners <!-- fcg-rewrite -->
  - Enable/disable per application <!-- fcg-rewrite -->

- **Admin Marketplace** (`/platform/admin/package-marketplace`): <!-- fcg-rewrite -->
  - Upload purchasable packages (admin only) <!-- fcg-rewrite -->
  - Manage commercial scanner packages <!-- fcg-rewrite -->
  - Approve purchase requests <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## API Reference <!-- fcg-rewrite -->

### Create Custom Scanner <!-- fcg-rewrite -->

```http <!-- fcg-rewrite -->
POST /api/v1/custom-scanners <!-- fcg-rewrite -->
Authorization: Bearer {jwt-token} <!-- fcg-rewrite -->
Content-Type: application/json <!-- fcg-rewrite -->

{ <!-- fcg-rewrite -->
  "scanner_type": "genai|regex|keyword", <!-- fcg-rewrite -->
  "name": "string", <!-- fcg-rewrite -->
  "definition": "string (for genai)", <!-- fcg-rewrite -->
  "pattern": "string (for regex)", <!-- fcg-rewrite -->
  "keywords": "string (for keyword, comma-separated)", <!-- fcg-rewrite -->
  "risk_level": "high_risk|medium_risk|low_risk", <!-- fcg-rewrite -->
  "scan_prompt": true|false, <!-- fcg-rewrite -->
  "scan_response": true|false, <!-- fcg-rewrite -->
  "notes": "string (optional)" <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### List Custom Scanners <!-- fcg-rewrite -->

```http <!-- fcg-rewrite -->
GET /api/v1/custom-scanners?application_id={app_id} <!-- fcg-rewrite -->
Authorization: Bearer {jwt-token} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Update Custom Scanner <!-- fcg-rewrite -->

```http <!-- fcg-rewrite -->
PUT /api/v1/custom-scanners/{scanner_id} <!-- fcg-rewrite -->
Authorization: Bearer {jwt-token} <!-- fcg-rewrite -->
Content-Type: application/json <!-- fcg-rewrite -->

{ <!-- fcg-rewrite -->
  "enabled": true|false, <!-- fcg-rewrite -->
  "risk_level": "high_risk|medium_risk|low_risk", <!-- fcg-rewrite -->
  "scan_prompt": true|false, <!-- fcg-rewrite -->
  "scan_response": true|false <!-- fcg-rewrite -->
} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

### Delete Custom Scanner <!-- fcg-rewrite -->

```http <!-- fcg-rewrite -->
DELETE /api/v1/custom-scanners/{scanner_id} <!-- fcg-rewrite -->
Authorization: Bearer {jwt-token} <!-- fcg-rewrite -->
``` <!-- fcg-rewrite -->

--- <!-- fcg-rewrite -->

## Next Steps <!-- fcg-rewrite -->

- [Deployment Guide](../getting-started/DEPLOYMENT.md) <!-- fcg-rewrite -->
