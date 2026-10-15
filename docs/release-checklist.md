# Release Candidate 发布门槛（F）

当前仅准备发布工程资产，不执行正式 Release。所有项目按照 `代码已开发 / CI 已通过 / 真实验收通过 / 未覆盖` 四级记录。

## 发布前必须核对

- [ ] Python 3.11、3.12 全量 CI 通过；不允许失败或未评估的必需单测。
- [ ] 在指定机器安装依赖，验证 CLI 和单用户 Web 启动/退出/历史清理。
- [ ] 从旧版备份复制 SQLite、Reference、Report，验证旧文件不会因升级被覆盖；演练失败回滚和恢复。
- [ ] 检查 `Authorization`、Cookie、URL Query Token、插件 stdout/stderr、用户回答等路径不会把密钥写入报告/ZIP/日志。
- [ ] 用用户持有的 GLM-5.3、Kimi-K3 官方和供应商 API，在明确授权和预算下执行单次受控 Smoke，复核实际发包、参数、缓存、协议和版本。
- [ ] 第三方四个 Adapter 固定版本、命令、真实结果合同与失败映射逐一留存脱敏验收记录；未验证者在产品中展示限制。
- [ ] Reference 官方来源、独立真值、受控路由变体、正负例与留出数据集检查；校准统计必须区分独立 case 与重复 run。
- [ ] 报告中文结论、未知用量、费用、历史、CLI/Web/JSON/HTML/ZIP 全链路与新旧数据兼容性。
- [ ] 只有符合客户事先明确同意的准入阈值，才对外发布正式供应商结论。
- [ ] 修改并冻结版本号、更新 CHANGELOG 与 README；确认 Git Tag/Release 内容与已验收范围一致。

## 统一验收命令模板（执行前必须确认成本与授权）

```bash
python -m pytest -q
model-detect oss-status --json
model-detect glm53 doctor --benchmark standard --verify-task-cache
model-detect glm53 compare --official-url <official> --customer-url <provider> --benchmark smoke
model-detect validation doctor --manifest ./controlled-cases.yaml --strict-reports
```

上面 `compare` **没有** `--execute`，仅生成预算预览。真实 API 调用须另行显式指定参数，不在代码开发阶段运行。

## 必须保留的未覆盖说明

- Mock CI ≠ 真正在线能力合格。
- 模型能力相近 ≠ 同一模型权重真实性证明。
- 未获官方凭据、独立网关日志或可信标签时不宣称 TP/FP 检测准确率。
- Token 费用只是可见用量和配置价格，未上报的第三方任务可能产生未知费用。

最终准入状态由实际证据决定，不根据 TODO 数量或 PR 数量自动判定。
