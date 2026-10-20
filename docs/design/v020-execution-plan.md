# model-detect v0.2.0 唯一执行计划（可更新）

状态：2026-10-19，P0 正在执行。**本文件可以更新进度、PR、验收结果；不得改动 [冻结产品宪章](product-charter-v1.md) 的目标。** 旧 17 号 M0～R 计划保留历史，但后续执行以本文件为准；减少文档重复，不再开新的大阶段。

## 基线与当前真实程度

main 为 M6 工程收尾版本（#122）；已有 Web/SQLite/报告、原生协议、lm-eval 对接、Kimi 固定官方测试子集、GLM 专项和历史 Reference/对比；具备 CI。已有 GLM-5.3 2026-10-13 实测，但随后发现并修复过规则误判及任务可比性缺陷，**修复后原始复测证据不足**。不应把 Mock 当真人，不应要求用户提供官方 API。PR #123 轮子隔离安装检查 CI 已通过但尚待合并；PR #124 不依赖官方 API 路线尚待整合，避免冲突 PR。旧 17/18/20 等继续作为历史证据，不用于新排期。

## 决策表：要 / 不要 / 暂缓

| 模块 | 决策 | 原因和处理 |
|---|---|---|
| Python Web、CLI、SQLite、中文 HTML/JSON/ZIP | **保留** | 自用完整闭环；整合入口 |
| 通用协议探针、真实错误响应、少量官方规则 | **保留精简** | 核心；避免各模型重复实现 |
| lm-evaluation-harness | **保留唯一主力能力引擎** | 固定/核验依赖、任务、评分器；保留可追溯 samples |
| Kimi Vendor Verifier | **保留专项** | 直接运行固定官方原测试源码；不是所有模型都必须走 |
| Reference / 公开数据 / 历史对比 | **合并精简** | 官方公开聚合=背景参考；同题同参数=可比；不要求官方自采 |
| GLM53 专项 CLI / 双端点工具 | **保留兼容、逐步抽通用逻辑** | 不急删已付费证据回放；单端主流程优先 |
| capability_lite | **降级 Smoke** | 不计入权威能力总分；成熟评分器优先 |
| provider_hypotheses、overall_score 和伪身份概率 | **退出主结论** | 可误导；先检查历史兼容再删除输出 |
| proxy-sleuth、promptfoo、fingerprint adapter | **默认停用，待引用审计后候选删除** | 缺新模型真值校准且功能重叠；先证明独有价值 |
| 自研 Coding Sandbox、回归 YAML 扩展、重复评价引擎 | **候选移除或隔离** | 维护重；有唯一用途才留 |
| TTFT/TPS/RPM、企业用户/账号、Agent、复杂调度/多数据库 | **明确不要** | 超出产品宪章 |

## 执行任务（严格顺序，一个小 PR 一个验收）

### P0：基线盘点与删减清单（零付费）
- [ ] 逐文件列代码入口、Web 路由、依赖、测试、持久化引用与真实独有价值；分 keep/merge/quarantine/delete，未证明无引用不得删除。
- [ ] 固化现有 CI、快照与 SQLite 兼容回归；PR #123 只在 CI 和 code review 通过后合并。
- [ ] 将旧 17 号标为历史并链接本文件，避免多计划互相竞争（必要时仅改链接，不删除历史证明）。
**退出**：逐路径删减矩阵 + 全量测试、构建绿；不得修改冻结宪章。

### P1：统一模型目录和协议（零付费）
- [ ] 核实 GLM-5.3、GLM-5.3-Flash、Kimi-K3、DeepSeek V4/V4.1 的厂商文档、有效 API model ID、版本/别名、思考/工具/JSON/SSE；每项有来源与核实日期，别名不等于实际权重。
- [ ] 一套协议执行器 + 小配置；未知参数返回 UNKNOWN/NOT_APPLICABLE；固定错误码/429/超时反例。
- [ ] 针对新模型用模拟协议端点做 offline fixture；不要硬编码未经核实的模型规格。
**退出**：五目标模型可在同一单端流程选择并完成支持项/不适用项的确定性回归。

### P2：精选开源检测器和减法（零付费起步）
- [ ] 对实际代理探测项目（proxy-sleuth 等）检查固定 commit、许可证、执行合同、真实测试用例和覆盖；与现有协议探针对照，**只选能证明独有且可靠的功能**，没有则不接。
- [ ] lm-eval 固定依赖/任务/评分器，验证离线预检，低样本仍标不确定；Kimi 官方 Pytest 子集保留可选。
- [ ] 逐 PR 删除确认无独有价值的适配/分数/UI，避免数据迁移破坏；按测试和历史数据兼容门槛验证。
**退出**：单核心探针 + lm-eval + 有价值的 Kimi 专项；简化 CLI/Web，不多造评分器。

### P3：公开证据和报告（无需官方 API）
- [ ] 优先 Kimi 和 GLM、DeepSeek 可核实的官方公开结果；存元数据：发布方、URL、发布日期/commit、确切版本、任务、样本数、评分方法、参数，缺字段记 unknown。
- [ ] 区分已发布汇总背景参考与逐样本同条件 Reference，不一致时禁止直接做差并宣布换模；真实公开结果做非敏感 fixture 测试。
- [ ] 统一报告四段：协议、能力、异常、证据等级；历史、复测和导出维持兼容。
**退出**：仅用供应商 URL/Key/模型能得到有来源、不会伪装官方认证的结果；无公开成绩也可运行协议检测。

### P4：单端可用性验收与发布（供应商实际调用由使用者控制）
- [ ] Python 3.11/3.12 CI、隔离 wheel、Web/SQLite/历史/删除/导出/备份恢复，401/429/超时和 Key 泄露测试。
- [ ] 离线确定性样本覆盖支持项、异常与不可比；有授权供应商时再做小额真实请求，不把它伪装成官方对照。
- [ ] 报告说明费用估计、未知成本、模型身份边界；确认后才打 v0.2.0 Release。
**退出**：单机自用闭环可信，五个型号配置齐全；未实测能力明确标注。

## PR 执行规约

每个小 PR：范围/删减价值 → 保留旧样本回放或兼容测试 → 修改 → CI → 路线偏移判定 → 合并。不得开发新 Agent、评分引擎或协议管理平台。**后续只更新本计划勾选状态、PR 链接和具体证据，不修改冻结宪章**。


## P0.1 已核实的代码引用与开源复用审计（2026-10-19）

此表基于逐文件读取主线 `audit.py`、`cli.py`、`webapp.py`、`config.py`、`scoring.py`、`adapters/lm_eval.py`、`regression_promptfoo.py`、`probes/provider.py` 和评测 profiles；只代表已核实的入口/引用，非全部仓库引用图。**当前没有证明任何候选文件可安全物理删除。**

| 模块/路径 | 实际引用与证据 | 决策 | 下一步动作 |
|---|---|---|---|
| `model_detect/audit.py` | 主执行器依赖 protocol/integrity/context/routing/capability/reference/OSS，且计算单一总体分数 | **keep/merge** | 单入口保留；先把非核心执行变显式 opt-in，保持旧 config/报告兼容 |
| `model_detect/cli.py` | 暴露 fingerprint/upstream policy/coding/regression/benchmark/reference，最终打印整体分数和 provider hypothesis | **merge** | 简化 Quick/Standard 首要参数；旧 CLI 选项先弃用提醒，不直接破坏脚本 |
| `model_detect/webapp.py` | 请求模型仍含 proxy/coding/regression/disallowed_upstreams，使用现有存储报告 | **keep/merge** | 前台隐藏未验证高级字段，不动旧历史记录读取 |
| `model_detect/scoring.py` | identity 35 / protocol 20 / integrity 15 / context 10 / routing 10 / capability 10 加权；基于自定义身份/路由推断给 final verdict | **quarantine** | 退出新报告主结论；先补旧文件加载和升级兼容测试 |
| `model_detect/probes/provider.py` | HTTP header/body provider hypotheses 与上游政策；被 audit 及 Web 引用 | **quarantine** | 不以概率判模型真实身份；证据可留但不进入准入 PASS/FAIL |
| `model_detect/adapters/lm_eval.py` + `data/lm_eval_profiles.yaml` | 已直接执行 EleutherAI 原始引擎，固定标准任务和结果读取；与自研评分不重复 | **keep** | 固定/核验版本、CLI 发包参数与原生评分；不自研数学分数 |
| `model_detect/regression_promptfoo.py` + `adapters/promptfoo.py` | 主 `audit.py` 直接调用，非孤立死代码 | **quarantine** | 不作为 V2 默认路径；检查 Web/CLI/YAML/测试/历史引用后决定删除或独立归档 |
| `adapters/proxy_sleuth.py` | `audit.py` + `cli.py` 仍引用，按现有配置默认关闭 | **evaluate/quarantine** | 检查真实运行成本、固定版本、独有协议/混路由能力后做去留决策 |
| `adapters/fingerprint.py` | `cli.py` 与 `webapp.py` 直接引用 | **quarantine** | 只有已知真值校准通过才允许参与身份结论，否则候选删除 |
| `probes/capability.py` / capability_lite | `audit.py` 执行自研能力题 | **keep as smoke** | 降级为低成本可用性探测，不进入正式能力评分 |
| `probes/coding.py` / sandbox | 主执行器依赖并受 opt-in 控制 | **evaluate/quarantine** | 若成熟 Benchmark 能覆盖用户场景则删除沙箱；先审计依赖和测试 |
| `storage.py`、`reporting.py`、`references.py` | 已有 Web/SQLite/历史/报告/Reference 基础 | **keep** | 禁止重建第二套 DB/报告系统；保留既有证据格式 |
| `kimi_cli.py` / Kimi Vendor Verifier | 固定官方子集的原始 Pytest 适配 | **keep** | 非默认收费路径，保留原测试器 |
| `glm53_cli.py` | 历史 GLM 真实付费数据与 replay 关联 | **merge, do not delete yet** | 提炼可复用通用部分，继续支持旧证据只读复算 |

### 强制执行：开源优先、禁止重复造轮子

1. 对每个拟新开发的测试器/评分器，先记录现有开源项目及固定版本、许可证、接口、维护状态、测试证据、调用成本；若成熟实现满足需要，必须复用，不允许自行复制功能。
2. 自研仅允许保留**必要的适配胶水、官方参数规则、证据规范、UI/报告**；绝不自研新的数学/代码 Benchmark 评分器、模型身份概率器。
3. `proxy-sleuth` 等不能因为 README 声称七层检测就无条件选为主引擎；必须用确定性正反案例证明与已有代码相比的**独有贡献**及可靠性。
4. 删除顺序固定为：依赖和历史格式回归 → 退出默认入口 → 删除调用/选项 → 删除适配器 → 移除测试与文档冗余；任何一步失败立即停止，不损坏用户数据。
5. 每次新增依赖需论证“比当前依赖更少、更稳、更可维护”，不为了多一种能力并行维护多个引擎。

**本小步验收**：完成初步代码引用矩阵及上述硬性开源复用规则；尚未达到整个 P0（全仓文件图、兼容测试、物理删减）的退出条件；不得勾选完整 P0 或声称已清理代码。


## P0 代码执行检查点（2026-10-19）

- [x] [#123](https://github.com/Ltqq/model-detect/pull/123)：隔离环境安装 wheel，在源码目录外运行 CLI、检查打包的 Web 资产；3.11/3.12 CI 通过并合并。
- [x] [#125](https://github.com/Ltqq/model-detect/pull/125)：冻结产品宪章与本执行计划，加入 P0.1 已核实的引用/删减矩阵；3.11/3.12 CI 通过并合并。
- [x] [#126](https://github.com/Ltqq/model-detect/pull/126)：CLI audit 主展示移除未校准总体分数/供应商身份概率，改为逐项结果计数；保留历史报告结构；3.11/3.12 CI 通过并合并。
- [x] [#127](https://github.com/Ltqq/model-detect/pull/127)：Web 历史列表不再突出旧加权总分，保留既有 JSON/SQLite meta 字段；同步更新 E2E 断言，3.11/3.12 CI 通过并合并。
- [ ] **P0 全仓关闭条件仍未达成**：需要可重复的仓库全文件/引用/许可证清单及旧历史兼容回归；尚未物理删除 promptfoo/proxy-sleuth/fingerprint/Coding Sandbox，不将“候选删除”描述为已删除。
- [ ] 主报告 `reporting.py` / `interpretation.py` 仍有类别分数、Provider/Identity 强证据措辞，下一批需先确认是否会误导，依据旧报告的兼容性选择“新报告降级展示、旧 JSON 保留”。
- [ ] P1 的五模型真实模型 ID/别名与官方来源仍未逐项核实；不能将规划模型当作已适配通过。

本检查点偏移判定：**未偏移**（优先减少不可信主结论，不添开源引擎/评分器，不破坏历史数据）。后续只修改执行计划状态，不改冻结产品宪章。


## P0 中文解释可靠性检查点（2026-10-19）

- [x] [#129](https://github.com/Ltqq/model-detect/pull/129)：新 HTML 报告首页改为逐项 PASS/FAIL/ERROR 与身份未经独立认证，保留历史 JSON/SQLite；Python 3.11/3.12 CI 通过并合并。
- [x] [#130](https://github.com/Ltqq/model-detect/pull/130)：去除“必须自行运行官方 API Reference”的指导和统计指纹匹配等于权重身份证明的表述；对应旧文案测试更新并通过双版本 CI。
- [x] [#131](https://github.com/Ltqq/model-detect/pull/131)：仅因统计指纹异常不再自动拒绝准入，改为人工复核并增加回归；双版本 CI 通过并合并。
- [ ] **遗留**：Provider 禁止上游策略、评分模块内部加权以及身份/参考来源在其他报告子区块的表述仍需审查。P0 全仓路径和安全物理删减尚未完成。

方向审查：未偏移。上述工作减少误导性主结论，保留历史存储格式，没有引入新引擎。冻结的产品宪章未修改。


## P0/P1 进度检查点（2026-10-19）

- [x] [#135](https://github.com/Ltqq/model-detect/pull/135)：Web 不再把官方端点 Reference 写成使用前提；3.11/3.12 CI 通过并合并。
- [x] [#136](https://github.com/Ltqq/model-detect/pull/136)：新增独立 GLM-5.3-Flash / FlashX 和 DeepSeek V4.1-Flash-1017 的有来源规则及离线测试；通过双版本 CI 并合并。DeepSeek legacy Flash model ID 路由至 V4.1 的依据：官方 2026-10-17 changelog。
- [x] [#137](https://github.com/Ltqq/model-detect/pull/137)：旧 DeepSeek V4 规则限定到 V4 Pro，不用宽泛通配捕捉 V4.1 Flash；双版本 CI 通过并合并。
- [ ] P1 **不视为完成**：五型号配置已有初步规则，但全部官方参数与复杂工具/多模态行为未逐项验证，供应商真实运行尚缺；先完成单引擎离线回归和适用性校验。
- [ ] P0 **不视为完成**：全仓引用和旧历史数据迁移回归、第三方候选模块物理删减仍未完成；这部分不能因 P1 有进展而跳过。

本批 Review：**未偏移**。仅新增小型模型数据规则，复用已有 `rules.py`，未开发新引擎；没用官方 Key、没消耗模型 Token；产品宪章仍冻结。


## v0.2.0 交付收敛门槛（2026-10-19；覆盖本计划的执行顺序，不改变冻结宪章）

**从此禁止无期限地修修补补。唯一目标：一名用户能输入供应商 URL/Key/model，运行 Quick/Standard，看到证据清晰的中文报告并复测；Deep 依赖成熟第三方评分器、严格 opt-in。**

执行工作包及顺序（每包独立 PR、CI、方向审查）：

- [ ] **D0 清理完成**：完整映射 Git 追踪文件、入口和引用；审查兼容并明确 keep/merge/quarantine/delete。移除确无独有价值的重复适配/不可信评分主入口；旧 JSON/SQLite 只读兼容，不擅自清历史。
- [ ] **D1 五模型协议闭环**：GLM-5.3、GLM-5.3-Flash、Kimi-K3、DeepSeek V4 Pro、V4.1 Flash 均复用统一协议引擎；每个 model ID/别名、支持或未知参数、来源、日期和确定性正反例写入测试；不需要官方 API；参数未知不可判 PASS。
- [ ] **D2 开源能力测试**：只选经实测和固定版本的 lm-evaluation-harness 原评分器、适用时 Kimi Vendor Verifier 官方 Pytest；不要开发新题库/评分引擎。Quick 只做冒烟，Standard 提供有限明确测试，Deep 才做付费高成本 Benchmark；启动前展示请求/Token 的估计及误差边界。
- [ ] **D3 公开参考证据**：官方发布成绩、社区发布成绩、用户同条件逐样本 Reference 分三类；必须记录 URL、发布时间/版本、任务、评分器和条件缺口。聚合分数不冒充同题实测，更不做“真假百分比”。
- [ ] **D4 v0.2.0 验收发布**：单用户 Web/CLI、SQLite、历史复测、HTML/JSON/ZIP 导出、异常 401/429/timeout/无效 SSE、安装轮子、备份恢复、密钥脱敏、3.11/3.12 CI；五模型 *配置和离线协议* 验收。真实供应商端点未提供时标注“未实测”，不阻塞离线可用版但不得伪称渠道验证通过。

**完成即停止 v0.2.0 范围扩张**：五模型均可选择并在统一单端流程运行已支持检测项；协议、能力、异常、证据局限四段报告齐全；缺项明确 UNKNOWN/NOT_APPLICABLE；历史/导出正常；测试全绿；无需官方 Key。不存在权重认证、全视觉/Agent 测试或性能压测等隐藏发布条件。

**已完成但不能重复统计为新成果**：#123–#140 的包安装、UI/报告去误导、模型配置、基础 Chat 和 SSE 正反例回归已合并；这些不等于 D0 全仓安全删除、D2 实测、D3 官方公开数据入库、D4 真实端到端验收。接下来的 PR 优先解决这些缺口；只修既有简单措辞不算里程碑。

**每个 PR Review 必答**：该 PR 是否减少未交付清单？复用了什么现有开源实现？做了什么离线/CI 证据？是否破坏旧报告？如不能证明有交付价值，就不继续添加。产品宪章 v1 不修改。


## v0.2.0 最终收敛执行令（2026-10-19；只更新本计划，不改冻结宪章）

**唯一目标**：交付单人本地可用的五型号供应商检测工具；验收达标后停止 v0.2.0 功能扩张。不要因为偶发小问题而无限增设新模块。此处将原 P0-P4 按以下最短交付路径执行，不能把工程 CI 当真实渠道验收。

### 实施优先级与阻断门槛

1. **P0 真减法**：全仓列出模块引用、第三方许可证、历史报告/SQLite 兼容性；对重复适配器先退出默认功能再按独有价值裁撤。必须至少交付实际可验证的代码删减，不能只改 README/报告。保留历史只读导入，禁止无迁移直接删除字段。
2. **P1 五型号协议闭环**：GLM-5.3、GLM-5.3-Flash、Kimi-K3、DeepSeek V4 Pro、DeepSeek V4.1 Flash，统一规则选择和模型版本/别名；已核实官方规则做断言，未知明确 UNKNOWN/不适用，覆盖 200 但结构错误、SSE 空流、401/429/超时与工具/JSON/思考差异的离线反例。
3. **P2 现成开源评分**：lm-evaluation-harness 固定可重现版本和真实任务评分；Kimi 官方 Pytest 只用于适用模型；其他 OSS 项目须提供其开源许可证、固定版本、独有价值和受控正反样例，证据不足即不集成。Quick/Standard 不默认触发高价 Benchmark。
4. **P3 公共证据**：先完成来源可追溯的官方/社区公开成绩小目录（不能虚构分数），明确 model revision、task/dataset/scorer、设置和是否同条件；公开总分只作背景，不做未经验证的同题差分；单供应商结果仍可独立出中文报告。
5. **P4 验收发布**：安装 wheel、Web/CLI、SQLite 历史/导出/删除/恢复、敏感信息脱敏、失败/未知分支、五型号模拟端点回归全绿；实际渠道是否符合预期只能由授权真实请求证实，缺少时清楚标“未实测”。发布前冻结新增功能并审查未解决阻断缺陷。

### 用户级最终验收清单

- [ ] 只输入待测 Base URL、API Key、Model ID、Quick/Standard/Deep 档位；不要求官方 API、GPU 或管理员账户。
- [ ] 五目标型号独立配置有确切来源、时间、别名解释，单套通用协议引擎能报告 PASS/FAIL/UNKNOWN/不适用。
- [ ] 必选协议项有离线正反例；错误/429/超时/空 SSE 绝不显示 PASS；模糊模型行为不冒充身份鉴定。
- [ ] 深入能力评测复用固定的真实开源评分器，并展示任务、样本、版本、费用/Token 使用局限；不自研评分引擎。
- [ ] 用户无官方端点也能看到有来源的公开参考资料及明确的可比性标注。
- [ ] 中文报告的四组结论（协议、能力、异常、证据）和 SQLite 历史、复测/导出功能可以在本机安装包直接用。
- [ ] 安全和升级：API Key 不入仓库/报告/SQLite，旧历史能加载，CI 3.11/3.12 和 wheel smoke 通过，v0.2.0 正式 Release。

### 开发纪律

每个小 PR 必须附：复用来源/无需新轮子的理由、改动范围和删减价值、离线测试/CI、历史兼容性、与产品宪章对照。**发现不影响最终验收的想法留到未来候选，不加进 v0.2.0**。当前历史 M/G/K/R 路线仅保留供回溯，所有待办和完成证据回写本文件。真实结果没有跑过绝不标已验收。

### 既有已合并成果

#123、#125～#140 已完成各自小步（请以 GitHub PR/CI 记录为准），包括 wheel smoke、模型 Flash 配置/别名、Chat 结构与 SSE 错判修复；它们**不等于**上述全部产品级验收完成。


## 执行检查点：2026-10-19 第二轮交付（P0/P1/P3/P4 并行收敛）

已验收并合并，均经过 Python 3.11 / 3.12 CI：

- [x] [#149](https://github.com/Ltqq/model-detect/pull/149)：v0.2.0 停止功能扩张的最终验收标准与顺序写入本计划。
- [x] [#150](https://github.com/Ltqq/model-detect/pull/150)：五目标型号共享规则引擎，目录、来源与更新时间统一离线回归。
- [x] [#151](https://github.com/Ltqq/model-detect/pull/151)：DeepSeek V4.1 Flash 1017 官方 HLE 42.6 / Terminal-Bench 4.0 42.3，背景参考，禁止同题未验证比较。
- [x] [#152](https://github.com/Ltqq/model-detect/pull/152)：Z.ai 官方 GLM-5.3 / Flash 模型卡 DeepSWE 66.9 / 63.4 的公开背景参考。
- [x] [#153](https://github.com/Ltqq/model-detect/pull/153)：DeepSeek V4 Pro 0813 官方 DeepSWE 62.7，和 V4.1 版本隔离。
- [x] [#154](https://github.com/Ltqq/model-detect/pull/154)：Web 移除未校准的 proxy-sleuth 身份猜测和禁止上游指纹下拉框，旧后端历史格式保留。
- [x] [#155](https://github.com/Ltqq/model-detect/pull/155)：wheel 内容与源码目录外安装后均校验五模型 YAML、公开成绩目录，双版本 CI 全绿。

**现状及不可越界的验收判断**

- 五型号初步规则、离线审计流水线、中文历史报告、官方公开背景参考现在均有实现和自动回归。已存在的五模型 HTTP MockTransport E2E 是**真实代码路径的模拟端点验证**，不是付费 API 的能力验证。
- 目前公开参考目录具有 Kimi K3、GLM-5.3、Flash、DeepSeek V4 Pro 和 V4.1 Flash 的型号覆盖；公开 Benchmark 多数用不同 Harness 和不明样本条件，**不声称和本地 lm-eval 严格可比**。
- P0 的剩余候选适配器（proxy-sleuth、fingerprint、promptfoo）还在后端/CLI：移除 Web 入口不等于物理删代码，必须先盘点独有能力、许可证、历史兼容和引用。
- 真实端点的工具/推理细节、开源 lm-eval 完整原生运行和真实供应商复测缺授权测试环境/配置；**不标已通过，也不创建正式 Release**。无官方 API 不是阻断，真实供应商调用仍需用户自己提供渠道凭据及成本授权。
- 下一优先：P0 代码全引用/OSS 独有价值审查与确定可删项；P2 评分引擎固定依赖和离线完整输出验收；P4 用户本机数据恢复和可控付费试验的最后一公里。没有证据时维持 UNKNOWN。

此检查点是执行计划状态更新，不修改冻结产品宪章，不创造新的功能阶段。


## 测试交付收口检查点（2026-10-19）

本轮已经经 Python 3.11 / 3.12 GitHub CI 双绿并合并：

- [x] [#158](https://github.com/Ltqq/model-detect/pull/158)：SQLite 旧审计历史的原生备份/恢复确定性回归（旧 meta + report_path）。
- [x] [#159](https://github.com/Ltqq/model-detect/pull/159)：SSE 必须包含有效 choices.delta；无效 JSON、错误响应、没有 Delta 的流式帧不再虚假 PASS。
- [x] [#160](https://github.com/Ltqq/model-detect/pull/160)：以供应商单端测试替代过时的双端官方 API 依赖门槛，并提供分层发布检查清单。
- [x] [#161](https://github.com/Ltqq/model-detect/pull/161)：`python scripts/acceptance_check.py` 零费用交付自检：五型号配置、SQLite、报告落盘；已加入双版本 CI。
- [x] [#162](https://github.com/Ltqq/model-detect/pull/162)：README 提供自检命令与其严格边界。

**可交付测试的准确含义**：当前代码的离线单机工程自检/全量 CI 可以交付测试人员执行；已配套模拟供应商审计 E2E 与明确的正式渠道验收清单。**不得推导**为五个实际中转供应商已通过、第三方原始 lm-eval 任务已在真实 API 上完整执行、所有冗余 OSS 代码已删或正式 v0.2.0 Release 已发布。

正式发布前阻断项仍保持待验收：
- [ ] P0 可证明安全的非核心适配器物理删减或有独有价值的明确保留决策（全仓引用、许可证、历史兼容先查）。
- [ ] P2 固定版本 EleutherAI 原始评分器 + 适用时 Kimi 官方子测试实际环境运行证据，结果按任务/样本/评分器说明；不得用 Adapter Mock 冒充。
- [ ] P4 在目标实际机器安装、备份恢复，以及至少一个授权供应商端点的受控小额调用和中文报告/下载/历史验收；五型号真实端点覆盖未测者应标未实测。
- [ ] 上述真实证据与安全门槛满足后，才标记“正式 Release”；本检查点阶段可称“离线工程测试可交付”。

产品方向审核：**未偏移**，没有修改冻结宪章，也未新增评分引擎、企业服务、性能压测或收费模型自动调用。

## OSS 原始链路与交付测试检查点（2026-10-19）
- [x] #164 lm-eval 无实际有效评分任务不得标完成。
- [x] #165 官方 EleutherAI lm_eval[api]==0.4.13 已在 GitHub Actions 原生安装并启动。
- [x] #166 OSS 取舍与兼容隔离决策，见 [开源适配审计](../oss-adoption-decisions-v020.md)：promptfoo 保留旧 YAML 回归，proxy-sleuth / fingerprint 标为实验性，默认不启用；未证实无引用不得物理删掉，避免破坏历史。
- [x] #167 真正运行 EleutherAI 原版评分器：本地 JSONL 任务、localhost OpenAI 兼容 Mock、原版 exact_match 分数及 results JSON，零付费 API。
- [x] #168 删除废弃的 Web provider-guess 模板数据构造。
- [x] #169 真正 checkout Moonshot Kimi-Vendor-Verifier 固定提交并检查四组官方 Pytest 源目录，零付费 API。

**工程交付判定**：原始 OSS 可执行性 / 合成评分链路、五型号模拟审计、SQLite 备份恢复、wheel 安装和离线自检均有 CI 证据；可交付人工测试。合成分数不是任何厂商的能力实测，Kimi 官方代码校验也不等于真实供应商通过协议测试。

**仍需真实凭据的门槛**：使用者在授权环境完成单供应商 API Quick / Standard，记录用量、费用、参数与异常；如要能力 Benchmark 则在限额和隐私审核后选择 Deep / 原版 Kimi 子套件。没有授权 API 与预算，本项目不能代替用户在真实渠道产生该证据。正式 Release 之前还应实机验证备份恢复与交付报告。无官方模型 API 要求。

冻结宪章不变；不新建大阶段、不重写功能方向。


## 方法体系补全与反“针对单次结果编程”规则（2026-10-20）

本节只更新执行顺序和证据状态，**不修改冻结产品宪章**。新增方法必须服务于“供应商 API 准入与异常筛查”，不是为某一个模型/报告增加特判。

### 当前发现

- [x] [开源检测方法与兼容性审计](../oss-compatibility.md)：按方法分类协议、参数完整性、厂商原始测试、能力 Benchmark、行为分布指纹、logprobs、上下文检索、路由一致性、服务商元数据和安全红队；明确每类能证明/不能证明的事情。
- [x] [开源组件取舍](../oss-adoption-decisions-v020.md)：纠正一个文档错位——当前 `model_detect/adapters/fingerprint.py` 实际调用的是 **ToseaAI/llm-fingerprint-detector**，不是 dreamor 的 `fp` CLI。dreamor/llm_check 是同类候选，不是当前适配器。
- [x] 已确认第二份 GLM-5.3-Flash 报告里 ToseaAI 指纹状态为 `not_run`、lm-eval 为 `disabled`、proxy-sleuth 为 `disabled`；这份报告不是开源能力 Benchmark 或统计身份检测结果。
- [x] 已定位通用误报根因：`probes/provider.py` 将整个 JSON 响应 body 序列化后做品牌子串匹配；例如自然语言中含 `markdown` 会匹配 `ark`，产生 Volcengine/Ark 假线索。此规则不具备供应商归因能力，必须从算法上移除，而非给单词加黑名单。
- [x] 已复核可复现性缺口：上游 package.json 有版本 `0.1.0`，但 npm registry 实测 404；已禁用自动 npx 下载，改为显式安装源码构建 CLI。

### 检测方法全景与取舍

| 方法 | 适用问题 | 是否成为本版本主线 | 验收要求 |
|---|---|---|---|
| 通用 API 合约测试（JSON/SSE/tool calls/错误码/usage/finish_reason） | 能否接入、协议行为是否符合明示契约 | **是** | 对正常、异常、截断、空流、429、错误 schema 建立正反例；不按单个模型结果改判定 |
| 参数完整性/差分探针 | 关键参数是否被拒绝、忽略或行为未见差异 | **是** | 参数适用性来自官方文档；接受字段不等于生效；无法证明时 UNKNOWN |
| 官方原始协议套件 | 具体厂商规定的兼容性 | **适用时**（当前 Kimi） | 固定上游源码/commit/测试 ID；真实端点和模拟端点分开记 |
| 通用能力 Benchmark | 数学、指令、知识等能力画像 | **是**，唯一主引擎 lm-eval | 固定版本、任务、样本、模板、参数、原 scorer；样本太少明确标 Smoke |
| 行为分布指纹（包括数字/颜色/选择题） | 与可信端点/参考分布的行为相似性、可能的模型替换/漂移 | **实验性** | 有相同协议的可信 Reference；重复样本、自一致性、正负对照、有效样本数和成本；不输出未经校准的身份概率 |
| Token logprobs / 候选概率 | 可见 token 概率的分布差异 | **候选研究** | 端点确实支持 logprobs；同 tokenizer/提示/采样条件；跨接口不支持时跳过，不伪造 |
| 上下文检索/有效长度 | 长输入中信息是否可用 | **轻量保留** | 随机标记、多位置、输出预算检查；长上下文成熟题集可由现有评测框架执行 |
| 多轮/重复请求/混路由迹象 | 同一端点是否行为漂移或疑似多个后端 | **保留异常信号** | 多轮/多批样本、控制温度与参数；区分缓存、更新、限流、采样噪声；单次差异不判定换模 |
| 响应 Header/结构化元数据 | 识别 API gateway/upstream 的可见线索 | **修正后保留辅助信息** | 只用可归因的 header/明确结构字段及来源；禁止扫描生成正文/推理正文品牌子串 |
| 模型自述、未经支持的“真假分” | 模型自己声称身份、未校准权重推断 | **不要** | 不作为任何 PASS/FAIL 或身份结论 |
| 安全红队（garak） | 越狱、注入、泄露风险 | **不属于 v0.2.0** | 不与供应商身份/一般能力混合；未来若要扩展须单独决策 |
| Inspect AI / OpenCompass / EvalScope | 替代或补充通用评测引擎 | **本版本不并行安装** | 只有 lm-eval 被证实无法覆盖明确需求时，才比较迁移/补充成本 |

### 新发现的独立开源候选（只研究，不直接接入）

- **[fpverify](https://github.com/Mohamed7415/fpverify)**：MIT，采用行为分布 + JSD + 序贯 betting e-process，支持早停；比单纯固定 JSD 阈值多一层统计决策。上游 `calibrate_delta` 对良性漂移的标定是后验预测近似，README 中的低 FPR/高检出率主要来自项目自有仿真/实验，不能直接视为真实中转 API 的准确率。没有 `pyproject.toml`；ToseaAI 同样没有可从 npm registry 直接安装的包，需显式源码构建。fpverify 参考入册预算约 36 cell × 20 次 = 720 请求，审计预算可达 600 次。**作为 Deep/研究候选，不加入默认 Quick/Standard**。
- **[llm-provider-audit](https://github.com/benbenlijie/llm-provider-audit)**：MIT、Alpha、要求 Python >=3.12。reference variance、negative controls、open-set thresholds 值得借鉴，但当前项目仍需支持 Python 3.11，且功能与指纹/路由重叠。**只提炼方法设计，不引入依赖**。
- **[model-audit](https://github.com/liuxiaotong/model-audit)**：目标偏向蒸馏/模型血缘取证，部分方法需要白盒表示；README 的 14 样本 100% 自报结果不足以证明 API 中转验真效果。**不进入 v0.2.0**。
- **选型原则**：不按仓库数量堆工具；只把能提供不同证据、固定版本、可复现且在正反样例中证明有效的方法纳入主流程。

### 接下来严格按此顺序执行

#### D0 — 通用证据正确性（先做，零 API 费用）

- [ ] **D0.1 移除自然语言 Provider 猜测**：品牌词只能从明确的响应头/可追溯结构化元数据产生提示；响应的 `choices[].message.content`、reasoning 文本、引用/错误自由文本不得当作上游身份。禁止把启发式置信值当概率；已有禁止上游策略不得因自由文本子串触发。
- [ ] **D0.2 跨文本假阳性矩阵**：把 `ark`、`openai`、`fireworks`、`anthropic` 等字符串放进普通答案、推理文本、JSON 字符串和错误自然语言，必须不触发上游身份；只有显式、有来源的 metadata/header 可触发“观察到线索”，仍不等于模型权重身份。
- [ ] **D0.3 反向样例**：缺少 Header、未知 Header、通用 request-id、伪造品牌 Header、429/401/500、响应正文中提到品牌但没有结构化证据，分别产生可解释结果；伪造/可转发 Header 仍仅作为弱信号。
- [ ] **D0.4 评分语义**：总分不得用少数已运行类别的归一化结果伪装为综合模型分；身份类别无强证据时 UNKNOWN；不将未运行/不适用/证据不足等同失败。
- **退出条件**：上述回归对所有模型通用，无 GLM/Kimi/DeepSeek 专属文本黑名单；Python 3.11/3.12 CI 通过。

#### D1 — 复用引擎的可复现性（零模型 API 起步）

- [ ] **D1.1 lm-eval**：固定 `0.4.13` 与任务配置，实际运行原始 scorer 的 Mock 链路已有证据；补充版本不符/任务不存在/无结果/样本日志缺失时不得报告完成；真实模型结果仍单独标未测。
- [ ] **D1.2 Kimi 原始测试**：固定 commit 与四组适用范围；保留原始测试 ID/退出码；不把它推广为其他型号的官方认证。
- [x] **D1.3.1 版本与执行策略**：PR #179 已固定目标 CLI `0.1.0` 并校验版本；npm registry 404 后在后续修复中禁用自动 npx 下载。
- [x] **D1.3.2 源码运行 smoke**：PR #181 已通过 CI；从固定 GitHub commit 构建上游 TypeScript CLI，再通过项目 adapter 调用 `references --json`。无模型 API 调用；只证明 CLI/JSON 合同可执行。
- [ ] **D1.3.3 方法对照与真值验收**：比较 ToseaAI 固定样本 JSD 与 fpverify 序贯 e-process，核对 reference 覆盖、FPR 假设、调用预算和成本；dreamor/llm_check 仅作同类参考，不接入多个并行引擎。
- [ ] **D1.4 proxy-sleuth**：固定上游 commit 与许可证/依赖，确认命令与 JSON schema；其输出只作为实验性信号，需和现有通用探针做差异比较；不能证明独有价值则保留关闭或删除。
- [ ] **D1.5 promptfoo**：只验证现存 YAML 回归的兼容性与旧历史读取，不作为默认模型身份/能力引擎。
- **退出条件**：`oss-status` 精确区分 adapter/executable/version/runtime/result validation；本地 Mock 只标执行链路通过，不标检测准确率通过。

#### D2 — 检测方法有效性（先离线，再在有授权时实测）

- [ ] 建立固定的**正例、负例、未知例**测试集：正确结构响应、错误协议响应、截断、参数被忽略、模型输出被缓存、不同后端响应、自由文本误导等。Fixture 要独立于被测模型报告，不可从一个失败案例直接改成特例。
- [ ] 对统计方法用生成的已知分布做单元测试验证 JSD/阈值实现；这只证明数学/代码正确，不证明真实模型可区分。
- [ ] 真实指纹准确性须有可信同模型端点重复运行、不同模型负对照、相同采样/提示条件和至少两轮重复；没有真值时只输出“实验性/证据不足”。
- [ ] 记录方法版本、样本数、有效率、采样参数、Reference 来源/日期/协议、分布距离/不确定性、调用/Token 费用。不要将不同方法的分数平均成“真模型概率”。
- [ ] Logprobs 仅在端点明确支持时试验；若没有共同 tokenizer/条件，明确不适用；不因此引入新必需依赖。
- **退出条件**：可用离线 fixture 证明误报规则被捕获、未知状态保留；若无真实端点对照，则只完成“方法执行验证”，不得声称真实身份识别准确率已验证。

#### D3 — 最终报告与 UI

- [ ] 主结论只展示真实执行的协议、能力和异常结果；每一项标明引擎/任务/版本/样本数/状态与证据来源。
- [ ] 官方发布聚合分数、社区 Benchmark、本地运行结果、自采可信 Reference 分开呈现；不一致时标不可比。
- [ ] 报告移除无校准的供应商置信百分比、综合“智商分”和未运行方法的虚假通过；把身份/路由结果写为证据级别和限制。
- [ ] Quick/Standard 不静默调用大样本指纹或 Deep Benchmark；Deep 显示预计请求/Token、已知限制和预算确认。
- **退出条件**：一份报告能准确回答“运行了什么、没运行什么、哪些证据支持结论、不能据此推断什么”。

### 反“针对结果编程”的强制 PR 检查

每个新增/修改检测规则的 PR 都必须包括：
1. **方法先验**：在看到某个具体模型输出之前就能写清楚的规则来源/通用假设。
2. **最小正反例**：至少一个应该通过、一个应该失败、一个应为 UNKNOWN/NOT_APPLICABLE；禁止只加“让当前官方模型通过”的断言。
3. **跨模型/模型无关 fixture**：规则依赖协议/参数/统计方法，不依赖某次响应中的专有词、固定答案或模型名，除非规则来自明确官方规格。
4. **无数据泄漏**：测试样例不能包含用户真实 Key、私有 Prompt、未脱敏报告。
5. **证据等级**：CI 通过只证明代码行为；Mock 通过只证明合成链路；真实方法准确性需单独记录。
6. **删减审查**：若新增一个工具与现有工具重复，必须说明它覆盖了哪个已证实缺口；否则不接入。

**不改变的约束**：冻结产品宪章 v1 不改；不因单份 GLM 报告增加特判；不把指纹当唯一检测方法；不并行堆砌 lm-eval/Inspect/OpenCompass/EvalScope；不把安全红队、性能压测或权重认证扩入 v0.2.0。
