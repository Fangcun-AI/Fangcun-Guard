# MCP 服务器安全扫描（MCP Scanner）

## 这是什么

对 AI 应用连接的 MCP（Model Context Protocol）服务器进行 **部署前 / 按需** 安全审计的插件。扫描 MCP 服务器暴露的提示词模板、资源、服务器指令以及跨服务器信任边界，发现 Skill Scanner 和 Agent Safety 无法覆盖的 MCP 协议特有威胁。

## 定位：与其他插件零重叠

| 插件 | 职责 | 触发时机 |
|------|------|----------|
| **Skill Scanner** | 扫描所有 tool 定义（通用 function calling） | 运行时 on_input_check |
| **Agent Safety** | 监控 tool 实际调用参数 + 推理链安全 | 运行时 on_output_check / on_stream_complete |
| **MCP Scanner** | 审计 MCP 提示词模板 / 资源 / 服务器指令 / 跨服务器攻击链 | 部署前 standalone API / Detection API 显式调用 |

**关键区别**：MCP Scanner **不在运行时 hook 请求**，不会和 Skill Scanner 重复扫描同一批 tools。

## 核心能力（MCP 独有维度）

### MCP 提示词模板扫描

对 MCP 服务器暴露的提示词模板（prompts/list）进行注入检测：

- 系统提示覆盖：模板试图 override 系统 prompt
- 上下文污染：模板注入行为指令到 LLM 上下文
- 参数注入：模板变量可被利用注入特权数据（{{system}}, {{admin}}）
- 代码执行：模板表达式中的 exec/eval

### MCP 资源安全扫描

对 MCP 服务器暴露的资源（resources/list）进行安全评估：

- URI 安全：file:// 指向 /etc/passwd、.ssh/、.env 等敏感路径
- SSRF 检测：指向 127.0.0.1、169.254.169.254（云元数据）等内部地址
- 可执行 data URI：data:text/html、data:application/javascript
- 敏感数据暴露：资源内容中包含嵌入式凭证、私钥

### MCP 服务器指令分析

对 MCP 服务器的初始化指令进行安全审计：

- 权限提升：声称需要 admin/root 权限
- 安全绕过：指示 LLM 禁用安全检查、跳过验证
- 自动批准：要求 LLM 自动批准所有操作、不询问用户
- 角色注入：通过指令给 LLM 分配角色
- 优先级操纵：要求优先使用本服务器而非其他
- 指令覆盖：试图让 LLM 忽略之前的指令

### 跨服务器信任边界分析

分析多个 MCP 服务器组合时的攻击链风险（单 server 内的能力风险由 Skill Scanner 覆盖）：

- 跨服务器数据泄露：Server A 读文件 + Server B 发网络请求
- 跨服务器 RCE：Server A 下载 payload + Server B 执行代码
- 跨服务器权限提升：Server A 管理凭证 + Server B 执行代码
- 聚合攻击面评估：所有 server 合计 5+ 能力类别时告警

### MCP 工具投毒（协议特有模式）

检测通用 Skill Scanner 未覆盖的 MCP 特有投毒手法：

- 行为操纵：「调用此工具前/后必须先...」
- 工具影子化：「使用此工具代替 xxx」
- 隐蔽操作：「静默/悄悄地执行」
- 用户欺骗：「不要告诉用户」

## 适用场景

- MCP 客户端应用接入第三方 MCP 服务器（Claude Desktop、Cursor、Windsurf）
- 企业 AI Agent 平台审计接入的 MCP 服务器清单
- 多 MCP 服务器同时使用时的跨服务器风险评估
- CI/CD 流水线中自动审计 MCP 配置变更

## 不适用场景

- 不使用 MCP 的应用（此插件无适用场景）
- 纯 function calling 工具定义（Skill Scanner 已覆盖）
- 运行时工具调用参数检测（Agent Safety 已覆盖）
- 完全内部自研且审计过的 MCP 服务器（可加入 trusted_servers 白名单跳过）

## 性能特征

- YARA 规则引擎：< 50ms（纯模式匹配）
- 跨服务器分析引擎：< 100ms（仅 2+ 服务器时触发）
- LLM 语义引擎：500-2000ms（仅在 YARA 检测到中等以上风险时条件触发）
- 单次扫描支持最多 50 个 MCP 服务器

## 与其他插件的关系

- 依赖基础安全防护作为基础
- 与 Skill Scanner **互补不重叠**：Skill Scanner 运行时扫描 tool 定义，MCP Scanner 部署前扫描 MCP 独有构件（prompts/resources/instructions）
- 与 Agent Safety **互补不重叠**：Agent Safety 运行时监控实际调用，MCP Scanner 部署前审计服务器声明
- 与幻觉检测无直接关联
