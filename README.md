# model-detect

**单机、自用的模型供应商检测工具**：只需待测供应商的 URL / API Key / Model ID，就能检查协议、基础能力和异常信号，生成中文报告及 SQLite 历史。**不需要官方模型 API**；官方公开成绩只作注明来源的背景参考，同条件逐题结果才能严格对比。

**不做** TTFT/TPS/RPM 性能压测、企业多租户、自动付费重试，也不宣称可通过黑盒成绩百分之百认证模型权重。

## 3 分钟开始

要求 Python 3.11 或 3.12：

```bash
git clone https://github.com/Ltqq/model-detect.git
cd model-detect
python -m pip install -e ".[dev]"
model-detect web
```

在本地 Web 首页填写 `Base URL / API Key / 模型 ID`，选择 Quick 或 Standard 进行检测。结果自动进入历史，可查看中文 HTML、JSON、ZIP、证据、删除记录。建议仅在受信任的本机运行，不要暴露在公网。

CLI 也可直接运行：

```bash
# 先在本机环境中安全设置密钥，不要把密钥直接写进命令、仓库或日志
model-detect audit \
  --base-url https://your-provider.example/v1 \
  --model glm-5.3 \
  --api-key-env MODEL_API_KEY \
  --profile standard
```

**默认**：内置协议与基础能力检测开启；proxy-sleuth、Docker 执行沙箱和 lm-eval 外部 Benchmark 均关闭。额外功能需手动选择；`--with-proxy-sleuth` 可以主动开启第三方增强检测。普通检测也会调用 API 并可能收费；`--native-soft-token-limit` 只是观察到 Token 使用后的软停止，不是完整账单硬限额。

## 目前支持的模型规则（规则存在不代表真实渠道验收通过）

- GLM-5.3：官方参数配置及历史专项回放。
- GLM-5.3-Flash / FlashX：独立模型规则，复用通用协议检查；视觉能力尚未完整评测。
- Kimi-K3：官方参数约束及固定原始 Pytest 子集（可选）。
- DeepSeek V4 Pro：保留独立模型规则，不以 API 名称证明实际权重。
- DeepSeek V4.1 Flash：官方当前 API 名 `deepseek-flash`，旧 `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` 别名已路由到 V4.1 Flash（2026-10-17 官方更新）。

模型规则有来源、核实日期和不确定项；五模型通用协议检查之外的真实能力验收仍需要对**待测供应商**进行实际请求。

## 官方/供应商对照：不同证据等级

| 来源 | 执行方式 | 结论边界 |
|---|---|---|
| **官方原始协议测试** | 已适配固定 Commit 的 Kimi Vendor Verifier 四组 Pytest 测试；官方运行器负责原始判定 | 可比较协议符合性，不等于官方认证模型身份 |
| **公开能力 Benchmark** | 可选 lm-evaluation-harness 的任务/原生评分器 | 可比较同任务条件下的能力差异；属于社区基准，非厂商官方认证 |
| **自行采集的官方端点 Reference** | 用官方 API 真实执行同版本同题测试并保存原始结果与脱敏快照 | 可复用，但仅凭“官方”标签不能证明来源已被独立核验 |

**离线比较已保存的两侧成绩：**

```bash
model-detect compare-evaluation-dirs \
  --official-dir ./runs/official/snapshots \
  --vendor-dir ./runs/vendor/snapshots \
  --output-dir ./comparisons/first
```

生成中文 `comparison.html`、`comparison.md`、`comparison.json`，严格核对模型、任务、评分器/数据集版本、实际样本 ID、生成参数。缺失/不一致标为不可比，不拿不同题集的分数硬减。已有 Kimi 官方 Pytest JSON 汇总时可追加 `--kimi-official <json> --kimi-vendor <json>`；同套用例才允许协议对比。

**需要自己采集 Reference** 时，可在 Web 高级选项中选择可选 Benchmark，勾选“保留评测结果并生成快照”，提供本机逐任务版本清单；执行完成后从历史记录一键选择官方/供应商两侧快照进行对照。CLI 路径参见 [完整评测采集说明](docs/design/17-engineering-closure-roadmap.md) 和 [Kimi 原始套件指南](docs/kimi-official-verifier.md)。原始 sample log 可能含完整 Prompt/回答，**不得公开上传**；版本标签由用户声明时 `source_verified=false`，不能冒充独立认证。

## 检测档位与可信度

| 选项 | 覆盖范围 | 建议 |
|---|---|---|
| Quick / Standard | 内置协议、参数、路由、基础能力抽检 | 日常使用 |
| Deep | 更广的内置抽检，不自动成为官方能力认证 | 重要供应商复核 |
| lm-eval Smoke / Standard | 公开基准的小样本/代表性测试 | 对照不同供应商 |
| lm-eval Deep | TruthfulQA、IFEval、**Minerva MATH-500**；每任务最多 100 样本，**需 `lm-eval[math]==0.4.13`** | 手动开启；先检查成本、依赖及题集版本 |

Deep 的 MATH-500 使用开源生成式任务和评分器，不是自研数学打分；但顶级模型的代码/Agent/视觉/长上下文仍**未完整覆盖**。新旧 Deep 任务配置不同，Reference 不能直接混用。高分一致有可能是题目过于简单，不能据此断言同权重。

Kimi 官方协议测试适配限定在 params、k3_features、tool_call_json_schema、prompt_tokens 四组；OCRBench/MMMU/BEAM/DeepSWE 等高成本能力套件**尚未完整接入及真实验收**。GLM-5.3 专项的预览、离线重算、官方/客户端点对照见 [GLM 专项指南](docs/design/18-glm53-customer-qualification.md)。

## 当前成熟度与后续工作

- **工程/离线 CI**：协议与能力抽检、Web/SQLite/中文报告、Kimi 官方套件导入、lm-eval 运行结果快照、离线供应商比较和历史浏览已具备；并不意味着每个外部评测器在本机/真实 API 上完成验证。
- **P0/P1 持续工程验收**：不需要用户提供官方模型端点；公开参考的来源核验和单个供应商端点的实际测试是两回事。所有仅离线检查或尚未实测的型号/能力必须标注 UNKNOWN/未实测。
- **版本**：`pyproject.toml` 中为开发版 `0.2.0`，不代表正式 Release 或官方认证。

**冻结产品方向**：[产品宪章 v1.0](docs/design/product-charter-v1.md)；**唯一可更新的开发进度**：[v0.2.0 执行计划](docs/design/v020-execution-plan.md)。17 号及其他历史计划仅供追溯，不再作为排期依据。

## 安全、发布和恢复

API Key 不应出现在 Evidence、报告或 SQLite；别向公开渠道上传原始 Benchmark 样本和 API Key。401/429/超时/不完整 SSE 应按实际错误或未知处理，不等同于模型通过。模型身份、混路由等均属黑盒辅助证据。

- [正式发布检查清单](docs/release-checklist.md)
- [单机升级/备份/恢复](docs/upgrade-and-restore.md)
- [官方 Kimi 适配范围与限制](docs/kimi-official-verifier.md)
- [第三方 OSS 兼容状态](docs/oss-compatibility.md)
- [变更记录](CHANGELOG.md)
