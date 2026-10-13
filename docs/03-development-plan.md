# 开发计划与路线图

> 本文件从 2026-09-30 起作为 model-detect 主开发计划。  
> 当前产品目标：**单机自用的 AI 中转站 / 上游供应商准入检测工具**。  
> 只需要 Web 检测、报告与本地历史记录。性能测试和平台化能力永久独立。

## 0. 最新状态与当前开发任务（2026-10-13）

**最新、唯一生效的后续任务清单：[17 号工程收尾与验收计划](design/17-engineering-closure-roadmap.md)。** 本文第 3～9 节保留为先前批次的实施记录，不再按其中“下一批”标题重复开发。

| 模块 | 状态 | 关键结论 |
|---|---|---|
| Web/CLI/中文报告/SQLite 历史 | 已完成代码 | 主流程可使用；最终真实 E2E 仍需验收 |
| Protocol/Integrity/Context/Routing/Capability | 已完成代码 | 可做黑盒证据采集，判定能力仍需实际校准 |
| Fingerprint / proxy-sleuth / promptfoo / lm-eval | 已有 Adapter | 需固定版本、安装并通过真实调用联调，不等于第三方所有能力已覆盖 |
| Official Quality Baseline / 同套件比较 | 已完成代码 | 合同不一致应不可比；Reference 覆盖保护、Collector 异常回滚尚待修复 |
| 受控实验/离线校准工具 | 已完成代码 | 真实 Kimi/GLM 正负例和请求日志尚未采集 |
| 每项 Token 用量、费用和执行前预算 | **待开发 P0** | 当前只有任务数/限制提示，不等于实际 Token/费用 |
| Moonshot 官方 Kimi-Vendor-Verifier | **待评估/接入 P1** | 官方专用完整测试未接入；先做差距清单和必要子集 |
| 完整真实验收与发布 | **待执行** | Mock CI 不是外部工具/付费 API E2E |

**新任务依序**：A Reference 安全覆盖/失败语义 → B Token Meter/预算 → C 官方 Kimi 专项验证 → D OSS/Web/CLI 集成验收 → E Kimi/GLM 真实数据校准 → F 发布评审。阶段 A～D 可先用本地 Mock 测代码，但不能凭此勾选 E。

### 2026-10-13 真实 GLM-5.3 客户测试后的优先级覆盖

当前唯一主路线仍是 [17 号工程收尾计划](design/17-engineering-closure-roadmap.md)，但因已上传真实测试证据，**新增临时 G0/G1 缺陷抢修排在常规 A1 之前**，详情见 [20 号 GLM-5.3 实测复盘](design/20-glm53-live-evidence-triage.md)。

- **G0 / P0**：修 Benchmark 稳定比较键（base_url/函数 repr 不能进入 task hash）、用真实原始报告回归、修 Capability 正则/判分和中文 thinking.disabled，报告不得夸大证据。
- **G1 / P1**：补全 lm-eval[api]/[math]、IFEval/NLTK 离线依赖预检与 venv PATH，核实推理强度参数及原始结果保留。
- **之后恢复 A1/A2/B**：Reference 安全替换、失败语义和 Token Meter 仍是全项目 P0；Kimi Vendor Verifier 和其他 OSS E2E 继续按 17 号文档执行。

本次提供的是**官方与客户受控同题对照样本**，不是 Kimi / GLM-5.2 的已知真值模型替换实验；相关校准不应提前勾选完成。

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

# 3. 历史阶段目标（已实现，非新的开发任务）

当前不是继续做更多排行榜题目，而是补齐两种核心资产：

1. **Regression Asset**：客户/准入问题可以快速固化为可重复测试；
2. **Knowledge Asset**：模型与 Provider 规则有版本、来源和可追溯证据。

这比先做 Scheduler、重 Web、Anthropic/Gemini Native 更优先，因为它直接提升供应商准入准确性。

# 4. 历史实施批次：lm-eval / promptfoo（已完成）

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

# 5. 历史实施批次：Knowledge Asset（已完成）

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

# 6. 历史实施批次：Audit Closure（已完成）

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

# 7. 历史实施批次：Lightweight Closure（代码完成）

这一批完成后停止功能扩张。

## Stage 1 — 产品范围收口

- [x] 单机单用户
- [x] Web + Report + SQLite History 为最终产品形态
- [x] Saved Endpoint / Scheduler / Notification / RBAC 移出路线
- [x] 性能测试继续独立

## Stage 2 — History Result UX

- [x] 历史列表直接显示 Verdict / Score
- [x] HTML / JSON / ZIP 都有直接入口
- [x] 失败任务仍显示错误原因

## Stage 3 — History Filters

- [x] 模型筛选
- [x] 状态筛选
- [x] Audit / Reference 类型筛选
- [x] 保持 SQLite 简单查询，不引入搜索服务

## Stage 4 — History Delete

- [x] 删除 SQLite 记录
- [x] 同步删除对应报告目录
- [x] 清理对应临时 ZIP
- [x] 禁止删除运行中任务

## Stage 5 — Local E2E Acceptance（自动化 Mock 路径，非真实 API E2E）

- [x] Web 提交 Audit
- [x] 任务完成进入 History
- [x] HTML / JSON / ZIP 可访问
- [x] Filter 可用
- [x] Delete 可完整清理

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

代码与模拟测试口径已满足；第三方真实环境兼容、准确率与成本尚未验收：

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
- [x] Web → Audit → History → HTML / JSON / ZIP → Filter → Delete 本地 E2E 闭环

仍需：

- [x] promptfoo 可作为 declarative regression adapter
- [x] Model Rule 有版本和来源
- [x] Web 更完整展示 identity/routing evidence


# 10. 新一轮工程收尾：不继续堆功能

现在执行 [17 号工程收尾与验收计划](design/17-engineering-closure-roadmap.md)，不以本文件前述历史批次当作待办：

- **A（P0）**：Reference 原子更新与异常保护、显式 Benchmark 失败与不可比状态、单机安全边界。
- **B（P0）**：逐 Probe 实际 Token 计量、缓存/Reasoning 正确口径、未知外部 Adapter 用量、执行前预算与费用表。
- **C（P1）**：审阅 MoonshotAI/Kimi-Vendor-Verifier 官方代码；优先评估参数、工具 Schema 和 Prompt Token 正确性；选择性 Adapter，不复制重型测试。
- **D（P1）**：四个 OSS Adapter 的真实安装/运行兼容性，Web/CLI/报告/历史 E2E 和规则来源复核。
- **E（数据 P0）**：真实 Kimi-K3/GLM-5.2 官方 Reference 与已知模型替换、不同推理档、混路由校准。**需要真实 API 凭据和受控网关，当前未执行**。
- **F（P2）**：满足 A～E 的验收与证据边界后发布版本，停止主动扩充 Probe。

工作方式依旧：**一次只完成一个小任务 → 及时提交 → 回归测试 → PR/CI → 合并**。禁止引入性能压测、定时任务、RBAC、Redis/Postgres/Worker 等无关平台化功能。
