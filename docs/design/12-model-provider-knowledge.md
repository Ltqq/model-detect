# V1.1-7 Model / Provider Knowledge Base 设计

## 1. 目标

把当前简单 YAML 规则升级成可追溯知识资产。

规则必须回答：

- 适用于哪个模型/版本？
- 这个结论来自哪里？
- 什么时间采集？
- 是官方事实、Reference 观察，还是 empirical 经验？
- 置信度和适用范围是什么？

## 2. Model Rule Schema

目标结构：

```yaml
schema_version: 2

id: kimi-k3
family: kimi
model_version: k3
patterns:
  - kimi-k3
aliases: []

updated_at: 2026-09-30

sources:
  - id: moonshot-doc-reasoning
    type: official_doc
    title: ...
    url: ...
    collected_at: ...
    confidence: high

features:
  reasoning_effort:
    expected: true
    values: [low, medium, high]
    source_refs:
      - moonshot-doc-reasoning

strict: false
notes: []
```

## 3. Source Type

首批：

- `official_doc`
- `trusted_reference`
- `empirical`

后续可加：

- `provider_doc`
- `community`

正式 strict rule 不允许只依赖低置信 community source。

## 4. 向后兼容

现有 v1 YAML：

- 没有 `schema_version`
- feature 结构较简单

Loader 必须仍能读取。

策略：

- 缺少 schema_version -> 当作 v1
- 内存中 normalize 成统一 ModelRule
- 不强制一次迁完所有旧文件

## 5. Provider Fingerprint Schema

Provider DB 后续也采用同类 provenance：

- schema_version
- rule id
- source refs
- evidence type
- false_positive_notes
- confidence weight

但本轮 5 小阶段只先实现 Model Rule schema。

## 6. 为什么现在做

model-detect 后面会覆盖：

- Kimi
- GLM
- Qwen
- DeepSeek
- GPT
- Claude
- Gemini

如果不先定 schema，几十个规则文件很快不可维护。

## 7. 验收

- v1 kimi/default 仍能加载
- v2 rule 能加载 version/source
- feature 能引用 source_refs
- source type/confidence 有枚举校验
- 测试覆盖 backward compatibility
