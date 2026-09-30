# 开发计划与路线图

> 本文件从 2026-09-30 起作为 model-detect 主开发计划。  
> 目标始终是：**AI 中转站 / 上游供应商准入与持续审计**。  
> 性能测试永久独立，不进入本项目。

## 1. 已完成主链

### V1 Core

- [x] CLI / Web
- [x] Unified ProbeResult
- [x] Raw Evidence + Secret Redaction
- [x] JSON / HTML Report
- [x] Provider Fingerprint
- [x] OpenAI-compatible Protocol Probe
- [x] Reference Registry
- [x] Score / Hard Cap / Identity Strength
- [x] SQLite Job History
- [x] Report Compare

### V1.1 P0

- [x] Fingerprint 深化
- [x] Parameter Integrity 深化
- [x] Mixed Routing 深化
- [x] Coding Sandbox
- [x] Capability Dataset 扩展

对应设计：

- `design/07-fingerprint-deepening.md`
- `design/08-integrity-probes.md`
- `design/09-mixed-routing.md`
- `design/10-coding-sandbox.md`

### Capability 当前规模

- [x] Reasoning 20+
- [x] Math 20+
- [x] Chinese 20+
- [x] Instruction Following 20+
- [x] Coding execute 10+
- [x] Tool Use 场景化
- [x] Structured Output 场景化

### lm-evaluation-harness

- [x] OpenAI-compatible Endpoint Adapter
- [x] 内置 smoke / standard / deep profile
- [x] 结果映射 Unified ProbeResult
- [x] 默认避免与 Capability Lite 重复执行
- [x] 用户可配置 benchmark profile

## 2. 明确排除

以下不开发：

- TTFT
- ITL / TPOT
- TPS
- RPM / TPM
- 并发吞吐
- GPU 指标
- 429 压力测试

这些由独立性能工具负责。

# 3. 当前阶段目标

当前不是继续做更多排行榜题目，而是补齐两种核心资产：

1. **Regression Asset**：客户/准入问题可以快速固化为可重复测试；
2. **Knowledge Asset**：模型与 Provider 规则有版本、来源和可追溯证据。

这比先做 Scheduler、重 Web、Anthropic/Gemini Native 更优先，因为它直接提升供应商准入准确性。

# 4. 下一批 5 个小阶段

严格一项一个 branch / commit / PR / CI / merge。

## Stage 1 — lm-eval 可配置 benchmark profile

- [x] 从用户 YAML 读取自定义 profile
- [x] 校验 task / limit / overlap policy
- [x] 不允许 API Key 写入 profile
- [x] 与内置 profile 使用同一执行入口

验收：用户可新增供应商专属 benchmark profile，不改 Python。

## Stage 2 — promptfoo HTTP Provider Adapter

设计：`docs/design/11-promptfoo-regression.md`

- [x] 检测 promptfoo 可用性
- [x] OpenAI-compatible HTTP provider config 生成
- [x] Base URL / model / API key env 映射
- [x] API Key 只通过环境变量传递
- [x] subprocess runner

## Stage 3 — promptfoo Regression YAML Loader

- [x] model-detect regression schema
- [x] YAML load / validation
- [x] deterministic assertions
- [x] JSON Schema assertion
- [x] Tool Call assertion
- [x] Repeat 基础字段
- [x] 禁止默认执行任意 JS/Python

## Stage 4 — Regression YAML -> promptfoo Config Compiler

- [x] 每个 regression case 编译为独立 provider/test
- [x] request 参数合并且禁止覆盖 model/messages/tools
- [x] JSON / Tool assertions 映射
- [x] repeat 映射
- [x] HTTP status expectation 映射
- [x] case metadata 保留给结果解析

## Stage 5 — promptfoo Result Mapping

- [x] promptfoo JSON result -> Unified ProbeResult
- [x] case id / assertion / reason / output metadata
- [x] Evidence artifact source
- [x] pass/warn/fail 映射
- [x] Regression 结果默认进入 protocol/integrity，而非 identity strong evidence

> Model Rule schema version/source 顺延到下一批第 1 项，设计仍见
> `docs/design/12-model-provider-knowledge.md`。

# 5. Knowledge Asset 下一批 5 个小阶段

严格继续一项一个 branch / commit / PR / CI / merge。

## Stage 1 — Model Rule v2 schema + backward compatibility

- [x] schema_version
- [x] family / model_version / aliases / updated_at
- [x] sources[]
- [x] source type / confidence enum
- [x] feature source_refs
- [x] v1 YAML backward compatibility
- [x] strict rule provenance guard

## Stage 2 — Kimi-K3 v2 Rule migration

- [x] 迁移 kimi-k3.yaml
- [x] 官方文档 / empirical source
- [x] feature source_refs
- [x] 不改变现有 non-strict 判定语义

## Stage 3 — Provider Fingerprint provenance schema

- [x] provider schema_version
- [x] source registry
- [x] source_refs
- [x] false_positive_notes
- [x] confidence calibration metadata
- [x] v1 backward compatibility

## Stage 4 — Provider DB migration

- [x] 现有 providers.yaml 迁移到新版格式
- [x] 保留原有 header/pattern 权重
- [x] 每个 provider 有 provenance
- [x] detection behavior regression test

## Stage 5 — First formal model knowledge rules

- [x] GLM
- [x] Qwen
- [x] DeepSeek
- [x] 官方来源 / empirical 来源分离
- [x] 每条 feature 可追溯

# 6. Audit Closure 下一批 5 个小阶段

设计：`docs/design/13-regression-audit-integration.md`

## Stage 1 — Regression Suite -> Audit Orchestrator

- [x] Audit 可执行多个 regression suite
- [x] Unified ProbeResult 合并进入主报告
- [x] suite 失败隔离，不中断整次 audit
- [x] adapter metadata 记录 artifact root / suite 状态
- [x] regression 仍不产生 strong identity evidence

## Stage 2 — Audit Profile 配置 regression suites

- [x] AuditConfig 定义 regression suites
- [x] quick / standard / deep 可分别启用
- [x] CLI config 与直接参数支持
- [x] 默认无 regression，保持 backward compatibility

## Stage 3 — Report regression evidence

- [x] report 复制/持久化 promptfoo artifact
- [x] HTML Regression section
- [x] case / status / reason / output 展示
- [x] ZIP 报告包含 regression artifacts

## Stage 4 — Web provenance / regression UX

- [x] Web 展示 Model Rule provenance
- [x] Web 展示 Provider Rule provenance
- [x] Web 发起 audit 时选择 regression suite
- [x] Job detail 展示 regression 状态

## Stage 5 — Claude / GPT / Gemini Model Knowledge

- [ ] Claude
- [ ] GPT
- [ ] Gemini
- [ ] 只写官方可验证能力
- [ ] expected feature 必须可追溯

# 7. 后续优先级

完成以上 5 项后：

## promptfoo 完整化

- Custom Python/JS assertion：显式 opt-in 后再支持
- Repeat assertions
- 客户 case -> regression library
- regression suite -> audit orchestration

## Model / Provider Knowledge Base

- GLM
- Qwen
- DeepSeek
- Claude
- GPT
- Gemini

Provider DB 增加：

- rule version
- evidence source
- false-positive notes
- confidence calibration

## Web / Continuous Audit

随后再做：

- Saved Endpoint
- Web Report Compare
- Local Scheduler
- Provider Drift
- Reference Drift
- Probe Regression
- Notification Hook
- Trend

# 8. 为什么现在不先做 Scheduler / Native Anthropic / Gemini

当前主要业务输入仍是 OpenAI-compatible 中转 Endpoint。

如果模型规则、回归测试和证据知识库还没有成熟，先做 Scheduler 只是在“自动重复跑不够好的检测”。

所以顺序必须是：

```text
Regression + Knowledge
        ↓
更可靠的准入检测
        ↓
Saved Endpoint
        ↓
Scheduler / Drift
```

Anthropic/Gemini Native 等出现真实准入需求时，再先完成 Protocol Abstraction 设计后开发。

# 9. V1.1 Definition of Done

已满足：

- [x] strong identity 可展示统计证据
- [x] self-consistency
- [x] system/tool/schema preservation
- [x] fingerprint routing consistency
- [x] routing cluster
- [x] coding sandbox execution
- [x] Capability Deep >= 80 个 native task / equivalent executable coverage
- [x] lm-eval 至少一个 benchmark profile 可定义和运行
- [x] 所有核心 Probe 可回溯 Evidence
- [x] 不引入性能测试

仍需：

- [x] promptfoo 可作为 declarative regression adapter
- [x] Model Rule 有版本和来源
- [x] Web 更完整展示 identity/routing evidence
