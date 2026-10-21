# Kimi Vendor Verifier 官方用例适配（C1 / C2 代码阶段）

官方源码： https://github.com/MoonshotAI/Kimi-Vendor-Verifier

本项目固定来源 commit：`66092cf444c97356c0e11c5078c67116390615d9`，许可证 MIT，Python >=3.12。

目前明确覆盖以下官方仓库测试目录（不是复制规则）：

| 官方测试目录 | 内容 | 本项目对应 |
|---|---|---|
| `tests/params` | temperature、top_p、penalty、n 等参数约束 | 协议参数 |
| `tests/k3_features` | 动态工具、response_format、tool_choice、thinking effort | 协议与工具 |
| `tests/tool_call_json_schema` | Tool Call JSON Schema | 工具参数 |
| `tests/prompt_tokens` | usage.prompt_tokens 正确性 | Token 计量 |

**明确排除**：OCRBench、MMMU Pro Vision、BEAM 1M、DeepSWE 等高成本任务，不承诺自动执行。

## 零调用离线使用

```bash
model-detect kimi-verifier plan --suite params --suite k3_features

model-detect kimi-verifier import-junit \
  --file ./private-results/junit.xml \
  --suite params \
  --model kimi-k3 \
  --output-file ./reports/kimi-params-summary.json
```

JUnit 必须来自用户自有授权环境的官方测试运行。报告包含所声明的官方源码版本、文件 SHA-256、用例状态计数、单项用例名摘要；不保存原始 XML、Prompt、失败堆栈、Key。请勿提交生产 XML 或 API Key。

报告标记 `user_supplied_unattested_junit`：无法仅凭文件证明它确实由固定官方源码生成；真实验证需在后续统一验收阶段于本机安装官方仓库、执行受控子集、保留运行环境和输出来源。未检查到的测试不能标为通过。

现有受控在线执行入口仅在手动加入 `--execute` 后运行固定 commit 的原始 Pytest；**没有跨套件的请求量或 Token 硬预算**。官方 Pytest 参数化可能造成请求数远超用例目录数，本工具不会估一个虚假的固定请求数。


## 官方仓库受控执行入口（默认 dry run）

先在本机独立目录检出指定 commit，安装并验证官方依赖（需 Python >=3.12）；**构建、安装依赖不属于本 CLI 的自动步骤**。

```bash
model-detect kimi-verifier run \
  --repo-dir ./vendor/Kimi-Vendor-Verifier \
  --python-executable ./vendor/.venv/bin/python \
  --suite params \
  --model kimi-k3 \
  --base-url https://your-authorized-endpoint.example/v1 \
  --output-dir ./private-kimi-results
```

上面没有 `--execute`，仅预览，不发出模型调用。统一真实验收阶段，准备好测试密钥环境变量 `KIMI_API_KEY` 后，才允许人工加 `--execute`。

- 校验本地 Git HEAD 与固定 commit 完全一致，不自动下载源码。
- 使用本地官方 pytest 文件，不复制官方测试逻辑；参数走环境变量，日志不回传到本工具结果。仍会在本地保存原始 JUnit，必须安全存储。
- Tool JSON Schema 套件设置最多 `--max-cases 20`，默认为 10；其他官方目录不能保证请求数上限，**无严格账单预算**，正式运行需由用户审阅官方测试源码和数据。
- 结果会保存原始 `pytest_exit_code` 及已脱敏的用例状态计数。只有退出码为 0，且至少一项 PASS、没有 FAIL/ERROR/SKIPPED 时状态才是 `finished`；退出码为 0 但包含跳过项返回 `inconclusive`；非零退出返回 `pytest_failed`。失败、超时仍尝试保存可用的脱敏结果；绝不能以 pytest 无报告或 skipped 冒充测试通过。
- `source_verification` 只表示**本地执行时**核验了固定 Git commit 和干净工作树，不能证明原始 JUnit 在离线复制后仍具备来源真实性，更不能认证模型权重。
- Python 3.11 只能使用离线规划/导入，官方验证器依赖 Python >=3.12；运行时应传单独 Python 3.12 虚拟环境可执行文件。
