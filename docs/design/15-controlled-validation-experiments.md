# Phase 3：受控模型鉴别实验设计与验收

## 目标

实现一套低成本、可复现、可审计的 **Validation（检测器有效性验证）** 流程，检验 model-detect 的身份指纹、质量退化及路由异常检测效果，而不是凭开发者主观给“准确率”。

## 一、场景与真实标签

实验包括：
- `same_model`：Official vs 同一官方 Endpoint（Known Positive）；身份应一致
- `different_model`：已知不同模型（Known Negative）；身份预期不一致
- `different_effort`：同一模型不同 reasoning 档位；是否产生质量退化需要真实标签，不假定低 effort 必然每道题更差
- `mixed_routing`：外部**受控**网关设置 0%、10%、30%、50% 路由比例；只由实验声明记录真值
- `different_provider`：同模型不同 Provider
- `different_version`：同模型家族不同版本

**真实标签必须单独明确指定**：`identity`（same/different）、`routing_mixed`（true/false）和 `quality_regressed`（true/false）；未实证确认的维度保持 `null`，不能自动推断。尤其不能从 model alias 或期望分流比例擅自推断身份结果。

## 二、工具形态

`model-detect validation run --manifest experiment.yaml --output-dir ...`
- 从 YAML/JSON 读取已明确指定的测试场景、Endpoint、API Key **环境变量名称**、Reference、Profile、重复次数
- 不保存 API Key，不读取 manifest 中的明文 Key，不进行自动混路由模拟
- 用户必须在外部准备可控制路由比例的测试网关；程序不会假装已经设置比例
- 每个 case 按真实 API 调用产生 `report.json`，同时保存真实标签与采集元信息
- 串行执行，默认关闭可选昂贵 Benchmark / Proxy；每个 case 限制重复次数，错误单独记录不伪造样本

`model-detect validation evaluate --manifest experiment.yaml --output-dir ...`
- 对已有报告离线评分，不请求付费 API
- 只取**对应维度的强证据**，不从综合分推算真假：
  - Identity：`identity.fingerprint.reference_compare` 的 MATCH / MISMATCH，uncertain 记 abstain
  - Routing：明确 `mixed-routing-likely` 的路由证据；仅 suspicious 记 abstain
  - Quality：`official_baseline_comparison` 的 valid `baseline_match` / `quality_regression`，条件不齐或 incomparable 记 abstain
- 每个维度独立 TP、TN、FP、FN、Abstain；灵敏度、误报率、精确率、负类识别率、有效覆盖率带分母
- 观察样本为实际完整报告，而不是配置表行数；按场景展示各次结果
- 输出 `validation.json` + 中文 `validation.md`；不把实验夹杂进生产准入评分

## 三、不可造假的边界

- manifest 是**实验人员声明的真值**，不是程序能够证明的物理事实；需要 `truth_source` 记录可复核的证据来源（如路由配置编号/实验记录），不可将其宣传为外部认证
- 路由比例为受控**配置目标值**，不等于通过本工具已验证的实际分流率
- `0/10/30/50` 是计划测试的四组比例，是否检出取决于已有 Probe 的请求数量及实际分流随机性
- 不使用弱 family feature 分数代替强身份匹配证据；不以“可疑”充当阳性
- 分母为零、未执行、缺失 Reference、结果不可比都必须显示样本不足，**不能输出虚假的 100% 准确率**
- CI 使用合成**报告结构**测试提取/汇总逻辑，真实模型检出率必须来自真实可追溯的请求报告

## 四、阶段小任务

1. [ ] 实验配置 Schema、真值约束、文件路径解析、安全验证
2. [ ] 离线结果分类、独立混淆矩阵、跳过/弃权与覆盖率
3. [ ] 可选真实 API 串行运行、同一配置重复采集、结果落盘
4. [ ] CLI、中文报告、示例 YAML 与 README
5. [ ] 3.11/3.12 CI、负样本和边界测试、合并

## 五、完成定义

✅ 工具允许用户基于真实标签复现实验并看出每类场景到底检出多少；
✅ 不需要额外的 Redis / Worker / 调度平台；
✅ 有报告才统计检出率；无报告不宣称任何结果；
✅ 完整保留 Phase 4 的真实 Kimi/GLM 官方校准为后续任务。

## 完成状态（2026-10-13）

Phase 3 的实验机制、CLI、离线统计、中文报告及测试已合并到 main：PR #47。Python 3.11/3.12 CI 通过。**真实官方/受控网关实验尚未执行**，实测检出率与误报率属于 Phase 4，不能用合成单元测试结果代替。
