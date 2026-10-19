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
| M4 | **工程闭环已合并；待 R 实测** | [#111](https://github.com/Ltqq/model-detect/pull/111) Web 离线对照及历史；[#113](https://github.com/Ltqq/model-detect/pull/113) Web 审计保留快照；本批校验 Web 所选模型与原始证据一致 | **偏移已修正**：关闭重复 #112，未新增 Web/SQLite/评分器；真实官方身份与题集验证仍属 R |
| M5 | **Deep 数学困难任务代码已合并；等待完整实证** | [#117](https://github.com/Ltqq/model-detect/pull/117) v2 Deep 包含 `minerva_math500`；本批补充固定上游源码/数据集、CLI/Web 提示，未接入昂贵多模态/Agent | **未偏移**：复用 lm-eval 原始生成式评分，未新建引擎或重复考题 |
| M6 | **进行中：轻量默认值与必要回归** | 默认关闭第三方 proxy-sleuth subprocess；保留明确 opt-in；核对双版本 CI、真实对照报告与 README | **未偏移（待 CI）**：减少非核心开销，没有删协议/能力/Reference/证据 |
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


### M4-A 统一 Web 离线对照与历史（2026-10-19）

- 在原首页增设「离线能力对照」，直接指定本机已有官方端点/供应商快照目录，按需附加一对 Kimi `summary.json`，**没有 API Key、不会运行或重试模型调用**。
- 复用 `compare_directories`、`compare_kimi_official_protocol_summaries` 和 `write_comparison_report`。根据声明的角色检查官方/供应商顺序；缺少配对返回 400；可比/不可比/不完整直接展示，来源认证状态始终为 false。
- 现有 `JobStore` 记录 `kind=comparison`，沿用 `/api/jobs` 历史、`/reports/{job_id}` 中文 HTML、`/api/audits/{job_id}/report` JSON、ZIP 下载与删除。仅将既有中文 Markdown 安全 HTML 转义成预览，不新造报表算法。输出目录归原报告根目录，历史删除同步清理文件。
- 现实边界：文件路径由**本地单用户**提供、对应服务端磁盘；请勿公网暴露本地 Web 或存储敏感 JSON。已保存 lm-eval 运行目录需要先生成快照；接下来还需 Web 内选择评测执行方式/真实 Kimi 引擎。
- **偏移判定：未偏移（待 CI）**。直接推进 Reference→官方/供应商对照→历史→报告与下载，修改既有三个模块和相关回归，无数据库迁移、不引入新 Web/任务系统。


### M4-B 从原 Web 检测直接保留 Reference 供后续对比（2026-10-19）

- 现有“开始检测 → 高级 Benchmark”可选「保留评测结果并生成快照」，需要本机 YAML 修订文件及启用 Benchmark。Web 接任务**先按档位核对 task 修订集合**，再排队，错误文件直接 400，不发收费请求。
- 用户确认后运行旧 audit、旧 lm-eval，并在 `state_dir/benchmark-runs/<audit_id>` 保存原始 JSON/逐题 sample；任务结束后基于相同任务版本清单生成 `snapshots/*.json`，原首页历史中可一键选作官方或供应商。真正网络调用/费用只在用户点击运行时发生，Mock E2E 不发付费请求。
- SQLite 使用原 audit job `meta` 字段记录生成快照目录与状态；删除 job 连同原始日志/快照一并删除。原始日志不自动放进中文报告和 ZIP；含 Prompt/答案，请勿公开。清单数据仍为人工声明，`source_verified=false`。
- **偏移检查**：推进“Web 评测 → 可保存 Reference → 官方/供应商对照 → 历史报告”；只扩展原审计配置与既有模板/删除逻辑，不另起后台服务/数据库。此前 #111 离线对照功能已合并；此次不会声称 Web 已经直接运行官方 Kimi 原始 Pytest 或深度 Benchmark，相关能力仍待 M5/R。


### M4-C 一致性与去重验收（2026-10-19）

- #111 和 #113 已经分别提供了 Web 离线对照历史与 Web 审计保存真实 Benchmark 产物的工程主链，因此并行 PR #112 属于**重复开发**，按本计划明确关闭，不合并。
- 检查发现提交到 Web 的显示用 `model` 尚未和本地 Benchmark Snapshot / Kimi 官方 JUnit 内实际记录的模型严格匹配。此问题可能把 GLM 的显示标签套在 Kimi 的成绩上，属于 P0 证据真实性问题。
- 本批在现有比较逻辑增加 **可选 expected_model** 校验；只有 Web 端强制提供，保持原有 CLI 无显式模型参数时的兼容性。模型不一致时请求失败、不会保存误导性 SQLite 历史。
- **偏移判定：偏移已修正**。不新增用户命令、API、存储表、评测器。真实官方数据来源仍不得由 Snapshot 自声明标记“已认证”。


### M5-A 解决 Deep 只有简单题的天花板问题（2026-10-19）

- 经核对 EleutherAI `lm-evaluation-harness v0.4.13` 的公开任务清单，`minerva_math500` 是生成式数学评测，与现有 `local-chat-completions` Adapter 及 GLM-5.3 专项一致；不引入不受支持的多选 loglikelihood 评测。
- `deep` 正式任务调整为 `truthfulqa_gen`、`ifeval`、`minerva_math500`；`standard` 仍保留 GSM8K。**这里是更高难的任务类型，而不仅仅多抽样 100 道基础题**，但这不证明当前顶级模型一定被有效区分。
- 评测版本 bump 为 `lm_eval_profiles.yaml version: 2`，使旧 Reference 不会与新 Deep 任务合同混比；依赖 `lm-eval[math]` 提供 SymPy 评分支持，不自动安装或下载收费模型。
- 统一从 YAML 读取任务难度（不重复写 Python 评分规则）；来源标记依然是 `community_benchmark_adapter`、`results_attested=false`，并非 Kimi 官方测试。
- **偏移复核：未偏移**——只改变一个现有深度档位的实际任务覆盖，复用官方上游评分器；复杂推理/代码与真实样本成本校准仍列 M5/R，待进一步实证选择。


### M5-B 来源与依赖可追溯（2026-10-19）

- 经 GitHub 官方仓库 **`EleutherAI/lm-evaluation-harness@v0.4.13`** 实际文件核对：`lm_eval/tasks/minerva_math/minerva_math500.yaml` 指向 `HuggingFaceH4/MATH-500`，是生成式任务；不是声称厂商正式认证。
- 在同一份 `lm_eval_profiles.yaml` 中声明任务源码 Tag、原始任务路径、数据集来源和 `lm-eval[math]==0.4.13` 可选依赖；唯一 `test_catalog` 从 YAML 投影，不重复抄入第二张任务表。Web/CLI Deep 描述提示额外数学依赖和更高成本。
- 真正执行时的数据集修订、题目 ID、评分器版本仍必须由 M2/R 的评测环境固定并核验；`source_tag` 只说明计划使用的上游实现，不能替代实装取证。代码配置已核对来源，**实际顶级模型区分度未验收**。
- 本项目标偏移：**未偏移**，属于困难任务可追溯要求，未添加运行器、身份分数或重复抽象。剩余困难代码/Agent 基准按成本和真实需求再评估，不能凭新增题名宣称全量覆盖。


### M6-A 精简入口与默认开销的目标偏移复核（2026-10-19）

- 原 `AuditConfig.proxy_sleuth_enabled=true`、WebRequest 默认 true，Web 复选框默认 checked；普通审计会无意启用外部 OSS 子进程，与单用户轻量目标不符。改为 CLI 默认关闭、Web 默认关闭，已有 `--with-proxy-sleuth` 与 Web 显式勾选保持有效；兼容显式 YAML true，不需要新命令/新框架。
- **保留**原生协议/模型能力/Reference、可选官方 Kimi、lm-eval、SQLite/报告、错误分类、安全脱敏。不是删掉 OSS 功能，仅调整默认；成本未知依然标 unknown。
- 回归以选项模型与现有 Web 页面为准；执行后必须 CI 3.11/3.12 全绿，否则不合并。
- **漂移判断**：减少不必要的运行路径，不新建引擎、评分器、持久化，未偏移。M6 尚需功能说明/交付命令梳理和最终工程审查；真实端点属 R，不能冒充通过。
