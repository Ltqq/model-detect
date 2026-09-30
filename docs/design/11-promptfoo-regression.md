# V1.1-6 Promptfoo Regression Adapter 设计

## 1. 目标

把“客户临时提出的协议/参数问题”从一次性脚本升级成可复用 regression case。

典型例子：

- 错误 `reasoning_effor` 是否应该报错
- `reasoning_effort` 的允许值
- thinking disable 行为
- 特定 JSON Schema
- 特定 Tool Call schema
- 错误字段 / 错误状态码
- 某模型特定返回结构

目标链路：

```text
customer issue
   ↓
model-detect regression YAML
   ↓
promptfoo config
   ↓
promptfoo eval
   ↓
JSON artifact
   ↓
Unified ProbeResult
   ↓
Evidence / Report
```

## 2. 为什么使用 promptfoo

promptfoo 当前支持：

- 通用 HTTP Provider
- request / response transform
- deterministic assertions
- JSON Schema assertions
- tool-call assertions
- JavaScript/Python assertions
- CLI JSON artifact

model-detect 不复制它的 assertion engine，只做 Adapter 与统一 Evidence/Result。

## 3. 安全边界

默认允许的 regression assertion：

- equals
- contains / icontains
- regex
- is-json / contains-json
- is-valid-openai-tools-call
- status / provider response metadata（通过 provider transform）

默认禁止：

- arbitrary JavaScript
- arbitrary Python

原因：项目可能加载来自供应商/客户的 YAML，不能默认把 YAML 变成本地代码执行入口。

Custom JS/Python 后续只能显式 opt-in。

## 4. model-detect Regression Schema

第一版：

```yaml
version: 1
suite: kimi-k3-regression
model_patterns:
  - kimi-k3

cases:
  - id: reasoning-invalid-field
    category: protocol
    prompt: "Reply OK"
    request:
      reasoning_effor: medium
    expect:
      http_status: 400

  - id: structured-output
    category: protocol
    prompt: "Return JSON"
    request:
      response_format: ...
    assertions:
      - type: is-json
        schema: ...

  - id: tool-call
    category: protocol
    prompt: "Use get_weather"
    tools: [...]
    assertions:
      - type: is-valid-openai-tools-call
```

## 5. Provider 生成

OpenAI-compatible HTTP Provider：

- URL: `<base_url>/chat/completions`
- POST
- Authorization: `Bearer {{env.MODEL_DETECT_PROMPTFOO_KEY}}`
- model: configured target model
- messages from prompt
- case-specific request fields merged into body
- response transform extracts assistant/tool response while preserving raw artifact

API Key 不写进 config 文件。

## 6. CLI 调用

优先检测本地 `promptfoo` binary，后续可考虑 `npx promptfoo@latest` fallback，但 V1.1 不自动下载依赖。

建议：

```text
promptfoo eval
  -c <generated-config>
  --output <result.json>
  --no-cache
```

具体 CLI 参数以实现时当前 promptfoo 版本为准。

## 7. Result Mapping

每个 regression case 映射：

```text
regression.<suite>.<case_id>
```

字段：

- category: case.category
- status: pass / fail / error
- score: assertion pass ratio 或 1/0
- confidence: deterministic assertions 默认高
- observed:
  - assertion results
  - output summary
  - provider metadata
- metadata:
  - engine=promptfoo
  - suite
  - case_id
  - artifact path

promptfoo regression **不能产生 strong identity evidence**。

## 8. Evidence

不把 promptfoo 临时 config 中的 secret 写入 artifact。

保存：

- sanitized generated config
- promptfoo JSON result
- mapped ProbeResult

## 9. 小阶段拆分

1. HTTP Provider Adapter
2. Regression YAML Loader
3. Result Mapping
4. Repeat / richer assertions
5. optional custom assertion opt-in

## 10. 验收

- API Key 仅通过 env
- deterministic case 可运行
- invalid YAML 明确报错
- JSON / Tool assertions 可表达
- result 能进入 Unified ProbeResult
- CI 不要求安装真实 promptfoo，可 mock subprocess
