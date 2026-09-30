# V1.1-8 Regression Audit Integration

## 1. 目标

把已经独立可运行的 promptfoo regression pipeline 接进主 Audit Orchestrator，使客户专项准入规则和原生 Probe 在同一份 AuditReport 中汇总。

## 2. 边界

Regression 仍然只是 supporting evidence：

- 可以进入 protocol / integrity / capability 分类；
- 不产生 strong identity evidence；
- regression runner 失败不能让整次 audit 中断；
- API Key 继续只通过进程环境传给 promptfoo；
- 性能测试仍然不进入本链路。

## 3. 数据流

```text
Audit
  ├─ native probes
  ├─ reference / fingerprint
  ├─ proxy-sleuth
  └─ regression suites
       ↓
     promptfoo
       ↓
  Unified ProbeResult
       ↓
  AuditReport.results
       ↓
  Score / Report / Web
```

## 4. 分阶段

1. Orchestrator 可调用 regression runner；
2. AuditConfig / CLI 定义不同 profile 使用哪些 suite；
3. Report 持久化并展示 regression artifact/evidence；
4. Web 展示 Model/Provider provenance 和 regression 状态；
5. 扩充 Claude / GPT / Gemini Model Knowledge。

## 5. 故障策略

单个 regression suite 出错：

- 写入 `internal.regression.N` ERROR；
- Adapter metadata 记录错误；
- 继续执行并生成完整报告。

这样 promptfoo 未安装、YAML 错误或外部 CLI 失败，不会吞掉其它准入证据。
