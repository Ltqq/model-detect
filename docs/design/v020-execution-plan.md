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
