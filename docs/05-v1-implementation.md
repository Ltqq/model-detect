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
| Provider Fingerprint | ✅ | YAML DB |
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
| lm-eval Profiles | 🟡 | built-in profiles complete; user-configurable pending |
| lm-eval Result Mapping | ✅ | Unified ProbeResult |
| Report Drift Compare | ✅ | manual report compare |
| promptfoo Regression | ❌ | next stage |
| Model Rule provenance | ❌ | next stage |
| Scheduler / Trend | ❌ | later |
| Anthropic/Gemini Native | ❌ | later |
| PostgreSQL / Redis / RBAC | ❌ | V2 |
| Performance Test | 🚫 | explicitly out of scope |

## 3. 当前模型真实性边界

当前已经具备：

- Trusted Reference
- Protocol Signature
- Statistical Fingerprint
- per-cell JSD
- self consistency
- Model Rule
- Provider Fingerprint
- Routing Consistency

仍坚持：

> 不输出“97.63% 是真模型”这类伪精确概率。

正式语义：

- MATCH
- REVIEW
- MISMATCH
- INSUFFICIENT

并同时展示 Confidence 与 Evidence。

## 4. 当前能力评测边界

Capability 用于供应商准入和明显降级检查，不用于做公开排行榜。

lm-eval 是外部 benchmark 参照，不替代自有 deterministic / executable Probe。

## 5. 当前真正缺口

最重要的不是更多题目，而是：

1. 客户问题如何快速沉淀成 declarative regression；
2. Model Rule 如何记录版本和官方/Reference/empirical 来源；
3. Provider Fingerprint 如何逐步成为可追溯知识库；
4. 后续如何把成熟准入能力接入自动重测与 Drift。

下一批 5 项见 `03-development-plan.md`。
