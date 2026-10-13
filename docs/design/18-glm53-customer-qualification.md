# GLM-5.3 客户专项：官方在线基准 + 协议准入 + 能力对照

> 临时业务需求；原 [17 号工程收尾计划](17-engineering-closure-roadmap.md) 原封保留。协议符合性、能力对照、模型身份是**三条不同证据**，不可相互替代。

## 目标与现状

通过官方 Z.ai Endpoint 与客户 Endpoint，在**相同模型 ID、请求参数、固定题集版本**下执行对照。输出中文报告，包含协议逐 Case 结果、能力分类成绩、官方基准方差/客户差异、未证实能力、请求量/粗预算与实际 usage（能取到时）。

不预置“官方 GLM-5.3 成绩”；每次运行应真实向用户提供的官方端点发起请求。模型厂商和客户密钥只从环境变量读取，不写入报告/仓库。

官方资料：
- GLM-5.3 模型特性 https://docs.z.ai/guides/llm/glm-5.3 ：1M context、128K 最大输出、thinking 必须 enabled、reasoning_effort=low/high/max（默认 max）；
- Chat Completions https://docs.z.ai/api-reference/llm/chat-completion；
- Function Calling https://docs.z.ai/guides/capabilities/function-calling；
- 官方模型开源仓库 https://github.com/zai-org/GLM-5 （注意：chat-template 非法值回退行为不等于官方 API 合同）。

API 格式：Z.ai OpenAI-compatible 路径形如 `https://api.z.ai/api/paas/v4/chat/completions`，以及文档所述 Coding Plan 专用前缀；**不能任意在 /api/paas/v4 后追加 /v1**。不以某客户端 URL 命名约定代替实际 endpoint 规范。

## 本次小阶段与验收

### Stage 1：模型规格与计划/预算（无需真实 Key）
- [x] `glm-5.3.yaml` 独立规则，正式声明 thinking、effort、语义来源；不能简单复制 GLM-5.2 的 high/max。
- [x] 协议+能力固定测试清单和稳定 ID；无官方文档证据的错误参数处理只能作观察，不能作为不合规。
- [x] **执行前**预估各类请求次数、题目数量、粗略输入 Token、输出上限；解释它不是账单或精确 tokenizer 计数。
- [x] 可配置 official/customer 重复次数、能力档位、执行模式；默认预览、须 --execute 才发付费请求。

### Stage 2：双端点协议实测
- [x] 模型 ID、thinking.enabled/disabled、effort low/high/max、SSE、tools、JSON、multi-turn、usage 基本校验；
- [x] 官方/客户各自保留逐 Case HTTP 状态、证据，不将 HTTP 200 等同于所有功能生效；
- [x] 必须区别“官方明确支持/禁止”“只做观察”“请求失败/不确定”，不兼容不应自动冒充模型替换证据；
- [x] 不把 `tool_choice=required`、`json_schema` 一律当 GLM-5.3 必选能力。

### Stage 3：双端点能力对照（轻量题集代码完成，高难 Benchmark 仍待评估）
- [x] 基于版本化固定客观题的轻量能力抽检（不是完整官方 Benchmark；不要给出“智商下降 X%”的绝对断言）；
- [x] 官方 N=3（可调）次，客户 M=1～3（可调）次；按类别/题目对照和题目级错误解释；
- [x] 低样本或大方差时标“证据不足”；官方自身波动超过阈值时不得宣称客户退化；
- [ ] 高难度编程/Agent 基准下一步可选通过现有 lm-eval、Coding Sandbox 或 zai-org/glm-simple-evals 来扩展，不自造不靠谱评分器。

### Stage 4：报告与回归
- [x] JSON + 中文 Markdown/HTML；内容分为协议、能力、对比有效性、用量/成本估计（不能获取 usage 时明确 unknown）；
- [x] 用 mock/fake endpoint 测不同 thinking/reasoning 响应、JSON、tools、SSE、Token usage、缺失响应、空参考、失败/预算上限；
- [ ] Python 3.11/3.12 CI 全绿，按小任务提交 PR 合并。

## 预算预估口径

**无须等待开发结束**：只要知道题数、输入文本、每题最大输出、重复轮次，就能估算。形式为：

```text
总请求数 = (官方轮数 + 客户轮数) × (协议 Case 数 + 能力题数)
预估输入 Token ≈ 每个请求输入启发式估算之和（注明 tokenizer 不确定性）
最大允许生成量（名义） = Σ各请求 max_tokens
官方/客户现金成本 ≈ 输入量 × 输入单价 + 输出量 × 输出单价
```

`max_tokens` 是每个请求给定的**生成预算**，不是必然消耗；推理 token 是否计入 output、缓存如何计费，需要按渠道账单/usage 校验。
真实口径另取 `usage.prompt_tokens / completion_tokens` 及其缓存、reasoning 子项。缺失记 `unknown`，不记 0。

默认目标是小样本上线前检查，**不是一轮几十亿 Token**。一切付费执行要显式允许，不能默认为用户调用官方端点。

## 与常规计划的关系

本文只针对 GLM-5.3 业务急单。原 [17 号工程收尾计划](17-engineering-closure-roadmap.md) 不修改；本业务完成后继续 A1 Reference 安全覆盖、A2 错误语义、Token Meter、官方 Kimi 验证。

## 实施状态（2026-10-13）

新增 `model-detect glm53 compare` 仅 CLI（Web 入口未新增）。支持离线预算预览（不需 API Key）、显式 `--execute` 的两端点串行调用、协议与轻量能力抽检、中文 JSON/Markdown/HTML。默认 10 个协议用例 + 每轮 25 道低难客观能力题，3 次官方 + 1 次客户合计 140 次 API 请求；所配置的最大输出预算之和为 245,760 Token，不等于真实使用量。**并未接入 GLM-5.3 官方高难 Coding/Agent Benchmark 的完整运行；请勿将轻量题集结果称为“满血”认证。** 原 17 号工程收尾路线不变。真实 API 付费实验尚未进行。
