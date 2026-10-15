# G1.2 请求体证据核验（离线）

本功能只能核验**已捕获**的 HTTP Chat Completions JSON 请求体；不生成或捕获它们，也不证明服务端实际应用了 reasoning_effort。不会向任何模型发请求，不涉及性能压测。

使用受控 HTTP Mock 或本机经过授权的代理，对官方/客户**各自**采集相同 lm-eval 套件的 HTTP 请求体，并将原始请求放在**本地非共享文件**（包含完整题目、上下文，属于敏感材料），格式：

```json
{
  "official": [
    {"model":"glm-5.3","messages":[{"role":"user","content":"example"}],"reasoning_effort":"max","max_tokens":1280,"temperature":0,"stop":[]}
  ],
  "customer": [
    {"model":"glm-5.3","messages":[{"role":"user","content":"example"}],"reasoning_effort":"max","max_tokens":1280,"temperature":0,"stop":[]}
  ]
}
```

```bash
model-detect glm53 verify-wire --captured-json ./private-capture.json --output-file ./wire-evidence.json --reasoning-effort max
```

- 按请求体的 messages SHA256 + 生成配置 SHA256 多重集合比较，不受请求顺序影响，重复请求也计入。
- reasoning_effort、model、max_tokens 缺失或错误时拒绝；temperature/stop 未捕获不填默认值，明确不可比。
- 输出只有端点标签、计数、错误类别、max_tokens 已见值及对照结果；不导出 prompt、Key、URL、响应和模型思考文本。
- 输入 JSON 可能包含敏感内容，**绝不能提交到公开仓库或作为 CI fixture 原样保存**。
- **缺口**：采集真实性、任务实际生效参数、服务端是否遵守设置、题集缓存/样本修订锁定，仍需额外环境验证。不能仅凭 `request_payload_matched` 声称模型能力等价、路由真实性或 G1.5 实测已通过。

安全要求：仅采集自己的受控测试端点，使用专门的最小权限 Mock Key。严格禁止把第三方用户真实请求或生产密钥导入本功能。
