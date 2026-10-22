# model-detect v0.2.0 交付测试与发布门槛

> 2026-10-19。产品定位与范围以 [冻结宪章](design/product-charter-v1.md) 为准；任务状态以 [唯一执行计划](design/v020-execution-plan.md) 为准。本清单只描述**如何验证**，不新增功能方向。0.2.0 是开发版本号，未通过本清单前不应宣称正式 Release。

## 2026-10-22 工程候选版验收状态（可追溯）

- [x] [PR #202](https://github.com/Ltqq/model-detect/pull/202)：冻结 v0.2.0 版范围，离线 handoff 用真实 PASS/ERROR/FAIL/SKIPPED 验证报告而非空报告；[CI #39714796543](https://github.com/Ltqq/model-detect/actions/runs/39714796543) 三个 job 全绿。
- [x] [PR #203](https://github.com/Ltqq/model-detect/pull/203)：原生 HTTP 在 JSON、SSE 和 HTML 错误中收到 API Key 回显时执行脱敏；新增真实报告文件回归；[CI #39729178696](https://github.com/Ltqq/model-detect/actions/runs/39729178696) 三个 job 全绿，Python 3.11 显示 613 passed。
- [x] [PR #204](https://github.com/Ltqq/model-detect/pull/204)：修复 Web 报告证据链接正则转义问题，并在 Web E2E 中点击证据 API；[CI #39729565094](https://github.com/Ltqq/model-detect/actions/runs/39729565094) 三个 job 全绿。
- [ ] **最新 main 提交验收**：每次合并后以对应 HEAD 的 Actions 日志为准，不能借用旧 PR 的通过记录。本分支已新增完整读取 ZIP（报告 JSON/HTML/Evidence）及合成密钥排查的 E2E，正式合并仍需确认对应 HEAD 的 CI。
- [ ] **用户机器验收**：实际环境的 Web 启停、同一套历史与 ZIP 下载、SQLite + Reference + 报告文件的备份恢复演练，以及授权供应商端点实测。CI 的临时目录和 Mock 不能替代这些动作。

**安全边界**：报告和 ZIP 应作为私有审计材料保存，尤其是显式启用的第三方回归工具可能打包原始 Prompt/输出或上游生成的运行文件。原生 HTTP 反射 Key 脱敏测试不代表所有外部工具产物都已自动脱敏；未经检查不得公开上传 ZIP。工程候选版不等于认证真实模型身份。

## A. 无 API Key 即可执行的工程交付测试

在 Python 3.11 / 3.12 环境：

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m compileall -q model_detect
model-detect version
model-detect oss-status --json
model-detect web --help
model-detect reference --help
```

GitHub CI 的 wheel + sdist 构建及**在源码目录以外安装 wheel**验证为必须通过的发布门槛，内容至少包含：五个目标型号的 YAML 规则、公开背景参考、Web 模板。未安装外部 OSS 工具时 `oss-status` 必须说明缺失或未验收，绝不能当通过。

- [x] 五型号 OpenAI Chat Completions 模拟 HTTP 服务全审计、报告写入、敏感信息脱敏的离线测试已有自动化覆盖。
- [x] HTTP 200 缺 message、SSE 头但没有 Delta、畸形 SSE、JSON 错误响应等反例均应失败。
- [x] SQLite `JobStore` 历史备份与恢复后的旧 JSON/报告路径兼容回归（#158）。
- [x] 五型号公开汇总参考和来源级别均通过确定性测试，只作背景，不得做未经同条件核验的分数差。
- [ ] 在**用户实际部署环境**完成完整 wheel 安装、Web 启停、历史保存/查看/下载/删除、Reference 和报告目录备份及恢复演练。GitHub CI 不能替代这一步。

## B. 真实供应商 API 测试（只需要待测渠道，不需要官方 API）

用户手动提供本人有权使用的单个供应商 `Base URL`、`API Key`、`Model ID`，从 Quick 开始，再按需要开启 Standard/Deep。真实调用会产生费用，**必须由执行人主动确认预算、请求上限、并验证渠道稳定性；软 Token 限额不是账单硬限额**。

验收每个目标型号时记录：日期、网关实际 Model ID、供应商地址的脱敏版本、档位、实际请求/Token 使用、协议 PASS/FAIL/UNKNOWN/不适用、错误和失败详情、报告文件。只测试已有的必要官方规则，未知行为不能写成 PASS。

- [ ] 五目标型号各至少一个授权供应商端点执行基础/流式/错误响应检查，并将费用及限制写进非公开验收记录。
- [ ] 按需执行第三方工具：固定版本的 EleutherAI lm-evaluation-harness 原生评分器，以及 Kimi-K3 官方 Pytest 子套件（适用时）；依赖未安装、题集不可用和成本不明时明确不执行，不显示通过。
- [ ] 使用者审阅一份真实中文报告、历史复测及导出，确认没有 API Key/完整私有 Prompt 泄漏。
- [ ] 不要求官方模型 API、不要求模型权重认证、不要求 Agent/视觉大型 Benchmark；无同题同参数逐样本 Reference 时官方公开分数为背景参考。

## C. 发布判定

- [ ] 当前产品范围内的安装/恢复和授权渠道测试有可复核证据。
- [ ] P0 冗余 OSS 适配/评分器经引用、许可证和历史兼容评估，已删除或隔离并形成明确的保留理由；不能将只隐藏 Web 控件算作物理删除。
- [ ] 主流程 401/403/429/超时/无效 SSE、原始秘密脱敏和缺乏证据的 UNKNOWN 状态回归完整通过。
- [ ] 运行结果/第三方评测的未覆盖项有明确标识；没有虚假“模型权重认证率”。
- [ ] 在用户实际本地环境做数据备份并演练恢复后，再执行 git tag / GitHub Release；未达到不得提前宣布正式发布。

## 结论边界

CI / Mock 通过只表明软件路径满足离线合约，**不证明任何特定供应商的真实性、模型权重、能力分数或费用**。其他模型、型号与新的 API 版本需独立核实。Kimi 官方验证器建议在 Python >=3.12 独立虚拟环境运行。见 [备份与恢复](upgrade-and-restore.md)。
