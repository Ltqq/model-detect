# V1 实现说明

## 状态

V1 已实现并进入可运行阶段。

目标：

> 面向 AI 中转站 / LLM Provider 准入，用一套可解释的黑盒审计流程，在客户之前发现模型替换、协议差异、Provider 指纹、参数降级、上下文截断和混合路由。

## 已完成阶段

### Phase 1 — Audit Core

- CLI
- Config
- Unified Probe Result
- Evidence
- Secret Redaction
- JSON / HTML Report

### Phase 2 — Protocol / Provider

- Chat Completions
- SSE
- Responses API feature detection
- usage / finish_reason
- invalid model / field / enum
- reasoning
- thinking
- tools / tool_choice / parallel tools
- JSON mode / JSON Schema
- Provider Fingerprint YAML DB

### Phase 3 — Identity

- llm-fingerprint-detector adapter
- proxy-sleuth layered adapter
- Reference Registry
- protocol signature reference
- fingerprint collect / import / verify
- model rules
- weak / medium / strong evidence semantics

### Phase 4 — Integrity / Routing

- max_tokens
- stop
- sampling controls
- reasoning effect
- Context Needle
- repeated routing signature
- model-field drift
- response-schema drift
- id-prefix drift
- quality inversion

### Phase 5 — Capability Lite

25 个确定性、低成本任务：

- Reasoning
- Math
- Coding reasoning
- Chinese
- Instruction Following

另外 Tool Use / Structured Output 直接复用协议 Probe，不重复消耗请求。

### Phase 6 — Score

- Category weights
- Hard Cap
- Identity mismatch cap
- Mixed routing cap
- Critical protocol cap
- strong identity evidence requirement

### Phase 7 — Web

- Audit form
- background job
- SQLite history
- progress
- report
- evidence
- report ZIP
- Reference list / collect / delete

## Quick / Standard / Deep

### Quick

用于初筛。

### Standard

默认供应商准入档。

包含 8K Context 与轻量 Capability。

### Deep

用于重要上游和正式准入。

包含更高 Routing 样本、8K/16K/32K Context 和完整 Capability Lite。

## 开源复用

### ToseaAI/llm-fingerprint-detector

用途：

- Trusted fingerprint collection
- Reference verification
- JSD statistical identity evidence

### Babapei/proxy-sleuth

其层级结果被映射到 model-detect：

- param_integrity -> integrity
- context_truncation -> context
- api_features -> protocol
- knowledge_probes -> identity
- statistical -> identity
- capability -> capability
- mixed_routing -> routing

model-detect 不复制其全部实现，而是保留 Adapter 边界。

## 不做性能测试

V1 不包含：

- TTFT
- ITL
- TPS
- RPM / TPM
- 并发吞吐
- 429 压力测试

原因是用户已有独立性能测试脚本，并且性能质量和模型真实性是两个不同产品问题。

## 当前原生协议边界

V1 原生 Probe 以 OpenAI-compatible API 为主。

其它协议可由 proxy-sleuth 提供补充检测；后续只有在实际供应商准入需要时，再增加 Anthropic / Gemini 原生 Probe，不把 V1 做成无边界的大而全兼容层。
