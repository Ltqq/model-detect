# GLM-5.3 专项准入：官方依据、检测能力与证据验收（2026-10-13）

## 定位

本专项只声明 **GLM-5.3 的 OpenAI-compatible Chat Completions API 行为** 与 **官方/供应商同一评测套件的能力差异**。它不验证 OpenAI Responses 协议、Anthropic Messages、百万 Token 真正满窗支持、视觉（官方当前只支持文本）、量化位宽或模型权重身份。

**权威性的三个层次**：
1. 协议规则来自第一方 Z.ai [GLM-5.3](https://docs.z.ai/guides/llm/glm-5.3) 和 [Chat Completion API](https://docs.z.ai/api-reference/llm/chat-completion)；受控 API 请求证实“被测端点观察到的行为”，无法证明客户真的部署了官方权重。
2. 能力快速筛查是自研客观小题（5 类 × 2/5 题），**不能说明官方满血**；默认只输出启发式差异，不宣称显著退化。
3. 可选的 **EleutherAI lm-evaluation-harness** 使用生成式标准任务 GSM8K、IFEval、MATH-500（`minerva_math500`），从相同客户端机器用同一任务版本分别运行官方和客户；核对评分指标、实际样本量、数据集版本和任务配置 SHA-256。分数只能与本次官方同配置运行直接对照，不可当作官方已发表 Benchmark 成绩复现。

Z.ai 的 [glm-simple-evals](https://github.com/zai-org/glm-simple-evals) 支持 AIME/GPQA/MATH500/MMLU-Pro/LiveCodeBench 等，但其开源指南专门针对 GLM-4.5/4.6，部分任务需要外部 Judge、数据集、Coding Environment。**本项目没有伪称实现完整官方 GLM-5.3 Vendor-Verifier**。普通 OpenAI Chat 端点无法进行 `multiple_choice`/logprob 任务，因此不直接套用默认 MMLU-Pro 的 likelihood 评分。

## 协议覆盖矩阵（Chat Completions）

| Case | 官方依据 | 本工具验证 | 结果边界 |
|---|---|---|---|
| chat.basic | Chat Completion 响应 | 200 + 可判定助手答案 | 不证明身份、延迟或推理生效 |
| thinking.enabled | GLM-5.3 强制思考 | enabled 请求接受 | 不证明服务器真实思考预算 |
| thinking.disabled | 官方不支持禁用思考 | 须实际返回**指向该参数**的 400/422 才算证实；401/403/429/5xx 都不可判 | 不是随便 4xx 都算成功 |
| reasoning.low/high/max | GLM-5.3 支持这三档 | 同样 body，分别发送不同等级 | 接受不代表真正生效 |
| chat.stream | Chat Completion SSE | 消耗完整流，确认 text/event-stream、终止原因和 `[DONE]` | 超过读取安全上限或提前断开为证据不足 |
| tools.auto | Function Calling | 工具名正确、arguments 可解析 JSON、工单号正确 | auto 不调用工具时“证据不足”，不是不支持 |
| json.object | 结构化 JSON 输出 | 返回可解析 JSON 对象 | 不等于严格 JSON Schema 支持 |
| chat.multiturn | 多轮对话 | 已知上下文的确定性提取 | 不能外推百万上下文 |
| usage | Chat Completion usage | 读取实际 prompt/completion、缓存与 reasoning 细分（存在时） | API 自报值并不是独立 Tokenizer 验证 |

**范围之外（不能默认判通过）：** Responses API、Anthropic Message、完整工具真实外部调用闭环、百万 Context、极限输出 128K、所有参数错误码具体形式、准确计费、Code Agent/TerminalBench 复现、模型真实性。

## 能力及成本档位

- `--mode protocol`：每轮 10 请求，推理/流式/工具/JSON/多轮。
- `--capability-profile smoke`：每轮 10 道简单客观题，**仅验证基本可答**。
- `--capability-profile standard`：每轮 25 道简单客观题，不是高难 Benchmark。
- `--benchmark smoke|standard|deep`：**额外显式选择**；生成式外部标准任务，各任务最多 5/25/100 样本，每个 Endpoint 默认 1 轮。
- `--benchmark-max-gen-toks 8192`：额外评测的单请求生成预算；评测子进程默认不重试。
- `--max-requests`：对原生 Case 数 + 额外 Benchmark **名义样本数**做运行前上限检查；外部工具的实际 HTTP 交互及 Token 不具备硬成本上限，**不要把名义上限当真实账单上限**。

**默认 `all+standard`、官方3次+客户1次**：10协议 + 25简单能力题，合计 140 个 API 请求，输出预算配置累计 `245760` token；实际输出可以少得多，SSE 的 usage 由完整流尝试读取。输入估算使用 JSON UTF-8 字节 /3 的粗估方法，并非 Tokenizer 精确计量。提供价格后只显示估算情景；执行后针对原生请求有实际 Usage（缺失记 unknown），**可选标准 Benchmark 子进程仍然无法计量真实 Token**。

如果增加外部 Standard Benchmark，官方与客户各1轮，额外 **3任务×25题×2=150 个名义样本**；名义输出配置上限 `150×8192=1,228,800`，这不是实际消耗，真实任务的 token 可能受任务默认生成参数、服务端预算、重试等影响。默认 `--max-requests=160` 会拒绝这个组合，须用户手动提高才可付费运行。

## 安全、数据来源与复现

- Key 只从本地环境变量 `GLM53_OFFICIAL_KEY` / `GLM53_CUSTOMER_KEY` 读取；不用聊天或命令行传密钥值。
- 官方端点默认要求 `https://api.z.ai/` 或 `https://open.bigmodel.cn/`；其他私有端点只能显式 `--allow-unverified-reference`，报告会标明不能证明第一方来源。
- 官方和供应商相同 Model ID 与测试请求；Capability Suite 有版本及 SHA-256；标准 Benchmark 记录 Harness 版本、任务配置 SHA-256、Dataset 版本、实际样本数、Metric。
- CLI 默认预览，使用 `--execute` 才付费执行；已有输出文件不能静默覆盖。
- HTTP 401/403/429/5xx、推理预算不足、SSE 提前断开、工具自动不调用等情况明确标 `insufficient/error`，不能计入正常协议符合度。
- CI 是 Fake Endpoint/Fixture 测试，不涉及模型真值或官方付费 API；只有真实运行后才能产出实际通过率。即使此时所有 Case 通过，也只能说明“这些 API 行为在本次环境下符合观察标准”，**不等于权重官方认证**。

## 执行方法

```bash
git pull origin main
pip install -e .
# 想运行额外标准 Benchmark，先 pip install 'lm_eval[api]'，并确认 lm_eval 命令可用

# 仅预览（不会发付费请求）
model-detect glm53 compare \
  --official-url https://api.z.ai/api/paas/v4 \
  --customer-url https://relay.example/v1 \
  --mode all --capability-profile standard

# 配好两组 API Key 环境变量后：
model-detect glm53 compare \
  --official-url https://api.z.ai/api/paas/v4 \
  --customer-url https://relay.example/v1 \
  --official-runs 3 --customer-runs 1 \
  --mode all --capability-profile standard \
  --execute --output-dir glm53-evidence/first-run

# 可选标准 Benchmark，评测请求可能较贵：必须手动调大预算上限
model-detect glm53 compare \
  --official-url https://api.z.ai/api/paas/v4 \
  --customer-url https://relay.example/v1 \
  --official-runs 1 --customer-runs 1 \
  --capability-profile smoke --mode all \
  --benchmark standard --benchmark-runs 1 \
  --max-requests 200 --execute \
  --output-dir glm53-evidence/benchmark-run
```

输出 JSON、中文 Markdown、独立 HTML。首先检查“官方各协议 Case 自身是否成功”；如果官方也失败，客户该 Case 不允许据此判“不符合”。标准评测对比发现差异，只能报观测差值和不可比，不能凭小样本报告“显著降智”。

## 对外正式验收仍需执行

1. Z.ai 官方 Key/地址真实联通，官方端点正常返回 Chat Completion、Thinking、Tools、JSON、完整 SSE；
2. 客户渠道使用相同真实测试脚本；保存报告哈希与运行日期；
3. 对强 Benchmark 的各 task 检查实际 Dataset 和 scoring code；如果评分器下载失败/依赖缺失，明确不通过验收；
4. 若客户要求“官方智商一致”，使用足够高难的独立 Benchmark、重复试验/保留样本、业务事先约定退化容忍度，避免只用 25 道简单题；
5. 另验收入站额度和 Token Usage 的真实性（可结合 tokenizer/网关原始账单），模型不能自己证明自己计费准确；
6. 若必须测 Coding Agent 或 1M Context，需要独立大成本实验环境；当前项目不宣称覆盖这些场景。

原工程开发路线 [17](17-engineering-closure-roadmap.md) 不改动；本临时 GLM-5.3 需求结束后再继续。
