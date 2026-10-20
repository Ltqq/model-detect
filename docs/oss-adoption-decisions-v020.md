# P0 开源组件与删减决策（2026-10-20）

遵守 [冻结产品宪章](design/product-charter-v1.md)。不能因为 README 声称精准识别就把某个项目作为身份认证；不能因为功能重复就未经引用/历史兼容审查物理删除。产品输出仍然是协议、能力、异常信号、证据与限制四类。

## 组件去留

| 组件 | 当前路径 / 来源 | 许可证、版本和成熟度 | 决策 |
|---|---|---|---|
| EleutherAI lm-evaluation-harness | `model_detect/adapters/lm_eval.py`；[上游](https://github.com/EleutherAI/lm-evaluation-harness) | MIT；项目目标 `0.4.13`；原始评分器在本地 OpenAI 兼容 Mock 上运行过 | **保留唯一主力能力评测引擎**。原始 scorer 优先；真实供应商成绩仍未验收 |
| MoonshotAI Kimi Vendor Verifier | `kimi_official.py`、`kimi_runner.py`；[上游](https://github.com/MoonshotAI/Kimi-Vendor-Verifier) | MIT；固定 commit `66092cf444c97356c0e11c5078c67116390615d9)；四组协议测试源码已固定 | **保留适用型号专项**；不能推广为其他型号的官方认证 |
| promptfoo | `adapters/promptfoo.py`、`regression_promptfoo.py`；[上游](https://github.com/promptfoo/promptfoo) | MIT；外部 CLI 完整实证尚未完成 | **兼容隔离**：保留旧 YAML 回归路径，默认不运行；不作为身份或 Benchmark 主引擎 |
| ToseaAI llm-fingerprint-detector | `model_detect/adapters/fingerprint.py`；[上游](https://github.com/ToseaAI/llm-fingerprint-detector) | MIT；源码版本 `0.1.0`；固定 commit `94dc44686a553595581b6d06405c17f070df9b8d`；npm registry 实测 404，CI 源码构建与 CLI/JSON smoke 通过 | **实验性候选**：显式安装、版本校验；不自动 npx 下载。内置参考只有 11 个旧型号，采集协议与当前探针不一致，最新五目标不全覆盖；需同协议 Reference。真实端点采集和准确性仍未验证 |
| dreamor llm-fingerprint | [上游](https://github.com/dreamor/llm-fingerprint) | MIT；自述参考库 176+ 模型，数据源标记为 2026-07，数据集 CC-BY-4.0 | **不另接适配器**；与 ToseaAI 属同类分布指纹路线，比较参考覆盖即可，避免重复维护引擎 |
| ps4398 llm_check | [上游](https://github.com/ps4398/llm_check) | MIT；自述包含 JSD、forensics 和漂移分析，需独立复核 | **不另接适配器**；作为同类候选，不把 README 指标当成本项目准确率 |
| Mohamed7415 fpverify | [上游](https://github.com/Mohamed7415/fpverify) | MIT；0.1.0；无 `pyproject.toml`，通过 `requirements.txt` 管理；36 个 cell × 20 样本的参考入册约 720 次请求，审计预算默认最高 600 次并可早停；当前不集成 | **研究候选，不接入 v0.2.0 默认流程**：e-process/序贯检验值得评估；README 对 `delta` 的后验预测标定明确属于近似；统计测试基于自有合成分布与仿真，不能证明真实 API 误报率 |
| benbenlijie llm-provider-audit | [上游](https://github.com/benbenlijie/llm-provider-audit) | MIT；Alpha `0.1.0`；要求 Python >=3.12，与当前 Python 3.11 测试矩阵不兼容 | **研究参考**：借鉴 reference variance、negative controls、open-set calibration；先比较独有价值，不作为当前依赖 |
| Babapei proxy-sleuth | `adapters/proxy_sleuth.py`；[上游](https://github.com/Babapei/proxy-sleuth) | MIT；上游标为 Alpha，当前版本/输出契约需固定 | **实验性隔离、默认关闭**；与现有参数/上下文/路由探针重叠，须证明独有贡献后再决定 |
| Inspect AI | [上游](https://github.com/UKGovernmentBEIS/inspect_ai) | MIT；UK AI Security Institute 维护，200+ 预构建评测 | **不加入 v0.2.0**；作为 lm-eval 的备选，只有明确任务缺口才评估替换/补充 |
| NVIDIA garak | [上游](https://github.com/NVIDIA/garak) | Apache-2.0；红队/漏洞扫描框架 | **当前不引入**：安全越狱与供应商身份/一般能力不是同一个问题 |
| liuxiaotong model-audit | [上游](https://github.com/liuxiaotong/model-audit) | MIT；Alpha；README 自述 14 样本上 100% 检出，尚未独立复现 | **不采用**：蒸馏/血缘取证与 API 供应商检测不等价，部分方法需要白盒表示 |
| 自研 capability_lite | `probes/capability.py` | 本项目自有 | **只保留 Smoke**；不计入权威能力总分 |
| 自研 Docker Coding Sandbox | 旧主流程已移除 | N/A | **保持删除**；不重建评分/沙箱轮子 |

## 方法选择规则（不可只按某一个指纹方法设计）

- **协议符合性**：确定性 HTTP/JSON/SSE/tool-call/错误码断言；Kimi 官方测试器只用于 Kimi 适用项。
- **参数完整性**：根据官方协议定义做合法/非法值、参数差分与响应观察；“服务端接受字段”不等于“模型真正按参数执行”。
- **能力**：优先复用 lm-eval 原任务/原 scorer，按样本数、数据集/模板/生成参数报告；不要新建自研通用评分引擎。
- **身份/行为变化**：行为分布指纹（固定样本 JSD 或 fpverify 的序贯 e-process）、可用时的 token logprobs、同题多轮差分、同条件能力画像可提供互补线索；这些不是全部独立证据，也不等同权重认证。fpverify 的误报控制和参考校准需按其实际假设复核，不能把 README 的仿真结果直接当成本产品真实端点准确率。模型自述、一个 header 或一次分数不能认证权重。
- **上下文与路由**：使用随机标记/多位置检索、重复请求和统计差异；截断、随机性、缓存、版本漂移需与混路由假设分开。
- **服务商元数据**：只使用可归因的 response headers、明确结构化元数据和来源文档；不能在模型自然语言/推理正文里搜索品牌词来猜上游。
- **logprobs**：仅在端点明确支持且同 tokenizer/同提示/同解码条件可比时作为补充；不是所有 OpenAI-compatible API 都暴露，不能做默认必选。
- **安全红队**：garak 等不是当前产品目标，不把安全风险分数混入模型身份/能力结论。

## 真实成熟度边界

1. 代码有适配器 ≠ 安装了依赖 ≠ 固定版本 ≠ 真实运行成功 ≠ 方法经过正反样例校准。
2. lm-eval 已在本地 Mock 验证原始 scorer 链路；这仅证明执行/解析，不校准真实模型身份识别准确率。
3. 第二份 GLM 报告里 ToseaAI 指纹为 `not_run`、lm-eval 为 `disabled`、proxy-sleuth 为 `disabled`；该报告没有开源统计指纹或标准能力 Benchmark 的实际结果。
4. ToseaAI、dreamor、llm_check 是同类行为分布路线，不应将三个结果当作三种独立证据叠加。
5. fpverify 增加序贯 e-process 与容差标定，值得候选评估；但它不是当前已集成的组件，且需要同条件 Reference、较高请求预算和真实端点正反验证。
6. llm-provider-audit 的 reference variance 和 negative controls 值得借鉴，但当前要求 Python >=3.12，且需先验证负对照的独立贡献和可复现性。
7. proxy-sleuth 不能因上游声称七层检测就作为主引擎；需固定 commit、许可证、命令/输出契约及受控真值验收。
8. 官方公开成绩有来源权威性，但不是本次 API 调用结果，也不自动可与不同 Harness 的本地成绩相减。

**P0 决策**：保留通用协议 + lm-eval + Kimi 官方专项 + promptfoo 旧回归兼容；把 ToseaAI 指纹与 proxy-sleuth 设为实验性并关闭默认；fpverify 与 llm-provider-audit 只做方法比较，不并行堆叠。先修通用证据误判和可复现性，再以正反例决定候选是否进入报告。
