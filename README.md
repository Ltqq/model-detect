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
- Model Rule v2 provenance：Kimi K3 / GLM-5.2 / Qwen3.8 / DeepSeek V4 / Claude 5 / GPT-5.6 / Gemini 3.8 Flash
- Provider Fingerprint v2 provenance
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

历史记录 UX 与本地 E2E 已完成。当前功能范围收口，后续主要维护 Model Rule、Provider Rule、真实 Regression Case，并修复实际使用中发现的问题。

详细文档：

- [产品目标](docs/01-product-goal.md)
- [总体架构](docs/02-architecture.md)
- [开发计划](docs/03-development-plan.md)
- [Probe Catalog](docs/04-probe-catalog.md)
- [当前实现状态](docs/05-v1-implementation.md)
- [技术决策](docs/06-technical-decisions.md)
- [Promptfoo Regression 设计](docs/design/11-promptfoo-regression.md)
- [Model / Provider Knowledge 设计](docs/design/12-model-provider-knowledge.md)

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
