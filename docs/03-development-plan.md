# 开发计划

## 总原则

先做“能发现真实问题”的内核，再做 UI。

不一上来做：

- 登录系统
- 权限
- 大屏
- 排行榜
- 多租户
- 性能压测

---

# Phase 0：开源项目验证

目标：

确认哪些能力可以直接拿来用。

## 任务

### 0.1 proxy-sleuth

验证：

- param-integrity
- api-features
- context
- knowledge
- routing

要求：

- 用一个官方 Endpoint
- 用一个中转 Endpoint
- 对比输出
- 看是否能作为 Python library 调用
- 找出哪些 detector 可直接 import，哪些要重新封装

产出：

`docs/research/proxy-sleuth.md`

### 0.2 llm-fingerprint-detector

验证：

- fingerprint 官方 endpoint
- fingerprint 中转 endpoint
- verify
- bundled references
- split-half JSD
- reasoning adapter

产出：

`docs/research/llm-fingerprint-detector.md`

### 0.3 promptfoo

验证：

- 自定义 HTTP endpoint
- status assertion
- JSON schema
- tool call
- repeat
- custom assertion

产出：

`docs/research/promptfoo.md`

### 0.4 lm-evaluation-harness

只验证 API 模型调用和少量 task。

不做大规模 benchmark。

---

# Phase 1：Audit Core MVP

目标：

不做 Web，也能通过 CLI 跑完整一次审计。

## 功能

### Endpoint Config

```yaml
base_url:
api_key_env:
model:
protocol:
profile:
```

### Job Runner

```bash
model-detect audit config.yaml
```

### Unified Probe Result

建立统一结果模型。

### Evidence

所有请求响应脱敏后可落盘。

### Report JSON

先输出：

```text
report.json
evidence/
raw/
```

## 验收

能对两个 endpoint 跑一次完整 Quick Audit。

---

# Phase 2：协议和上游指纹

目标：

先把最贴近当前业务的问题解决。

## Provider Fingerprint

支持第一批：

- Azure APIM
- Fireworks
- OpenRouter
- Together
- DeepInfra
- Anthropic
- OpenAI
- Google / Vertex
- AWS Bedrock
- vLLM
- SGLang

注意：

每条规则必须：

- 有 evidence
- 有 confidence
- 可配置

## Protocol Probe

第一批：

- chat completion
- stream
- usage
- model field
- finish reason
- invalid model
- invalid param
- unknown param
- tools
- tool_choice
- json mode
- json schema
- reasoning_effort
- thinking
- temperature
- top_p
- max_tokens

## 验收

可以复现类似：

```text
FW-Kimi-K3 + Azure APIM
```

这种结果的证据链。

---

# Phase 3：真实性检测

## 3.1 Statistical Fingerprint

接入 `llm-fingerprint-detector`。

功能：

- collect reference
- verify
- import bundled reference
- 保存 artifact
- 查看 per-cell JSD
- 查看 split-half JSD

## 3.2 Knowledge / Behavior Probe

优先复用 proxy-sleuth。

## 3.3 Reference Registry

CLI：

```bash
model-detect reference collect ...
model-detect reference list
model-detect reference verify ...
```

## 验收

同模型同 Endpoint 多次：

大体稳定。

不同模型：

能明显产生差异。

不要求“100% 判真”。

---

# Phase 4：完整性 / 混合路由

## Parameter Integrity

检测：

- reasoning downgrade
- max token clamp
- system prompt injection
- tool removal
- sampling param ignore

## Context

复用 proxy-sleuth Needle-in-Haystack 思路。

V1 不追求测试最大极限 context。

主要判断：

> 是否明显早于声明窗口被截断。

## Routing

重复采样：

- 相同 Probe 重复
- 简单题 / 复杂题
- 行为簇差异
- fingerprint self consistency

输出：

```text
stable
suspicious
mixed-routing-likely
insufficient
```

---

# Phase 5：Capability Lite

目标：

有一个可解释能力画像，但不变成 benchmark 大平台。

## 能力项

建议：

### Reasoning

10–30 道高区分度题。

### Math

10–30 道自动判分题。

### Coding

执行验证，小规模。

### Chinese

中文指令、表达、知识。

### Instruction Following

约束遵循。

### Tool Use

通过 protocol probe 共用。

### Structured Output

通过 protocol probe 共用。

## 复用

优先：

- lm-evaluation-harness task
- proxy-sleuth capability
- promptfoo assertion

避免自己维护大数据集。

---

# Phase 6：Score Engine

## 分数

建议：

```text
Identity               35
Protocol               20
Parameter Integrity    15
Context                10
Routing                10
Capability             10
```

这只是初始权重，最终要用真实案例校准。

## Hard Cap

必须实现。

示例：

```text
identity=mismatch         total <= 40
mixed-routing-likely      total <= 60
protocol critical fail    total <= 60
insufficient evidence     no high-confidence score
```

Provider Fingerprint 不参与总分。

---

# Phase 7：Web MVP

只有 Audit Core 稳定后再做。

## 页面

### New Audit

输入：

- Base URL
- API Key
- Model
- Protocol
- Profile

### Audit Progress

显示 Probe 执行状态。

### Report

显示：

- 总结
- 身份
- 协议
- 完整性
- 能力
- Provider fingerprint
- Raw Evidence

### Reference

管理可信 Reference。

---

# Phase 8：生产化

后面再考虑：

- PostgreSQL
- Redis queue
- 历史趋势
- 周期性重测
- Provider baseline drift
- CI / API
- 多用户
- 权限
- 报告导出

---

# 第一版开发顺序

建议严格按这个顺序：

```text
1. OSS research
2. Unified models
3. Evidence
4. Native HTTP probes
5. Provider fingerprint
6. proxy-sleuth adapter
7. statistical fingerprint adapter
8. Reference Registry
9. routing/context
10. capability lite
11. score engine
12. web
```

不要反过来先写 Web。

---

# MVP Definition of Done

第一版必须达到：

- [ ] OpenAI-compatible endpoint 可以直接测
- [ ] API Key 不进入日志
- [ ] 能抓完整 response headers / error body
- [ ] Provider fingerprint 至少覆盖 5 个常见上游
- [ ] 15+ protocol probes
- [ ] 接入 proxy-sleuth 至少 3 层
- [ ] 接入 llm-fingerprint-detector
- [ ] 支持 trusted reference
- [ ] context truncation
- [ ] mixed routing 基础判断
- [ ] capability lite
- [ ] JSON report
- [ ] HTML report
- [ ] 每个结论都可点回 evidence
- [ ] 不包含性能压测

