# Basic Guard Overview

## 1. Background

As large language models are widely adopted across industries, AI systems face an increasing number of content safety risks, including:

- Users attempting to bypass safety restrictions via prompt injection attacks
- After successful prompt attacks, LLMs leaking system prompts or internal instructions in outputs
- Models generating violent, pornographic, hateful, or other harmful content
- Sensitive information such as ID numbers, credit card numbers appearing in user inputs or model outputs (data leakage)
- In streaming output scenarios, malicious content cannot be detected in real time during token-by-token transmission
- Malicious users repeatedly sending high-risk requests, consuming system resources

Basic Guard is Fangcun Guard's foundational safety plugin, providing comprehensive baseline protection from content safety detection and data leakage prevention to streaming output auditing. It serves as the front layer for all other safety plugins — every request passes through Basic Guard's detection first.

## 2. Technical Overview

Basic Guard's capabilities are divided into two parts: the **Core Detection System** (running in the Fangcun Guard main service) and **Streaming Output Safety Detection** (running in the basic_guard plugin hooks).

### 2.1 Core Detection System

The core detection system is provided by the Fangcun Guard main service and includes the following five capabilities:

- **Content Safety Detection**: Uses a safety model to classify input and output text across 21 risk categories (S1–S21), supporting 119 languages. Risks are handled at three severity levels:
  - High Risk (auto-block): Sensitive political topics (S2), insulting national symbols (S3), violent crime (S5), prompt attacks (S9), weapons of mass destruction (S15), sexual crimes (S17) — 6 categories.
  - Medium Risk (configurable): Harm to minors (S4), non-violent crime (S6), pornographic content (S7), self-harm/suicide (S16) — 4 categories.
  - Low Risk (pass by default): General political topics (S1), hate/discrimination (S8), profanity (S10), privacy violations (S11), commercial violations (S12), IP infringement (S13), harassment (S14), threats (S18), professional financial advice (S19), professional medical advice (S20), professional legal advice (S21) — 11 categories.
  - For long texts, sliding window detection is used (default window: 7168 tokens, 20% overlap), with all windows running in parallel — a match in any window triggers detection.

- **Data Leakage Prevention (DLP)**: Automatically identifies sensitive entities such as ID numbers, credit card numbers, phone numbers, and email addresses. Supports two identification methods: regex matching (for formatted data) and GenAI entity recognition (for sensitive information in natural language). The system automatically detects the input text format (JSON, YAML, CSV, Markdown) and segments intelligently by format structure (each segment ≤ 4000 characters) to avoid breaking data structures during splitting. Five handling strategies are available:
  - Block: Reject the request outright.
  - Anonymize: Replace sensitive information with placeholders (e.g., `John Smith` → `[PERSON]`).
  - Reversible Anonymize: Replace with numbered placeholders (e.g., `John Smith` → `[PERSON_1]`), automatically restored in output.
  - Switch to Private Model: Automatically forward the request to an enterprise private model.
  - Log Only (pass): No intervention, audit log only.

- **Blocklist/Allowlist**: Fast keyword-based filtering. Allowlist matches pass immediately (skipping all subsequent detection); blocklist matches are blocked. Runs in memory cache with latency under 1 millisecond.

- **Ban Policy**: When a user or IP triggers high-risk detection multiple times within a specified time window, they are automatically banned. Trigger threshold, time window, and ban duration are all configurable.

- **Response Templates/Knowledge Base**: Provides customized safety guidance responses for blocked scenarios. The knowledge base supports FAISS-based vector similarity matching, returning the most relevant safety guidance based on user input content.

### 2.2 Streaming Output Safety Detection

Streaming output detection is provided by the basic_guard plugin, using hooks to perform safety auditing on the complete output after streaming transmission finishes. It includes three parallel detection engines:

- **Content Pattern Engine**: Uses 4 regex patterns to detect output safety anomalies, including system prompt leakage ("my system prompt is", etc.), jailbreak mode activation ("DAN enabled", etc.), instruction override confirmation ("ignoring previous instructions", etc.), and encoded obfuscation output (base64/hex/rot13 followed by large character blocks).

- **Reasoning Deviation Engine**: Uses 3 regex patterns to detect abnormal deviations in the model's chain of thought (CoT), including intent reinterpretation ("the user actually wants", etc.), safety bypass reasoning ("I should ignore", etc.), and role-play deviation ("pretend", "act as if", etc.).

- **Output Anomaly Engine**: Uses a 50-character sliding window to detect repetitive loop patterns in output. When the repetition rate exceeds the threshold (default 40%), it is flagged as anomalous.

All three engines run in parallel with a total detection latency under 5 milliseconds.
