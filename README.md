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
