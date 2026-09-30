# V1.1-3 Mixed Routing 深化设计

## 目标

检测同一个 model id 背后是否存在明显的多后端/多模型路由特征。

这仍是黑盒推断，不把单一异常当成“混合路由证明”。

## 可解释特征

每个重复请求提取：

- response model
- response id prefix
- response schema signature
- finish_reason
- usage / reasoning detail shape
- selected provider-style response header names
- logical sampling window

Deep Tool Probe 额外提取：

- tool call id prefix
- tool name
- arguments representation
- finish_reason

## 多窗口采样

Standard：

- 2 windows
- 每窗口 3 samples

Deep：

- 3 windows
- 每窗口 4 samples

窗口之间只做短间隔，目标是增加 load-balancer/backend rotation 的观察机会，不把时间延迟本身作为性能指标。

## routing.cluster

使用 feature tuple 做规则分桶，不使用不可解释 ML。

多个 bucket 只有在关键字段确实不同才记 suspicious：

- model drift
- schema drift
- id prefix drift
- usage shape drift

## routing.fact_inversion

对稳定事实重复提问。

关注的不是“答错”，而是：

> 同一个事实在 temperature=0 下，一部分请求答标准答案，另一部分请求答不同答案。

这种 inversion 比“全部答错”更像后端不一致信号。

## simple / complex strata

分别记录简单任务与复杂任务的 pass rate。

如果简单任务系统性失败但复杂任务稳定成功，记 quality inversion；仅作为 weak routing signal。

## Fingerprint 融合

V1.1-1 已产生：

- routing.fingerprint.consistency
- identity.fingerprint.reference_compare

Routing Summary 将引用：

- split-half stability
- reference mean JSD
- protocol/model/schema cluster
- fact inversion

## 最终语义

输出：

- stable
- suspicious
- mixed-routing-likely
- insufficient

只有 model field 明确漂移等强信号才允许 `mixed-routing-likely` / FAIL。

多个弱信号组合只给 WARN。
