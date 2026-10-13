# GLM-5.3 真实实测复盘、缺陷优先级与复测准则（2026-10-13）

> **来源**：用户提供的 `glm53-evidence.zip`，含 01 协议、02 Smoke、03 Standard、04 Benchmark Smoke（含首次失败）、05 双端点原始 lm-eval 标准报告、日志和人工复核记录。实测环境 Ubuntu 24.04 / Python 3.12.3 / lm-eval 0.4.13；测试 model-detect `main@0634849`。本文件只保存**脱敏统计、缺陷和复现规则**，**不上传**原始 zip、请求/回答、密钥、供应商私有地址和可能含敏感数据的运行日志。
>
> 本文件是 GLM-5.3 临时准入事项的**实证缺陷入口**；[17 号常规工程收尾路线](17-engineering-closure-roadmap.md) 仍为总体主计划。[18 号专项实施](18-glm53-customer-qualification.md)、[19 号协议与证据边界](19-glm53-qualification-verification.md) 为具体实现与能力覆盖说明。

## 1. 实际执行与数据核验（不是模拟测试）

| 实测批次 | 官方 / 客户 | 客观结果 | 已知限制 |
|---|---|---|---|
| 01 协议 | 1 / 1 轮，10 Case/端 | 工具自动判 9 项 consistent、1 项 official_inconclusive | thinking.disabled 官方中文 400 被误判；人工核对双方都明确拒绝 |
| 02 协议 + Smoke | 1 / 1 轮，每端协议 10 + 能力 10 | 协议仍自动 9+1；能力小样本对照可生成 | 数学/正则严格匹配带来假阴性；官方只有 1 轮，无法给稳定阈值 |
| 03 协议 + Standard | 3 / 1 轮，每轮协议 10 + 能力 25，合计 140 次调用 | 9 consistent + 1 inconclusive；五类均未提示 observable_drop | 能力评分存在确定性误判，结论不能直接作为正式能力等价判据 |
| 04 首次 Benchmark Smoke | 协议正常后标准任务失败 | 报告 `standard_benchmark.result=error` | ifeval 依赖缺失、NLTK 资源下载问题 |
| 04 成功 Benchmark Smoke | 官方/客户各 5 道 GSM8K、5 道 IFEval | 双端都有分数：GSM8K 1.0/1.0，IFEval 0.4/0.4 | 工具错误地将所有 Task 标记 incomparable |
| 05 标准 Benchmark 原始报告 | 官方/客户各运行 3 任务 × 25 样本，退出码均为 0 | 原始 lm-eval JSON 均可解析，见下表 | 未能由 CLI 正常获得自动 comparable；仅凭 25 题不能宣称总体显著性 |

### 05 原始标准评测数据（逐指标）

| 任务 / 指标 | 官方 | 客户 | 差值：客户 - 官方 |
|---|---:|---:|---:|
| GSM8K · `exact_match,flexible-extract` | 0.960 | 0.960 | +0.000 |
| IFEval · `prompt_level_strict_acc,none` | 0.480 | 0.480 | +0.000 |
| IFEval · `inst_level_strict_acc,none` | 0.4324 | 0.5135 | +0.0811 |
| MATH-500 · `exact_match,none` | 0.880 | 0.880 | +0.000 |
| MATH-500 · `math_verify,none` | 0.920 | 0.880 | -0.040 |

双方的 `n-samples.effective` 均为每任务 25；任务版本 GSM8K 3.0、IFEval 4.0、MATH-500 3.1；lm-eval 0.4.13；任务哈希/shot 信息一致。逐配置比较：GSM8K / IFEval 仅 `configs[task].metadata.base_url` 不同；MATH-500 另外 `fewshot_config` 中函数 repr / 内存地址随进程变化。**因此当前整个 `configs` 的 SHA-256 不适合作为跨端点可比性键。**

**审计解读（保守）**：本次 25 题抽样没有观察到大范围系统性退化；**不能断言“差异处于正常统计波动范围”**（尚未完成成对统计/足够样本/评分配置生效性校验），更不能声称“官方满血一致”或证明权重身份。手写汇总报告的“已验证符合”必须降级为“所测范围未观察到明显偏离，正式能力等价性证据不足”。

### 轻量评分器污染证据

Standard 的每类 5 题中：
- 官方 `coding.complexity` 连续 3 次对正确 `O(log n)` 判 fail，客户 1 次亦如此：`capability_lite.yaml` 中正则多写了反斜杠（YAML 单引号内保留原字面反斜杠）。
- 官方 `math.algebra-1` 连续 3 次返回 `x = 8`、客户 `**x = 8**`，按过严的 `^8$` 判 fail。
- 官方 `math.fraction-1` 的 `**11/8**`、`reasoning.conditional-1` 的 `**NO**` 亦被当成错误。
- 这些是**客观可复核的答案格式 / 匹配缺陷**，不等于模型推理失败。修复后预期该轻量题集有明显天花板效应，**应继续作为 Smoke，不作为微弱能力退化的最终判据**。

### Token 实测（原生 03，非全部阶段之和）

03 Standard 合计 140 次请求，已获取 usage 136 次（官方 102/105，客户 34/35），还有 4 次无 usage（涉及拒绝类请求）。观察到官方输入 3,798、输出 8,241；客户输入 1,212、输出 2,591；**共至少 15,842 Token**（输入 5,010 + 输出 10,832，仅已上报请求）。推理 Token 是输出细分，不得重复相加。外部 lm-eval 75 + 75 样本未采集网络级 Token，总成本**未知**。这批数据说明执行前 `max_tokens` 加总是预算情景，非实际 Token 用量。

## 2. GLM-5.3 真实缺陷：修复优先级

### G0 · P0：先让结果正确（不需要再次消耗 Token）

- [ ] **G0.1 稳定 Benchmark 可比性契约**：从 Task 配置中排除 `metadata.base_url`、任何凭据/运行路径及不确定的函数 repr/进程内存地址，但**保留**会改变提示/输出/评分的关键项，例如 task、dataset path/name、dataset revision/任务实现版本（可获得时）、fewshot 数/固定示例策略、过滤/抽取/评分规则、`generation_kwargs`、`max_gen_toks`、模型配置和推理强度。禁止“删除整个 metadata 后照单全收”。单独保存 Endpoint/Provider 溯源，不参与比较键。对缺少可复现稳定配置的情况标 `incomparable`，不冒险强行比较。
- [ ] **G0.2 用 04 / 05 实测 fixture 回放**：将相关原始 JSON **先经脱敏与最小化**（删除 URL、系统环境、生成文本、密钥等）作为测试样本，验证相同任务 `comparable`、改变 seed/fewshot/generation/metric/dataset 时 `incomparable`，跨进程 hash 稳定；模拟 05 的 3 个任务自动对比。
- [ ] **G0.3 修 Capability scorer**：修复 `coding.complexity` 的错误 Regex；对有限且语义确定的数学、布尔、等式答案做**保守、按题型**的规范化（Markdown 强调、首尾空白、`x =`）。不能全局删除任意字符；保留原回答和规范化依据用于审计。补正确/错误/歧义反例，不引入“答案其实错误但被清洗成正确”。
- [ ] **G0.4 修 GLM-5.3 thinking.disabled 中文错误**：官方 `HTTP 400 + code=1210 + 始终思考/不支持关闭思考` 应识别为明确拒绝；英文 `thinking must be enabled` 同理；401/403/429/5xx 和任何不相关 400 仍不得通过。按**特定模型/Code + 文本**范围实现，勿把其他模型的 code=1210 泛化为协议符合。
- [ ] **G0.5 修自动总结语义**：专项报告按 `pass/fail/insufficient/error`、协议正式要求/观察项、能力分数和 Benchmark 的真实可比性分别汇总；`official_inconclusive` 和小样本相等不能汇总为“已认证”。修正手写报告“统计正常波动/已验证符合”的过度结论（保留历史原始文档，不改写用户报告原件）。

**G0 验收**：在本地**不消耗付费 API** 的回放中，04/05 的三任务能够得到正确对比差值；03 所列正确答案不再误判；官方中文 400 正确判拒绝；改动有反例和 CI 3.11/3.12 全绿。

### G1 · P1：让可选标准评测能安装且真正可复现

- [ ] **G1.1 依赖和预检**：固定经验证的 lm-eval 0.4.13（或明确兼容范围）；在文档/可选 extras 列出 IFEval 的 `langdetect`、`immutabledict` 与 NLTK `punkt/punkt_tab` 离线预置；Standard/Deep MATH-500 另需 `lm_eval[math]`，确认 antlr4 / math_verify 版本兼容。CLI 在**付费调用前**做本地 import/资源/任务检查；不再“先测官方客户协议、然后才发现 Benchmark 依赖缺失”。
- [ ] **G1.2 安装路径兼容**：有 venv 时从当前解释器查找 `lm_eval`，不只依赖 shell PATH；失败提示精确依赖/版本/修复命令；NTLK 资源预检不允许静默网络长等待。
- [ ] **G1.3 评测参数有效性**：锁定两端相同 reasoning_effort / thinking、输出上限、温度、数据集样本选择和任务版本；`lm-eval` 目前对 API 的 Thinking 参数未明确注入，不能仅凭同一模型 ID 认定推理设置一致。确认 IFEval 的任务内 `max_gen_toks=1280` 与命令级 8192 的优先关系，记录实际**生效**请求参数与截断比例；原始日志提示 `--limit SHOULD ONLY BE USED FOR TESTING`，必须继续标为抽样成绩。
- [ ] **G1.4 失败保留与断点续跑**：在不泄露凭据前提下，失败时保留成功的官方/客户 Task 汇总与失败类型；不要因临时目录清理导致所有中间证据丢失。分任务/端点状态记录，并支持对**同一已冻结测试契约**恢复未完成工作，不重复扣费。
- [ ] **G1.5 客观报告补强**：保留每题可追溯的正误/评分失败分类、评测套件及代码 Git SHA、源数据集版本/修订、抽样选择策略；提供脱敏报告 ZIP 与可核验的摘要 hash。不要在报告里明文列出受测账号或 Secret。

**G1 验收**：新环境离线预检可快速报缺少的依赖；无需付费即可在 Mock 上测配置一致性；必要时对双方各跑 5 题 Smoke，能自动比较且错误可追踪。

### G2 · P1/P2：能力可信度与成本（按客户验收目标再扩大）

- [ ] **G2.1 证据充足性**：明确定义“API 协议符合 / 观测能力接近 / 正式准入阈值 / 无法判断”四个不同结论。正式能力差异使用**预先约定**容忍度、足够独立样本、成对题目差异与不确定性区间；25 题不能下“满血等价”结论。官方采样只 1 轮的外部 Benchmark 不得伪装成稳定官方基准。
- [ ] **G2.2 有区分度的任务**：轻量 Capability 作为 Smoke；如客户业务针对 Coding/Agent，优先复用成熟的可执行 Coding/Agent Benchmark，先固定运行环境与客观评分器；不能因为 GLM-5.3 宣称擅长 Coding 就随意自造“官方基准”。
- [ ] **G2.3 Token Meter**：将 03 真实 usage 样本纳入标准化 Parser 规格，记录 unknown 和每 Probe 成本；标准 lm-eval subprocess 尚无网络级 Token，用可复核的用量记录/上游日志补齐，不得展示“总体成本已精确计算”。这一项应复用全项目 [17 号 B 组](17-engineering-closure-roadmap.md)，**不单独复制一套 GLM Meter**。

**G2 验收**：报告不给超出证据的结论；每轮明确测试配置、样本和预算缺口；正式客户准入需要先完成 G0 + G1 再议样本量与阈值。

## 3. 这批数据对整体项目的影响

| 全局计划项 | 调整建议 | 原因 |
|---|---|---|
| 17.A2 证据语义 / 不可比 | **优先由 G0.1、G0.4、G0.5 补充跨端点真实 fixture** | 已发现比较契约导致 100% 假 `incomparable` 的确定性问题 |
| 17.B Token Meter | **保留全局 P0，不推迟到官方 Kimi 适配以后** | 原生 03 的实际用量远低于生成预算上限；外部 Benchmark 仍是未知成本 |
| 17.D 外部工具集成验收 | 将 **G1.1～G1.4** 纳入第一份 OSS 真实兼容样板 | Mock CI 绿不代表 lm-eval 实际可以运行，安装依赖显著影响测试 |
| 17.A1 Reference 原子覆盖 | 继续全局 P0，不因 GLM 临时问题取消 | 覆盖失败会丢失已付费真实基准 |
| 17.C Kimi Vendor Verifier | 仍 P1，但排在 GLM 已证实的 P0 缺陷之后 | 先使通用核心可靠，再扩展模型专项 |
| 17.E Kimi/GLM 真值校准 | 05 是**GLM-5.3 官方/客户对照样本**，**不是 Kimi/GLM-5.2 的换模/混路由受控校准** | 不得据此勾选 E 的真实性检测完成 |

## 4. 建议执行顺序

**先停新增付费重复测试** → G0.1 Stable Task Contract → G0.2 真实 Fixture → G0.3 Capability Scorer → G0.4 中文错误 → G0.5 报告结论 → G1.1 依赖预检 → G1.2 路径 → G1.3 参数有效性 → G1.4 原始证据/恢复 → G1.5 报告 → 针对性双端 Smoke 复测 → 若目标要求，标准评测扩样 → 恢复 17.A1/A2/B 与后续 Kimi 计划。

执行方式：**一个小改动一个 commit、回归测试、CI，全绿再合并 PR**。当前需求是**更新开发文档与优先级，未要求本轮直接修复实现**；不要把勾选的实施计划冒充代码已经修好。

## 5. 安全与源文件处理

原始 Zip 只存在用户本地和会话临时环境，仓库只存汇总事实和测试方法。将来准备 Fixture 时必须删除原始 Endpoint URL、账号/Authorization、日志环境信息、请求内容及可能受保护的 Benchmark 题干/回答，不提交原始评测结果包，也不复制第三方受限题库内容。
