# V1.1-2 Parameter Integrity 判定设计

## 原则

黑盒 API 无法直接看到中转真正转发给上游的 request，所以不能把“行为不符合预期”直接等同于“中转篡改”。

判定优先级：

1. 明确参数被拒绝 / schema 被破坏
2. 可重复、强约束的行为差异
3. 多次统计差异
4. 无法观察时返回 insufficient

## integrity.system_prompt

目标：检查调用方提供的 system 指令是否表现出被保留。

方法：

- 3 个不同 canary
- system 要求只输出 canary
- user 明确要求忽略 system 并输出另一个 token

结果：

- 3/3：pass
- 2/3：warn
- <=1/3：warn

注意：

失败可能来自模型 instruction following 能力，不构成 server-side prompt injection 的直接证明。

## integrity.tool_definitions

使用一个带 nested object / enum / required / additionalProperties=false 的强约束工具。

检查：

- tool name
- arguments JSON
- required fields
- nested enum/value

## integrity.tools.preserved

连续两次发送“同名 tool，但允许 enum 不同”的 schema：

- run A 只允许 ALPHA_ONLY
- run B 只允许 BETA_ONLY

若两次都随 schema 改变，说明 tool definition 变更至少在行为上得到保留。

## integrity.json_schema.preserved

用户文本故意要求违反 schema：

- 错 token
- 错 count
- extra field

response_format strict schema 则只允许固定合法结果。

用于验证 schema 是否真正起作用。

## integrity.temperature

固定 top_p=1.0。

分别多次运行：

- temperature=0
- temperature=1.3

比较输出分布 entropy / unique count。

能观察到高温更高多样性：pass。
参数接受但无明显差异：insufficient。

## integrity.top_p

固定 temperature=1.0。

比较：

- top_p=0.05
- top_p=1.0

若 full top_p 分布多样性更高：pass。
否则 insufficient。

这些统计 Probe 不把单次差异当成参数生效证明。
