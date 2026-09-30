# V1 Probe 清单

本文件先定义 V1 检测范围，后续每个 Probe 应拥有唯一 ID。

命名：

```text
category.subcategory.name
```

例如：

```text
protocol.reasoning.invalid_field
provider.azure_apim.headers
integrity.tools.preserved
```

---

## A. Endpoint / Provider

### provider.response.headers

收集全部响应头并匹配 Provider rule。

### provider.error.invalid_model

发送不存在的模型名，检查错误结构。

### provider.error.invalid_parameter

发送非法参数，检查 Error Schema。

### provider.response.model_alias

检查 response 中 model 字段是否发生改写。

### provider.response.id_pattern

检查 response id / request id 模式。

### provider.stream.chunk_signature

检查 SSE event / chunk 格式。

---

## B. Protocol

### protocol.chat.basic

基础 `/v1/chat/completions`。

### protocol.chat.non_stream

非流式。

### protocol.chat.stream

SSE 流式。

### protocol.usage

usage 是否存在且字段合理。

### protocol.finish_reason

finish_reason / stop_reason。

### protocol.invalid.unknown_field

未知字段是否报错或静默忽略。

### protocol.invalid.bad_enum

非法枚举值。

### protocol.invalid.bad_model

非法模型。

### protocol.system

system role。

### protocol.multiturn

多轮上下文。

---

## C. Reasoning

### protocol.reasoning.low

### protocol.reasoning.medium

### protocol.reasoning.high

### protocol.reasoning.invalid_value

### protocol.reasoning.invalid_field

特别用于发现：

`reasoning_effor`

这种错误字段是否被错误接受。

### integrity.reasoning.effect

不同 reasoning level 是否存在可观察差异。

注意：

不能简单根据回答长短判断生效，要结合任务与多次样本。

---

## D. Tool Calling

### protocol.tools.basic

单工具调用。

### protocol.tools.arguments_schema

arguments 是否符合 JSON schema。

### protocol.tools.tool_choice

### protocol.tools.multiple

### protocol.tools.parallel

### protocol.tools.invalid_schema

### integrity.tools.preserved

中转是否丢工具定义。

---

## E. Structured Output

### protocol.json_mode

### protocol.json_schema

### protocol.json_schema_strict

### protocol.json.invalid_schema

### integrity.json_schema.preserved

---

## F. Parameter Integrity

### integrity.max_tokens

判断是否明显 clamp。

### integrity.temperature

判断 temperature 是否可能被固定。

### integrity.top_p

### integrity.system_prompt

检测额外 system prompt 注入迹象。

### integrity.stop

### integrity.tool_definitions

---

## G. Context Integrity

### context.short

基础多轮。

### context.needle.8k

### context.needle.16k

### context.needle.32k

根据 declared context 动态决定。

V1 不需要测试到模型最大窗口，只需要验证：

> 是否存在明显提前截断。

---

## H. Identity

### identity.fingerprint.quick

4 cells × N samples。

### identity.fingerprint.standard

8 cells × 25 samples。

### identity.fingerprint.deep

更高采样量。

实现：

`llm-fingerprint-detector`

### identity.reference.compare

和 trusted reference 对比。

### identity.self_consistency

split-half JSD。

### identity.knowledge

复用 proxy-sleuth knowledge probes。

### identity.family_features

模型族特有参数 / 行为。

---

## I. Routing

### routing.repeat.same_probe

同 Probe 多次。

### routing.fingerprint.consistency

### routing.quality_inversion

### routing.fact_inversion

### routing.cluster

后续可增加简单聚类。

---

## J. Capability Lite

### capability.reasoning

### capability.math

### capability.coding

### capability.chinese

### capability.instruction_following

### capability.tool_use

直接复用 Tool Probe 结果。

### capability.structured_output

直接复用 JSON Probe 结果。

---

# Probe Result 标准

每个 Probe 必须返回：

```json
{
  "probe_id": "protocol.reasoning.invalid_field",
  "status": "pass",
  "score": 1.0,
  "confidence": 0.98,
  "summary": "invalid field was rejected with HTTP 400",
  "expected": {},
  "observed": {},
  "evidence_ids": []
}
```

status：

```text
pass
warn
fail
error
skipped
insufficient
```

---

# 判定规则原则

优先级：

1. deterministic（确定性规则）
2. statistical（统计）
3. reference compare（参考对比）
4. LLM judge

LLM Judge 必须是最后选择，不能把所有东西都丢给 Judge。

---

# 首批建议实现的 20 个 Probe

如果要尽快出 MVP，先实现：

1. chat basic
2. non-stream
3. stream
4. usage
5. finish reason
6. invalid model
7. unknown field
8. invalid enum
9. system
10. multi-turn
11. reasoning valid
12. reasoning invalid field
13. tool basic
14. tool schema
15. json mode
16. json schema
17. provider headers
18. provider error signature
19. fingerprint standard
20. context needle

做到这 20 个，已经能覆盖很大一部分供应商准入问题。

