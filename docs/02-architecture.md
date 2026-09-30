# 总体技术架构

> 本文以当前 `main` 代码为准，不再描述“建议中的架构”。  
> 当前版本：`0.2.0`。目标是做 LLM API 的黑盒真实性、协议完整性、能力与供应商准入审计；性能压测明确独立。

## 1. 产品边界

model-detect 只负责：

- 模型身份一致性
- Provider / Gateway 指纹
- 协议兼容性
- 参数完整性
- Context 完整性
- Mixed Routing / 路由稳定性
- Capability Lite
- Reference 基准
- Evidence / Score / Report / Drift

明确不负责：

- TTFT / ITL / TPS
- RPM / TPM
- 大并发吞吐
- 429 压力曲线
- GPU / 显存 / 节点指标

这些继续由独立性能测试工具完成。

---

## 2. 当前技术栈

### 主语言

Python 3.11+

原因：

- LLM eval / benchmark 生态以 Python 为主
- `proxy-sleuth` 为 Python
- 便于快速增加 Probe / 数据集 / Adapter
- 后续接 `lm-evaluation-harness`、代码沙箱等成本最低

### CLI

- Typer
- Rich

主要入口：

```text
model-detect audit
model-detect reference ...
model-detect compare
model-detect web
model-detect oss-status
```

### Web / API

- FastAPI
- Uvicorn
- Jinja2

当前定位是轻量本地/内网 Web，不做重前端。

### HTTP

- HTTPX AsyncClient

### 配置 / 数据

- Pydantic
- PyYAML

### 本地持久化

- SQLite：Web Job 历史
- 文件系统：Reference、Evidence、Report

### 外部开源引擎

- `ToseaAI/llm-fingerprint-detector`
- `Babapei/proxy-sleuth`

---

## 3. 当前逻辑架构

```text
                         ┌──────────────────────┐
                         │      CLI / Web       │
                         │ Typer / FastAPI      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Audit Orchestrator │
                         │ model_detect/audit.py│
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼──────────────────────┐
              │                     │                      │
              ▼                     ▼                      ▼
    ┌─────────────────┐   ┌──────────────────┐   ┌────────────────────┐
    │ Native Probes   │   │ OSS Adapters     │   │ Reference / Rules  │
    │ protocol        │   │ fingerprint      │   │ trusted reference  │
    │ integrity       │   │ proxy-sleuth     │   │ model rules        │
    │ context         │   └────────┬─────────┘   │ provider rules     │
    │ routing         │            │             └─────────┬──────────┘
    │ capability      │            │                       │
    └────────┬────────┘            │                       │
             └─────────────────────┴───────────────┬───────┘
                                                   ▼
                                      ┌────────────────────────┐
                                      │ Unified Probe Result   │
                                      │ + Raw Evidence         │
                                      └────────────┬───────────┘
                                                   │
                                      ┌────────────▼───────────┐
                                      │ Score / Evidence Fusion│
                                      │ Hard Cap / Confidence  │
                                      └────────────┬───────────┘
                                                   │
                          ┌────────────────────────┼─────────────────────┐
                          ▼                        ▼                     ▼
                 ┌────────────────┐       ┌────────────────┐    ┌────────────────┐
                 │ JSON / HTML    │       │ Web Job Store  │    │ Drift Compare  │
                 │ Report         │       │ SQLite         │    │ report vs report│
                 └────────────────┘       └────────────────┘    └────────────────┘
```

---

## 4. 模块职责

### `audit.py`

唯一主编排入口。

职责：

1. 解析 Quick / Standard / Deep
2. 调 Native Probe
3. 调 Integrity / Context / Routing / Capability Suite
4. 加载模型规则
5. 加载 Trusted Reference
6. 调 Statistical Fingerprint
7. 调 proxy-sleuth
8. 聚合 Provider Fingerprint
9. 统一评分
10. 生成 AuditReport

原则：

> Probe 只负责“观察和判定局部事实”，Audit Orchestrator 负责执行顺序，Score Engine 负责全局结论。

### `probes/protocol.py`

协议能力：

- Chat Completions
- Streaming
- Responses API feature probe
- usage / finish_reason
- invalid model / field / enum
- reasoning
- thinking
- tool calling
- tool_choice
- parallel tools
- JSON mode / JSON schema

### `probes/integrity.py`

参数是否被中转层吞掉、钳制或降级：

- reasoning level effect
- max_tokens
- stop
- sampling controls

V1.1 将继续补：

- system prompt injection
- tool definitions preserved
- JSON Schema preserved
- temperature / top_p 独立完整性

### `probes/context.py`

Needle-in-Haystack 形式的上下文完整性测试。

目前支持：

- 8K
- 16K
- 32K

根据 profile 与用户声明窗口动态决定测试档位。

### `probes/routing.py`

检查：

- 相同请求重复采样
- response model 漂移
- response schema 漂移
- response ID prefix 漂移
- quality inversion

V1.1 将增加：

- fingerprint consistency
- fact inversion
- cluster / 行为聚类

### `probes/capability.py`

当前 Capability Lite：

- Reasoning
- Math
- Coding reasoning
- Chinese
- Instruction Following
- Tool Use
- Structured Output

V1.1 将把 Coding 从“代码理解题”升级为“小规模代码生成 + 沙箱执行”。

### `adapters/fingerprint.py`

封装 `llm-fingerprint-detector`。

当前：

- collect
- verify
- verdict
- mean JSD

后续：

- per-cell JSD
- split-half self consistency
- richer artifact parsing

### `adapters/proxy_sleuth.py`

把 proxy-sleuth 多层结果映射到统一分类：

```text
param_integrity    -> integrity
context_truncation -> context
api_features       -> protocol
knowledge_probes   -> identity
statistical        -> identity
capability         -> capability
mixed_routing      -> routing
```

它是增强层，不是系统唯一真相来源。

### `references.py`

可信 Reference Registry。

保存：

- manifest
- protocol signature
- fingerprint artifact
- baseline report

Reference 是模型真实性检测的核心资产。

### `rules.py`

加载：

- 模型规则
- 模型特有 feature expectations

规则必须基于可验证官方行为或可信 Reference，禁止拍脑袋写死。

### `probes/provider.py`

通过 YAML Provider Fingerprint DB 做启发式识别。

证据来源：

- headers
- error body
- response model
- response id
- SSE pattern

输出是 hypothesis + confidence，不是“确定上游”。

### `scoring.py`

维度：

```text
Identity               35
Protocol               20
Parameter Integrity    15
Context                10
Routing                10
Capability             10
```

Provider Fingerprint 不计分。

Hard Cap：

- identity mismatch -> 总分 <= 40
- mixed routing critical fail -> <= 60
- critical protocol fail -> <= 60

身份信号分：

- weak
- medium
- strong

没有 strong identity evidence 时，即使其它分数很高，也不能直接给 verified pass。

---

## 5. Evidence 数据流

```text
HTTP Request
  ↓
AuditHttpClient
  ↓
敏感头/字段脱敏
  ↓
Evidence
  ├─ request body
  ├─ response status
  ├─ response headers
  ├─ response body / SSE preview
  ├─ error
  └─ elapsed_ms（只作证据，不用于性能评分）
  ↓
ProbeResult.evidence_ids
  ↓
Report 可点击回原始 Evidence
```

API Key 禁止进入：

- SQLite
- Evidence
- Report
- CLI 参数日志
- 外部 Adapter 命令参数

---

## 6. 当前部署模型

V1 / V1.1 继续保持单机单进程优先：

```text
model-detect web
   │
FastAPI
   │
Background Task
   ├─ Native Probe
   ├─ proxy-sleuth process
   └─ llm-fingerprint process
   │
SQLite + Filesystem
```

原因：

- 当前主要是内部准入工具
- 任务量低
- 不需要提前引入 PostgreSQL / Redis / Worker 运维成本

只有满足以下任一条件才进入分布式生产架构：

- 多人同时使用
- 同时运行多个 Deep Audit
- 周期性自动重测规模扩大
- 需要权限 / 审计 / 团队共享
- 单机任务丢失不可接受

---

## 7. V2 生产化目标架构

达到上述条件后升级为：

```text
                   ┌──────────────┐
                   │ Web / API    │
                   │ FastAPI      │
                   └──────┬───────┘
                          │
                ┌─────────▼─────────┐
                │ PostgreSQL         │
                │ Job / Result / ACL │
                └─────────┬─────────┘
                          │
                     Job Queue
                          │
                ┌─────────▼─────────┐
                │ Redis + Worker     │
                │ Audit Workers      │
                └──────┬─────┬─────┘
                       │     │
              Native Probe  OSS Adapter
                       │     │
                       └──┬──┘
                          ▼
                 Evidence / Artifact
                 Local / Object Storage
```

Worker 技术在真正进入 V2 时再定；优先选择简单、可靠、Python 原生的队列，不为了架构“高级”而提前引入复杂组件。

---

## 8. 核心技术原则

1. **Evidence First**：先有证据，再有结论。
2. **Reference First**：重要模型尽量先建立可信官方 Reference。
3. **Evidence Fusion**：不依赖单一 Fingerprint。
4. **Deterministic First**：能规则判定就不用 LLM Judge。
5. **OSS Reuse**：成熟算法通过 Adapter 复用。
6. **No Performance Coupling**：性能测试与真实性审计分离。
7. **Profile Controls Cost**：Quick / Standard / Deep 控制请求量。
8. **No Premature Distributed Architecture**：先单机可用，再生产化。
