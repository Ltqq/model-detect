# 当前实现状态与缺口

> 本文回答“现在到底做到哪里”。  
> 架构见 `02-architecture.md`，后续计划见 `03-development-plan.md`。

## 1. 当前产品状态

model-detect 已经可以完成供应商准入主链：

```text
Endpoint
  ↓
Protocol / Provider Fingerprint
  ↓
Parameter Integrity
  ↓
Context Integrity
  ↓
Mixed Routing
  ↓
Capability + Coding Sandbox
  ↓
Reference / Statistical Fingerprint / OSS Adapters
  ↓
Declarative Regression / Model Knowledge
  ↓
Score / Verdict
  ↓
Evidence / Report / Web
```

## 2. 当前完成度

| 模块 | 状态 | 当前实现 |
|---|---|---|
| Audit Core | ✅ | CLI / Web |
| Evidence / Redaction | ✅ | request/response/evidence links |
| OpenAI-compatible Protocol | ✅ | chat/stream/responses/tools/json/reasoning |
| Provider Fingerprint | ✅ | v2 provenance YAML DB |
| Fingerprint Deepening | ✅ | mean/per-cell JSD + split-half |
| Parameter Integrity | ✅ | system/tool/schema/temp/top_p/max_tokens/stop |
| Context | ✅ | 8K/16K/32K |
| Mixed Routing | ✅ | multi-window/fact inversion/cluster/fingerprint fusion |
| Capability | ✅ | 20 reasoning + 20 math + 20 Chinese + 20 instruction |
| Coding Reasoning | ✅ | 5 tasks |
| Coding Execution | ✅ | Python/Go Docker sandbox >=10 tasks |
| Tool Use | ✅ | multi-scenario aggregate |
| Structured Output | ✅ | JSON mode/schema aggregate |
| Reference Registry | ✅ | collected/imported/bundled |
| llm-fingerprint | ✅ | structured evidence |
| proxy-sleuth | ✅ | layered mapping |
| lm-eval Endpoint | ✅ | local-chat-completions |
| lm-eval Profiles | ✅ | built-in + user-configurable YAML |
| lm-eval Result Mapping | ✅ | Unified ProbeResult |
| promptfoo Regression | ✅ | YAML -> compile -> eval -> ProbeResult |
| Model Rule provenance | ✅ | schema v3 + sources + source_refs |
| Formal Model Rules | ✅ | Kimi K3 / GLM-5.2 / Qwen3.8 / DeepSeek V4 / Claude 5 / GPT-5.6 / Gemini 3.8 Flash；协议级语义 |
| Official Quality Baseline | ✅ | Reference 内保存重复同套件实测 baseline.json |
| Baseline Collector | ✅ | Standard/Deep 同端点串行重复 1–5 次；默认推荐 3 次 |
| Quality Comparison | ✅ | mean/stddev/task granularity/retention；低样本保守判定 |
| Chinese Quality Report | ✅ | 官方/可信基准、当前渠道、保持率、基准下界、退化说明 |
| Provider Rule provenance | ✅ | schema v3 + source refs + false-positive notes |
| Report Drift Compare | ✅ | manual report compare |
| Regression Audit Orchestration | ✅ | Audit/Profile/CLI/Web/Report 已接通 |
| SQLite History | ✅ | 本地任务历史已保存，最后补 UX 收尾 |
| Scheduler / Trend | 🚫 | 当前产品不需要 |
| Anthropic/Gemini Native | 🚫 | 当前主要测 OpenAI-compatible relay |
| PostgreSQL / Redis / RBAC | 🚫 | 单机自用不需要 |
| Performance Test | 🚫 | explicitly out of scope |

## 3. 当前模型真实性边界

当前已经具备：

- Trusted Reference
- Protocol Signature
- Statistical Fingerprint
- per-cell JSD
- self consistency
- Model Rule v3 provenance
- Provider Fingerprint v2 provenance
- Routing Consistency
- Declarative Regression

仍坚持：

> 不输出“97.63% 是真模型”这类伪精确概率。

正式语义：

- MATCH
- REVIEW
- MISMATCH
- INSUFFICIENT

并同时展示 Confidence 与 Evidence。

## 4. 当前知识规则

首批正式可追溯 Model Rule：

- Kimi K3
- GLM-5.2
- Qwen3.8
- DeepSeek V4 / V4.1
- Claude Fable 5.1 / Opus 5 / Sonnet 5
- GPT-5.6 family
- Gemini 3.8 Flash

原则：

- 官方事实与 empirical observation 分开记录；
- `expected != null` 的 v3 feature 必须有 `source_refs`；
- Gateway 差异默认不直接升级成模型身份强证据；
- 不确定的能力保持 `expected: null`。

## 5. 当前真正缺口

核心开发已经完成。现在剩下的是**真实世界校准数据**，不是继续扩产品功能：

1. 使用真实官方 Kimi K3 Endpoint 采集至少 3 次 Standard Quality Baseline + Statistical Fingerprint；
2. 使用真实官方 GLM-5.2 Endpoint 做同样采集；
3. 用同一 Reference 对现有供应商渠道复测，观察自然波动与 Quality Regression 阈值是否合理；
4. 后续按实际业务优先级补 Qwen / DeepSeek / GPT / Claude / Gemini 官方基准；
5. 定期复审 Model Rule 官方来源，避免厂商 API 演进后规则过期。

真实官方数据需要对应厂商 API Key。本仓库只提供采集、比较和报告流程，不保存凭据，也不伪造“官方基准结果”。

更强的公开 Benchmark 可继续通过现有 lm-evaluation-harness Adapter 扩展，但只有当官方端点与供应商端点使用完全相同 Dataset / Harness / Prompt / 参数时才允许直接比较。

性能测试继续永久独立。
