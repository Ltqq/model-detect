# 技术决策与演进原则

本文记录后续开发时不应反复讨论的核心决策。

## ADR-001：性能测试独立

决定：

model-detect 不接 TTFT / ITL / TPS / RPM / TPM / 并发性能压测。

原因：

- 已有独立工具
- 性能与模型身份是不同问题
- 避免报告把“快”误解成“真”
- 避免 Deep Audit 请求调度变复杂

## ADR-002：Python 为主语言

决定：

核心继续 Python。

原因：

- eval 生态
- proxy-sleuth
- lm-eval
- sandbox runner
- 数据分析

除非出现性能瓶颈，否则不引入 Go 重写 Core。

## ADR-003：单体优先

决定：

V1/V1.1 继续单体 FastAPI + CLI。

不拆微服务。

外部引擎通过 Adapter / subprocess 调用。

## ADR-004：Evidence First

任何评分项必须能定位到：

- Probe
- Expected
- Observed
- Evidence

没有证据的结论不得进入正式 Verdict。

## ADR-005：强身份结果必须有 strong evidence

模型规则、字段行为只能作为 weak/medium。

最终 verified pass 需要 Statistical Fingerprint 或同等级 strong identity evidence。

## ADR-006：Reference 是核心资产

重要模型先建立：

```text
official/trusted endpoint
  ↓
protocol signature
  ↓
statistical fingerprint
  ↓
baseline report
```

再测供应商。

## ADR-007：OSS 通过 Adapter 复用

不 fork 后魔改成一个不可维护大项目。

统一结构：

```text
OSS Tool
  ↓
Adapter
  ↓
Unified Probe Result
```

## ADR-008：LLM Judge 最后使用

判定优先级：

1. deterministic
2. executable test
3. statistical
4. reference compare
5. LLM judge

能写规则就不让另一个模型来“感觉一下”。

## ADR-009：Coding 必须沙箱

代码生成测试禁止直接在宿主执行。

默认 Docker：

- no network
- memory limit
- CPU limit
- timeout
- temp workspace

## ADR-010：暂不迁 PostgreSQL / Redis

继续 SQLite + filesystem，直到出现实际并发/多人需求。

迁移条件见 `02-architecture.md`。

## ADR-011：协议层需要抽象

OpenAI 已经做起来，但 Anthropic/Gemini 不能继续复制整套 Probe。

V1.2 前先抽象：

```text
ProtocolClient
  request_chat()
  request_stream()
  request_tools()
  request_structured()
  normalize_usage()
  normalize_error()
```

各协议实现 Adapter。

## ADR-012：报告避免伪精确

不要输出：

```text
这个模型 97.63% 是真的
```

除非这个数字有经过校准的统计含义。

优先：

```text
Verdict: MATCH / REVIEW / MISMATCH / INSUFFICIENT
Confidence: low / medium / high
Evidence: ...
```

分数用于准入维度，不冒充数学意义上的“真伪概率”。
