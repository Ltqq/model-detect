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

## 当前开发状态与下一步（2026-10-13）

主链已具备 Web/CLI、中文报告、历史记录、Reference、Fingerprint、协议/参数/Context/路由探测、强 Benchmark、受控实验和离线校准的**代码实现**。

但 **代码实现与 CI 通过 ≠ 真实外部工具/模型检测准确率已验证**。工程收尾还有几个明确项：

1. **P0：Reference 安全覆盖与失败保护**，避免重采集失败丢失原基准。
2. **P0：每项 Token/费用计量、未知值标注与预算提醒**，当前尚无准确的整次付费成本报表。
3. **P1：按官方源码评估并选择性接入 [Kimi-Vendor-Verifier](https://github.com/MoonshotAI/Kimi-Vendor-Verifier)**，现有通用 Probe 不等于官方套件。
4. **P1：固定 OSS 版本和 Web/CLI 真正的端到端集成验收**。
5. **必须用真实数据完成 Kimi-K3/GLM-5.2 校准**，不能从模拟单测推算误报/漏报。

**权威后续任务入口：[工程收尾与最终验收路线](docs/design/17-engineering-closure-roadmap.md)**。旧开发计划保留作为历史记录，不再照其中“下一批”重复开发。坚持单机自用，不加入压测或重型平台化能力。

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


## Phase 4：受控渠道结果的离线校准分析

已经通过 `validation run` 取得实际报告后，执行：

```bash
model-detect validation calibrate \
  --manifest examples/controlled-validation.yaml \
  --output-dir validation-results/run-001
```

该命令不联网、不产生 Token 成本。它重新读取原始报告，生成
`calibration.json` 和 `calibration.md`：

- 逐次审计和**独立 Case**两套 TP/TN/FP/FN，避免把同一渠道重复测五遍冒充五个独立供应商；
- 身份、混路由、质量分别计算覆盖率、灵敏度、误报率及 Wilson 95% 描述性区间；
- 0/10/30/50% 受控目标路由比例分组和不同实验场景诊断；
- 在同套件/有效 Contract 的质量维度上回放 `1×/2×/3×stddev` 阈值，**仅对照，不自动更改生产阈值**；
- 记录模型规则、评测框架、Dataset/任务版本、实际题数与采集时间；不输出 API Key 或请求正文；
- 无数据、不足独立正/负例及弃权都会明确显示“证据不足”，从不生成凭空的检出率。

[详细 Phase 4 设计](docs/design/16-phase4-calibration-analysis.md) ·
[操作指南](docs/08-controlled-validation-guide.md)。

**注意：工具代码准备好 ≠ Kimi/GLM 实测校准已完成。**
真实模型实验仍需你自己运行官方/受控端点，并保留外部网关路由日志与原始真值依据。


## GLM-5.3 客户专项对照（临时需求；不覆盖 17 号计划）

这项工作是一次**官方端点在线实测 → 客户端点同测试 → 中文对照报告**，用于快速准入核查。独立设计：[GLM-5.3 客户专项计划](docs/design/18-glm53-customer-qualification.md)。

目前新增独立 CLI：`model-detect glm53 compare`；默认 **只预览**，不会发出模型请求。将官方和客户 Key 放在各自环境变量后，再显式传入 `--execute`：

```bash
# 测试前：只看预算，官方 API 可能是 /api/paas/v4 或文档列出的 Coding Plan 前缀
model-detect glm53 compare \
  --official-url https://api.z.ai/api/paas/v4 \
  --customer-url https://customer.example/v1 \
  --official-runs 3 --customer-runs 1 \
  --capability-profile smoke --mode all

# 正式运行：绝不在命令行直接写 API Key，先设置 GLM53_OFFICIAL_KEY / GLM53_CUSTOMER_KEY
model-detect glm53 compare \
  --official-url https://api.z.ai/api/paas/v4 \
  --customer-url https://customer.example/v1 \
  --official-key-env GLM53_OFFICIAL_KEY \
  --customer-key-env GLM53_CUSTOMER_KEY \
  --official-runs 3 --customer-runs 1 \
  --capability-profile standard --mode all \
  --max-requests 160 --execute \
  --output-dir glm53-output
```

| 选项 | 每端点每轮 |
|---|---:|
| `--mode protocol` | 10 个 GLM-5.3 专项协议用例 |
| `--mode capability --capability-profile smoke` | 10 道固定客观能力小题 |
| `--mode capability --capability-profile standard` | 25 道固定客观能力小题 |
| `--mode all --capability-profile standard` | 10 个协议 Case + 25 道能力题 |

默认 3 轮官方 + 1 轮客户、`all + standard`，理论共 **140 个 API 请求**；每轮名义最大生成 Token 预算为 `10 × 1024 + 25 × 2048 = 61,440`，四轮合计 **245,760**。这是给请求配置的生成上限之和，**不是实际必然消耗量**；真实输入 Token 的执行前估算基于 UTF-8 字节长度启发式，不是模型 Tokenizer 的准确结果，思考 Token 与缓存计费也依赖上游。

可以通过 `--input-price`、`--output-price` 输入每百万 Token 单价（同一种货币）以预览粗略费用情景；正式报告汇总接口实际返回的 `usage`，缺失的 usage 会标为**未计量**而不是当作零成本。流式请求只取 SSE 初段检测协议，usage 可能拿不到，必须在报告明确记为未知。

结果保存在 `glm53-comparison.json`、`glm53-comparison.md` 和 `glm53-comparison.html`，协议与能力分开展示。注意：`Standard` 能力档仍是轻量**客观小题抽检**（不是高难 Coding/Agent 官方成绩）；默认输出预算可能仍不足以让个别持续思考请求完成，截断记为证据不足。正式高难能力评测可在固定环境下追加现有 lm-eval/可执行 Coding 评测，不允许将此小题抽检称为“GLM-5.3 满血官方认证”。

用户自行提供官方地址与凭据；本项目不内置 Key、官方分数或虚构的真实验收结果。


## GLM-5.3 真实测试复盘：先修评测可信度（2026-10-13）

已经在真实官方和客户 GLM-5.3 端点上运行了 10 项协议和轻量能力、lm-eval 0.4.13 的 GSM8K / IFEval / MATH-500（每端点各 25 样本/任务）。结果文件说明**代码 CI 全绿仍可能出现真实误判**：

- Benchmark 两边都产出了原始成绩，但 task hash 包含 Endpoint URL、函数对象内存地址，导致比较结果错误地标 `incomparable`。
- 轻量能力 `O(log n)` 正则、Markdown/代数答案的评分、官方中文 thinking.disabled 400 的判定存在假阴性。
- 安装 lm-eval 的 IFEval/Math 依赖、离线 NLTK 数据、环境 PATH 影响真实执行；Benchmark 子进程真实 Token 用量仍无法统一计量。

**请先按 [实测复盘与 G0/G1 缺陷清单](docs/design/20-glm53-live-evidence-triage.md) 修复并使用脱敏 fixture 离线回放，再扩大付费 Benchmark。** 原 [17 号工程收尾路线](docs/design/17-engineering-closure-roadmap.md) 保留，临时 G0/G1 已提到最前面。

## GLM-5.3 严格准入增强（官方同条件对照）

参见 [GLM-5.3 官方依据与完整覆盖矩阵](docs/design/19-glm53-qualification-verification.md)。

GLM-5.3 专项已增加完整 SSE 读取/结束验证、真正与 `thinking.disabled` 相关的错误码判别（401/429 不会假通过）、工具名/JSON 参数校验、恶意响应安全 HTML、官方参考域名校验及不覆盖原报告等。**注意范围限 OpenAI Chat Completions**，不是其他协议全覆盖；不做模型权重鉴定。

原来的轻量协议+能力检查仍按 `glm53 compare` 工作；如需更有区分度的标准能力评测，可在原命令上**显式增加**：

```bash
pip install 'lm_eval[api]'

# 先预览；外部标准 Benchmark 默认为关闭，需提高名义请求/样本预算上限
model-detect glm53 compare \
  --official-url https://api.z.ai/api/paas/v4 \
  --customer-url https://relay.example/v1 \
  --mode all --capability-profile smoke \
  --official-runs 1 --customer-runs 1 \
  --benchmark standard --benchmark-runs 1 \
  --max-requests 200

# 本地设置 GLM53_OFFICIAL_KEY / GLM53_CUSTOMER_KEY 后，再追加 --execute
```

标准档位的外部生成式评测为 GSM8K（数学）、IFEval（指令遵循）和 minerva_math500（MATH-500）。它们来自 EleutherAI 的 `lm-evaluation-harness`，**不是官方发布的 GLM-5.3 编程/Agent 榜单成绩复现**。普通 Chat Completions API 不支持基于 prompt logprobs 的默认 MMLU-Pro 选择题配置，所以不会错误地加入该任务。两端点独立运行，按 Harness 版本、任务配置、数据集版本、实际样本量、评分指标核对可比性；若有差异，报告只给观察值或“不可比”，绝不声称官方满血认证。

默认 `all+standard` 仍为约 140 次原生请求和 245,760 Token 的**名义最大输出配置之和**，不是实际消耗。额外 `--benchmark standard --benchmark-runs 1` 会增加 150 道名义样本，上限另按每题 8192 输出 Token 计算，**外部评测子进程尚不能统一计量真实 Token**，可能远高于想象，务必先预览。客户正式验收仍须配好官方 Key、真实运行、保存日期和原始报告。
