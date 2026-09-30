# 开发计划与路线图

> 本文件从 2026-09-30 起作为 model-detect 主开发计划。  
> 当前产品目标：**单机自用的 AI 中转站 / 上游供应商准入检测工具**。  
> 只需要 Web 检测、报告与本地历史记录。性能测试和平台化能力永久独立。

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

- [x] Claude
- [x] GPT
- [x] Gemini
- [x] 只写官方可验证能力
- [x] expected feature 必须可追溯

# 7. Lightweight Closure 最后一批 5 个小阶段

这一批完成后停止功能扩张。

## Stage 1 — 产品范围收口

- [x] 单机单用户
- [x] Web + Report + SQLite History 为最终产品形态
- [x] Saved Endpoint / Scheduler / Notification / RBAC 移出路线
- [x] 性能测试继续独立

## Stage 2 — History Result UX

- [ ] 历史列表直接显示 Verdict / Score
- [ ] HTML / JSON / ZIP 都有直接入口
- [ ] 失败任务仍显示错误原因

## Stage 3 — History Filters

- [ ] 模型筛选
- [ ] 状态筛选
- [ ] Audit / Reference 类型筛选
- [ ] 保持 SQLite 简单查询，不引入搜索服务

## Stage 4 — History Delete

- [ ] 删除 SQLite 记录
- [ ] 同步删除对应报告目录
- [ ] 清理对应临时 ZIP
- [ ] 禁止删除运行中任务

## Stage 5 — Local E2E Acceptance

- [ ] Web 提交 Audit
- [ ] 任务完成进入 History
- [ ] HTML / JSON / ZIP 可访问
- [ ] Filter 可用
- [ ] Delete 可完整清理

# 8. 明确不进入当前路线

- Saved Endpoint
- Scheduler / 定时巡检
- 自动 Drift / 告警
- Notification / Webhook
- PostgreSQL / Redis / Worker
- Login / RBAC / Team
- 多租户 SaaS
- Anthropic / Gemini Native Protocol（除非以后真有直接测 Native API 的需求）

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
