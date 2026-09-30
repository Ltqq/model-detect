# model-detect

面向 AI 中转站 / LLM API 聚合平台的 **模型真实性与能力准入审计工具**。

> 目标不是做性能压测，也不是做一个只会跑 benchmark 的排行榜。
>
> 核心要回答的是：
>
> 1. 这个 Endpoint 后面到底是不是它声称的模型？
> 2. 它可能来自哪个 Provider / Gateway / 上游链路？
> 3. 官方声明支持的协议、参数、Tool Calling、结构化输出、推理能力等，在这个 Endpoint 上是否真的可用？
> 4. 是否存在参数被静默忽略、能力降级、上下文截断、混合路由、模型替换等问题？
> 5. 最终能否形成一份 **可解释、可复现、有证据链** 的准入审计报告？

## 当前阶段

项目刚初始化，先完成产品与技术设计，不急着写业务代码。

详细文档：

- [产品目标与边界](docs/01-product-goal.md)
- [总体架构与开源复用方案](docs/02-architecture.md)
- [开发计划](docs/03-development-plan.md)
- [V1 检测项清单](docs/04-probe-catalog.md)

## 明确不做

V1 不集成性能压测：

- TTFT
- ITL / TPOT
- TPS
- RPM / TPM
- 并发压测
- 吞吐
- 429 压力测试

这些继续由现有独立压测脚本 / 工具负责。

## V1 目标

输入：

- API Base URL
- API Key
- 声称模型名
- 协议类型（OpenAI / Anthropic / Auto）

输出：

- 模型身份一致性结论
- Provider / Gateway 指纹证据
- 协议与参数兼容性
- Tool Calling / Structured Output / Reasoning 等能力
- 上下文完整性
- 混合路由 / 能力降级风险
- 基础能力评分
- 原始证据
- 综合准入结论

## 原则

1. **优先复用成熟开源项目，不重复造轮子**
2. **单一指纹不能作为“真假模型”的绝对证明**
3. **所有结论必须能回溯到 Probe 与原始响应**
4. **区分模型身份、协议能力和模型能力，不混成一个黑盒总分**
5. **API Key 不落日志，不写报告，不进入数据库明文**
6. **检测结论使用 match / uncertain / mismatch / insufficient 等证据等级，而不是武断声称“100% 真/假”**

---

Status: Design / MVP planning
