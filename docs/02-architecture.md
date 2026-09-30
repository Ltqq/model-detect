# 总体技术架构

> 本文以当前 `main` 代码为准。  
> 当前版本：`0.2.0`。目标是做 LLM API 的黑盒真实性、协议完整性、参数完整性、能力与供应商准入审计；性能压测明确独立。

## 1. 产品边界

model-detect 负责：

- 模型身份一致性
- Provider / Gateway 指纹
- 协议兼容性
- 参数完整性
- Context 完整性
- Mixed Routing / 路由稳定性
- Capability 准入
- Trusted Reference
- Evidence / Score / Report / Drift

明确不负责：

- TTFT / ITL / TPS
- RPM / TPM
- 大并发吞吐
- 429 压力曲线
- GPU / 显存 / 节点指标

这些继续由独立性能测试工具完成。

## 2. 当前技术栈

- Python 3.11+
- Typer + Rich：CLI
- FastAPI + Uvicorn + Jinja2：Web/API
- HTTPX AsyncClient：API Probe
- Pydantic + PyYAML：配置与规则
- SQLite：Web Job History
- Filesystem：Reference / Evidence / Report

外部引擎：

- `ToseaAI/llm-fingerprint-detector`
- `Babapei/proxy-sleuth`
- `EleutherAI/lm-evaluation-harness`
- `promptfoo/promptfoo`：下一阶段 declarative regression

## 3. 当前逻辑架构

```text
CLI / Web
   ↓
Audit Orchestrator
   ├─ Native Probes
   │    ├─ protocol
   │    ├─ integrity
   │    ├─ context
   │    ├─ routing
   │    ├─ capability
   │    └─ coding sandbox
   │
   ├─ OSS Adapters
   │    ├─ llm-fingerprint-detector
   │    ├─ proxy-sleuth
   │    └─ lm-eval
   │
   └─ Reference / Knowledge
        ├─ trusted reference
        ├─ model rules
        └─ provider fingerprints
             ↓
      Unified ProbeResult + Evidence
             ↓
      Score / Hard Cap / Confidence
             ↓
      JSON / HTML / Web / Drift
```

## 4. 当前能力状态

### Fingerprint

已完成：

- collect / verify
- mean JSD
- per-cell JSD
- split-half self consistency
- routing fingerprint consistency
- collected / imported / bundled reference source
- HTML/Web fingerprint evidence

### Integrity

已完成：

- reasoning effect
- max_tokens
- stop
- sampling controls
- system prompt canary
- tool definition preservation
- JSON Schema preservation
- temperature / top_p statistical effect

### Routing

已完成：

- repeated samples
- model field drift
- schema drift
- response-id prefix drift
- multi-window sampling
- fact inversion
- quality inversion
- explainable cluster
- fingerprint consistency fusion

### Capability

当前内置：

- Reasoning 20
- Math 20
- Chinese 20
- Instruction Following 20
- Coding Reasoning 5
- Executable Coding >= 10（Python + Go）
- Tool Use 多场景聚合
- Structured Output 多场景聚合

外部 benchmark：

- lm-eval OpenAI-compatible endpoint adapter
- built-in smoke / standard / deep profiles
- result -> Unified ProbeResult
- 与 Capability Lite 默认去重

## 5. Evidence 数据流

```text
HTTP Request
  ↓
AuditHttpClient
  ↓
敏感字段脱敏
  ↓
Evidence
  ├─ request
  ├─ response status
  ├─ response headers
  ├─ response body / SSE
  └─ error
  ↓
ProbeResult.evidence_ids
  ↓
Report / Web
```

API Key 禁止进入：

- SQLite
- Evidence
- Report
- 外部 Adapter 命令参数

## 6. 当前部署模型

V1/V1.1 继续保持：

```text
FastAPI + Background Task
SQLite + Filesystem
External CLI Adapters
```

当前不迁 PostgreSQL / Redis / Worker。

只有出现多人并发、周期任务规模扩大、权限共享或单机任务可靠性要求时，才进入 V2。

## 7. 下一阶段架构重点

下一阶段不继续堆 benchmark 数量，而是补齐“供应商问题沉淀”和“模型知识库”：

```text
客户/准入问题
   ↓
Regression YAML
   ↓
promptfoo Adapter
   ↓
Unified ProbeResult
   ↓
Evidence / Report
   ↓
沉淀为 Model Rule / Provider Rule
```

同时把模型规则从简单 feature map 升级为可追溯知识：

```text
rule
├─ schema_version
├─ model/family/version
├─ sources[]
├─ collected_at
├─ features
└─ notes
```

## 8. 技术原则

1. Evidence First
2. Reference First
3. Deterministic First
4. Strong Identity Requires Strong Evidence
5. OSS Through Adapters
6. No Performance Coupling
7. Profile Controls Cost
8. Small PR / Small Commit
9. 新数据模型或跨模块流程先设计再开发
