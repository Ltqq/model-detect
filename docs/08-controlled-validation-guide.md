# Phase 3：受控鉴别实验操作说明

本流程的目的是实测检测器的 **检出率和误报率**，而不是证明某个模型是官方认证的。计划参见 [14 号开发计划](design/14-comparison-integrity-and-strong-benchmark-plan.md) 和 [15 号实验设计](design/15-controlled-validation-experiments.md)。

## 1. 前置条件

- 官方 / 高可信 API 和 `reference collect` 创建的 Statistical Fingerprint；如果需要质量退化实验，Reference 还必须带 Quality Baseline。
- 对 Known Negative、混路由、低 reasoning 档等实验，需要**外部受控网关**。本项目只发送模型请求和评估响应，不会替你设置 10% / 30% / 50% 流量策略。
- 所有标签必须由实验人员根据可核查的路由配置、端点日志、版本信息手动标定。`truth_source` 记录对应配置、文件编号或者内部实验记录；仅填写说明文字不能把标签升级为独立验证的真相。

## 2. 最小操作流程

复制 `examples/controlled-validation.yaml`，把其中的占位 URL、Reference ID、`truth_source` 和环境变量名换成你的真实信息。示例里每个实验均为独立 Endpoint，端点是否按声明配置受控上游需要你在网关侧确认。

设置密钥（示例）：

```bash
export OFFICIAL_KIMI_KEY="..."
export CONTROLLED_GATEWAY_KEY="..."
export OTHER_PROVIDER_KEY="..."
```

**先预览，不付费：**

```bash
model-detect validation run \
  --manifest examples/controlled-validation.yaml \
  --output-dir ./validation-results/run-001
```

确认请求数量、参考基准、实验标签以后再执行：

```bash
model-detect validation run \
  --manifest examples/controlled-validation.yaml \
  --output-dir ./validation-results/run-001 \
  --execute --max-audits 16
```

这里的 `--max-audits` 控制完整审计次数，不等于 API 请求数量或 Token 数。每一次完整审计内部都会发送多条请求；如果勾选 Strong Benchmark / Fingerprint，成本还会明显提高。可先用少量场景和 `runs: 1` 试跑，再扩大到每个 Case 3–5 次。当前本地执行硬上限每组 5 次、总 40 次审计。

每次报告保存在：

```text
validation-results/run-001/
  official-self/01/report.json
  switched-model/01/report.json
  routing-10/01/report.json
  ...
  validation-run.json
  validation.json
  validation.md
```

然后可以**完全离线**反复汇总（不访问任何 API）：

```bash
model-detect validation evaluate \
  --manifest examples/controlled-validation.yaml \
  --output-dir ./validation-results/run-001
```

也可在 manifest 每个 case 的 `reports` 字段列出现有历史 `report.json` 路径，此时只用 `evaluate`，不要用 `run --execute`。

## 3. 如何理解三个维度

| 维度 | 真正的正类（TP） | 实测依赖 | 缺证据时 |
|---|---|---|---|
| 模型身份 | 已知不同模型，强指纹给 MISMATCH | 可信 Fingerprint Reference | 弃权 |
| 混合路由 | 外部真实混路由，路由融合给 mixed-routing-likely | 连续路由采样且有足够显著特征 | 弃权 |
| 质量退化 | 已确认质量退化，官方基准对比给 QUALITY_REGRESSION | 同测试套件、有效合同与重复基准 | 弃权 |

`UNCERTAIN`、`SUSPICIOUS`、`INSUFFICIENT` 和 `INCOMPARABLE` 不被强行当成正常/未发现，全部计为弃权。

报告包含 TP/TN/FP/FN、覆盖率、灵敏度、误报率、Precision、Specificity，其中无分母指标会显示“样本不足”。

**统计口径：** 每个报告计一次判断，不同 Case 可以重复运行；同一个 Case 的重复测量不是独立随机总体，输出的是本次受控样本描述性统计，不可直接推广为所有厂商的普遍准确率或显著性结论。

## 4. 实验场景注意事项

### 同模型 self-match

Reference 与当前 Endpoint 使用同一底层模型。标签 `identity: same` 仅在确有相同来源的前提下填写。测试的重点是模型自身误报 MISMATCH 的比例。

### 明确偷换模型

请求的 `model` 依然填声明 ID（如 `kimi-k3`）；外部受控网关在后台转发至另外一个**已知真实模型**。如果直接在请求模型字段改为 `glm-5.2`，那测到的只是显式模型变更，不是“偷偷换模型”。

### 同模型不同 reasoning 档位

应优先保持客户端请求和 Baseline 一致，在受控网关后台将实际后端推理等级强制改为 `low` / `high` / `max`（仅选模型实际支持的档位），并保存后端配置为 `truth_source`。工具 **不会**自动改变 reasoning 档位；不同档位也**不必然**意味着每道能力题都退化。因此，如果还没有独立的退化证据，`quality_regressed: null`，不要提前写成 `true`。

### 10% / 30% / 50% 混路由

分流比例由外部网关配置，本工具只记录目标值，不会证明实际流量一定按比例分发。Standard 的重复路由探测本身只有约 6 次请求，10% 低占比的异常路由可能完全采不到；建议给每组重复 3–5 次，对比不同比例的真实检出率，而不是保证某个百分比一定可检出。

### 不同 Provider / 不同版本

先确认它们确实是同一或不同的模型版本，并对这些不同维度分别设置真值。无法核实模型来源时 `truth.identity` 不要直接写 `same` 或 `different`；可以先只观察路由/质量，待证据明确再补身份标签。

## 5. 完成与下一阶段

Phase 3 提供**实验机制**，不等于 Phase 4 的真实官方校准已经执行。Phase 4 需要在真实 Kimi/GLM 官方参考和已知受控上游环境里运行实验、查看错误类型，再决定是否调整模型 Fingerprint/路由/质量阈值。

不可据此推断精确量化格式、GPU、Serving Engine，也不可将出自模拟测试的回归统计标为真实世界检出率。


## 6. Phase 4：离线校准诊断（新增）

完成实际受控实验后，使用同一套 YAML 对已有报告再做离线诊断：

```bash
model-detect validation calibrate \
  --manifest examples/controlled-validation.yaml \
  --output-dir validation-results/run-001
```

这个命令**不会请求任何模型 API 或消耗 Token**，输出：

```text
validation-results/run-001/
  validation.json     # Phase 3 原始实验矩阵（原有）
  validation.md       # Phase 3 逐次报告（原有）
  calibration.json    # Phase 4 诊断结果（新增）
  calibration.md      # Phase 4 中文诊断（新增）
```

Phase 4 进一步分析：

1. **独立 Case 级混淆矩阵**：与“报告逐次统计”分离；同 Case 3 次重复不算 3 个独立模型。任意缺失、弃权或预测不一致，该 Case 的该维度弃权。
2. **不确定度**：独立 Case 的灵敏度、误报率和覆盖率附 Wilson 95% 描述性区间。零分母显示样本不足，不输出假的 100%。
3. **不同场景**：分别分析 `same_model`、`different_model`、`different_effort`、`mixed_routing`、`different_provider`、`different_version`。
4. **混路由分组**：0/10/30/50% 是受控网关**目标配置比例**，不是模型请求实际被路由到其他上游的实测百分比。要核实请同时保留网关请求日志。
5. **阈值回放**：在已有且可比的 `OfficialBaselineComparison` 维度上离线复算 `mean - max(k×stddev, task_granularity)`，其中 `k=1/2/3`。必须同时有真实标签和完整对比契约；不符合者弃权。不改变生产默认阈值。
6. **准备情况**：低样本提示证据不足，即使 Case 数量足够也只给描述性诊断，**永远不标注“官方认证”**。

### 建议真实校准顺序

先选 Kimi K3：

- 官方 Reference 至少 3 次 Standard（如有需要可启用同版本 Strong Benchmark）；
- 相同官方模型回放 self-match，先确认误报；
- 受控网关强制转发另一个确定模型，观察身份 MISMATCH；
- 在网关侧分别强制不同 supported reasoning effort，记录实际生效参数（`truth_source`）；
- 受控网关路由比例 0 / 10 / 30 / 50%，每个 Case 可重复 3–5 轮，保留实际命中日志；
- 离线输出 `calibration.md`。基准明显不一致时先修 Benchmark Contract/缺证据，而不是直接调阈值。

GLM-5.2 按相同流程重复。真实部署数据和 API Key 只保存在你的运行环境，本仓库不会生成或提交真实凭据与厂商推断结果。

### 目前不能声称什么

仅安装本次代码、或者只在 CI 跑合成测试，不能声称“模型替换检出率 95%”或“混路由 10% 必定检出”。当前默认 `2×stddev` 仍是**未经过现实世界校准的启发式阈值**；需要足够独立的真实正例/负例、较好的有效覆盖率、未用来调阈值的保留样本才能考虑修改它。更不能从黑盒结果认定具体量化精度或 Serving Engine。
