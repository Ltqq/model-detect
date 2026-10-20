# P0 开源组件与删减决策（2026-10-20，执行证据）

遵守 [冻结产品宪章](design/product-charter-v1.md)。不能因为 README 声称精准识别就把某个项目作为身份认证；不能因功能重复就未经引用/历史兼容审查物理删除。只有四类产品输出：协议、能力、异常信号、证据与限制。

## 组件去留

| 组件 | 当前真实路径 / 来源 | 许可证、版本和成熟度 | 决策 |
|---|---|---|---|
| EleutherAI lm-evaluation-harness | `model_detect/adapters/lm_eval.py)；[上游](https://github.com/EleutherAI/lm-evaluation-harness) | MIT；项目目标 `0.4.13)；本地 OpenAI 兼容 Mock 已真实启动原始任务/评分器链路 | **保留唯一主力能力评测引擎**。原始 scorer 优先；真实渠道能力结果仍未验收 |
| MoonshotAI Kimi Vendor Verifier | `kimi_official.py`、`kimi_runner.py)；[上游](https://github.com/MoonshotAI/Kimi-Vendor-Verifier)；固定 commit `66092cf444c97356c0e11c5078c67116390615d9) | MIT；四组协议测试源码已固定 | **保留适用型号专项**；官方源码可追溯不等于真实供应商通过 |
| promptfoo | `adapters/promptfoo.py`、`regression_promptfoo.py)；[上游](https://github.com/promptfoo/promptfoo) | MIT；外部 CLI 版本尚未完成完整实证 | **兼容隔离**：保留旧 YAML 回归路径，默认不运行；不作为身份或 Benchmark 主引擎 |
| ToseaAI llm-fingerprint-detector | `model_detect/adapters/fingerprint.py)；[上游](https://github.com/ToseaAI/llm-fingerprint-detector) | MIT；上游 `package.json` 当前版本 `0.1.0)，Node >=18.17；当前适配器未固定 npx 版本且全局命令版本未校验 | **实验性候选**：本次报告未运行；先修复版本/CLI 可复现性，再做同模型正例、异模型负例、参考库覆盖和成本验证。不能进入正式身份结论 |
| dreamor llm-fingerprint | [上游](https://github.com/dreamor/llm-fingerprint) | MIT；自述参考库 176+ 模型，数据源 2026-07，数据集 CC-BY-4.0 | **不另接适配器**；作为 ToseaAI 的同类候选比较，避免维护重复 JSD 引擎。新模型未入库时无匹配真值 |
| ps4398 llm_check | [上游](https://github.com/ps4398/llm_check) | MIT；自述提供 JSD、forensics 与历史/漂移功能；仍需独立验证其真实误报 | **不另接适配器**；作为同类方法比较，不把 README 指标当作本项目准确率 |
| Babapei proxy-sleuth | `adapters/proxy_sleuth.py)；[上游](https://github.com/Babapei/proxy-sleuth) | MIT；上游项目标为 Alpha；当前版本/输出契约需固定 | **实验性隔离、默认关闭**；与现有参数/上下文/路由探针重叠，须证明独有贡献及正反样例效果后才决定去留 |
| Inspect AI | [上游](https://github.com/UKGovernmentBEIS/inspect_ai) | MIT；UK AI Security Institute 维护，200+ 预构建评测 | **不加入 v0.2.0**；作为 lm-eval 的备选，只有确认任务/Agent 评测存在实际缺口才评估替换/补充 |
| NVIDIA garak | [上游](https://github.com/NVIDIA/garak) | Apache-2.0；红队/漏洞扫描框架 | **当前不引入**：安全越狱与供应商身份/能力是不同问题，避免偏离产品宪章 |
| 自研 capability_lite | `probes/capability.py` | 本项目自有 | **只保留 Smoke**；不计入权威能力总分 |
| 自研 Docker Coding Sandbox | 旧主流程已移除 | N/A | **保持删除**；不重建评分/沙箱轮子 |

## 方法选择规则（不可只按某一个指纹方法设计）

- **协议符合性**：确定性 HTTP/JSON/SSE/tool-call/错误码断言；Kimi 官方测试器只用于 Kimi 适用项。
- **参数完整性**：根据官方协议定义做合法/非法值、参数差分与响应观察；“服务端接受字段”不等于“模型真正按参数执行”。
- **能力**：优先复用 lm-eval 原任务/原 scorer，按样本数、数据集/模板/生成参数报告；不要新建自研通用评分引擎。
- **身份/行为变化**：行为分布指纹、可用时的 token logprobs、同题多轮差分、同条件能力画像可以提供不同线索，但各自的适用条件不同；模型自述、一个 header 或一次分数不能认证权重。
- **上下文与路由**：使用随机标记/多位置检索、重复请求和统计差异；截断、随机性、缓存、版本漂移需与混路由假设分开。
- **服务商元数据**：只使用可归因的 response headers、明确结构化元数据和来源文档；不能在模型自然语言/推理正文里搜索品牌词来猜上游。
- **logprobs**：仅在端点明确支持且同 tokenizer/同提示/同解码条件可比时作为补充；不是所有 OpenAI-compatible API 都暴露，不能做默认必选。
- **安全红队**：garak 等不是当前产品目标，不把安全风险分数混入模型身份/能力结论。

## 真实成熟度边界

1. 代码有适配器 ≠ 安装了依赖 ≠ 固定版本 ≠ 真实运行成功 ≠ 方法经过正反样例校准。
2. 当前项目已在本地 Mock 验证 lm-eval 原始 scorer 链路，但这仅证明执行/解析，不校准模型身份识别准确率。
3. 当前 ToseaAI 指纹适配器在第二份 GLM 报告里是 `not_run`；因此该报告没有任何统计指纹身份结论。
4. ToseaAI、dreamor 和 llm_check 是同类行为分布路线，不应将三个结果当作三种独立证据叠加。
5. proxy-sleuth 不能因上游声称七层检测就作为主引擎；需要固定 commit、许可证、命令/输出契约及受控真值验收。
6. 官方公开成绩有来源权威性，但不是本次 API 调用结果，也不自动可与不同 Harness 的本地成绩相减。

**P0 决策**：保留通用协议 + lm-eval + Kimi 官方专项 + promptfoo 旧回归兼容；把指纹与 proxy-sleuth 设为实验性并关闭默认；不并行引入 Inspect/garak/多个同类指纹；先修通用证据误判和可复现性，再以正反例决定候选是否进入报告。
