# 2026-10-20 GLM-5.3-Flash 官方接口现场测试复盘

状态：**真实用户报告已检查；软件修复 CI 通过，修复后实际官方 API 需要再次测试**。此文档保存去敏的现象和验收清单，不保存用户 ZIP、Key、Header、原始 Prompt 或私有内容。

## 观察事实

- 输入：官方 OpenAI 兼容 GLM-5.3-Flash；`quick`；未配置 Reference。
- 本次报告：21 检测项 = 13 PASS / 5 WARN / 3 INSUFFICIENT / 0 FAIL；约 21.4 秒，10 个 API 请求，8 项有 usage。
- 基础聊天：`max_tokens=16`，输出 16 个推理 Token、正文空、`finish_reason=length`，但原先误判 PASS。
- System 和多轮：各 `max_tokens=32`，全部被推理占用、正文空、`finish_reason=length`，原先误判模型不遵循。
- JSON：`max_tokens=64`，63 个推理 Token、正文空、`finish_reason=length`，原先误报 JSON 不支持。
- 未知字段/推理字段拼错：服务端 HTTP 200 接受或忽略，意味着严格未知字段拒绝未实现，**不能推出模型不是官方权重**。
- 身份分数：仅 `identity.family_features.tools=PASS` 而其他身份相关项未测，旧汇总却显示 `identity=100`，属证据类型混淆。
- 旧 Web 首页：Reference/身份解释抢占首屏；新建审计、声明式回归、离线双端点对照和历史混在一个页面。原报告约 5,600px 长，官方公开基准位于具体风险之前；未跑 Reference 也被放在“优先风险”。

## 代码修复

- [#171](https://github.com/Ltqq/model-detect/pull/171)：thinking 模型基本文本探针提高生成预算，`length` 截断但无可判答案返回 INSUFFICIENT 而不是 PASS/WARN，增加合成回归。
- [#172](https://github.com/Ltqq/model-detect/pull/172)：弱模型特征行为不能产生 100% 身份分数。
- [#173](https://github.com/Ltqq/model-detect/pull/173)：首页以 URL/Key/Model/Quick 为主、Reference 和离线比较折叠、浅色响应式设计，保持旧 DOM/API。
- [#174](https://github.com/Ltqq/model-detect/pull/174)：报告把实际异常放在前、官方背景分数与弱证据折叠、UI 重设，保留证据下载/技术明细。
- [#175](https://github.com/Ltqq/model-detect/pull/175)：Quick 未执行身份/路由深测不再自动导致“人工复核”；协议检测本身截断仍不视为成功。

## 用户复测验收（不可用旧 ZIP 代替）

1. 运行新版本，确认首页可在无需 Reference 的情况下直接发起 Quick；用户需自行授权真实模型调用成本。
2. 对 GLM-5.3-Flash 重测：System/多轮/JSON 的正文确实生成再评判，若生成预算仍被推理耗尽，应显示“证据不足/被截断”，不可显示模型不支持。
3. 检查基础 Chat 的 `finish_reason=length` 且正文为空不再 PASS；正常 tool_calls 与 SSE 保留原来正向行为。
4. 检查身份未采样、路由未重复检查不得产生 100% 身份置信与假风险；官网公开分数仅作为背景信息。
5. 展示完整中文报告、错误原始 Evidence 可展开、历史可读取和下载；UI 桌面 1440px、窄屏 390px 手工检查，特别关注长表格和高级折叠内容。
6. 记录本次请求总量及实际 Token；对 reasoning 模型新的 `max_tokens` 上限提高，需要实测确认费用和效率是否合理。

**判定边界**：上述修复有确定性单测和 CI 证据，但目前没有使用用户官方 Key 重跑；模型实际协议能力不得据此提前宣称已通过。产品方向和冻结宪章保持不变。
