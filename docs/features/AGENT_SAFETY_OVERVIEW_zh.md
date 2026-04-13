# Agent Safety 概述

## 1. 项目背景

AI Agent 通过 function calling 调用外部工具完成任务，但这个过程中存在多种安全风险：

- 攻击者通过工具调用参数注入恶意命令（如 Shell 注入、SQL 注入、SSRF）
- Agent 调用未经授权的危险工具（如 execute_shell、eval_code）
- Agent 的推理链（Chain of Thought）被劫持，偏离用户的原始意图
- 攻击者利用工具定义中的漏洞，构造跨工具攻击链
- Agent 被操纵频繁调用工具，消耗资源或放大攻击效果

Agent Safety 提供三层运行时防御，覆盖工具定义审计、工具调用监控和推理链安全审计三个阶段，形成从"工具长什么样"到"工具怎么被用"到"Agent 怎么想"的完整防护链。

## 2. 技术现状

Agent Safety 采用三层检测架构，分别在请求的不同阶段执行。

### 2.1 第一层：工具定义验证（on_input_check）

当请求中包含工具定义时，首先进行工具名的白名单/黑名单校验：
- 如果配置了白名单（tool_whitelist），不在白名单中的工具将被拦截。
- 如果配置了黑名单（tool_blacklist），命中黑名单的工具将被拦截。
- 检查顺序：白名单 → 黑名单 → 放行。

通过白名单/黑名单校验后，如果启用了工具定义安全扫描（enable_tool_definition_scan），系统会复用 Skill Scanner 的三个静态引擎对 JSON 格式的工具定义进行并行扫描：
- 静态模式引擎：31 条正则检测提示注入、命令注入、数据泄露等 6 类威胁。
- 结构验证引擎：校验 JSON Schema 合规性、参数约束完整性、危险工具名称。
- 能力风险引擎：8 类能力域分类 + 5 种跨工具攻击链检测。

### 2.2 第二层：工具调用监控（on_output_check）

当 LLM 返回的响应中包含 tool_calls 时，执行以下检查：

- **工具名校验**：再次检查白名单/黑名单，防止 LLM 调用未授权的工具。

- **调用频率限制**：
  - 单次请求限制：默认最多 20 次工具调用（可配置 0-1000），超出标记为 excessive_tool_calls。
  - 跨请求滑动窗口：在 60 秒窗口内跟踪调用频率，上限为单次限制的 5 倍或 100（取较大值）。超出标记为 high_frequency_tool_calls。过期记录在 300 秒后自动清理。

- **参数注入检测**：使用 19 条内置正则表达式检测工具调用参数中的注入攻击，覆盖 8 类注入：
  - Shell 命令注入（4 条）：分号命令链（`;rm`）、反引号执行、$() 子shell、路径遍历（`../../`）和敏感文件路径（`/etc/passwd`）。
  - Python 代码注入（5 条）：危险模块导入（os/subprocess/shutil）、eval()、exec()、\_\_import\_\_()、os.system/os.popen/subprocess 调用。
  - SQL 注入（2 条）：破坏性 DDL/DML（DROP TABLE/DELETE FROM/TRUNCATE）、布尔注入和 UNION SELECT。
  - XSS 注入（1 条）：`<script>` 标签和 `javascript:` 协议。
  - SSRF（2 条）：云元数据端点（169.254.169.254、metadata.google.internal 等）和内网 IP 地址（127.0.0.1、10.x.x.x、192.168.x.x 等）。
  - NoSQL 注入（1 条）：MongoDB 操作符（$gt/$ne/$where/$regex 等）。
  - LDAP 注入（1 条）：LDAP 过滤器语法注入。
  - XXE 注入（1 条）：XML 实体声明（<!ENTITY）、DOCTYPE SYSTEM、CDATA。
  - 环境变量泄露（1 条）：process.env、os.environ、getenv() 等。
  - 此外，用户可通过策略配置自定义正则表达式，扩展检测能力。

### 2.3 第三层：推理链安全审计（on_stream_complete）

当模型的输出包含推理链（reasoning_content）时，使用 GenAI 安全模型对推理过程进行审计。审计维度包括：
- 目标劫持（goal_hijacking）：推理是否偏离用户的原始意图。
- 注入影响（injection_influence）：推理是否受到提示注入的影响。
- 对齐偏离（alignment_issue）：推理是否规划了有害或未授权的操作。
- 数据窃取意图（data_exfiltration）：推理是否计划收集或泄露敏感信息。

推理链审计需要外部模型 API 支持，推理内容截取前 2000 字符、用户消息截取前 500 字符进行分析，延迟约 100-500 毫秒。
