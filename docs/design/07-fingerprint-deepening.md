# V1.1-1 Fingerprint 深化设计

## 目标

把当前 `llm-fingerprint-detector` 集成从“解析 CLI 文本中的 verdict / mean JSD”升级为结构化统计证据。

本阶段不实现新的 JSD 算法，直接复用上游工具的 `--json` 输出。

## 数据流

```text
Trusted Reference
   │
   ├─ local collected fingerprint
   ├─ imported fingerprint
   └─ bundled reference id
   │
   ▼
llm-fingerprint verify --json
   │
   ├─ verdict
   ├─ meanJsd
   ├─ comparison.cells[]
   ├─ comparison.thresholds/baselines
   ├─ target.splitHalfJsd
   ├─ target.adapter
   ├─ target.fingerprint metadata
   └─ warnings
   │
   ▼
model-detect
   ├─ identity.fingerprint.reference_compare
   ├─ identity.self_consistency
   └─ routing.fingerprint.consistency
```

## Probe 语义

### identity.fingerprint.reference_compare

强身份证据。

包含：

- verdict
- mean JSD
- comparable cells
- per-cell JSD
- protocol mismatch
- thresholds
- paper baselines

### identity.self_consistency

描述当前一次采样的内部稳定性。

它不能单独证明“模型是假”，因此失败不触发 identity mismatch Hard Cap。

初始解释区间沿用 fingerprint 工具的同类距离区间：

- <= 0.25：稳定
- 0.25–0.35：可疑
- > 0.35：明显不稳定

这不是“真假概率”，报告必须注明属于启发式稳定性判断。

### routing.fingerprint.consistency

复用 split-half JSD 作为 Mixed Routing 的统计信号。

- stable
- suspicious
- unstable

它进入 Routing 分数，但不能单独宣称存在混合路由。

## Reference Metadata

Reference Manifest 增加：

```text
fingerprint_source:
  collected | imported | bundled

fingerprint_reference:
  本地 artifact 名或 bundled id

fingerprint_metadata:
  format_version
  protocol
  model
  collected_at
  samples_per_cell
  cell_count
  post_reasoning
  meta
  source attribution
```

Bundled Reference 明确标记来源，不能伪装成用户自己从官方 Endpoint 采集的 trusted reference。

## 报告

HTML/Web 增加 Fingerprint 区域：

- verdict / mean JSD
- split-half JSD
- reasoning adapter
- warnings
- per-cell JSD 表
- reference source / collected_at / protocol

## 评分修正

`identity.self_consistency` 的 fail 不等于 identity mismatch。

只有明确的强身份比较结果给出 `verdict=mismatch` 时，才触发 Identity Hard Cap。

## 验收

- 结构化 JSON 解析单测
- per-cell JSD 可进入 report.json / report.html
- split-half 产生 identity + routing Probe
- collected/imported/bundled Reference 可区分
- 旧 Reference Manifest 仍能读取
- CI Python 3.11 / 3.12 全绿
