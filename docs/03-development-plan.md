# 开发计划与路线图

> 本文从 2026-09-30 起作为 model-detect 的主开发计划。  
> 旧文档中“建议做什么”的内容以本文件状态为准。

## 1. 当前状态

### V1 主链：已完成

- [x] CLI
- [x] FastAPI Web
- [x] Unified Probe Result
- [x] Raw Evidence
- [x] API Key 脱敏
- [x] JSON / HTML Report
- [x] Provider Fingerprint
- [x] OpenAI-compatible Protocol Probe
- [x] Reasoning / Thinking
- [x] Tool Calling
- [x] JSON Mode / JSON Schema
- [x] Parameter Integrity 基础版
- [x] Context Needle
- [x] Mixed Routing 基础版
- [x] Capability Lite
- [x] Score / Hard Cap
- [x] Trusted Reference Registry
- [x] llm-fingerprint-detector Adapter
- [x] proxy-sleuth Adapter
- [x] SQLite Job History
- [x] Web Reference 管理
- [x] Report ZIP
- [x] Report Drift Compare
- [x] CI / Wheel Package Check

### 明确排除

- [ ] 性能测试集成 —— **不做**

TTFT / ITL / TPS / RPM / TPM / 吞吐 / 并发 / 429 压测继续由独立工具负责。

---

# 2. 下一阶段：V1.1 完整审计

目标：

> 补齐之前规划但 V1 只做了基础版的真实性、完整性、路由与能力检测，使 Deep Audit 真正适合供应商正式准入。

优先级按 P0 → P1 → P2。

---

## P0-A：Fingerprint 深化 ✅

完成于 V1.1-1。实现设计见 `docs/design/07-fingerprint-deepening.md`。

### 目标

让“模型真实性”从当前 verdict + mean JSD，升级为可解释的统计证据。

### 任务

- [x] 解析 per-cell JSD
- [x] split-half JSD
- [x] identity.self_consistency
- [x] Reference fingerprint metadata/version
- [x] 显示 fingerprint cell 明细
- [x] 在 HTML/Web 展示 fingerprint evidence
- [x] fingerprint consistency 纳入 routing
- [x] 支持 bundled reference 导入与来源标识

### 验收

同一个可信 Endpoint 重复采样：

- self-consistency 稳定
- Reference verify 大体稳定

明显不同模型：

- 能给出可解释 mismatch/uncertain
- 报告能看到导致差异的 cell

---

## P0-B：Parameter Integrity 补齐 ✅

完成于 V1.1-2。判定设计见 `docs/design/08-integrity-probes.md`。

当前已有：

- reasoning effect
- max_tokens
- stop
- sampling controls

继续补：

- [x] `integrity.system_prompt`
- [x] `integrity.tools.preserved`
- [x] `integrity.tool_definitions`
- [x] `integrity.json_schema.preserved`
- [x] `integrity.temperature`
- [x] `integrity.top_p`

### 设计原则

不能只判断“HTTP 200”。

例如 Tool Definition Preservation 要比较：

```text
发送给中转的 schema
    ↓
模型实际 tool call 行为
    ↓
多组边界输入
    ↓
判断是否存在字段丢失/改写
```

System Prompt Injection 使用可复现 challenge set，不以“模型说自己有 system prompt”作为证据。

---

## P0-C：Mixed Routing 深化 ✅

完成于 V1.1-3。设计见 `docs/design/09-mixed-routing.md`。

当前已有：

- repeated request
- model field drift
- response schema drift
- ID prefix drift
- quality inversion

继续补：

- [x] `routing.fingerprint.consistency`
- [x] `routing.fact_inversion`
- [x] `routing.cluster`
- [x] 多时间窗口采样
- [x] 简单题 / 复杂题分层
- [x] Reference fingerprint cluster 对比

### 第一版聚类

不要先上重 ML。

先使用可解释 feature：

- response model
- response id prefix
- schema signature
- tool-call style
- reasoning metadata
- fingerprint distance
- deterministic answer consistency

再做简单聚类/分桶。

---

## P0-D：Coding 执行评测 ✅

完成于 V1.1-4。安全设计见 `docs/design/10-coding-sandbox.md`。

当前 Coding Lite 仍保留代码理解题，同时新增 Docker 隔离的 Python/Go 可执行代码生成评测。

目标：

```text
Prompt
  ↓
Model generates code
  ↓
Extract code
  ↓
Sandbox
  ↓
Unit tests
  ↓
Capability score
```

### 技术方案

首选 Docker sandbox：

- [x] 无网络
- [x] CPU 限制
- [x] 内存限制
- [x] 超时
- [x] 只读基础文件系统
- [x] 临时工作目录
- [x] 禁止宿主目录挂载

首批语言：

- Python
- Go

首批规模：

- Standard：每种 2–3 题
- Deep：每种 5–10 题

不自己造大型 benchmark，题目优先来自许可证允许的公开 task 或自建小题。

---

# 3. P1：能力评测体系增强

## Capability Dataset

当前 85 题（Reasoning 20、Math 20、Chinese 20、Instruction Following 20、Coding Reasoning 5）。

目标：

- [x] Reasoning 20+
- [x] Math 20+
- [x] Coding execute 10+
- [x] Chinese 20+
- [x] Instruction Following 20+
- [ ] Tool Use 场景化
- [ ] Structured Output 场景化

预计 Deep 总量控制在 80–150 个低成本任务，不做几千题排行榜。

## lm-evaluation-harness Adapter

- [ ] API Endpoint 调通
- [ ] 选择少量 task
- [ ] 统一结果格式
- [ ] 不重复运行 Capability Lite 已覆盖内容
- [ ] 可配置 benchmark profile

用途：

> 给 Capability 分数提供外部公开 benchmark 参照，而不是替代 model-detect 自有准入 Probe。

## promptfoo Adapter

- [ ] 自定义 HTTP Provider
- [ ] YAML Test Case
- [ ] JSON Schema assertions
- [ ] Tool Call assertions
- [ ] Repeat assertions
- [ ] Custom Python/JS assert
- [ ] 结果映射 Unified Probe Result

用途：

> 把客户临时提出的协议问题快速沉淀成 declarative regression probe。

例如 Kimi K3：

```text
错误 reasoning 字段
thinking 限制
特定 tool schema
特殊返回字段
```

不需要每次改 Python 主程序。

---

# 4. P1：模型 / Provider 知识库

## 模型规则库

当前：

- default
- kimi-k3

继续增加时遵循“有证据才写”：

- [ ] GLM 系列
- [ ] Qwen 系列
- [ ] DeepSeek 系列
- [ ] Claude 系列
- [ ] GPT 系列
- [ ] Gemini 系列

每条规则记录：

- 来源
- 适用版本
- collected_at
- 官方 / Reference / empirical
- expected behavior
- strict / non-strict

## Provider Fingerprint DB

继续扩：

- header
- error schema
- ID format
- model alias
- SSE format
- Gateway 特征

同时增加：

- [ ] rule version
- [ ] evidence source
- [ ] false-positive notes
- [ ] confidence calibration

---

# 5. P1：多协议原生支持

## OpenAI-compatible

继续作为主协议。

## Anthropic Native Adapter

- [ ] `/v1/messages`
- [ ] stream event
- [ ] usage
- [ ] tool_use
- [ ] thinking
- [ ] stop_reason
- [ ] invalid parameter behavior
- [ ] Evidence normalization

## Gemini Native Adapter

- [ ] generateContent
- [ ] streamGenerateContent
- [ ] function calling
- [ ] structured output
- [ ] thinking / reasoning fields
- [ ] invalid parameter behavior
- [ ] Evidence normalization

## Protocol abstraction

避免在 Probe 内写大量：

```text
if openai ...
elif anthropic ...
elif gemini ...
```

目标抽象：

```text
ProtocolClient
  ├─ OpenAIClient
  ├─ AnthropicClient
  └─ GeminiClient
```

Probe 使用统一 capability interface。

---

# 6. P1：Web 与 Drift

## Web

- [ ] Protocol selector
- [ ] Probe 明细筛选
- [ ] Evidence Drawer
- [ ] Category 图表
- [ ] Fingerprint 明细
- [ ] Reference Detail
- [ ] Compare 两次 Report

## 自动重测

- [ ] Saved Endpoint
- [ ] Schedule
- [ ] 周期性 Standard Audit
- [ ] Reference drift
- [ ] Provider drift
- [ ] Probe regression
- [ ] 通知接口

V1.1 先做本地 scheduler 即可，不上 Redis。

## 历史趋势

趋势数据：

- overall score
- category scores
- provider hypothesis
- fingerprint distance
- routing verdict
- selected probes

目标是看变化，不做性能 Dashboard。

---

# 7. P2：生产化 V2

只有多人正式使用后再做。

## 存储

SQLite → PostgreSQL：

- audit_job
- endpoint
- reference
- probe_result
- evidence metadata
- drift event
- schedule
- user / team

Evidence 大正文不建议全部塞 PG，可放：

- filesystem
- OSS / S3-compatible object storage

PG 保存索引。

## Queue

达到并发任务需求后：

```text
FastAPI
  ↓
Redis Queue
  ↓
Audit Worker
```

Worker 独立运行 Deep Audit。

## 多用户

- [ ] 登录
- [ ] Team
- [ ] RBAC
- [ ] Endpoint Secret 管理
- [ ] Audit 操作记录
- [ ] Reference 权限
- [ ] Report Share

## Secret

生产环境不允许 API Key 明文长期落库。

候选：

- 环境 Secret
- Vault/KMS
- 加密后的 credential store

---

# 8. 开发顺序

从当前 `main` 往后严格按：

```text
V1.1-1 Fingerprint 深化
      ↓
V1.1-2 Integrity 补齐
      ↓
V1.1-3 Mixed Routing 深化
      ↓
V1.1-4 Coding Sandbox
      ↓
V1.1-5 Capability 扩展
      ↓
V1.1-6 promptfoo / lm-eval
      ↓
V1.1-7 Model / Provider DB
      ↓
V1.2   Anthropic / Gemini
      ↓
V1.2   Web Compare / Schedule / Trend
      ↓
V2     PostgreSQL / Queue / Multi-user
```

不建议先做：

- 大屏
- 排行榜
- 登录权限
- PostgreSQL
- Redis
- 漂亮重前端

直到真实性和准入检测的准确性稳定。

---

# 9. V1.1 Definition of Done

V1.1 完成必须满足：

- [ ] strong identity 可以展示完整统计证据
- [ ] self-consistency 可检查
- [ ] system/tool/schema preservation 有 Probe
- [ ] fingerprint routing consistency
- [ ] routing cluster 基础版
- [ ] code generation sandbox execution
- [ ] Capability Deep >= 80 个有效 task 或等效外部 benchmark
- [ ] promptfoo 可作为 declarative regression adapter
- [ ] lm-eval 至少一个 benchmark profile 可运行
- [ ] Model Rule 有版本和来源
- [ ] Web 可查看更完整 identity/routing evidence
- [ ] 所有新增结论可回溯 Evidence
- [ ] 不引入性能测试
