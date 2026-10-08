# Official Baseline / Quality Regression 设计

## 1. 目标

在现有 model-detect 的供应商准入审计基础上，增加“官方/可信端点 vs 当前供应商端点”的同套件质量对比能力。

本模块回答：

1. 当前渠道与官方/可信 Reference 的模型身份行为是否一致？
2. 当前渠道在协议、参数、Context、Tool、Structured Output、Capability、Coding 等维度是否相对基准退化？
3. 退化是否超过基准自身的正常波动范围？
4. 哪些异常只能说明“实现差异”，不能推断为具体量化格式、GPU、Serving Engine 或模型权重来源？

## 2. 三类数据必须严格分离

### 2.1 Official Spec

来源：模型厂商官方文档、官方 GitHub、官方 API 文档。

用途：
- 支持哪些参数
- reasoning/thinking 档位
- context/max output
- tool/structured output
- 固定请求约束
- 协议差异

Official Spec 进入 Model Rule，并保留 source_refs。

### 2.2 Measured Trusted Baseline

来源：model-detect 对官方或人工确认的高可信端点实际发起请求得到的结果。

用途：
- Statistical Fingerprint
- Probe 状态
- Capability/Coding/Tool/Structured Output/Context 分数
- 多次重复采样的均值和方差

这是质量退化比较的主要基准。

### 2.3 Published Benchmark

来源：厂商 README / 技术报告公布的 GPQA、SWE、Terminal-Bench 等成绩。

用途：
- 人工参考
- 记录厂商公开能力定位

禁止直接拿 Published Benchmark 与 model-detect 自己的不同 harness 分数做百分比差值。

## 3. Model Rule v3：协议级语义

当前 V2 的 features 是模型全局语义，无法准确表达 Chat Completions 与 Responses 的差异。

V3 保留全局 features，并增加 protocol_features：

```yaml
schema_version: 3

features:
  reasoning_effort:
    expected: true

protocol_features:
  chat_completions:
    reasoning_effort:
      values: [low, high, max]
      default: high
      source_refs: [...]
  responses:
    reasoning_effort:
      values: [none, low, high, max]
      default: high
      source_refs: [...]
```

解析规则：
- 先读取全局 feature；
- 再以 protocol_features[protocol][feature] 覆盖；
- source_refs 同样必须可追溯；
- 不确定的官方行为继续保留 expected: null；
- 第三方托管平台差异不得覆盖模型厂商 Official Spec。

## 4. Official Baseline 数据模型

ReferenceManifest 向后兼容扩展：

```json
{
  "baseline_schema_version": 1,
  "baseline_suite_version": "official-baseline-v1",
  "baseline_runs": 3,
  "baseline_artifact": "baseline.json",
  "model_rule_id": "kimi-k3",
  "model_rule_updated_at": "2026-10-08"
}
```

baseline.json 保存聚合数据：

```json
{
  "schema_version": 1,
  "suite_version": "official-baseline-v1",
  "model": "kimi-k3",
  "runs": 3,
  "dimensions": {
    "reasoning": {
      "samples": [0.95, 0.90, 0.95],
      "mean": 0.9333,
      "stddev": 0.0236
    }
  },
  "probes": {}
}
```

API Key 永远不进入 Reference / Baseline / Report / SQLite。

## 5. Baseline Suite

第一版不追求排行榜复刻。

### 5.1 Lightweight Baseline

复用现有确定性 Probe：
- protocol
- integrity
- context
- routing
- capability.reasoning
- capability.math
- capability.chinese
- capability.instruction_following
- capability.coding
- capability.tool_use
- capability.structured_output
- executable coding（可选）

目标是低成本、可重复、官方和供应商使用完全相同的请求。

### 5.2 Strong Benchmark

保留现有 lm-evaluation-harness Adapter，用于后续更正式的 Profile。

要求：
- 官方端点与供应商端点必须使用相同 Dataset / Harness / Prompt / 参数；
- Dataset/Harness 版本必须写入 Baseline；
- 不把不同来源排行榜成绩混入 measured comparison。

## 6. Comparison Engine

对可比较维度计算：

- reference mean
- reference stddev
- target score
- absolute delta
- retention ratio
- z-like normalized delta（只有重复基准足够时）

第一版判定遵循保守规则：

1. Reference 只有 1 次：
   - 可以显示 delta / retention；
   - 不能输出“超出正常波动”。

2. Reference >= 3 次：
   - 使用基准自身重复采样估计波动；
   - 明显低于基准区间才标记 regression。

3. 低样本离散任务：
   - 不输出伪精确百分比；
   - 优先显示“通过题数 / 总题数 + 与基准差”。

4. Fingerprint：
   - 继续使用 llm-fingerprint-detector 的 JSD/verdict；
   - 不和 Capability 分数揉成“模型真实性概率”。

## 7. 输出语义

新增：

- BASELINE_MATCH：质量在可信基准正常范围
- QUALITY_REVIEW：存在可疑退化，需要复测
- QUALITY_REGRESSION：一个或多个关键维度显著低于基准
- BASELINE_INSUFFICIENT：基准样本不足

中文报告展示：

```text
模型身份：MATCH / REVIEW / MISMATCH
质量保持：
- Reasoning
- Math
- Chinese
- Instruction
- Coding
- Tool Use
- Structured Output
- Context

实现差异风险：
- mixed routing
- parameter integrity
- upstream policy

原因边界：
“观察到质量退化”不等于“检测到 INT4 / AWQ / GPTQ / FP8”。
```

## 8. 非目标

永久不做：
- 性能压测（TTFT/ITL/TPS/RPM/TPM）
- 根据黑盒输出猜 GPU 型号
- 根据黑盒输出宣称确定量化格式
- Redis / Worker / RBAC / 企业平台化
- 使用 LLM Judge 替代确定性/统计证据作为主判据

## 9. 实施阶段

### Phase 1
Model Rule v3 + 七个模型官方来源审计 + 协议级规则。

### Phase 2
ReferenceManifest 扩展 Official Baseline 元数据与 artifact。

### Phase 3
Baseline Collector：同一 Suite 重复运行、聚合均值/方差。

### Phase 4
Comparison Engine + 中文报告能力保持/质量退化展示。

### Phase 5
真实官方端点校准：
- Kimi K3
- GLM-5.2
- 后续 Qwen / DeepSeek / GPT / Claude / Gemini

Phase 5 的真实数据采集需要相应官方 API Key；没有凭据时只完成采集与校准能力，不伪造结果。
