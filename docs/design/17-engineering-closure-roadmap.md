> **执行顺序更新（2026-10-15）**：根据项目维护者要求，先开发并合并 G1/A/B/C/D/E/F 全部可实现的代码、文档及 Mock/CI 测试，再集中执行真实官方/供应商 API 测试、第三方工具实测、校准和最终验收。此前“必须完成真实端点验收才能进入下一开发阶段”的表述统一解释为**发布/对外准入门槛**，不再阻止下一阶段代码开发。严禁将“代码完成/CI 通过”标为“真实实测完成”。

# 当前有效执行看板（2026-10-15，基于 main 4504a72f）

> **本节优先于下方历史状态表、旧任务复选框及按日期追加的过程记录。** 下方内容保留作为技术要求和开发经过，并非当前完成度。唯一任务主表仍是本文件；后续 PR 必须更新此看板和对应回归测试。当前策略为 **先全部完成工程开发与离线 Mock/CI，最后统一真实模型、第三方适配和校准验收**。禁止声称代码通过 CI 等于正式可用。

## 代码事实与遗留清单

| 任务 | 已合并实现（定位） | 剩余工程开发（不需模型付费） | 真实验收状态 |
|---|---|---|---|
| G0 结果契约与评分 | #53～#59：版本化基准 Contract、共享评分、GLM 中文协议、离线重算 | 同步通用评分/历史数据格式的边界清理 | 用户原始 ZIP 全链路验收待统一执行 |
| G1 外部评测可靠性 | #60、#62、#66～#69、#85、#90、#92：预检、脱敏检查点巡检、本地 lm-eval 实际 HTTP 发包捕获、网络错误类别 | **仍缺安全的任务级续跑/防重复付费**；本地合成捕获不能代替远端参数生效验证 | 双端实测、官方/客户实际生效语义待验 |
| A Reference 与安全 | #63～#65、#82、#87：Reference 原子创建/备份/哈希、显式缺失目标恢复、日志脱敏 | **异常断电恢复及 HTML/ZIP 安全回归**；备份恢复不是原子交换 | 断电/磁盘/并发恢复演练待验 |
| B Token 与预算 | #70～#74、#86、#88、#91：UsageRecord、部分费用、外部 unknown、CSV、原生运行时软停机 | **外部工具实际 Token 采集及 Web 完整操作一致性**；不能给真实费用硬上限 | 账单/缓存字段比对待验 |
| C Kimi 官方适配 | #75、#76、#79、#89：固定官方 Commit、JUnit 导入、受控执行、独立 HTML/JSON 报告附录 | **官方测试真实请求量/预算预览及 Web 历史自动关联** | 官方源码/供应商真实执行待验 |
| D 产品和 OSS | #77、#78：四 OSS 状态矩阵、Web 全链路 Mock E2E | **D-C1：所有 CLI 入口本地回归与报告路径**；**D-C2：模型规则来源/版本/解释一致性审核** | 4 OSS 真实兼容性和端到端验收待验 |
| E 校准 | #80 + 既有 validation/calibration：独立 Case、正负例、弃权、Wilson 区间、离线 Doctor | **E-C1：离线可重复的真值清单与报告导出合同；不伪造真值** | 独立已知正负样本、受控路由待验 |
| F 发布准备 | #81、#83：CHANGELOG、发布清单、升级恢复、release-doctor | **F-C1：统一工程开发状态、可复现安装/版本冻结与发布前检查完善** | 正式 Tag/Release 在真实验收之后 |

## 2026-10-15 已合并批次核对

- 文档主表合并：[#84](https://github.com/Ltqq/model-detect/pull/84)
- G1 检查点、客户端发包与错误分类：[#85](https://github.com/Ltqq/model-detect/pull/85)、[#90](https://github.com/Ltqq/model-detect/pull/90)、[#92](https://github.com/Ltqq/model-detect/pull/92)
- A 安全备份恢复：[#87](https://github.com/Ltqq/model-detect/pull/87)
- B 外部未知费用、CSV 与运行时原生软停机：[#86](https://github.com/Ltqq/model-detect/pull/86)、[#88](https://github.com/Ltqq/model-detect/pull/88)、[#91](https://github.com/Ltqq/model-detect/pull/91)
- C Kimi 官方验证器独立中文报告附录：[#89](https://github.com/Ltqq/model-detect/pull/89)

**上述 PR 均已通过 CI 并合并。** 这表示代码与 Mock 回归交付，不表示真实服务端参数生效、真实独立真值、第三方工具成本及正式客户验收通过。**未完成工程重点：G1 安全续跑；A 安全 ZIP/断电恢复；B 外部工具真实 Usage；C 预算与 Web 关联；D CLI/规则源审核；E 数据合同；F 冻结与 Release。**

## 固定开发批次与停止标准

1. **批次 1 / G1-C1、G1-C2**：HTTP wire 证据由实际发送层捕获，敏感字段脱敏；异常/检查点回放需按真实状态分类，不自动重复付费。
2. **批次 2 / B-C1～B-C3**：统一把每类外部工具标记已观察或未计量，CSV/HTML/JSON/CLI 一致；有来源的软预算限制，无来源时不保证硬上限。
3. **批次 3 / A-C1～A-C2**：安全恢复工具必须核验备份、Manifest、hash 和互斥锁；失败不覆盖健康 Reference。
4. **批次 4 / C-C1～C-C2、D-C1**：官方 JUnit 与本地审计结果分栏显示；完整 CLI/Web 路径、报告和历史离线 E2E。
5. **批次 5 / D-C2、E-C1**：模型规则可追溯校对；独立样本校准数据合同和报告解释。
6. **批次 6 / F-C1**：补全开发状态、版本与依赖冻结、验收手册、用户操作说明；**不做付费调用，也不创建正式 Release**。

每批必须满足：最小变更范围、明确失败反例和未知状态、脱敏 Mock 回归、Python 3.11/3.12 CI 通过、代码 review 后 Squash Merge。任何依赖真实官方账号/独立上游日志的工作只记为「待统一真实验收」，不得把它标成工程阻塞，也不得假设其结果。当前不增加性能压测、RBAC、调度、SaaS、大型 Agent 或全量 Benchmark。

---

# model-detect 总开发计划：实测缺陷修复 → 工程收尾 → 真实校准 → 发布

> **更新：2026-10-13｜状态：计划已冻结、待逐项实施｜唯一有效的未来开发任务主表。**
>
> 该计划整合原 A～F 工程收尾路线及本次 GLM-5.3 实际运行暴露的 G0/G1 问题。**原 18/19 号专项技术设计不废弃，20 号文档专门保存脱敏实测依据；本文件统一管理任务顺序、优先级、验收门槛与交付。**
>
> 产品定位不变：**单机、单用户、Web + CLI、中文报告、SQLite 历史记录**的模型中转/供应商协议、身份辅助证据和能力对照工具。**不做并发/吞吐压测，不做 SaaS/RBAC/调度/企业管理，也不自建大型 Benchmark。**

## 0. 事实基线、完成定义与决策

### 0.1 已经具备的能力（代码实现，不等于真实验收）

- OpenAI-compatible 协议、参数完整性、Context、Routing、基础能力、Coding Sandbox、Fingerprint、Reference、结果对照、中文报告及 Web/CLI/历史。
- `llm-fingerprint-detector`、`proxy-sleuth`、`promptfoo`、`lm-evaluation-harness` 适配器；**集成了入口不代表所有第三方能力可用**。
- Official/Trusted Quality Baseline、Benchmark Contract、`validation run/evaluate/calibrate` 与 GLM-5.3 专项 `glm53 compare`（原生协议+轻量题+可选生成式 lm-eval）。
- Python 3.11/3.12 Mock/Fixture CI；**CI 绿不等于在线真实准确率已校准**。

### 0.2 已有真实证据（注意正确解释）

来源：[20 号 GLM-5.3 实测复盘](20-glm53-live-evidence-triage.md)，原始 `glm53-evidence.zip` 只由用户保存，**不提交仓库**。

- GLM-5.3 官方/客户均完成协议、轻量能力与标准评测调用；Standard 原生检测为官方 3 轮、客户 1 轮，140 次请求。
- 标准生成式 Benchmark 各自运行 GSM8K、IFEval、MATH-500，各任务 **25** 个有效样本；lm-eval 版本 **0.4.13**。观察到 GSM8K 96%/96%、IFEval prompt strict 48%/48%、MATH-500 exact 88%/88%；另有子指标差异。**不等于统计学证明二者能力等价。**
- 真实缺陷：任务比较 hash 混入 `base_url`/函数内存 repr，误判 `incomparable`；轻量题正则/答案格式误判；官方 GLM 中文 `thinking.disabled` 拒绝被判无证据；lm-eval 依赖/资源预加载导致首次失败。
- 已观察到原生部分 usage，但外部 lm-eval 未统一计量；执行前所有 `max_tokens` 相加不是实测 Token，也不是账单上限。

### 0.3 任务状态定义（必须统一）

- **已开发**：实现 + 单测/静态检查通过。
- **已集成验收**：依赖可安装，实际完整运行，结果/错误可复现。
- **已实证校准**：可信真值 + 受控正负样本 + 覆盖率/误报/漏报/弃权 + 独立验证。
- **证据不足 / 不可比**：不能升级为通过，也不等同于失败。
- **不做**：排除出版本范围，不要悄悄加入规划。

**核心原则：报告结论正确性与可追溯性优先于题量、功能数量、UI 美观。**

## 1. 总路线、优先级和依赖

| 顺序 | 任务组 | 优先级 | 当前状态 | 前置依赖 | 验收交付物 | 粗估 |
|---|---|---|---|---|---|---|
| **G0** | 实测 P0：稳定 Benchmark Contract、评分器、中文协议与结论 | **P0 / 第一批** | 待修 | 已有 GLM53 zip，可脱敏提炼回归用例 | 05 原始结果可正确比较、03 正确答案不误判、报告保守 | 2～4 人日 |
| **G1** | 实测评测链路：依赖、参数、失败恢复、证据 | **P0/P1 / 第二批** | 待修 | G0，实测环境配置可用 | 外部 lm-eval 可复现、不会无意义重复付费 | 2～4 人日 |
| **A** | 全局审计可靠性：Reference 原子更新、失败语义与安全 | **P0** | 待修 | G0 的通用 Contract/错误语义复用 | 旧 Reference 不丢、任何失败不假通过 | 2～4 人日 |
| **B** | 统一 Token Meter、成本与预算保护 | **P0** | 待开发 | A 的 Evidence 错误语义；可并行设计 | 分 Probe 实测/估算/未知、执行前预算 | 3～5 人日 |
| **C** | Kimi Vendor Verifier 官方专项适配 | P1 | 待开发 | A/B 可信 Evidence 与费用界限 | 官方专项子集可运行、原始断言可追溯 | 2～4 人日 |
| **D** | 外部 OSS + Web/CLI/报告/历史真实 E2E | P1 | 待验收 | G1 + A/B/C 可分批 | 四个 Adapter 与 Web 主流程验收记录 | 2～4 人日 |
| **E** | Kimi K3/GLM-5.2/按需 GLM-5.3 实测校准 | 数据 P0 | 部分真实对照，**非真值校准完成** | G0/G1、可信官方 Key、受控网关 | TP/TN/FP/FN/弃权、置信区间及有条件准入 | 2～5 人日起，依赖环境 |
| **F** | 验收、版本发布与维护交接 | P2 | 待实施 | G0～E 的完成/明确豁免 | Release、文档、升级/回滚说明、停止标准 | 1～2 人日 |

**粗略工程规模：全范围合计约 16～30 人日，即单人约 3～6 个工作周**；若只交付 G0/G1/A/B 的紧急可信闭环，可更早分阶段验收。以上不含付费测试等待、环境搭建、外部依赖变化和额外 Coding Agent/1M Context 任务。每阶段不为凑进度而提前宣布完成。

### 发布门槛

- **门槛 1（允许继续付费）**：G0 全绿 + G1 的依赖/参数预检 + 可避免昂贵任务无证据丢失；不足时仅允许低成本端点诊断。
- **门槛 2（允许官方/客户能力差异入报告）**：同一数据集/任务/评分器/实际推理参数，比较契约可复验，真实成功调用，观测样本足够且报告说明不确定性。
- **门槛 3（允许正式供应商准入）**：A/B 稳定、必要的 OSS/专项集成实际验收、客户业务阈值在测试前商定；未知不能写成通过。
- **门槛 4（允许声称真实模型真实性检测效果）**：E 有可信已知正负真值及保留测试集；**仅官方 vs 客户结果相近绝非权重身份认证。**

## 2. G0 · 第一批 P0：纠正实测错误（全部先用离线数据）

### G0 技术修复收尾进度（2026-10-14；G1 尚未开始）

- [x] **G0.1**：通用 `lm-eval-task-v2` 可比性契约（PR #53），跨官方/客户 Base URL 不影响同题配置可比；模型、版本、题集/评分/生成参数改变仍不允许静默比较。
- [x] **G0.2 工具链部分**：新增 `glm53 replay --evidence-zip ... --output-dir ...`，**本地只读**重算 01/02/03 原生审计与 05 的官方/客户原始标准成绩，保存 SHA256 来源和新 JSON/Markdown/HTML；04 的旧 Smoke 因缺原始任务配置只保留诊断，**不冒充重算通过**。脱敏正反 Fixture 进 CI。原始 ZIP 不入仓库。详见 [21 号离线重算验收](21-glm53-offline-replay-acceptance.md)。
- [x] **G0.3**：共享评分器、Big-O 正则、指定格式保守归一化，03 真实保存答案独立复核，旧 66/75 → 75/75（官方）、23/25 → 25/25（客户），属于抽检天花板效应，不是新实测。
- [x] **G0.4**：GLM 中文 400 禁止关闭思考识别，401/429 等负例不能假通过；**原始旧报告未保存完整中文错误体，所以离线重算仍保留官方此项“证据不足”**，不凭手写备注篡改历史。
- [x] **G0.5**：标准 Benchmark GSM8K/IFEval/MATH-500 全部有效评分指标独立对照，`sample_len` 不算成绩；区分 `customer_inconclusive` 与客观偏离，协议/轻量能力/标准指标/身份结论分开，旧报告不覆盖。

**边界**：代码、脱敏 Fixture 与 CI 验证可以进入 G1。真实 ZIP 已独立核对配置哈希与旧答案变化，但上面新增 `glm53 replay` 的用户本机**全链路实跑**仍应作为发布前验收步骤；也需要 G1 实测确认 lm-eval 的思考等级是否真正被两个渠道接受和应用。G0 已修的是“已有证据的评分、比较与重算工具”，不能被理解成已经完成真实模型权重认证或正式客户验收。

### G0.1 实施进度（2026-10-14）

- **已在 PR #53 合并**：新增 `benchmark_contract.py`，将 lm-eval 的稳定 Task Config + Run Options 统一计算版本化 `lm-eval-task-v2` hash；剔除 Endpoint URL 和已知非评分传输字段，将内存地址型函数 repr 规范化为函数名并保留 harness/task 版本约束。无法安全识别的对象 repr 不生成比较键。旧版/未知版本比较结果不再直接认作可比。
- **已添加脱敏真实场景回归**：复现 GLM-5.3 05 中官方与客户路径/函数地址不同、各 25 样本、lm-eval 0.4.13、主要指标匹配的配置形态，以及修改数据集、样本数/任务版本、fewshot、生成参数/随机种子等负例。
- **剩余边界（不得误标全部完成）**：已知 Python callable 名称本身无法密码学证明函数实现一致，必须综合评测框架版本/Task 版本，真正依赖源码差异的情况仍应保守不可比；G0.2 还需继续做**完整原始结果的离线脱敏回放**，以及所有次级指标和旧报告重算。现有代码仅修复可比合同，不会自动重写历史报告。

### 本轮增量完成状态（2026-10-14）

| 已合并 PR | 对应任务 | 已完成的代码范围 | 仍然待完成 |
|---|---|---|---|
| [#53](https://github.com/Ltqq/model-detect/pull/53) | G0.1 + G0.2 部分 | 通用 v2 Benchmark Hash、端点路径/函数 repr 脱噪、版本不一致 fail closed、基于 05 实测形态的脱敏回归 | **完整原始 JSON 离线回放、全部子指标与历史报告重算**；函数名不是代码内容认证 |
| [#54](https://github.com/Ltqq/model-detect/pull/54) | G0.3 | 通用 Capability 正则及保守格式归一化，GLM 专项共享评分器，正反例测试 | **旧 03 报告按新版评分器重新计算**，并检验通用审计输出语义 |
| [#55](https://github.com/Ltqq/model-detect/pull/55) | G0.4 | 中文 1210/“始终思考”及英文禁止关闭思考识别，拒绝无关 400/401/429 假阳性 | **用旧 01/03 原始结果重新产出可追溯的新判定报告** |

**下一项优先任务（G0 收尾后）**：进入 G1.1 依赖/离线预检，G1.2 实际 reasoning/生成参数一致性，再处理付费结果保留与恢复；原始旧文件不改写，本轮没有新增收费 API 测试。

### G0.1 稳定、可审计的 Benchmark 比较契约

- [ ] 审核 `model_detect/adapters/lm_eval.py` 的 `task_config_hash`、`glm53_benchmark.py` 的对比逻辑，编写结构化 Canonical Benchmark Contract。
- [ ] **排除仅用于传输/环境标识**的 `metadata.base_url`、API Key、运行输出路径、进程对象内存地址和函数 repr；**保留任何影响实际得分**的数据集修订、subset/split、样本选择/seed、题目 ID、num_fewshot/示例策略、prompt 模板/过滤器、生成参数（thinking/effort/温度/max_gen_toks）、评分器版本/主 Metric。
- [ ] 区分 `observed_provenance` 与 `comparable_contract`；无法从函数 repr 复原真实题目代码语义时保守标 `unknown/incomparable`，不能为了消除假不相等而一律丢弃关键配置。
- [ ] 原生 Quality Baseline、通用 lm-eval、GLM-5.3 专项尽可能共用同一版本的契约校验器；旧结果须有格式升级或明确旧版不可比标记。
- **验收**：同配置官方/客户跨进程比较键一致；改变真实题集、题量、抽样种子、评分、effort、输出预算任何一项均拒绝可比；不泄露 URL/Key。

### G0.2 从本次真实 03/04/05 制作脱敏 Fixture 回归

- [ ] 只提取必要指标/配置，删除完整 Endpoint URL、Account/Key、原始 Prompt/Answer、OS 环境路径和不能公开的 Benchmark 内容。
- [ ] 回放 05 的 GSM8K / IFEval / MATH-500 全部实际指标（避免只取单个分数就误认为任务仅有一个 Metric），验证可比性、成绩差值和有效样本数。
- [ ] 测 04 真实 Smoke 的 5 题对照以及 03 的轻量判分；同时加入专门“近似但不同”的负例。
- **验收**：本地无需付费、无外网，Python 3.11/3.12 CI 通过；错误合同能在测试中明确失败。

### G0.3 轻量能力评分器修复与语义边界

- [ ] 修 `capability_lite.yaml` 的 `coding.complexity` 正则双重转义；逐条静态校验题库的 Regex 是否能匹配该题标准答案。
- [ ] 对明确题型做**保守**规范化：Markdown 加粗、首尾空格、`x = 8` 等等价答案；记录规范化前后及规则来源。
- [ ] 一律不能“全局清洗直到答对”；不同单位/数量级、逻辑相反、无有效答案仍判失败；输出截断记 `insufficient`。
- [ ] 修复会影响其他模型的通用能力评分入口，避免只针对 `glm-5.3` 写临时 `if`。
- **验收**：用户样本中正确的 `O(log n)`、`**11/8**`、`x = 8`、`**NO**` 匹配；错误变体明确不通过；报告有答案提取轨迹（脱敏）。

### G0.4 GLM-5.3 官方中文 Thinking 拒绝与错误分类

- [ ] 在 GLM-5.3 专项协议中识别明确的中文 `HTTP 400 / code 1210 / 始终思考、不支持关闭思考` 与英文 `thinking must be enabled` 等官方错误；同时保留证据/来源。
- [ ] 401/403/429/5xx、不相关 400、所有无错误体都按权限/限流/证据不足，不算符合；不能把 1210 推广成所有模型的通用成功码。
- [ ] 补多语言/错误码 Positive、Negative Fixture，并用 01/03 的脱敏记录回放。
- **验收**：这次官方明确拒绝 disabled 的记录可判 pass，错误 HTTP 仍严格不通过。

### G0.5 全局判定与客户报告修正

- [ ] `protocol`、`capability_lite`、`standard_benchmark` 与模型身份分开汇总；`partial/incomparable/insufficient` 不会被其它通过项掩盖。
- [ ] 对 25 题抽样，报告只能给“已观察差异 / 未观察明显差异 / 证据不足”，不能宣称“通过了厂商公布的满血标准”或“差异属于正常统计波动”。
- [ ] 正确显示 IFEval 两种级别 Metric、MATH500 的 `exact_match` 与 `math_verify`，不能把单项与总任务混为一谈。
- [ ] 旧版 01～05 报告**保持不可变**；另出重算版本并记录来源文件摘要、解析/评分器版本，不悄悄覆盖已交付文档。
- **验收**：对同份原始数据重算，可复核数值与判定边界；客户报告明确分“官方依据 / 官方观测 / 客户观测 / 解释限制”。

## 3. G1 · 第二批：真实评测链路可靠性

### G1 开发进度（2026-10-14）

- **G1.1 第一批工程实现**：新增只读 `model-detect glm53 doctor --benchmark smoke|standard|deep`，检查本机经实测的 `lm-eval==0.4.13`、当前 venv 入口、IFEval 和数学可选 Python 模块、NLTK `punkt`/`punkt_tab` 数据。选择 Benchmark 的 `glm53 compare --execute` 在任何原生官方/供应商调用前做同一预检；直接调用 Benchmark Runner 亦不可绕过。Mock 回归验证缺依赖时不会发起任何收费请求。
- **尚待完成（不能标 G1.1 全部验收）**：特定任务注册/数据集 revision 和本地缓存尚无法由静态 Python 包检查证明；doctor 显示 `dataset-cache=unverified`，不会自动下载题集。须按 G1.1 补独立预热与真正离线数据集验证，再推进 G1.2 的实际请求参数快照和端点一致性。
- **G1.2～G1.5**：仍未开始。CI 只覆盖模拟缺依赖与命令行为，**本批次没有付费模型调用，也未取得生产环境真实预检通过证据**。

### G1.1 可复现安装 + 付费前 Preflight

- [ ] 固定已实测的 `lm-eval 0.4.13` 为支持目标或写出验证过的兼容范围；检查 `lm_eval[api]`、IFEval `langdetect/immutabledict`、NLTK `punkt/punkt_tab`、Math `lm_eval[math]` 所需 math_verify/ANTLR 环境。
- [ ] 从当前 Python 虚拟环境定位执行器、校验任务名/输出类型/评分器/数据集离线可读性和版本；不能只根据 PATH 是否存在就宣布安装成功。
- [ ] 给 `model-detect glm53 doctor` 或 `compare --preflight` 一个只检查环境、不调用收费 API 的入口；列缺失包和具体安装命令。
- [ ] 对首次 NLTK/数据集缓存缺失，**在付费前**提供独立准备步骤，失败立即退出而不启动官方/客户调用。
- **验收**：全新 Python 3.11/3.12 虚拟环境按文档装完能预检成功；故意删包/缓存时给出可操作错误；不消费 API Token。

### G1.2 本批次实施范围（2026-10-14）

- **已经实现的部分**：对 `lm-eval==0.4.13` 增加显式 `--benchmark-reasoning-effort low|high|max`（默认 max）。使用官方 `--gen_kwargs reasoning_effort=...` 路径让所有 `generate_until` 任务更新生成配置，`local-chat-completions` 后端经 `**gen_kwargs` 发送字段；官方和客户调用同一 CLI 参数。设置写进新的 `glm53-lm-eval-generative-v2` 套件 hash，重新运行时从输出 `configs[task].generation_kwargs` 读取并校验该设置，若缺失或不一致则 **incomparable**。
- **不声称完成的部分**：当前还没有在网络层捕获实际 JSON 请求，也不能证明供应商真正应用推理等级；任务 YAML 的 `max_gen_toks` 优先级、采样题目 ID、异常截断率仍需完整验收。旧 2026-10-13 历史证据的推理等级未记录，离线重算**绝不继承新的 max 默认值**。
- **G1.2 下一小任务**：基于脱敏 HTTP Mock 做真实 `lm-eval 0.4.13` 的请求体抓取，分别检查官方与客户的 `thinking`、`reasoning_effort`、`max_tokens`、`temperature` 与 stop，以及数据集样本/任务版本，不通过就 fail closed。

### G1.2 Benchmark 请求配置与可比性真实性

- [ ] 抽取并记录评测框架**真正生效**的请求体：`temperature`、`thinking.type`、`reasoning_effort`、`max_tokens`、chat template、few-shot、抽样题目 IDs；官方/客户任一项不相同时阻止成绩比较。
- [ ] 特别核对 lm-eval Task 默认生成参数与命令级 `max_gen_toks` 优先级（IFEval 可能有任务内输出上限），不能只看 CLI 选项名称就以为生效。
- [ ] 在范围内允许显式 `--reasoning-effort max` 等参数，文档说明默认值；证明两边请求并非被代理吞参数，并将最终生效性限制如实写入报告。
- [ ] 识别截断、工具异常、非 JSON、超时、429；无效样本不应默认算正常答错。
- **验收**：脱敏 HTTP Mock 检查双方一致；错误参数或不同 Task Contract 必须得到 `incomparable`，不浪费正式评分流量。

### G1.3 中间产物、安全与续跑

- [ ] 标准 Benchmark 每次执行保存运行 manifest：套件哈希、任务、endpoint label（非敏感 URL）、样本范围、状态、耗时、脚本版本和去敏的任务结果。
- [ ] 官方采集成功而客户失败时保留已付费的官方原始**非敏感**摘要；可按相同 suite/参数/样本范围恢复未完成项，禁止混用不同版本。
- [ ] 清理临时密钥、隐藏思考和完整受版权保护的题目/回答；调试日志不得把 Authorization、Query Token 或账号信息写进 artifact。
- [ ] 如果工具不支持安全断点恢复，先交付“每端点单独保存结果/离线导入比较”，**不要承诺尚未实现的真续跑**。
- **验收**：模拟任务中途失败后已完成成绩不丢、重复执行不会默默覆盖或重新消费已成功请求。

### G1.4 协议兼容与精确失败定位

- [ ] 对 GLM-5.3 Chat Completions 的 `thinking/reasoning`、SSE 尾包/usage、tools/JSON 和不同错误码做真实文档核对；保留 Source URL、测试日期、行为等级（必须/可选/观察）。
- [ ] 对 HTTP 401/403/429、HTML 200、超时、响应 schema 缺失、部分 SSE 使用同一错误体系，给报告中的失败项明确定位。
- [ ] 对外部 `lm-eval` 执行错误保留异常类型/所缺包信息，**不保存任何含 Key 的原始异常文本**。
- **验收**：不论官方还是客户异常，都能明确区分“被测 API 不符合”和“测试框架没跑成功”。

### G1.5 GLM-5.3 再验证门槛（付费前确认）

- [ ] G0 所有脱敏真实 Fixture 通过，且 G1.1～G1.4 全绿后，才允许追加新的付费 Benchmark。
- [ ] 先双方各跑 **5 个样本/任务的 Smoke**，确认双方评分器和数据集配置一致；其后按客户业务需要跑 25/100+ 样本。
- [ ] 对 Coding/长程 Agent 如确有客户合同要求，评估已有可执行 Benchmark；**不默认实现整套 DeepSWE/TerminalBench、1M Context**。
- **验收**：新增一次真实 GLM 复测得到自动可比结果，没有人工手改 hash；原始证据可追踪，异常可解释。

## 4. A · 全局 P0：Reference/审计可靠性

### A1 Reference 原子保存、覆盖和失败回滚

- [ ] Web/CLI 共用安全的 Reference 存储服务；新版本先在临时工作目录完成 Baseline、Fingerprint、Manifest、Report 并验证，**不能先删旧 Reference**。
- [ ] 写入成功并完整校验之后再切换；同盘 rename + 备份/恢复、并发同 ID 防护、磁盘满/超时/进程中断处理。
- [ ] 默认 ID 重复拒绝，用户明确确认才能覆盖；版本/sha 可追溯。
- [ ] 注入故障测试：原有可信基准在任意失败点保持可用，防止报错时留下半成品或泄密日志。
- **验收**：原文件所有重要 SHA-256 在失败后仍一致；成功替换能完整读取/回滚。

### A2 Official Baseline 合法性与错误状态

- [ ] 每轮合法性：目标 ID/Profile/Suite/模型规则、HTTP 返回、可用 Probe/Benchmark、任务参数契约、真实有效 run 数。
- [ ] 客户明确选了 Strong Benchmark/Fingerprint/Regression 却失败时显示 `ERROR/PARTIAL/INSUFFICIENT`，其余原生结果允许保留，不会伪装最终无异常。
- [ ] `baseline_match` 仅覆盖明确可比的真实维度；不可比需要列逐维原因并显著提示。
- [ ] 将 G0 修好的比较契约/评分语义回归到通用审计路径，避免 GLM 专项与通用路径结果矛盾。
- **验收**：空、部分、无法解析、失效、模型不匹配的 Reference 绝不会显示完整可用。

### A3 单机安全边界

- [ ] Web 默认 loopback 监听；公网转发必须在文档明确外部认证/Nginx IP 控制，避免默认暴露密钥/历史。
- [ ] secret redaction：Authorization、Cookie、Query Token、第三方异常、客户回答中意外含密钥；路径与 Reference ID 验证，避免目录穿越。
- [ ] 不引入登录/RBAC/组织成员/多租户功能。
- **验收**：安全回归及异常路径测试通过，不持久化密钥。

## 5. B · 全局 P0：Token、成本与预算（复用 GLM 实测）

### B1 请求级 UsageRecord 和覆盖率

- [ ] 统一 `UsageRecord`：probe、stage、请求/重试、HTTP 状态、prompt/completion、reasoning（输出子项）、cache read/write（输入子项）、usage_source=observed/estimated/unknown、缺失原因。
- [ ] 支持普通 JSON 和完整 SSE usage；异常/流终止时未上报必须是 unknown，不把缺失计量做成 0。
- [ ] 总 Token 不要重复加 reasoning/cache 子项；用户供应商不同 usage 字段通过明确版本化映射。
- [ ] 回放 03 实测的 136/140 usage 覆盖（而不是误认为总 140 都精确计量）并加错误/限流用例。
- **验收**：任一 Audit 可定位每个 Probe 实际已观测量、缺失比例及估算来源。

### B2 统一汇总、费用和可用报告

- [ ] 用配置价格（input/output/cache read/write）与 usage 计算可核对费用，分别标已观察费用、估算费用、未知费用。
- [ ] CLI/Web/JSON/HTML/ZIP/Reference 与 GLM 专项使用**同一个计量器**；外部 subprocess 无 usage 时显示 `external_unmetered`。
- [ ] 不复制所有原始生成文本；成本只依赖必要统计字段；可选 CSV 导出。
- **验收**：报告可回答协议、Capability、Benchmark、Fingerprint、外部任务各用了多少 Token、哪些未知；不会展示假的“精确总成本”。

### B3 运行前预算与停机保护

- [ ] 预览原生请求数、重复轮数、Benchmark samples、输入 Token 估算方法、`max_tokens` 合计、失败重试风险；计算费用情景，不把名义输出上限叫作实测。
- [ ] 对原生请求/观察到的 Usage 允许软件限额中止；对外部子进程只承诺其实际支持的限制，其他情形仍明确“无法保证硬预算上限”。
- [ ] 默认不开昂贵 Benchmark；有偿运行必须显式 `--execute`；支持失败前保留安全结果，不重复扣费。
- **验收**：用户可先估成本、可选择只跑免费预检或 5 题 Smoke，不会因配置遗漏盲目发起大额调用。

## 6. C · P1：Kimi Vendor Verifier 官方专项

### C1 官方源码与本项目功能映射

- [ ] 固定 [MoonshotAI/Kimi-Vendor-Verifier](https://github.com/MoonshotAI/Kimi-Vendor-Verifier) Commit、许可证和准确执行入口；按代码统计实际样本数/请求数/上限。
- [ ] 对照本项目 Kimi K3 的协议、thinking/effort、Tool JSON Schema、Prompt Token 准确性，列 `已覆盖/部分/缺失/不适用`。
- [ ] 优先选择可自动核验的**参数合法性、工具 Schema 和 Prompt Token 正确性**；视觉、超长 Context、Agent/Coding 高成本流程按需另行立项。
- **验收**：有官方 case ID / 本地映射 / 费用 / 版本来源，不声称所有官方测试均被覆盖。

### C2 轻量官方 Adapter

- [ ] 支持按模型/Case 子集显式启用；不存在/不可安装时 `skipped/insufficient`，不假通过。
- [ ] 以隔离子进程执行或安全导入官方 JSON 成绩，保留可追溯的 Commit、用例、原始判定及失败原因；避免重新写一套“看似官方”的断言。
- [ ] 将官方专项与通用协议和模型身份**分栏展示**，不擅自混进综合分。
- [ ] Mock 解析/路径/超时/异常 + 真实环境 E2E 后才标集成验收。
- **验收**：官方已覆盖 Case 与未覆盖 Case 均清楚，有预算预览，原始结果可核查。

## 7. D · P1：四大 OSS 适配器与产品 E2E

### D1 第三方依赖兼容与安装记录

- [ ] 分别验证 `lm-evaluation-harness`、`promptfoo`、`proxy-sleuth`、`llm-fingerprint-detector` 固定版本安装、CLI 启动、结果解析和失败类型。
- [ ] 将经证实的版本、命令、操作系统和可用性写入 `docs/oss-compatibility.md`，区分 `adapter存在/已安装/可运行/可信结果`。
- [ ] G1 中的 GLM 实测作为 lm-eval 已经跑过的基础，不能由其自动推断另外三个集成都可靠。

### D2 全链路 UI/CLI 验收

- [ ] Web：创建 Reference → 供应商审计 → 结果/证据 → 中文 HTML/JSON/ZIP → SQLite 历史 → 查看/删除/比对。
- [ ] CLI：官方比较、Reference collect、audit、受控实验、离线 calibration、GLM53 专项均有 Smoke。
- [ ] 处理 403/429、缺 Key/无公网、多个任务、失败重试、特殊模型规则、任务取消及输出路径。
- [ ] 单用户操作清晰，不增企业功能；若确有客户验收使用需要，可再决定增加“专项 Web 一键入口”，不应阻塞 P0 修复。

### D3 模型规则与报告审核

- [ ] 审阅 Kimi/GLM/Qwen/DeepSeek/Claude/GPT/Gemini 官方来源和更新时间；针对硬编码模型限制进行兼容性验证。
- [ ] 报告提供“官方要求、测试观察、质量对照、身份辅助证据、失败/未知、费用”，并附模型规则与测试套件版本；不能让异常项被综合分抹平。
- [ ] 完善入门文档、FAQ、安装、参数限制、可复现执行与升级说明。
- **验收**：至少在目标机器跑过真实第三方工具的 smoke，报告和 Web/CLI 全链路留存脱敏验收记录。

## 8. E · 真实校准（按证据级别分阶段）

### E1 官方能力基准，不把结果相似当身份真值

- [ ] GLM-5.3 官方/客户能力同题对照属于**能力观察**；G0/G1 修复后完成自动重算及必要小样本复测。
- [ ] 根据客户实际验收标准预先设定能力容忍度，固定数据集、版本、评分器、推理强度、有效输出限制和时间窗；样本不足只得出“证据不足”。
- [ ] 如果需更高判别力，引入客观、可执行 Coding/Agent 基准并固定运行环境；**不凭 25 道简单题宣布智商相同**。

### E2 Kimi K3 / GLM-5.2 官方 Reference

- [ ] 官方或可证实来源分别采集至少 3～5 次匹配合同的 Reference，记录模型完整版本、采集时间、关键推理参数和 Token 用量。
- [ ] 对同一模型官方自比先测误报，再跑已知不同模型、不同 reasoning effort、0/10/30/50% 受控路由，保留网关实际命中日志；模型 ID 的声明值不等于真实上游真值。
- [ ] 独立 Case 与重复 run 分开做 TP/TN/FP/FN/弃权、覆盖率和 Wilson 区间，不能把重复运行当多家供应商。
- [ ] 只在留出一部分独立对照数据后调整阈值，说明误报/漏报代价，不公布无数据的“99% 真模型概率”。
- **验收**：可重复、真实标签可查、运行环境可追溯，明确哪些模型/渠道的结果覆盖尚不足。

### E3 结果与客户签收

- [ ] 将“协议符合 / 能力已观察差异 / 证据不足 / 身份辅助信号”分别表述。
- [ ] 对已知失败、规则争议和阈值调整提供复测依据；客户认可验收范围与不覆盖内容。
- [ ] 对无法获得真实凭据/受控环境的项目只能标“待校准”，不使整个工具假装通过。

## 9. F · 发布、冻结新功能与维护规则

- [ ] 整理升级/迁移、CHANGELOG、依赖版本锁定、数据路径/恢复、密钥安全说明，CI 3.11/3.12 全绿。
- [ ] A/B/G0/G1 必须完成；C/D/E 需要达到声明的**具体子集**，不能用“测试过一点”代表全覆盖。
- [ ] 经真实客户需求确认后发布下一版本；明确测试范围、失败/未知项、实测与模拟证据分离。
- [ ] 发布后停止无差别增加普通 Probe，将精力转为模型规则维护、客户新问题回归、必要的数据集升级。

## 10. 执行拆分与 PR/Commit 纪律

### 建议开发批次（保证每次小范围可审查）

| 批次 | 对应任务 | 建议提交组织 | 通过后才允许 |
|---|---|---|---|
| 批次 01 | G0.1 + G0.2 | 每个合同/Fixture 逻辑独立 commit；先 fixture 再修 | 准确对比已有真实 Benchmark |
| 批次 02 | G0.3 + G0.4 + G0.5 | 评分器、协议、报告各独立 commit | 低成本协议 Smoke 复测 |
| 批次 03 | G1.1 + G1.2 | 依赖预检、真实请求参数快照分别提交 | 新的收费 Benchmark |
| 批次 04 | G1.3 + G1.4 + G1.5 | 失败恢复、错误分类、端点 Smoke 验收 | 正式 GLM 客户数据 |
| 批次 05 | A1 | 原子更新、回滚及故障注入独立提交 | Reference 重新采集 |
| 批次 06 | A2 + A3 | 失败有效性与安全边界分开提交 | 常规审计可信用 |
| 批次 07 | B1 | 统一 UsageRecord 和单元测试 | 分请求实际计量 |
| 批次 08 | B2 + B3 | 报告费用、预算保护分别提交 | 可靠成本报告 |
| 批次 09 | C1 + C2 | 官方差距清单、选择性 Adapter 逐步提交 | Kimi 专项可用 |
| 批次 10 | D1～D3 | 依赖兼容、Web/CLI E2E、报告按子 PR 拆 | 产品集成验收 |
| 批次 11 | E1～E3 | 真实校准数据不入公开仓库；提交脱敏结果及复现说明 | 对外准入结论 |
| 批次 12 | F | 文档/版本发布 | 稳定维护 |

**建议一个小任务一个 commit，每批最多 2～4 个紧密相关任务；必要时再拆 PR。** 变更必须写：修改动机、影响范围、原始失败、修复证据、回归测试、Token/付费风险、与旧版兼容性。只修文档时 PR 也必须通过 CI；重要测试用真实脱敏 fixture 回放，不能仅靠造一个 Fake 结果说明问题解决。

### 每个任务的统一验收模板

1. 输入、前置依赖及权威依据明确；引用固定的代码和测试套件版本。
2. 正常、异常、边界、未知四类结果有清楚定义；用例里至少包含失败反例。
3. 正确记录 Evidence、失败原因、可比性与费用数据的已知/未知状态。
4. 本地关键单测 + Python 3.11/3.12 CI 通过，PR Review 后合并 main。
5. **没有真实 API 数据的模块只标“代码完成”，不能标“实证验收完成”。**

## 11. 版本/工作量预估与停止条件

- G0：2～4 人日；G1：2～4 人日；A：2～4 人日；B：3～5 人日；C：2～4 人日；D：2～4 人日；E：2～5 人日起（受 API/网关/样本依赖）；F：1～2 人日。**这是粗估、不是已完成承诺**。
- 若只有时间完成核心：**最小可信版本 = G0 全部 + G1.1～G1.4 + A1/A2 + B1/B3 + 必要 E1 在线复核**；Kimi C、完整 D/E 可以单独标 Beta 后续，不得将其挂在强制准入上。
- 如果 G0/G1 修完实测依然出现不可比或评分器不稳定，不进入新的付费大样本/模型扩展；先缩小问题并修。
- **不做**：TTFT/ITL/TPS/RPM/TPM/429 压测、量化位宽/Serving 引擎猜测、SaaS/RBAC/调度、重型 Agent Harness 自研、所有官方 Benchmark 的“成绩复刻”。
- 当核心结果正确、预算可控、可复核且用户已通过真实受控实验确认满足范围时，停止主动开发通用功能，改为模型规则与测试集维护。

## 12. 文档关系（消除重复计划）

| 文档 | 用途 | 优先级 |
|---|---|---|
| **本文件 17** | **唯一总开发主表：先后、依赖、验收、PR** | **最高** |
| [20：GLM-5.3 实测复盘](20-glm53-live-evidence-triage.md) | 真实数据、具体 Bug 复现与 P0/P1 证据 | 支撑 G0/G1 |
| [18：GLM-5.3 临时专项](18-glm53-customer-qualification.md) | 初版需求边界、协议/能力 CLI 设计 | 历史/专项 |
| [19：GLM-5.3 验收边界](19-glm53-qualification-verification.md) | 协议规则、源码依据、标准评测与成本 | 专项技术说明 |
| [14/15/16：对比/实验/校准设计](14-comparison-integrity-and-strong-benchmark-plan.md) | 已完成阶段设计与实验指导 | 作为复用技术资产 |
| [开发总计划](../03-development-plan.md) | 历史实施批次索引，**不得另起冲突清单** | 历史索引 |

**后续收到“按文档继续开发”时，从本文件第 10 节第一个未完成小任务执行，而不是重新规划或直接跳到新增 Probe。**


## 2026-10-15 · A 阶段工程实施记录（PR #63；不得等同完整验收）

- **A1 新建保护已实现**：可信 Reference 先在同盘临时目录生成协议签名、Fingerprint、Quality Baseline 和 Manifest，再将目录发布到正式 ID；ID 重复默认拒绝。CLI 在付费采集前检查重复 ID，指纹先写隔离临时目录。导入型 Manifest 改为原子文件替换。新增故障注入测试验证写入失败时不发布半成品、不修改旧 Reference。
- **A2 合法性基础校验已实现**：审计选中 Reference 时核对声明模型、签名是否存在及可解析、fingerprint 文件、baseline 轮次/套件/Schema 的基本匹配；无效时产出 `INSUFFICIENT`，不参与正常 Reference 对照。仍需更多真实基准和异常情况集成验证。
- **A3 路径安全增量已实现**：Reference ID 使用严格白名单，拒绝路径穿越、清洗后重名冲突、符号链接；Manifest 中附件名限定为固定的本地 JSON 文件，拒绝任意路径。
- **尚未达到 A 阶段全部验收**：显式覆盖旧基准的事务回滚/备份恢复、跨进程同 ID 并发锁、断电和磁盘满等真实故障验证、完整 Web/CLI 安全测试与密钥脱敏审计。上述项目不得因本 PR 单元测试通过而勾选全完成。
- **顺序说明**：main 上 #60/#61/#62 的 G1 补丁仍待合并；A 目前在独立分支交付，不代表 G1.5 的真实双端点实测已经完成。


### G1 收尾集成（2026-10-15，PR #60/#62 已合并；G1 检查点基于新 main 重放）

- 日志脱敏及异常安全：#60 已合并；离线 HTTP 请求 JSON 比较：#62 已合并，尚不能证明 lm-eval 实际发包或服务端参数生效。
- Benchmark 逐轮脱敏 Checkpoint、失败分类和付费重复执行保护：从 #61 安全移植到新分支，避免覆盖 #62 的 CLI 更新。Checkpoint 存在即在任何原生付费调用前终止；仍不支持自动安全续跑。
- G1.1 数据集完整离线校验、G1.2 真正 SDK 发包捕获、G1.4 HTTP 细粒度错误定位、G1.5 正式双端 Smoke 仍未完成。没有以上证据，G1 不得标记整体验收通过。


### G1.1 离线任务加载预检增量（2026-10-15；待 CI）

- 新增 opt-in `model-detect glm53 doctor --benchmark smoke|standard|deep --verify-task-cache`：独立进程用 lm-eval 0.4.13 `TaskManager/get_task_dict` 实例化所选 Task，设置 Hugging Face 离线标志，剥离 API Key/Token 等环境变量，超时与异常仅返回安全分类，不导出 stderr/raw 数据。
- 只有子进程确认所有任务本地加载完成才标 `verified`；默认 `doctor` 保留轻量依赖检查，不冒充数据集缓存认证。离线环境不通过时不进行自动下载。
- **风险边界**：第三方任务自定义代码可能绕过 HF 离线环境变量；该检查不验证远端模型参数、真正发包和在线基准成绩，也不自动解锁大额付费测试。


### 2026-10-15 G1.1 付费前缓存保护（待 CI）

- `glm53 compare --benchmark smoke|standard|deep --require-offline-task-cache --execute` 可选强制检查本地任务能否离线实例化；若失败，阻断任何官方/客户端点调用。默认不改变用户的调用方式，预览 `--execute` 之外不启动检查、不产生付费请求。
- 这不是数据集不可变哈希证明，也不是 SDK 真正发包或服务端 reasoning 参数的生效证明。G1.2/G1.4/G1.5 仍需独立验收。


### 2026-10-15 B1 开发起点（仅代码与 CI）

- 增加独立 `model_detect/usage_meter.py`：请求级 `UsageRecord`（observed/estimated/unknown）、普通 JSON 与完整 SSE 使用同一导入结构、输出/缓存为子集，缺失计量标 unknown；汇总保留覆盖率与未知原因。
- 以本机造数回归 136/140 计量覆盖率，不声称重新处理过用户原始 03 Evidence。后续 B1 还需接入通用 `AuditHttpClient`、GLM、Benchmark/Fingerprint 外部任务；B2/B3 未完成。


### 2026-10-15 B2 报告集成（代码阶段）

- 通用 YAML `token_prices` 可配置币种、输入、输出、缓存读和缓存写每百万 Token 单价；`run_audit()` 从 B1 UsageRecord 计算价格，未上报 Usage 或未配置必要价格时归类为未知，使用 Decimal 防止浮点金额误差。
- HTML、JSON 统一呈现已观察/未知请求、输入输出、推理及缓存子项与可计价部分；历史原始报告不存在计价字段时兼容不展示。
- 外部 subprocess（lm-eval、Fingerprint、promptfoo 等）的真实计量仍未纳入；只能标未计量，不能填 0。下一批补 CLI 覆盖参数和费用 CSV 导出；未做真实 API 测试。


### 2026-10-15 B3 增量：GLM53 付费前名义 Token 容量保护

- GLM53 `compare` 新增可选 `--max-nominal-output-tokens` / `--max-estimated-input-tokens`，在读取 API Key、任何付费请求之前检查计划值；同时保留 `--max-requests` 和默认不开额外 Benchmark。
- **边界**：输入仅 UTF-8 字节估算；输出是配置名义上限（包含外部 Benchmark 额外样本），均不等于实际账单硬封顶。第三方 retry、缓存与模型记账差异不能由此保证严格费用限制。


### 2026-10-15 D2 Web 本地集成测试补齐（Mock 开发阶段）

- 从未合并的旧 #40 中只移植 `tests/test_web_e2e.py`，覆盖 Web 提交 Audit → 异步完成 → SQLite History → JSON/HTML/Evidence/ZIP → 搜索筛选 → 删除记录及清理文件。
- 不合并 #40 中基于旧路线宣称轻量产品全部验收完成的文档修改；此次 Mock API 测试不等于真实模型、支付资源或第三方引擎 E2E 实证。


### 2026-10-15 E1 离线受控实验准备（代码阶段）

- 新增 `validation doctor --manifest <cases.yaml> [--strict-reports]`：本地核对独立 Case 的正负标签数、重复轮数、报告文件是否存在，避免把重复 run 当成多个独立客户/供应商。
- 真值来源仍是用户声明，工具明确标未实证核对；没有真实报告不能算出准确率、虚构 TP/FP 或宣布校准完成。
- 后续统一真实验收阶段，需要官方端点、独立网关命中日志、Kimi/GLM Reference 与受控路由变体，之后使用现有 `validation evaluate/calibrate` 做独立实证。


### G1-C2 检查点巡检增量（2026-10-15）

- 新增 `glm53 inspect-checkpoint --checkpoint <path>`，仅离线检查 Schema、suite SHA256、已保存官方/供应商运行组数量及失败次数。不打印任何原始请求、答案、日志或环境变量，也不会重新调用模型。
- 仍不自动恢复外部 lm-eval 消耗过 Token 的任务；下一步需设计带明确人工确认和任务级幂等边界的安全续跑机制。本检查命令**不是完整 G1-C2 交付**。


### B-C1 进展（2026-10-15，待 CI）

- 通用审计增加 `external_token_usage`，对 lm-eval、promptfoo、llm-fingerprint、proxy-sleuth 的实际调用缺乏 Usage 时标 `external_unmetered`，不再暗示原生请求费用等于全部费用。
- JSON/HTML/ZIP 增加未计量工具数量；目前并未真正从 subprocess 收集 Usage，因此 B-C1 的跨工具精确计量仍未完成。


### A-C1 受控 Reference 备份恢复（2026-10-15；待 CI）

- 新增 `reference recover --id <ID> --reference-dir <dir>` 只读列出旧备份及 SHA256 完整性，`--backup-name <name> --restore` 才显式恢复。仅允许目标 ID 不存在且无 writer lock、备份 Manifest/附件哈希合法时同盘重命名恢复；复核后互斥锁保护。
- 不会自动清除陈旧锁、覆盖现有 Reference 或自动选择备份。真实崩溃恢复、目录 fsync、持续竞态和平台差异仍需验收，**不称为完整 crash-atomic 替换**。


### B-C2 CSV 使用记录导出（2026-10-15；待 CI）

- 新增 `usage-csv --report <report.json> --output <usage.csv>`：离线读取、验证并导出已存 Request UsageRecord；保留 unknown 与 missing_reason，不输出原始 Prompt/Answer/Key，不覆盖现有 CSV 文件。
- 只能导出已有报告计量；不是重新测量或真实第三方工具用量采集。CLI/Web 一致展示仍需补齐。


### C-C1 官方 Kimi 脱敏结果作为中文报告附录（2026-10-15，待 CI）

- `kimi-verifier attach-report --audit <report.json> --summary <official-junit-summary.json> --output-dir <new-dir>` 将经官方版本、Suite、Model、Case 总数结构校验的结果作为**独立的**报告 Adapter，生成新 HTML/JSON/ZIP 兼容源，绝不修改旧原始审计，也不改变整体得分、身份判定。
- 输出中仅保留官方 Git commit、Suite、次数与结论，原始 JUnit 名称、Prompt、失败日志和未信任字段不随导入。属于用户文件、未证明正式执行来源；Web SQLite 自动关联仍待进一步完善。


### G1-C1 离线真实 lm-eval 客户端发包捕获（2026-10-15，待 CI）

- 新增 `glm53 capture-local-wire --benchmark smoke --output-file <wire.json>`：在回环 HTTP 监听模拟 Chat Completions 模型返回、让实际 lm-eval 可执行程序向该地址发包；记录脱敏的请求参数、消息 SHA256 与设置 SHA256，不保存实际 Prompt 或 Key。
- 指定运行仅使用回环 `127.0.0.1`、模拟 API Key、Hugging Face 离线标志，避免付费。不能证明 lm-eval 本地第三方 task 插件绝不联网，也不能证明官方/客户服务端采纳这些参数。若本地无 lm-eval 数据集缓存则预检失败。
- 必须使用用户本机已安装的 lm-eval 0.4.13 和数据集在统一验收阶段运行该新入口，才可获得本机真实 CLI 请求证据；CI Mock 目前只证明捕获/脱敏链路。


### B-C3 原生运行时软停机增量（2026-10-15，待 CI）

- YAML `native_soft_token_limit` 或 `audit --native-soft-token-limit <N>`（必须显式开启），按实际返回 Usage 的 prompt+completion 累计。达到阈值或未收到 Usage 时 fail closed，后续原生 HTTP 请求被拒绝，不执行后续审计阶段；多任务同一个 HTTP client 的请求被串行保护避免预算竞态。
- 单次在途请求可能超出上限，外部 OSS 子进程不保证限额；**这不是实际供应商账单硬上限**。未开启时原有行为保持不变。真实供应商和 Web 端完整策略待统一验收。


### G1-C2 HTTP 错误证据语义（2026-10-15；待 CI）

- `Evidence.error_category` 新增结构化 HTTP/网络分类：timeout、connection_error、http_protocol_error、redirect_error、transport_error、authorization_rejected、rate_limited、upstream_server_error、non_json_html_success、stream_incomplete 等。
- 异常文本、URL Query、API Key 不导出，不能用 429、HTML 200、SSE 中断算模型能力失败；后续恢复与重试必须由类别及幂等性决定，**目前不自动重试已计费请求**。
