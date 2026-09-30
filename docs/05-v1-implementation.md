# 当前实现状态与缺口

> 本文用于回答“现在到底做到哪里”。  
> 架构见 `02-architecture.md`，后续计划见 `03-development-plan.md`。

## 1. 当前发布状态

版本：`0.2.0`

当前 V1 已经能完成一条完整的供应商准入审计：

```text
Endpoint
  ↓
Protocol
  ↓
Provider Fingerprint
  ↓
Parameter Integrity
  ↓
Context
  ↓
Routing
  ↓
Capability Lite
  ↓
Reference / Fingerprint / proxy-sleuth
  ↓
Score / Verdict
  ↓
Evidence / Report / Web
```

## 2. 已完成

| 模块 | 状态 | 说明 |
|---|---|---|
| Audit Core | ✅ | CLI / Web 都可运行 |
| Unified Probe | ✅ | 统一 status/score/confidence/evidence |
| Evidence | ✅ | Request / Response / Header / Error |
| Secret Redaction | ✅ | API Key 不进入报告 |
| Provider Fingerprint | ✅ | YAML 可维护 |
| OpenAI Chat | ✅ | native |
| Streaming | ✅ | SSE |
| Responses API | ✅ | feature probe |
| Reasoning | ✅ | valid / invalid / low-medium-high |
| Thinking | ✅ | 当前先记录行为 |
| Tool Calling | ✅ | basic / choice / schema / parallel |
| JSON | ✅ | JSON mode / schema / invalid schema |
| Integrity | 🟡 | 基础版完成 |
| Context | ✅ | 8K / 16K / 32K |
| Routing | 🟡 | 基础版完成 |
| Capability Lite | ✅ | 当前 25 题 |
| Coding Execution | ❌ | 当前只有代码理解题 |
| Reference Registry | ✅ | collect/list/show/verify/import |
| Statistical Fingerprint | 🟡 | collect/verify/mean JSD 已有 |
| proxy-sleuth | ✅ | 分层映射 |
| Scoring | ✅ | weights + hard cap |
| Identity Strength | ✅ | weak/medium/strong |
| HTML / JSON Report | ✅ | Evidence 链接 |
| Drift Compare | ✅ | 手动 report compare |
| Web | ✅ | Audit / history / reference |
| Scheduler | ❌ | 未做 |
| Trend | ❌ | 未做 |
| Anthropic Native | ❌ | 未做 |
| Gemini Native | ❌ | 未做 |
| promptfoo Adapter | ❌ | 未做 |
| lm-eval Adapter | ❌ | 未做 |
| PostgreSQL / Queue | ❌ | V2 再做 |
| Multi-user / RBAC | ❌ | V2 再做 |
| Performance Test | 🚫 | 明确不集成 |

## 3. 当前“真实性”能力边界

已有强项：

- Trusted Reference
- Statistical Fingerprint
- Protocol Signature
- Model Rule
- Provider Fingerprint
- Knowledge / Statistical OSS Layer
- Routing 重复采样

仍需要补强：

- per-cell fingerprint
- split-half self consistency
- fingerprint routing consistency
- fact inversion
- routing cluster

所以当前报告可以作为供应商准入依据之一，但不应该表达成：

> 100% 证明某模型是真的。

正确表达：

- match
- review
- mismatch
- insufficient

并展示证据。

## 4. 当前“能力评分”边界

当前 Capability Lite 适合：

- 供应商准入
- 明显能力降级检测
- 横向粗粒度能力画像

不适合：

- 权威模型排行榜
- 大模型综合 benchmark 排名

后续通过：

- 扩题
- Coding sandbox
- lm-eval

提高能力评分可信度。

## 5. 当前“Provider Fingerprint”边界

用于判断：

> 这个 API 暴露出了哪些 Provider / Gateway 特征。

不是：

> 精确证明整条供应链。

例如 Azure APIM + Fireworks 同时出现时，应解释为：

> 当前证据同时命中 Azure API Management 与 Fireworks 特征，可能存在对应网关/上游链路。

而不是直接宣称完整供应链拓扑。

## 6. 下一步

直接执行 `03-development-plan.md` 的 V1.1 P0：

1. Fingerprint 深化
2. Parameter Integrity 补齐
3. Mixed Routing 深化
4. Coding Sandbox
