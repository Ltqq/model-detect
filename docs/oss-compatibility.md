# 第三方 OSS 兼容性清单（D1）

本表只描述代码中已存在的适配器和本地可观测状态，**不是第三方工具已完成真实模型验收的证明**。

```bash
model-detect oss-status
model-detect oss-status --json
```

| 工具 | 适配模块 | 固定/已检查版本 | 代码状态 | 待统一真实验收 |
|---|---|---|---|---|
| EleutherAI/lm-evaluation-harness | adapters/lm_eval.py | 本项目 GLM53 目标 **0.4.13** | adapter exists，CLI/Task 环境可离线检查 | 完整任务安装、模型发包、成绩 |
| promptfoo/promptfoo | adapters/promptfoo.py | 未完成固定版本兼容实证 | adapter exists，检测本机命令 | 运行和 JSON/错误映射 |
| Babapei/proxy-sleuth | adapters/proxy_sleuth.py | 未完成固定版本兼容实证 | adapter exists，检测本机命令 | 命令、结果映射与未知状态 |
| ToseaAI/llm-fingerprint-detector | adapters/fingerprint.py | 未完成固定版本兼容实证 | adapter exists，检测直装命令或 npx | CLI JSON 合同、自一致性和身份表述 |

检查字段区分：`adapter_exists`（存在适配代码）、`executable_found`（可找到入口）、`version_compatible`（有已确认版本约束）、`runtime_verified`（是否实跑成功）、`result_trust_verified`（是否可信地验证结果）。`npx` 找到不代表依赖已经缓存，某些执行方式会下载包。

当前实现只提供**完全本地**的命令可用性诊断。最后集中真实验收时才运行第三方工具，并记录 OS、Python/Node 版本、工具固定版本、原始脱敏产物与失败类别。

发布门槛：四大工具中没有完成真实验收的部分必须在正式报告中显示未验证/未计量，不可用「命令存在」冒充「结果可信」。
