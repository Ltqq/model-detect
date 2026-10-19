# 变更记录

## Unreleased — 工程开发阶段（尚未发布）

> 当前为代码开发进展，不代表已完成官方与供应商真实测试、身份真值校准或客户验收。正式版本号和 Release Tag 在统一验收后确定。

### M0～M6：权威评测轻量主线（仅工程/CI，未完成 R 实测）

- 统一测试来源目录，继续复用固定版本 Kimi 官方协议 Pytest、lm-evaluation-harness 的原始评分器。
- 按需保留 lm-eval 原始结果与样本日志、自动生成不可覆盖的 Reference 快照；来源数据集/评分器修订由用户提供时保持未独立认证状态。
- 已支持任务的官方/供应商同条件分数及 Kimi 协议用例分栏对照，接入已有 Web/SQLite、中文 HTML/JSON/ZIP、历史与删除。
- 可选 Deep 包含现成 MATH-500 高难数学任务；Kimi OCRBench/MMMU/BEAM/DeepSWE 等高级能力仍未完整接入。
- [#119](https://github.com/Ltqq/model-detect/pull/119)：第三方 proxy-sleuth 默认关闭、手动启用仍支持。
- [#120](https://github.com/Ltqq/model-detect/pull/120)：合并过时 README 与排期，保留一份 M0～R 开发/验收状态表。
- [#121](https://github.com/Ltqq/model-detect/pull/121)：Web 审计/Reference 失败异常不再将 Key、Prompt、内部错误原文持久化到 SQLite 或显示到历史。
- **后续只执行 R 真实 API/目标机验收后再决定正式版本 Release，不因为 Mock/CI 通过就宣称模型身份验证准确率。**

### 可信对照与 GLM53 实测链路

- G0：版本化任务比较契约、历史证据离线回放与可解释能力评分。
- G1：Benchmark 依赖检查、离线任务缓存检测、参数证据核验、脱敏逐轮检查点、原生请求异常归类和付费前预算保护。
- 保持 `unknown/insufficient` 与 `fail` 语义分离；不把能力相近升级为模型身份认证。

### Reference

- Reference 创建/导入暂存、原子发布、旧版备份与显式覆盖、同 ID 锁、SHA-256 完整性验证。
- 路径穿越及恶意 Manifest 附件路径保护；旧 Reference 无文件哈希时不冒充已校验来源。

### 用量与成本

- 请求级 UsageRecord；未返回 Usage 的任务保持 unknown。
- 支持缓存读写和推理 Token 子项（不重复计费）、配置单价、部分费用统计与中文报告。
- GLM53 名义 Token 预算和请求数上限；不能保证供应商账单硬上限。

### Kimi 官方适配

- 固定官方 Kimi Vendor Verifier 源码版本；测试目录范围选择、离线 JUnit 结果导入。
- 显式授权后的本地官方 pytest 执行入口；要求 HEAD 和工作区洁净，并避免泄露凭据。

### 产品集成与校准准备

- OSS 四引擎离线状态检查；不将工具存在误认为可靠运行。
- Web/SQLite 历史、报告 ZIP、删除的本地 Mock E2E。
- 校准 Manifest 独立正负例和缺失报告预检。

## 发布条件

在真实环境与完整回归通过前，上述改动均为 **Unreleased**。查看 [发布清单](docs/release-checklist.md)。

### 精简维护
- 移除仅检查文档/测试文件存在性的 `release-doctor`，与现有 CI/发布清单职责重复。保留真正防误判、安全和数据完整性的测试。
