# 总体架构与开源复用方案

## 1. 核心原则

这个项目不应该自己重新发明所有检测算法。

优先组合成熟开源组件，再补我们真正缺的部分：

```text
已有成熟组件
    ↓
Adapter / Runner
    ↓
统一 Probe Result
    ↓
Evidence Engine
    ↓
Score / Verdict
    ↓
Report
```

---

## 2. 推荐开源组件

### 2.1 proxy-sleuth

项目：

`Babapei/proxy-sleuth`

许可证：

MIT。

它目前已经实现 7 层检测：

- param-integrity
- context
- api-features
- knowledge
- fingerprint
- capability
- routing

这和 model-detect 的目标高度重合。

### 使用策略

**优先研究并复用其 detector 设计、数据和算法，不建议直接把它当完整产品套壳。**

原因：

1. 它目前主要是 CLI；
2. 我们需要统一任务、Reference、Evidence、报告；
3. 我们未来会有自己维护的模型规则；
4. 需要支持更多协议和供应商；
5. 需要可解释评分和历史记录。

最值得直接吸收：

- param integrity
- context truncation
- api feature probes
- knowledge probes
- mixed routing 设计
- scoring 思路

---

### 2.2 llm-fingerprint-detector

项目：

`ToseaAI/llm-fingerprint-detector`

许可证：

MIT。

核心方法：

**Single-token behavioral fingerprint（单 Token 行为指纹）**

通过约 100–400 次低成本短输出请求，形成输出分布，再使用 Jensen-Shannon Divergence（JS 散度）与可信 Reference 对比。

输出：

- match
- uncertain
- mismatch
- insufficient

还提供：

- split-half self consistency
- reasoning adapter detection
- bundled references
- TypeScript library
- CLI

### 使用策略

**直接作为 statistical fingerprint engine。**

V1 不自己重写 JSD 和整套采样协议。

我们只需要包一层：

```text
FingerprintRunner
  -> 调用 library / CLI
  -> 标准化输出
  -> 保存 fingerprint artifact
  -> 与 Reference Registry 关联
```

后续需要扩模型时，主要维护 Reference，而不是改算法。

---

### 2.3 promptfoo

许可证：

MIT。

适合：

- 自定义 HTTP Provider
- declarative test cases
- deterministic assertions
- JSON schema
- tool-call validation
- model-graded assertions
- repeat
- concurrency
- 自定义 JS / Python assert

### 使用策略

用于：

**协议 Probe / 能力 Probe 的执行与断言层。**

例如：

```yaml
name: invalid_reasoning_field

request:
  reasoning_effor: medium

expect:
  status: 400
```

但不要让 promptfoo 负责整个产品状态机。

---

### 2.4 lm-evaluation-harness

项目：

`EleutherAI/lm-evaluation-harness`

适合：

- 标准公开 benchmark
- API endpoint
- 自定义 task
- Reasoning / Knowledge / Math 等基础能力

### 使用策略

作为 **可选的 capability benchmark adapter**。

V1 不跑几十个 benchmark，只挑少量具有区分度和可维护性的任务。

后续如果需要更完整评分，可直接扩 benchmark profile。

---

## 3. 不建议 V1 引入的东西

### EvalScope Perf

性能模块不需要。

如未来只需要 EvalScope 的能力 benchmark，也应先和 lm-evaluation-harness 比较再决定，不要同时接两套功能高度重叠的框架。

### Garak / 大型安全红队

不是 V1 核心目标。

### 自己实现统计指纹算法

没有必要。

---

## 4. 我们真正需要自研的核心

开源工具很多，但以下部分必须自己掌控。

### 4.1 Unified Probe Model

所有开源组件输出格式不同，需要统一：

```json
{
  "probe_id": "protocol.reasoning.invalid_field",
  "category": "protocol",
  "status": "pass",
  "score": 1.0,
  "confidence": 0.95,
  "summary": "unknown reasoning field correctly rejected",
  "evidence_ids": ["ev_xxx"],
  "metadata": {}
}
```

### 4.2 Raw Evidence

保存：

- request metadata
- request body（API Key 脱敏）
- status code
- response headers
- response body
- stream chunk sample
- error body
- timestamp
- duration（仅做证据，不做性能评分）

原始证据必须和评分分离。

### 4.3 Provider Fingerprint Rules

维护自己的特征库：

```yaml
azure_apim:
  headers:
    - x-ms-request-id
    - ocp-apim-subscription-id
  body_patterns:
    - ...
  confidence: ...

fireworks:
  model_patterns:
    - FW-*
  error_patterns:
    - ...
```

输出 hypothesis + evidence，不输出绝对断言。

### 4.4 Reference Registry

核心资产。

```text
ModelReference
  model_family
  model_version
  provider
  endpoint_type
  protocol
  collected_at
  fingerprint artifact
  protocol signature
  feature matrix
  notes
```

正式准入尽量和可信 Reference 比。

### 4.5 Score / Verdict Engine

统一产生：

- score
- confidence
- hard cap
- warnings
- final verdict

### 4.6 Report Engine

输出可解释报告。

---

## 5. 建议技术架构

V1 先不要做微服务。

建议：

```text
model-detect
├── API / Web
├── Job Orchestrator
├── Probe Engine
│   ├── native probes
│   ├── promptfoo adapter
│   ├── proxy-sleuth adapter
│   ├── fingerprint adapter
│   └── lm-eval adapter
├── Evidence Store
├── Reference Registry
├── Score Engine
└── Report
```

### 推荐语言

#### 主服务：Python

V1 推荐 Python 而不是 Go。

理由：

- proxy-sleuth 是 Python
- lm-evaluation-harness 是 Python
- LLM eval 生态绝大多数 Python
- 数据处理、统计、模型 benchmark 集成简单
- 可以直接 import 开源组件，减少 shell 调度

#### Fingerprint：Node sidecar / library

`llm-fingerprint-detector` 是 TypeScript。

V1 两种方案：

A. CLI 调用，最省事；
B. 单独 Node worker。

先用 A。

### Web

V1 可以：

- FastAPI + 简单前端
- 或 FastAPI + Next.js

不建议一开始做重前端。

---

## 6. 目录建议

```text
model-detect/
├── app/
│   ├── api/
│   ├── core/
│   │   ├── models.py
│   │   ├── scoring.py
│   │   └── evidence.py
│   ├── probes/
│   │   ├── protocol/
│   │   ├── provider/
│   │   ├── integrity/
│   │   ├── context/
│   │   ├── capability/
│   │   └── routing/
│   ├── adapters/
│   │   ├── proxy_sleuth.py
│   │   ├── fingerprint.py
│   │   ├── promptfoo.py
│   │   └── lm_eval.py
│   ├── references/
│   ├── reports/
│   └── jobs/
├── configs/
│   ├── providers/
│   ├── models/
│   ├── profiles/
│   └── scoring/
├── references/
├── tests/
├── docs/
└── scripts/
```

---

## 7. 数据模型

### audit_jobs

```text
id
base_url
claimed_model
protocol
profile
status
created_at
finished_at
summary_json
```

API Key 不直接写库。

### probe_results

```text
id
job_id
probe_id
category
status
score
confidence
summary
metadata_json
```

### evidence

```text
id
job_id
probe_result_id
type
request_json
response_status
response_headers_json
response_body
created_at
```

敏感字段脱敏。

### references

```text
id
model_family
model_version
provider
protocol
collected_at
artifact_type
artifact_path
metadata_json
```

---

## 8. 最终执行流程

```text
Create Audit
     ↓
Endpoint Preflight
     ↓
Provider Fingerprint
     ↓
Protocol / API Feature
     ↓
Parameter Integrity
     ↓
Identity Probes
     ├── knowledge
     └── statistical fingerprint
     ↓
Context Integrity
     ↓
Routing Stability
     ↓
Capability Lite
     ↓
Normalize Evidence
     ↓
Score + Hard Caps
     ↓
Report
```

---

## 9. 最重要的设计约束

### 不把某一个开源项目当“真理”

例如 statistical fingerprint 本身就可能受：

- serving stack
- system prompt
- reasoning mode
- quantization
- model update

影响。

所以结果必须是：

```text
Evidence Fusion
多证据融合
```

而不是：

```text
JSD > 0.35 => 供应商一定造假
```

### 不做不可解释的 AI Judge 总分

LLM Judge 可以作为能力项辅助评分，但最终报告必须能看到：

- 题目
- 输出
- 判定规则
- Judge 原因
- 原始证据

