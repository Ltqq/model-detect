# model-detect 唯一执行计划：权威评测主链（2026-10-19）

> **冻结范围与状态**：以 `main@b2351bb` 为初始代码基线。本文取代此前 G0/G1/A～F、K1～K12/S1～S7 的「未来开发排期」，过去的技术文档和已合并 PR 仅作背景。**不得追加一套编号、为完成 PR 数量而增加能力、或者把 CI/模拟数据称为真实模型验收。** 一个里程碑合并后在本文填写交付 PR、证据及是否偏移；尚未实现的功能明确写「待做」。

## 0. 不可更改的产品目标

**用户要做的事**：选模型和测试标准（优先供应商官方公开套件），运行同一套标准对官方/可信 API 与供应商 API 的测试；自动持久化原始评测元数据与脱敏产物；后续复用同版本官方 Reference；在 Web/CLI 中得到协议符合性、能力差异、不可比原因、样本量/成本与中文报告/历史。先纵向打通 Kimi K3 和 GLM-5.3，再通过配置/适配扩展模型。

**产品职责**：model-detect 负责 **规划执行、调用外部原始评测器、保存来源/产物、严格检查可比性、归纳报告和历史**。Pytest/官方 Verifier、lm-eval/Inspect 等成熟框架负责各自原始评分；不复刻评分器，不以简单自编题验证顶级模型“真假”。

**边界**：身份/模型换模/推理强度均属辅助证据，不能认证权重；“官方测试源码”≠“官方发布的成绩”≠“在官方端点实测 Reference”。真实端点调用始终明确授权，成本未知时不得保证费用上限。单用户本地 Web+CLI/SQLite，不开发 TTFT/TPS 压测、Agent 平台、RBAC、自动重试/多层任务恢复/企业计费。

## 1. 已有资产及现在真正缺口

| 已有资产（仅代码） | 仍缺的闭环 |
|---|---|
| 协议/工具/Thinking/JSON/Context/路由/基础能力 Probe，Reference 安全存储、HTML/JSON/ZIP、Web+SQLite | 真正一次运行并在 Web 中获得可解释的官方/供应商对照 |
| Kimi 官方 `tests/params`/`k3_features`/`tool_call_json_schema`/`prompt_tokens` 固定源码适配、JUnit 导入 | 将**原始官方执行结果**纳入对照流程；覆盖限制和版本可追溯 |
| lm-eval Adapter、GLM-5.3 Benchmark、`--log_samples`、离线 snapshot/多任务对照 | 执行产物放临时目录会丢，run→样本→Reference→对比尚未打通；真实数据集/评分器修订不可由用户随意声明为已认证 |
| `test_catalog.py` 和 `evaluation_catalog.py` 两套目录、十余个辅助 CLI | 重复抽象和入口分散；deep 主要增加简单任务题数，不是困难测评 |

## 2. 顺序执行，禁止插队

| 阶段 | 唯一交付物（每阶段完结后合并 PR） | 必须满足的验收 | 不做什么 |
|---|---|---|---|
| **M0 计划冻结** | 本文件作为唯一进度表 | 基线/验收/偏移规则清晰；不增加新模块 | 不复制旧计划 |
| **M1 统一权威目录** | `test_catalog` 作为唯一测试来源；其它目录视图只读取它 | Kimi 官方 4 套与 lm-eval 任务同源；候选高难套件标「未集成」；有小范围回归 | 不再维护双重注册表 |
| **M2 真实运行产物闭环** | lm-eval 运行时**显式选择**保留任务输出和 sample log；可从一份保存的 run 导入一份或多份结果快照 | 用实际产物结构的本地 fixture 端到端验证；缺实际 doc_id/版本/评分器即未知；不丢失证据、不误触付费重复运行 | 不自造分数、不构建新数据库 |
| **M3 官方/供应商比较主链** | 同一任务合同复用 Reference，自动比较双方快照/官方 Kimi JUnit 结果，生成一次性脱敏中文汇总 | 不可比、缺测、部分失败独立显示；无认证来源不标「官方认证」；不把 protocol pass 当身份认证 | 不重复写官方评分器 |
| **M4 Web/历史产品闭环** | 在原 Web 的一个主页面选择日常/官方专项/能力对照；统一查看对照证据和下载报告 | Mock E2E 覆盖“发起/查看/下载/异常”，保持 SQLite/原审计功能可用 | 不另起一套 Web 或任务调度 |
| **M5 有区分度的困难评测** | 从已确认的开源任务/框架里**选择、固定、运行**适合目标模型的困难任务 | 记录任务版本、指标、样本 ID、成本；先证明一个代码/复杂推理专项可用再扩大；高成本默认关闭 | 不把 deep=重复 100 道简单题当完成 |
| **M6 收尾和版本说明** | 精简不用的入口/重复代码，更新 README/功能范围/一页使用指南 | 有代表性安全、评分、Reference、Web CI；验收过的能力与待实测能力分列 | 不加新基础设施、无关 doctor |
| **R 真实官方/供应商验收** | 需有权凭据/预算后分别跑 Kimi K3、GLM-5.3 真实端点，报告来源/误判/费用 | 真实证据可复查，才标「实测通过」；发布标签需用户决定 | **不在 Mock/CI 中发付费请求** |

**完成标准**：M1～M6 每项都有实用路径和对应合并 PR；R 的真实证据单独标注。高成本或不适用的官方专项可明确标未覆盖，但不能让其无限拖延已支持范围的版本发布。

## 3. 每个环节必须执行的「偏移检查」

PR 完成后强制逐项回答（写入本表最后日志）：

1. **目标**：是否直接推进官方评测运行、证据复用、供应商比较、Web/报告之一？不直接推进则必须证明是该路径的阻断修复。
2. **复用**：是否调用官方/开源评分器？是否重复建设已有 Adapter、Catalog、History、Reference？
3. **可证实**：源版本、数据集/样本、指标、费用未知和结论边界是否在真实/Mock 之间分清？
4. **复杂度**：是否加入额外 CLI、状态、兜底或测试框架？能否用已有代码完成？
5. **退出条件**：是否达到表中验收？未达到则不把阶段标完成，直接记录剩余缺口及是否阻断下一步。

判定统一写为 **未偏移 / 偏移已修正 / 存在偏移，停止扩展**。偏移时优先删除/整合新增抽象，而不是在文档中解释为何要继续扩张。

## 4. 执行看板（每批次更新同一表，不追加平行排期）

| 阶段 | 状态 | 代码/验收证据 | 目标偏移判断 |
|---|---|---|---|
| M0 | **代码已合并** | [#105](https://github.com/Ltqq/model-detect/pull/105)，CI 成功，文档替代旧排期 | **未偏移**：只冻结主链、退出标准及复用边界 |
| M1 | **代码已合并** | [#106](https://github.com/Ltqq/model-detect/pull/106)：两目录共用唯一注册表，CI 通过 | **未偏移**：复用已有目录，旧命令仅兼容展示 |
| M2 | **代码已合并** | [#107](https://github.com/Ltqq/model-detect/pull/107)、[#108](https://github.com/Ltqq/model-detect/pull/108)：运行结果保留、清单预检、自动生成多任务快照，CI 通过；真实评测器验收属于 R | **未偏移**：只复用 audit、lm_eval、snapshot 导入器，未新增引擎 |
| M3 | **离线核心代码已合并** | [#109](https://github.com/Ltqq/model-detect/pull/109) CI 成功：已有 CLI 将同套 Kimi 官方 JUnit 与多任务 Benchmark 分栏汇总；多套自动编组/历史归档归 M4 | **未偏移**：沿用原测试、原对照报告，不重复评分 |
| M4 | **进行中，待 CI/合并** | 现有 Web 按本地运行目录比较 Benchmark/Kimi，结果写入现有 SQLite jobs、查看 HTML/JSON/ZIP、历史可删 | **未偏移（待验证）**：一个 POST 入口，原比对函数、JobStore、模板，无新数据库或评测执行器 |
| M5 | 待做 | 经实证选择困难任务 | 待判定 |
| M6 | 待做 | 精简、文档和安全回归 | 待判定 |
| R | 待真实账号及成本授权 | Kimi/GLM 真实 API 与独立真值 | 待判定 |

### 既有完成资产（不作为阶段验收）

[#94](https://github.com/Ltqq/model-detect/pull/94) 精简旧 release-doctor；
[#96](https://github.com/Ltqq/model-detect/pull/96)、[#97](https://github.com/Ltqq/model-detect/pull/97) 两套目录；
[#98](https://github.com/Ltqq/model-detect/pull/98)～[#102](https://github.com/Ltqq/model-detect/pull/102) 快照和导入；
[#103](https://github.com/Ltqq/model-detect/pull/103) 多任务报告；
[#104](https://github.com/Ltqq/model-detect/pull/104) 证据来源边界。


### 本批 M1 目标偏移核对（2026-10-19，提交前）

- 目标：唯一目录让未来执行计划只依赖 `test_catalog`；现有 `evaluation-catalog` 命令仅提供兼容视图，不独立维护任何测试清单。
- 复用：直接读取 `build_test_catalog()`；保留已存在的 benchmark comparability 校验。
- 来源：官方固定 Commit、社区任务、未接入的高成本候选分别标识；所有 `run_verified/results_attested` 仍是 false。
- 复杂度：修改 2 个已有代码模块 + 1 份断言；**没有添加新模块、数据库或 CLI**。
- 退出：目录数量和来源完全一致，相关 CI 通过后填「代码已合并」；否则继续修复，禁止跳到 M2。


### M2-A 里程碑内小步（2026-10-19，提交前偏移复核）

- `model-detect audit --benchmark-profile smoke --benchmark-evidence-dir ./evidence-run-001 ...`：明确要求时将原生 lm-eval 的执行结果、逐题 JSONL 持久化，不再使用会被删除的临时目录；其它默认行为维持原状。使用旧目录直接拒绝覆盖，且在发送任何模型请求之前完成校验。
- 明确风险：原始 sample log **可能包含 Prompt/响应**；不要上传公开仓库，脱敏 Reference 快照仍然不含正文。
- **尚未达 M2 完成标准**：这一步只保留真实产物，后续需复用现有导入器完成「评测成功后自动转换为同版本 Reference」，不加新的独立目录或导入命令。
- 偏移判定：本次修改既有 `audit`/`lm_eval` 接口、路径配置与最小回归，**未偏移**；如 CI 失败需修复后才能合并。


### M2-B 运行结果自动转 Reference（2026-10-19，提交前偏移复核）

- 现有 `audit` 增加可选 `--benchmark-revisions revisions.yaml`，必须同时设置 `--benchmark-profile`、`--benchmark-evidence-dir`；清单 `schema: benchmark-revisions-v1`、`provider_role: official|vendor`、`tasks: {gsm8k: {dataset_revision: ..., scorer_revision: ...}}`。
- 运行前严格检查清单 task 与 profile 任务集合相等、身份角色和修订字段合法；异常不发送收费请求、不创建输出目录。
- lm-eval 正常结束后复用已存在的结果解析、任务合同、sample ID hash 和 `EvaluationSnapshot`，批量保存至 `<benchmark-evidence-dir>/snapshots/<task>.json`；所有任务先完成验证后保存。原始数据仍只保留在用户明确指定的目录。
- **来源仍未经认证**：输入修订由用户声明，即使 role=official 也不属于官方认证成绩；缺样本/版本/评分器则在审计报告标记 `snapshot_import=incomplete`，不计算虚假可比结论。
- 漂移检查：沿用现有 audit、lm_eval、导入器、score/Reference 模型，未增加新的评测引擎或独立入口，**未偏移**。真正官方执行与日志样本兼容性需 R 阶段实测；本阶段只标工程代码可用。


### M3-A Kimi 协议与能力基准分栏汇总（2026-10-19）

- 现有 `compare-evaluation-dirs` 支持可选 `--kimi-official <summary.json> --kimi-vendor <summary.json>`；官方端点和供应商必须同模型、同套件、同固定源码、同一 testcase SHA256 集合。仅在此情况下统计官方端点通过但供应商不通过的数量。
- Pytest 的原始通过/失败由 Kimi 官方代码产生；本项目不重复判题，只对已有状态进行对照。skip/error 显示「不完整」，用例/版本不一致显示「不可比」，不污染 Benchmark 综合分或宣称权重认证。
- 单独 Kimi JUnit 也可生成中文 JSON/Markdown；有 Benchmark 时与分数对照共用一份文件。来源真实性仍记「输入声明、未独立认证」。
- 偏移复核：直接使用已有 `kimi_report` JUnit 校验与 `evaluation_batch_report`、原 CLI；未新增命令/框架。尚需 M4 统一 Web/SQLite 与整条真实端点验收。


### M3 阶段结束复核（2026-10-19）

1. **业务目标**：已有一份同时报告官方 Pytest 协议差异与公开 Benchmark 分数差异的 JSON/中文 Markdown（CLI），没有重新解释官方评分规则。
2. **复用**：`kimi_report._validated_summary`、`evaluation_batch_report`、`compare-evaluation-dirs`；未另建报告格式或评分引擎。
3. **可证实边界**：同模型/源码/套件/用例 SHA 集合才对照；执行 skip/error 为不完整；来源标 `attested=false`，权重身份永不由分数自动确认。
4. **复杂度**：**没有新增 CLI 命令或 Python 模块**；扩展已有命令以支持 Kimi 结果作为可选输入。
5. **阶段退出**：离线工程代码已合并且 CI 通过；当前 CLI 可提供一个 Kimi 官方协议子套件的配对比较，Web/SQLite、多个子套件自动编组和真实环境兼容性未交付，归 M4/R，不能宣称全部产品完成。

**最终判定：未偏移目标。** 从 M4 起只有能推进现有 Web 的持久化/查看/导出才进入当前开发，不继续新增报告辅助工具。


### M4-A Web/SQLite 同一路径（2026-10-19，本批偏移审计）

- 只增加 `POST /api/evaluation-comparisons`：以 `model`、`official_run`、`vendor_run` 和两类布尔选项选择本地评测对照；在**现有 Web 首页**增加简短表单，不新增第二套页面/SPA。
- 数据放在本地 `<state-dir>/evaluation-runs/<run-name>/snapshots/*.json`，Kimi 官方协议汇总可选 `<run-name>/kimi-summary.json`；只接收不包含斜杠的目录名，阻止路径穿越及符号链接。该对比接口**不会运行模型或第三方工具，不消耗 Token**。
- 自动复用 `compare_directories` 和 Kimi JUnit 比较，检查两端 **model 一致、role 分别是 official/vendor**，写入已有的 `JobStore`（`kind=comparison`）。中文报告由 `/reports/<job>` 查看，现有 JSON/ZIP 下载与历史删除也支持 comparison。
- 结果来源尚未经独立认证，不可用 `role=official` 标签证明上游真实身份。任务文件必须事先由 CLI 真实运行或可信导入生成。
- **目标偏移检查**：符合 M4 的已有 Web/SQLite/对照报告三者直接连通；没有加后台调度器、评测框架、账号体系或第二张历史表。最终 CI 和 Web E2E 通过后才标本环节合并；之后仍需审查是否有 M4 整体未解决的关键断点。
