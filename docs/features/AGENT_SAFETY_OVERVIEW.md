# Agent Safety Overview

## 1. Background

AI Agents use function calling to invoke external tools to complete tasks, but this process introduces multiple security risks:

- Attackers inject malicious commands through tool call parameters (e.g., shell injection, SQL injection, SSRF)
- Agents invoke unauthorized dangerous tools (e.g., execute_shell, eval_code)
- The Agent's chain of thought (CoT) gets hijacked, deviating from the user's original intent
- Attackers exploit vulnerabilities in tool definitions to construct cross-tool attack chains
- Agents are manipulated into calling tools excessively, consuming resources or amplifying attack effects

Agent Safety provides three layers of runtime defense, covering tool definition auditing, tool call monitoring, and reasoning chain security auditing — forming a complete protection chain from "what tools look like" to "how tools are used" to "how the Agent thinks."

## 2. Technical Overview

Agent Safety uses a three-layer detection architecture, executing at different stages of a request.

### 2.1 Layer 1: Tool Definition Validation (on_input_check)

When a request contains tool definitions, tool name allowlist/blocklist validation is performed first:
- If an allowlist (tool_whitelist) is configured, tools not on the allowlist are blocked.
- If a blocklist (tool_blacklist) is configured, tools matching the blocklist are blocked.
- Check order: allowlist → blocklist → pass.

After passing allowlist/blocklist validation, if tool definition scanning is enabled (enable_tool_definition_scan), the system reuses Skill Scanner's three static engines to scan JSON-formatted tool definitions in parallel:
- Static Pattern Engine: 31 regex rules detecting 6 threat categories including prompt injection, command injection, and data leakage.
- Structure Validation Engine: Validates JSON Schema compliance, parameter constraint completeness, and dangerous tool names.
- Capability Risk Engine: 8 capability domain classifications + 5 cross-tool attack chain detections.

### 2.2 Layer 2: Tool Call Monitoring (on_output_check)

When the LLM's response contains tool_calls, the following checks are performed:

- **Tool Name Validation**: Re-checks allowlist/blocklist to prevent the LLM from calling unauthorized tools.

- **Call Frequency Limiting**:
  - Per-request limit: Default maximum of 20 tool calls (configurable 0–1000); exceeding this is flagged as excessive_tool_calls.
  - Cross-request sliding window: Tracks call frequency within a 60-second window, with an upper limit of 5× the per-request limit or 100 (whichever is greater). Exceeding this is flagged as high_frequency_tool_calls. Expired records are automatically cleaned up after 300 seconds.

- **Parameter Injection Detection**: Uses 19 built-in regex patterns to detect injection attacks in tool call parameters, covering 8 injection categories:
  - Shell Command Injection (4 rules): Semicolon command chaining (`;rm`), backtick execution, $() subshell, path traversal (`../../`), and sensitive file paths (`/etc/passwd`).
  - Python Code Injection (5 rules): Dangerous module imports (os/subprocess/shutil), eval(), exec(), \_\_import\_\_(), os.system/os.popen/subprocess calls.
  - SQL Injection (2 rules): Destructive DDL/DML (DROP TABLE/DELETE FROM/TRUNCATE), boolean injection, and UNION SELECT.
  - XSS Injection (1 rule): `<script>` tags and `javascript:` protocol.
  - SSRF (2 rules): Cloud metadata endpoints (169.254.169.254, metadata.google.internal, etc.) and internal IP addresses (127.0.0.1, 10.x.x.x, 192.168.x.x, etc.).
  - NoSQL Injection (1 rule): MongoDB operators ($gt/$ne/$where/$regex, etc.).
  - LDAP Injection (1 rule): LDAP filter syntax injection.
  - XXE Injection (1 rule): XML entity declarations (<!ENTITY), DOCTYPE SYSTEM, CDATA.
  - Environment Variable Leakage (1 rule): process.env, os.environ, getenv(), etc.
  - Additionally, users can define custom regex patterns via policy configuration to extend detection capabilities.

### 2.3 Layer 3: Reasoning Chain Security Audit (on_stream_complete)

When the model's output contains reasoning content (reasoning_content), a GenAI safety model is used to audit the reasoning process. Audit dimensions include:
- Goal Hijacking: Whether reasoning deviates from the user's original intent.
- Injection Influence: Whether reasoning is influenced by prompt injection.
- Alignment Deviation: Whether reasoning plans harmful or unauthorized actions.
- Data Exfiltration Intent: Whether reasoning plans to collect or leak sensitive information.

Reasoning chain auditing requires an external model API. The first 2000 characters of reasoning content and the first 500 characters of user messages are analyzed, with latency of approximately 100–500 milliseconds.
