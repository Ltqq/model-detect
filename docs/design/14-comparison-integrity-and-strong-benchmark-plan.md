# 模型真实性与降智检测：下一阶段实施计划（2026-10）

## 背景与当前状态

model-detect 主流程已具备 Web/CLI、官方 Model Rule、协议/参数/Context/路由探测、Statistical Fingerprint、Trusted Reference、Official Quality Baseline、中文报告和历史记录。**不代表模型真假或质量退化判定已完成大规模实证校准**。

当前主要风险：
- Baseline 仅严格比较 model / profile / suite_version；缺少对实际执行题集、请求参数、采样数、Benchmark 数据集/版本与 harness 配置的一致性契约。
- Capability Lite 的 Standard 每类别只有 2 题、Deep 每类别 5 题，不能支撑细微“智商百分比”断言。
- EleutherAI lm-evaluation-harness Adapter 已有执行与 ProbeResult 映射，但标准 Benchmark 未完全接入官方 Reference 采集和供应商自动比较流程。
- Baseline 当前 3 次均值/标准差和离散题粒度阈值只是启发式规则，尚未实证校准假阳性/假阴性。

## 总体原则

1. **证据优先**：对比条件不一致则报告 `BASELINE_INSUFFICIENT` / 某维度 `INCOMPARABLE`；不得显示正常或给出“显著退化”。
2. **身份与质量分离**：Fingerprint 身份结论不能被 Capability 分数冒充；质量下降也不等于确认具体量化格式。
3. **不重复造轮子**：标准能力 Benchmark 复用 EleutherAI lm-evaluation-harness，原生小题仍是 Smoke Test。
4. **同测试才可比较**：官方与供应商使用同一 Profile、题集、采样预算、配置、Harness 及 Dataset 版本。
5. **低开销/可控**：本地单机；默认不执行大样本 Benchmark，显式选择 Profile 与样本上限；用户可提前看到执行范围和预估题目数（Token/费用需依据实测/指定假设）。
6. 不增加性能压测、Redis、消息队列、企业 RBAC、定时任务或不可信黑盒“量化类型识别”。

## Phase 1 · P0 可比性与有效性校验（本次执行）

**1.1 Comparison Contract（对比契约）**
- 在 Baseline 与 Supplier Report 中记录可复现的每维度输入/请求设置指纹；
- 至少包含实际题目/场景 ID、请求模型参数、输出预算、关联 Probe、样本数量，以及 Benchmark Profile/Task/Dataset/Harness/Limit 信息；
- 防止只凭 `suite_version=official-baseline-v1` 将不同数据或请求参数强行比较；
- 不保存 API Key、Authorization、Base URL、响应文本中的敏感内容。

**1.2 对比校验**
- 模型、Profile、Suite 版本一致才可进行基础对比；
- 每个维度若 Contract 不一致或基准缺失契约，单独 `INCOMPARABLE`，且不能参与 `BASELINE_MATCH`；
- 部分维度可比时只对这些维度给出结论，最终不得掩盖其他维度缺失；
- 旧 Reference 向后兼容读取，但旧格式无契约时强对比明确要求重新采集；
- 回归测试覆盖：题目变化、温度/推理档位变化、输出上限变化、样本量变化、旧 Baseline、完整匹配。

验收：`PASS` / `REGRESSION` 只能来自可比输入；不再出现“同名不同题仍然保持正常”的情况。

## Phase 2 · P1 Strong Benchmark 主链路（本次执行）

**2.1 模型与任务**
- 继续复用 `lm-evaluation-harness` Adapter，不自造“MMLU 实现”；
- 选择仓库已有的轻量 Benchmark Profile（需明确任务列表、限制、版本）；
- 可选 Strong Benchmark：默认关闭；支持 CLI 与 Web 显式启动；
- 支持安全上限与固定配置，所有输出保留来源/版本，失败不冒充通过。

**2.2 官方 vs 供应商一条链**
- Reference Collector 选择相同 Benchmark Profile，执行后写入 Baseline；
- Supplier Audit 使用同一 Reference 自动运行对应 Benchmark Profile；
- 从 `capability.external.lm_eval.*` 抽取同任务分数，使用同维度 Contract 做可比性校验；
- 结果进入中文报告和 JSON，显示官方均值/方差、供应商分数、题目数、保持率、不可比原因；
- 如果缺少本地 `lm_eval` / 参考配置，则明确 `INSUFFICIENT`，不默默跳过。

**2.3 测试**
- 用 mock/mock runner 跑端到端 Baseline→Reference→Supplier→Report；
- 测错误 Dataset/Limit/Harness、失败/缺失、默认关闭、预算限制；
- 测 CI Python 3.11/3.12 和 CLI/Web 基本路径。

验收：官方和供应商可在同一显式 Benchmark Profile 下形成同套件结果并展示中文差异，不要求立刻上线真实付费测试。

## Phase 3 · P1 受控鉴别实验（代码完成；真实实验数据待 Phase 4）

- Known Positive：官方 Endpoint 对自己；
- Known Negative：明确不同模型及明显更弱模型；
- Same Model / Different Effort：同模型同 Prompt，`low/high/max` 等受支持档位；
- Mixed Routing：0%、10%、30%、50% 的已知流量比例；
- 同模型不同 Provider / 不同模型版本；
- 记录真实标签、报告结论和 Evidence，统计检出率、误报率、漏检率。

验收：对照实验可重复运行，明确支持边界，不公布无数据的“准确率”。

现已实现实验 YAML、`model-detect validation run/evaluate`、真实标签/强证据对比、
逐轮中文报告与混淆矩阵。操作详见 [15 号实验设计](15-controlled-validation-experiments.md)
和 [受控实验使用指南](../08-controlled-validation-guide.md)。
真实 Kimi / GLM 官方与受控网关测量仍需 Phase 4 在有凭据的环境执行。

## Phase 4 · P2 真实渠道校准（后续，需官方 API Key）

- 先 Kimi K3、GLM-5.2，再按业务添加 Qwen/DeepSeek/GPT/Claude/Gemini；
- 官方 Reference 3–5 次、正常/异常渠道多次测试；
- 校准统计阈值，避免把短小 Lite Suite 作为精密降智证明；
- 报告注明模型版本、日期、Dataset、Harness、样本量；
- 不将 published leaderboard 分数与自建不同 harness 的成绩直接比较。

## Phase 5 · P2 中文报告与产品验收（后续）

- 清晰区分：身份匹配、质量退化、参数不兼容、渠道混路由、不可比、未执行；
- 明确对比是否有效、成本/题量、置信区间或统计不确定性；
- Web → Reference → Supplier → HTML/JSON/ZIP → 历史记录完整走查；
- 达到实证验收指标后发布版本。

## 提交策略

- 一个独立小改动一个 commit；
- 本次只完成 Phase 1 和 Phase 2，不提前实现 Phase 3–5；
- 先文档，再模型与契约，再比较保护，再 Benchmark 接入，再 Web/CLI/报告与测试；
- 各阶段 CI 全绿后提交 PR 并合并。

## 已知限制

现阶段即使检测到明显质量差异，也无法从黑盒直接判断 INT4/FP8/GPTQ/AWQ、蒸馏、GPU 型号或 Serving 框架。Statistical Fingerprint 是统计证据，不是模型权重身份证明。
