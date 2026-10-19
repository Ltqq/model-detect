# model-detect

**单机、自用的模型供应商检测工具**：检查 OpenAI 兼容接口的协议/参数行为、抽查模型能力、复用官方端点或可信端点的 Reference（对照基准），比较供应商差异，并输出中文报告与 SQLite 历史。

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

## 官方/供应商对照：两条不同的证据路线

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
- **待真实验收 R**：授权后分别用 Kimi K3、GLM-5.3 的真实官方与供应商端点固定模型/题集/参数/版本进行抽样，复查费用、参数实际生效及可比性；缺证据的项目必须保持 UNKNOWN/未实测。
- **版本**：`pyproject.toml` 中为开发版 `0.2.0`，不代表正式 Release 或官方认证。

**唯一有效的下一步进度/偏移审查**：[M0～R 执行看板](docs/design/17-engineering-closure-roadmap.md)。历史技术设计、受控身份校准和专项细节保留在 [docs/](docs/)；不再用旧开发计划推动新功能。

## 安全、发布和恢复

API Key 不应出现在 Evidence、报告或 SQLite；别向公开渠道上传原始 Benchmark 样本和 API Key。401/429/超时/不完整 SSE 应按实际错误或未知处理，不等同于模型通过。模型身份、混路由等均属黑盒辅助证据。

- [正式发布检查清单](docs/release-checklist.md)
- [单机升级/备份/恢复](docs/upgrade-and-restore.md)
- [官方 Kimi 适配范围与限制](docs/kimi-official-verifier.md)
- [第三方 OSS 兼容状态](docs/oss-compatibility.md)
- [变更记录](CHANGELOG.md)
