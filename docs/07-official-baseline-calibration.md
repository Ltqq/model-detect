# 官方 / 可信 Baseline 校准流程

本文件用于真实环境校准，不包含任何厂商 API Key 或预置“官方分数”。

## 1. 目标

通过同一套 model-detect Suite 对官方 / 高可信 Endpoint 与当前供应商 Endpoint 进行可复现的黑盒对比。

校准结果用于回答：
- Statistical Fingerprint 是否匹配；
- Capability / Tool / Structured Output / Context 等维度是否相对可信基准退化；
- 退化是否超过可信端点自身重复采样的正常波动。

不能用于直接证明具体量化格式、GPU 型号、Serving Engine 或模型权重的密码学同一性。

## 2. 为什么至少采 3 次

- 1 次：只保存差值和保持率，不能声称“超出正常波动”；
- 2 次：仍不足以稳定估计自然方差；
- 3 次及以上：开始计算 sample stddev，并结合题目离散粒度形成保守下界；
- 第一版 Web / CLI 上限为 5 次，避免把轻量工具做成大规模 benchmark 平台。

当前比较下界：

    lower_bound = baseline_mean - max(2 × sample_stddev, one_task_granularity)

这是第一版保守阈值，必须通过真实 Kimi / GLM 数据继续校准，不能视为行业统一标准。

## 3. Kimi K3 校准

准备官方 Kimi API Key，只通过环境变量传入：

    export KIMI_OFFICIAL_API_KEY="..."

采集：

    model-detect reference collect \
      --id kimi-k3-official-202610 \
      --base-url <Kimi 官方 OpenAI-compatible Base URL> \
      --model kimi-k3 \
      --api-key-env KIMI_OFFICIAL_API_KEY \
      --provider official \
      --quality-baseline \
      --baseline-runs 3 \
      --fingerprint

成功后 Reference 目录应包含 manifest.json、protocol-signature.json、baseline.json、fingerprint.json（可用时）和 baseline-report/。

检查 manifest：baseline_suite_version=official-baseline-v1、baseline_runs>=3、model_rule_id=kimi-k3，并确认 model_rule_updated_at 与当前规则一致。

随后供应商使用同一个 Reference，并保持 profile=standard。

## 4. GLM-5.2 校准

流程与 Kimi 完全相同：

    export GLM_OFFICIAL_API_KEY="..."

    model-detect reference collect \
      --id glm-5.2-official-202610 \
      --base-url <GLM 官方 OpenAI-compatible Base URL> \
      --model glm-5.2 \
      --api-key-env GLM_OFFICIAL_API_KEY \
      --provider official \
      --quality-baseline \
      --baseline-runs 3 \
      --fingerprint

供应商检测必须继续使用同一 Profile，否则第一版 Quality Comparison 会返回 BASELINE_INSUFFICIENT。

## 5. 校准时重点观察

Identity：Fingerprint verdict、Mean JSD、Per-cell JSD、Split-half JSD。

Quality：Reasoning、Math、Chinese、Instruction Following、Coding Reasoning、Tool Use、Structured Output、Context，以及明确启用时的 Coding Execute。

Routing / Integrity：mixed routing、reasoning 参数、temperature/top_p/max_tokens、tool/schema preservation、Provider/Gateway 指纹。

## 6. 如何判断阈值是否要改

至少需要官方 Baseline 3–5 runs、同一官方 Endpoint 后续复测、1–2 个已知正常供应商，以及如果有的话一个已知明显异常渠道。

正常渠道频繁 QUALITY_REGRESSION 时，先确认 Suite/Profile 完全一致，再检查低样本离散题，最后才考虑调整容忍区间或增加 Strong Benchmark。

明显劣化渠道仍 BASELINE_MATCH 时，优先增加 Capability 样本、使用 Deep 或用 lm-evaluation-harness 做同套件官方/供应商对照；不要为了抓某个供应商拍脑袋调阈值。

## 7. Strong Benchmark

现有 lm-evaluation-harness Adapter 可用于更强的能力对比，但第一版不自动把公开排行榜分数当成 Official Baseline。

只有 Dataset、Dataset version、Harness、Harness version、Prompt/Chat Template、reasoning 参数、sampling 参数、limit/few-shot 设置全部一致时，结果才允许直接横向比较。

正确方式是：官方 Endpoint 和 Supplier Endpoint 跑同一个 lm-eval profile。不要把厂商官网 GPQA 分数直接和本工具自己的 Reasoning 小题做百分比差。

## 8. Phase 5 完成标准

代码侧：官方 Reference 可采 Quality Baseline；同一 Reference 可保存 Fingerprint 与 Baseline；Supplier Audit 自动加载并比较；中文报告展示保持率/基准下界/退化；低于 3 次 Baseline 不输出显著退化；API Key 不进入持久化数据。

数据侧：至少真实采集 Kimi K3 与 GLM-5.2 官方 Baseline，各用至少一个供应商渠道复测，再根据真实数据决定是否调整第一版阈值。

数据侧需要你持有对应厂商官方凭据，因此不在仓库 CI 中伪造。