# GLM-5.3 G0 离线重算验收手册（2026-10-14）

> 用途：在 **G1 前**完成旧证据评分修复与可审计重算。与 [17 号总开发计划](17-engineering-closure-roadmap.md)、[20 号真实测试复盘](20-glm53-live-evidence-triage.md) 同步。**本文并非官方模型认证结果。**

## 命令与安全边界

首次执行前先更新仓库（`git pull origin main`，`pip install -e .`）。

```powershell
# 完全离线，既不需要官方/客户 API Key，也不会产生 Token 费用
model-detect glm53 replay `
  --evidence-zip ./glm53-evidence.zip `
  --output-dir ./glm53-offline-replay-20261014
```

将原始 ZIP 放在本地；命令**只读取、不解压到磁盘、不修改源文件**。生成：
- `glm53-replay.json`：来源 ZIP/成员 SHA-256、各阶段重算摘要、全部标准 Benchmark 子指标、结果判定状态；
- `glm53-replay.md`：中文正式复核草稿；
- `glm53-replay.html`：可独立打开的安全 HTML 表格。

若输出文件已存在将拒绝覆盖。原先的 01～05 报告原封保留。**不要把原始 ZIP 或包含密钥、渠道详情、题目与回答的日志上传到公开仓库。**

## 真实 ZIP 中已能独立核验的观察事实（不等于 CLI 全链路验收）

使用用户本次提供的 `glm53-evidence.zip` 原始 01/02/03/05 记录核对：

| 项目 | 官方旧评分 | 官方按 v2 格式规则重算 | 客户旧评分 | 客户重算 |
|---|---:|---:|---:|---:|
| 02 Smoke 客观能力 | 9/10 | 10/10 | 10/10 | 10/10 |
| 03 Standard 客观能力 | 66/75 | 75/75 | 23/25 | 25/25 |

03 中 **11 次旧 fail 被纠正**（官方 9、客户 2）：包括 Big-O 正则转义问题、Markdown 加粗、`x = 8` 格式差异。这是离线利用已保存的短答案摘录按严格题型正规化重新判分的结果，**显示轻量题集已出现严重天花板效应，不能用满分说明“满血模型”**。01 为协议-only，不存在能力题重算。

05 的真实 lm-eval 0.4.13 任务配置使用版本化 v2 哈希比较，剔除不同 base_url / 函数对象地址后，这三项原始配置哈希均一致（已在本地对原始 JSON 独立核验）：

| Task（25 样本/端） | 指标 | 官方 | 客户 | 差值 |
|---|---|---:|---:|---:|
| GSM8K | exact_match,strict-match | 96% | 96% | 0 |
| GSM8K | exact_match,flexible-extract | 96% | 96% | 0 |
| IFEval | prompt_level_strict_acc | 48% | 48% | 0 |
| IFEval | inst_level_strict_acc | 43.24% | 51.35% | +8.11 个百分点 |
| IFEval | prompt_level_loose_acc | 48% | 48% | 0 |
| IFEval | inst_level_loose_acc | 43.24% | 51.35% | +8.11 个百分点 |
| MATH-500 | exact_match | 88% | 88% | 0 |
| MATH-500 | math_verify | 92% | 88% | -4 个百分点 |

所有 Task 的 **`sample_len` 是样本数而不是评分指标**，必须排除出分数表；标准指标的 `stderr` 也不能混进得分对比。

04 的首次 IFEval 依赖失败和后来 Smoke 只保存汇总，没有可供再解析的完整 Task Config JSON；离线重算**只能保留其来源摘要和历史诊断**，绝不能凭 05 的成功替 04 判通过。

## G0 工程验收口径

- **G0.1**：可比性契约 v2 复用在标准 Benchmark，真正参数或评分规则不同仍 `incomparable`。
- **G0.2**：旧 ZIP 具备只读 `replay` 流程，01～03 Native 能重判、05 双端完整原始 JSON 全部指标可重比；04 仅保留诊断。CI 使用脱敏结构与正反例，**不存放真实原始 ZIP**。
- **G0.3**：共享轻量评分器处理已证实的规范化问题，不放宽不相关答案。
- **G0.4**：新增运行对明确的中文/英文禁用思考 400 正确认定，401/429 不能假通过。历史 01/03 的 JSON **未保存原始中文 400 错误体**，因此历史记录仍为 `official_inconclusive`；手写补充备注只能作为待人工复核来源，不能自动改变历史证据状态。
- **G0.5**：报告必须将协议、轻量能力、标准 Benchmark 各指标、身份结论分开；`customer_inconclusive` 与 `deviation` 不混淆；只陈述观测差值，不能宣称统计学等价、权重身份或供应商准入认证。

## G1 尚未开始（重要）

此次改进**不验证**实际请求是否准确传入并生效了 `thinking`/`reasoning_effort`、可执行 Coding/Agent、1M Context、外部 lm-eval 的完整 usage/费用，也未修复依赖预检、外部进程失败恢复。这些仍须按照 17 号计划进入 G1/A/B；修完 G0 不意味着可以直接扩大付费 Benchmark。

当 `replay` 在客户本机产生新结果时，应保存新报告/原 ZIP 的 SHA-256，并与本次核对值逐项对照；如因文件不一致得到 `incomparable`，要检查版本和合同而非强行改成通过。
