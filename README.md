# model-detect

面向 AI 中转站、LLM API 聚合平台和模型供应商准入的 **模型真实性 / 协议完整性 / 能力审计平台**。

它不是性能压测工具。TTFT、ITL、TPS、RPM、TPM、吞吐、并发和 429 压力曲线继续使用独立压测工具。

## 产品要回答的问题

1. 这个 Endpoint 后面是否与它声称的模型一致？
2. 它可能来自哪个 Provider / Gateway / 上游链路？
3. 协议、参数、Tool Calling、JSON Schema、Reasoning 等能力是否真实可用？
4. 中转层是否存在参数吞掉、能力降级、上下文截断或混合路由？
5. 模型基础能力是否达到准入要求？
6. 每个结论能否回溯到原始、已脱敏的 Request / Response Evidence？

## V1 状态

**V1 已可运行。**

当前原生 Probe 以 OpenAI-compatible API 为主，并可通过开源 Adapter 补充多层黑盒检测。

已实现：

- Provider / Gateway Fingerprint
- Chat Completions / Streaming / Responses API 能力探测
- usage / finish_reason / model / response-id / header 指纹
- 非法 model / 非法参数 / unknown field
- Reasoning low / medium / high、非法值、错误字段
- thinking disable 行为记录 + 模型规则比对
- Tool Calling / tool_choice / invalid schema / parallel tools
- JSON Mode / JSON Schema / invalid schema
- max_tokens / stop / sampling controls 完整性检测
- Context Needle 8K / 16K / 32K（按档位和声明窗口）
- Mixed Routing 重复采样 / response schema / model-id / quality inversion
- Capability Lite：Reasoning / Math / Coding / 中文 / Instruction Following
- Tool Use / Structured Output 派生能力评分
- Trusted Reference Registry
- 协议签名 Reference 对比
- Statistical Fingerprint Reference 对比
- `llm-fingerprint-detector` Adapter
- `proxy-sleuth` 分层 Adapter
- 模型级规则库
- 可配置 Provider 指纹库
- JSON / HTML 报告
- Evidence 原始证据
- Hard Cap 评分
- weak / medium / strong 身份证据分级
- 报告 Drift 对比
- SQLite 任务历史
- Web UI
- Web Reference 管理
- ZIP 报告下载
- API Key 脱敏且 Web Key 不落数据库

详细设计：

- [产品目标与边界](docs/01-product-goal.md)
- [总体架构与开源复用方案](docs/02-architecture.md)
- [开发计划](docs/03-development-plan.md)
- [V1 Probe 清单](docs/04-probe-catalog.md)
- [当前实现状态与缺口](docs/05-v1-implementation.md)
- [技术决策与演进原则](docs/06-technical-decisions.md)

---

## 安装

Python 3.11+：

```bash
git clone https://github.com/Ltqq/model-detect.git
cd model-detect
pip install -e ".[dev]"
```

### 推荐安装的开源增强引擎

统计模型指纹：

```bash
npm install -g llm-fingerprint-detector
```

多层真实性检测：

```bash
git clone https://github.com/Babapei/proxy-sleuth.git
cd proxy-sleuth
pip install -e .
```

查看当前可用状态：

```bash
model-detect oss-status
```

没有安装这些开源引擎时，model-detect 自带的原生 Probe 仍然可以运行；只是模型身份强证据会减少，最终 Verdict 不会被错误标成已验证通过。

---

## 最推荐：Web 使用

```bash
model-detect web
```

浏览器打开：

```text
http://127.0.0.1:8787
```

可以：

- 输入 Base URL / API Key / Model
- Quick / Standard / Deep
- 选择 Trusted Reference
- 设置声明 Context Window
- 查看任务实时状态
- 查看历史报告
- 查看 Provider Fingerprint
- 点击 Evidence
- 下载完整 ZIP
- 维护 Reference

Web 输入的 API Key 只进入当前后台任务内存，不写 SQLite、Evidence 或 Report。

---

## CLI 审计

PowerShell：

```powershell
$env:MODEL_DETECT_API_KEY="sk-xxx"

model-detect audit `
  --base-url https://example.com/v1 `
  --model kimi-k3 `
  --api-key-env MODEL_DETECT_API_KEY `
  --profile standard
```

Linux/macOS：

```bash
export MODEL_DETECT_API_KEY="sk-xxx"

model-detect audit \
  --base-url https://example.com/v1 \
  --model kimi-k3 \
  --api-key-env MODEL_DETECT_API_KEY \
  --profile standard
```

输出：

```text
model-detect-output/<model>/
├── report.json
├── report.html
└── evidence/
    ├── ev_xxx.json
    └── ...
```

### 三档检测

**Quick**

低请求量初筛：

- 基础协议
- Header / Error Fingerprint
- Streaming
- invalid model / unknown field
- reasoning 错字段
- system / multiturn
- Tool Calling
- JSON Mode

**Standard**

供应商日常准入默认档：

- Quick 全部
- Responses API feature
- Reasoning 参数完整性
- Tool Choice / invalid schema
- JSON Schema
- max_tokens / stop
- 8K Context Needle
- Routing 重复采样
- Capability Lite（每类 2 题）
- proxy-sleuth standard（已安装时）

**Deep**

重要渠道 / 正式准入：

- Standard 全部
- Parallel Tool Calling
- 8K / 16K / 32K Context Needle（不超过声明窗口）
- Sampling Control
- 更多 Routing 样本
- Quality Inversion
- Capability Lite 全量 25 题
- proxy-sleuth full（已安装时）
- Trusted Statistical Fingerprint（配置 Reference 时）

---

## Trusted Reference

### 从官方 / 可信 Endpoint 采集

```powershell
$env:OFFICIAL_KEY="sk-xxx"

model-detect reference collect `
  --id kimi-k3-official `
  --base-url https://official.example.com/v1 `
  --model kimi-k3 `
  --api-key-env OFFICIAL_KEY `
  --provider official
```

如果 `llm-fingerprint-detector` 可用，会同时采集 Statistical Fingerprint。

Reference 目录包含：

```text
references/kimi-k3-official/
├── manifest.json
├── protocol-signature.json
├── fingerprint.json        # 可选
└── baseline-report/
```

### 查看 Reference

```bash
model-detect reference list
model-detect reference show kimi-k3-official
```

### 导入已有 fingerprint

```bash
model-detect reference import-fingerprint \
  --id kimi-k3-imported \
  --model kimi-k3 \
  --file reference.json
```

### 用 Reference 验证中转

```bash
model-detect reference verify \
  --id kimi-k3-official \
  --base-url https://relay.example.com/v1 \
  --model kimi-k3 \
  --api-key-env RELAY_KEY \
  --profile deep
```

---

## 身份判定原则

不会根据单一 Probe 声称“100% 真模型”。

模型身份信号分为：

- **weak**：模型特有字段 / 行为规则
- **medium**：协议 Reference、Knowledge Boundary 等
- **strong**：统计 Fingerprint 等强对比证据

即使协议、工具和能力全部高分，**没有 strong identity evidence 时最终也不会标成 verified pass**，而是提示继续人工复核 / 补 Reference。

---

## Provider Fingerprint

内置 YAML 指纹库覆盖：

- Azure APIM
- Azure OpenAI
- Fireworks
- OpenRouter
- Together
- DeepInfra
- OpenAI
- Anthropic
- Google Vertex
- AWS Bedrock
- Groq
- Cerebras
- Alibaba DashScope
- Volcengine
- SiliconFlow
- Cloudflare
- vLLM
- SGLang

判断证据包括：

- Response Headers
- Error Body
- model alias
- response id
- SSE chunk
- Provider 特有返回格式

这些结果是 evidence-based hypothesis，不作为密码学证明。

---

## 报告漂移

对比两次报告：

```bash
model-detect compare old/report.json new/report.json
```

查看：

- Category 分数变化
- Probe 状态变化
- Provider 指纹变化
- Overall Verdict 变化

适合检查供应商偷偷换路由 / 改模型 / 改推理栈。

---

## 不包含的性能指标

model-detect **明确不做**：

- TTFT
- ITL / TPOT
- TPS
- RPM / TPM
- 并发吞吐
- GPU 指标
- 429 压力曲线

这些和“模型真实性 / 能力准入”是不同问题，继续使用独立性能测试工具。

---

## 安全原则

- API Key 不写 Evidence
- API Key 不写 Report
- Web API Key 不写 SQLite
- 外部 OSS 工具通过环境变量获取 Key
- Provider 判断保留证据，不做无依据绝对断言
- Fingerprint mismatch 是统计证据，不直接等同于供应商欺诈

