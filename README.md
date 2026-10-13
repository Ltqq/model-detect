# model-detect

面向 AI 中转站、LLM API 聚合平台和模型供应商准入的 **模型真实性 / 协议完整性 / 参数完整性 / 路由真实性 / 能力审计平台**。

它不是性能压测工具。TTFT、ITL、TPS、RPM、TPM、吞吐、并发和 429 压力曲线继续使用独立压测工具。

## 当前目标

给定：

```text
Base URL
API Key
Claimed Model
Optional Trusted Reference
```

model-detect 要回答：

1. 模型与声明是否一致？
2. Provider / Gateway 有哪些可观察指纹？
3. reasoning / tools / JSON Schema / context 等能力是否兑现？
4. 中转层是否吞参数、改 schema、注入 system prompt 或提前截断？
5. 是否存在 mixed routing？
6. 能力是否达到供应商准入要求？
7. 所有结论能否回溯 Evidence？

## 当前已实现

- OpenAI-compatible Protocol
- Provider / Gateway Fingerprint
- Statistical Fingerprint：mean/per-cell JSD
- split-half self consistency
- Trusted Reference
- Parameter Integrity
- Context Needle
- Mixed Routing + explainable cluster
- Reasoning 20 / Math 20 / Chinese 20 / Instruction Following 20
- Python / Go Coding Sandbox >=10 executable tasks
- Tool Use / Structured Output 场景化
- proxy-sleuth Adapter
- lm-evaluation-harness Adapter + built-in/user profiles + result mapping + dedup
- promptfoo declarative regression：YAML -> compile -> eval -> Unified ProbeResult
- Model Rule v3 provenance：Kimi K3 / GLM-5.2 / Qwen3.8 / DeepSeek V4 / Claude 5 / GPT-5.6 / Gemini 3.8 Flash；支持协议级参数语义
- Provider Fingerprint v2 provenance
- Official / Trusted Quality Baseline：同 Suite 重复采样、均值/方差、能力保持率与质量退化
- JSON / HTML / Web / Evidence / Drift Compare

## 当前产品形态

model-detect 现在定位为**单机、自用、轻量**工具：

```text
Web 发起检测
  ↓
生成 HTML / JSON / ZIP 报告
  ↓
SQLite 保存历史
  ↓
回看 / 筛选 / 下载 / 删除
```

不会继续建设 Saved Endpoint、Scheduler、通知、RBAC、PostgreSQL、Redis 等平台能力。

核心产品闭环已经完成。当前维护重点是 Model Rule / Provider Rule / Regression Case，以及使用官方 / 可信端点持续采集 Quality Baseline 做真实渠道校准。

详细文档：

- [产品目标](docs/01-product-goal.md)
- [总体架构](docs/02-architecture.md)
- [开发计划](docs/03-development-plan.md)
- [Probe Catalog](docs/04-probe-catalog.md)
- [当前实现状态](docs/05-v1-implementation.md)
- [技术决策](docs/06-technical-decisions.md)
- [Promptfoo Regression 设计](docs/design/11-promptfoo-regression.md)
- [Model / Provider Knowledge 设计](docs/design/12-model-provider-knowledge.md)
- [Official Baseline / Quality Regression 设计](docs/design/13-official-baseline-comparison.md)
- [官方基准校准流程](docs/07-official-baseline-calibration.md)

## 快速开始

```bash
git clone https://github.com/Ltqq/model-detect.git
cd model-detect
pip install -e ".[dev]"
model-detect web
```

CLI：

```powershell
$env:MODEL_DETECT_API_KEY="sk-xxx"

model-detect audit `
  --base-url https://example.com/v1 `
  --model kimi-k3 `
  --api-key-env MODEL_DETECT_API_KEY `
  --profile standard
```

## 核心原则

- Evidence First
- Reference First
- Deterministic First
- Strong Identity Requires Strong Evidence
- OSS 通过 Adapter 复用
- API Key 不写入 Evidence / Report / SQLite
- 性能测试永久独立


## 官方 / 可信质量基准

如果要判断“当前供应商和官方到底差多少”，不要直接拿厂商排行榜分数和本工具的小题分数相减。

正确流程是：

```text
官方 / 可信 Endpoint
  ↓
同一 Standard Suite 重复采集 3 次
  ↓
Reference = Fingerprint + Quality Baseline
  ↓
供应商 Endpoint 用同一 Profile 检测
  ↓
Identity Compare + Quality Compare
```

CLI 示例：

```bash
export MODEL_DETECT_OFFICIAL_KEY="sk-..."

model-detect reference collect \
  --id kimi-k3-official-202610 \
  --base-url https://api.moonshot.cn/v1 \
  --model kimi-k3 \
  --api-key-env MODEL_DETECT_OFFICIAL_KEY \
  --provider official \
  --quality-baseline \
  --baseline-runs 3 \
  --fingerprint
```

随后检测供应商时选择这份 Reference。质量对比只在模型、Profile 和 Baseline Suite 一致时生效。

注意：

- QUALITY_REGRESSION 表示黑盒能力/行为相对可信基准明显下降；
- 它不能单独证明具体是 INT4、FP8、AWQ、GPTQ、蒸馏、低 reasoning 档位、GPU 或 Serving Engine 导致；
- 真实官方 Baseline 必须使用你持有的官方 API 凭据实际采集，本仓库不会内置或伪造官方实测结果。

## 对比有效性保护与标准 Benchmark（P0/P1）

从本版本开始，Official Baseline 与供应商分数比较会核对实际 Probe 请求题目和参数的 SHA-256 指纹。
如果题目、temperature/reasoning、max_tokens、场景集合、请求数量等不一致，
或 Reference 是缺少契约的旧版本，相关维度会标为 **不可比 / BASELINE_INSUFFICIENT**，不会误报通过。
旧 Reference 可读取，但如需有效质量对比，必须重新采集。

`lm-evaluation-harness` 已能以可选 Strong Benchmark 参与官方 Reference 和供应商检测，
默认 **关闭**，必须主动指定：

```bash
# 官方基准：Standard（原生审计）× 3 + Smoke Benchmark（每轮最多 5 题）
model-detect reference collect \
  --id kimi-k3-official-bench \
  --base-url https://your-official-api.example/v1 \
  --model kimi-k3 \
  --api-key-env KIMI_OFFICIAL_API_KEY \
  --quality-baseline --baseline-runs 3 \
  --benchmark-profile smoke

# 供应商：必须选择相同 Reference 与 benchmark_profile
model-detect audit \
  --base-url https://your-vendor-api.example/v1 \
  --model kimi-k3 \
  --api-key-env SUPPLIER_API_KEY \
  --profile standard \
  --reference-id kimi-k3-official-bench \
  --benchmark-profile smoke
```

内置 Benchmark 档位：`smoke` 1 类 × 5 题；
`standard` 3 类 × 25 题；`deep` 3 类 × 100 题，实际题数以 lm-eval 输出为准。
Reference 每重复一轮都会重复执行 Benchmark，因此有额外 Token 开销。
需要本机预先安装 `lm-evaluation-harness` 并可运行 `lm_eval`。

报告将记录官方均值、供应商分数、能力保持率、对比契约及不可比原因。
Benchmark 契约核对任务配置哈希、实际样本数、任务版本、评测框架版本、
评分指标、Profile 与参数；仍不能在无法确认数据集不可变修订版本时宣称完整可复现实验。
`3 次 + 2×stddev` 仍是待真实渠道校准的启发式阈值，并非正式的统计显著性检验。

完整计划： [下一阶段实施计划](docs/design/14-comparison-integrity-and-strong-benchmark-plan.md)。


## 受控鉴别实验（Phase 3）

为了验证“模型被偷偷替换”“同模型降低推理档位”“混合路由”等场景**到底能检出多少**，
本项目提供独立的 `validation` 工作流，不修改现有准入综合分。

先复制并修改 [受控实验模板](examples/controlled-validation.yaml)，完成外部真实路由配置、
官方 Reference 与真实标签来源的标注。完整操作见
[受控鉴别实验指南](docs/08-controlled-validation-guide.md)。

```bash
# 第一步：预览，不发送请求，不消费 Token
model-detect validation run --manifest examples/controlled-validation.yaml

# 第二步：明确允许付费后串行运行（默认最多 16 次完整审计）
model-detect validation run \
  --manifest examples/controlled-validation.yaml \
  --output-dir validation-results/run-001 \
  --execute --max-audits 16

# 第三步：对已有真实报告离线复算混淆矩阵，不调用 API
model-detect validation evaluate \
  --manifest examples/controlled-validation.yaml \
  --output-dir validation-results/run-001
```

`validation.json` / `validation.md` 按身份/路由/质量分别给出
TP、TN、FP、FN、弃权、有效覆盖率、灵敏度与误报率，并逐次记录
“真实标签 vs 工具判断”。无报告/证据不足则没有准确率；分流比例只是
**外部受控目标值**，不会被当作已证实的实测分流率。
测试框架不提供虚构的官方基准或其他模型真假标签。
