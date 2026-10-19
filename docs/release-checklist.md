# model-detect v0.2.0 发布检查（单用户、已支持范围）

> **截至 2026-10-19：仅工程与离线 CI 已通过，真实端点验收 R 未完成；尚未打正式 Git Tag / Release。** `pyproject.toml` 的 `0.2.0` 是项目开发版本，不代表厂商官方认证。

## A. 工程交付（CI 已验证 ≠ 实机已验收）

- [x] Python 3.11 / 3.12 的 GitHub CI 执行全量 pytest、编译、CLI Smoke，并构建 wheel/sdist；已合并的 M1～M6 PR 各按绿灯门槛合并。
- [x] 一个测试来源目录（`test_catalog`），既有 Kimi 固定官方协议套件 + lm-eval 公开能力任务，未接入任务标明范围。
- [x] Web/CLI 产生报告、SQLite 历史、JSON/HTML/ZIP；官方端点与供应商快照合同不一致时标不可比；离线导入明确不调用模型。
- [x] 默认不启动可选 proxy-sleuth、Coding Sandbox、lm-eval 深度任务；用户显式 opt-in 才执行第三方工具。
- [x] Web 审计与 Reference 后台异常只存固定错误分类，不把原始含 API Key / Prompt 的第三方错误写入 SQLite、JSON、HTML（[#121](https://github.com/Ltqq/model-detect/pull/121)）。
- [x] 简化 README 和唯一 M0～R 看板，保留真实验证与来源范围的明确说明。
- [ ] **在实际部署的单机环境**完成依赖安装、Web 启停、旧 SQLite/Reference/报告恢复；CI 的 Mock 不代替实机演练。

## B. R：真实官方/供应商端点验收（尚未进行）

- [ ] Kimi K3 官方固定 Pytest 子套件在独立 Python >=3.12 环境真实运行，官方/供应商同套用例，对比 JUnit 摘要和原始证据。
- [ ] GLM-5.3 官方与供应商协议/思考参数和标准能力同配置运行，验证实际请求内容及服务端响应。
- [ ] lm-eval 原生公开评分（含适用时的 MATH-500）在固定依赖、数据集与评分版本/样本 ID 下实际运行，确认快照可比；不适用/缺环境项目明确标未覆盖。
- [ ] 真实 Web 使用路线验收：报告、历史、下载、删除、401/429/超时/中断 SSE，检查 API Key/Token/Prompt 泄露及费用未知标注。
- [ ] 在正式发布前由用户核定测试预算、可执行范围、最终功能说明、数据备份及 Release 版本/标签。

**重要**：`oss-status` 只能说明工具是否可调用，不代表运行结果可信。非核心 promptfoo/proxy-sleuth/fingerprint 等辅助适配器无须逐个完成昂贵实测才能发布**明确标注覆盖范围**的自用版本；开启过的功能必须如实标注真实验收状态，不能把未测试的功能宣称认证通过。高成本 OCRBench/MMMU/BEAM/DeepSWE、通用 Agent/多模态/长上下文能力未完整接入，不能暗示已覆盖。

## 只读/低成本检查

```bash
python -m pytest -q
model-detect version
model-detect oss-status
model-detect glm53 doctor --benchmark standard
model-detect kimi-verifier --help
model-detect web --help
```

这部分**不应自动调用付费模型**。真实测试必须单独确认用户授权、API 环境变量、名义请求/Token 预算，才使用相应命令的显式执行开关；不要在代码测试或 CI 中默认运行付费 Benchmark。

## 必须诚实保留的结论边界

- Mock/CI 成功不能证明厂商实测准确率、参数确实生效或身份认证。
- 能力相近、协议相同不能证明同一模型权重；混路由结论依赖独立真值。
- 用户输入的 `official` 角色和 `source_verified=true` 不会自动构成独立来源认证。
- Token 费用仅在有实际 Usage/可信单价时可估算；外部子进程成本可能未知。
- 历史版本 Deep Reference 与不同任务/评分器修订版本不得直接比较。

**唯一 M0～R 执行状态**：[17 号路线](design/17-engineering-closure-roadmap.md)。单机升级/备份/恢复见 [升级指南](upgrade-and-restore.md)。
