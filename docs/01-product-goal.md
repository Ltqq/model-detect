# 产品目标与边界

## 1. 产品定位

model-detect 是一套面向 **AI 中转站、模型聚合平台、模型供应商准入、渠道验收** 的 LLM API 审计系统。

它不是传统 benchmark 平台，也不是性能压测平台。

它的核心价值是：

> 在接入一个未知或不完全可信的模型 Endpoint 前，用黑盒方式判断“它是谁、它支持什么、它有没有偷偷改东西、它是否达到声明能力”。

典型业务场景：

- 上游供应商声称提供 Kimi K3，实际是否真的是同一模型族？
- 客户检测到 `FW-Kimi-K3 + Azure APIM`，我们能否在客户之前发现类似上游指纹？
- 某上游声称支持 `reasoning_effort`，参数是真生效还是被静默忽略？
- 官方错误字段应该报 400，但供应商却返回 200，是否存在协议转换或字段吞掉？
- Tool Calling / JSON Schema / Streaming 是否和官方行为一致？
- 32K / 64K / 128K 上下文是不是名义支持，实际被截断？
- 同一个 model id 是否在不同请求中混合路由到不同模型？
- 是否存在 system prompt 注入、max_tokens 被缩小、reasoning 被降档、工具被移除等中转层篡改？

---

## 2. 产品最终要回答的 5 个问题

### Q1. 模型身份是否一致？

不是简单问模型“你是谁”，而是组合多类证据：

- 行为统计指纹
- Knowledge Boundary / 知识边界
- 模型特有能力与参数行为
- 响应字段与错误行为
- 重复采样稳定性
- 官方 Reference 对比

输出：

- `MATCH`
- `UNCERTAIN`
- `MISMATCH`
- `INSUFFICIENT`

并给出置信度与证据。

### Q2. Provider / Gateway 是谁？

通过以下信息判断可能的上游链路：

- HTTP Response Headers
- request-id / trace-id 格式
- response id 格式
- model 字段
- error body
- SSE chunk 形态
- HTTP 状态码与错误结构
- TLS / Server / APIM / CDN 特征（可选）
- Provider 特有参数接受/拒绝模式

输出示例：

```text
Provider hypothesis:
  Fireworks      high confidence
  Azure APIM     medium/high confidence

Evidence:
  x-ms-request-id
  apim-* header
  FW-Kimi-K3 model alias
  Fireworks-style error schema
```

注意：这里只能输出“证据支持的推测”，不能把启发式识别包装成绝对事实。

### Q3. API 协议与模型能力是否兑现？

重点验证：

- Chat Completions
- Responses
- Anthropic Messages（后续）
- Streaming SSE
- usage
- finish_reason / stop_reason
- tools
- tool_choice
- parallel tool calls
- JSON mode
- JSON Schema
- system message
- reasoning / thinking
- temperature / top_p
- max_tokens
- 参数非法值错误
- 未知参数错误
- 多轮上下文

这类测试尤其适合发现“中转转换层”和“官方模型”之间的行为差异。

### Q4. 中转层有没有篡改或降级？

检测：

- max_tokens 被截断
- reasoning_effort 被静默降级
- temperature 被锁死
- tool definitions 被丢弃
- system prompt 注入
- content 被修改
- context 被提前截断
- 某些参数被静默忽略

### Q5. 能力表现是否达到模型应有水平？

V1 做 **轻量能力验证**，不是追求完整排行榜。

维度建议：

- Reasoning / 推理
- Coding / 代码
- Math / 数学
- Chinese / 中文
- Instruction Following / 指令遵循
- Tool Use / 工具使用
- Structured Output / 结构化输出
- Long Context / 长上下文

目标是：

> 判断“这个 Endpoint 的能力画像是否与声明模型大体一致，以及是否满足平台准入要求”。

而不是追求跑完所有公开 benchmark。

---

## 3. 产品边界

### V1 明确不做

性能压测独立存在，不集成：

- TTFT
- ITL / TPOT
- TPS
- RPM / TPM
- 吞吐
- 大并发
- 峰值容量
- 429 压力曲线
- GPU 利用率

原因：

1. 已有现成脚本；
2. 性能和模型身份是两个问题；
3. 避免 model-detect 变成大而全平台。

### 当前产品明确不做

- 图像 / 视频生成模型真实性
- Embedding / Rerank 深度检测
- Agent 长周期 benchmark
- 安全红队
- 多租户 SaaS
- 登录 / RBAC / Team
- PostgreSQL / Redis / 分布式 Worker
- Saved Endpoint 管理平台
- Scheduler / 定时巡检
- 自动通知 / Webhook / 告警中心
- 商业计费

当前定位是**单机、单用户、自用工具**。这些能力不是“暂时没做”，而是没有真实需求前不进入产品路线，避免项目变重。

---

## 4. 用户角色

当前主要用户就是工具维护者本人。

典型使用方式：

- 新供应商 / 新渠道上线前做一次准入审计；
- 客户反馈某个模型协议问题时复现并固化 Regression Case；
- 需要时重新打开历史报告查看 Evidence；
- 不承担多人协作、权限管理、任务分发。

---

## 5. 最终产品形态

### 输入

```text
Base URL
API Key
Claimed Model
Profile
Optional Trusted Reference
Optional Regression Suites
```

### 输出与历史

```text
HTML Report
JSON Report
ZIP Artifacts
SQLite History
```

历史记录只需要支持：查看、筛选、重新打开报告、下载 JSON/ZIP、删除。

### 三种检测模式

#### Quick

预计几十个请求。

用途：

- 上游初筛
- 快速发现明显假模型
- 检查协议基础能力
- Provider 指纹

包含：

- Response / Error fingerprint
- API feature probe
- Parameter integrity
- 少量 identity probe

#### Standard

默认模式。

包含：

- Quick 全部
- Statistical fingerprint
- Context integrity
- Tool / JSON / Reasoning
- 混合路由基础检测
- 轻量能力集

#### Deep

用于重要供应商准入。

包含：

- Standard 全部
- 更高采样量 statistical fingerprint
- 官方 Reference 对照
- 重复路由检测
- 扩大能力集
- 更严格上下文验证

---

## 6. 评分原则

不建议只显示一个“总分”。

必须同时展示几个独立维度：

```text
Identity Confidence        模型身份一致性
Protocol Compatibility     协议兼容性
Parameter Integrity        参数完整性
Capability                 能力表现
Context Integrity          上下文完整性
Routing Stability          路由一致性
Provider Fingerprint       上游识别（不计分）
```

### 总分可以有，但必须有 Hard Cap

例如：

- 明确模型身份 mismatch -> 总分最高 40
- 高置信混合路由 -> 总分最高 60
- 核心协议不兼容 -> 总分最高 60
- 证据不足 -> 不给高分，只显示 insufficient

这样避免：

> “模型是假货，但数学和代码题做得不错，所以综合 85 分”

这种无意义结果。

---

## 7. 产品成功标准

V1 成功不是“有漂亮 UI”，而是至少能复现以下真实业务问题：

1. 能发现 Provider / Gateway 痕迹；
2. 能发现非法字段被错误接受；
3. 能发现 reasoning 参数支持差异；
4. 能发现 Tool Calling / JSON 行为差异；
5. 能发现 context truncation；
6. 能用统计指纹给出 match / uncertain / mismatch；
7. 能识别一定程度的 mixed routing；
8. 所有结果有 Raw Evidence；
9. 同一 Endpoint 重跑结果大体稳定；
10. 可以维护官方 Reference 库。

---

## 8. 产品一句话定义

> **model-detect = 面向 LLM API 中转与供应商准入的黑盒真实性、协议完整性和能力审计平台。**

