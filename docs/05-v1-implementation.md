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
| Model Rule provenance | ✅ | schema v2 + sources + source_refs |
| Formal Model Rules | ✅ | Kimi K3 / GLM-5.2 / Qwen3.8 / DeepSeek V4 / Claude 5 / GPT-5.6 / Gemini 3.8 Flash |
| Provider Rule provenance | ✅ | schema v2 + source refs + false-positive notes |
| Report Drift Compare | ✅ | manual report compare |
| Regression Audit Orchestration | ✅ | Audit/Profile/CLI/Web/Report 已接通 |
| SQLite History | ✅ | Verdict/Score、HTML/JSON/ZIP、筛选、删除均完成 |
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
- Model Rule v2 provenance
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
- `expected != null` 的 v2 feature 必须有 `source_refs`；
- Gateway 差异默认不直接升级成模型身份强证据；
- 不确定的能力保持 `expected: null`。

## 5. 当前状态

轻量产品闭环已经完成：

- Web 发起 Audit；
- SQLite 保存历史；
- 历史显示 Verdict / Score；
- HTML / JSON / ZIP 可直接打开或下载；
- 模型 / 状态 / 类型可筛选；
- 历史记录可删除并同步清理本地 Audit 文件；
- Local E2E 覆盖“提交 -> 完成 -> 历史 -> 报告 -> 筛选 -> 删除”。

当前停止扩功能。后续只在真实使用中维护 Model Rule、Provider Rule、Regression Case，并修复实际发现的问题。

性能测试继续保持独立。
