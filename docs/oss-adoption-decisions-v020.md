# P0 开源组件与删减决策（2026-10-19，执行证据）

遵守 [冻结产品宪章](design/product-charter-v1.md)。原则：**不能因为代码“看起来多”而删掉已有用户数据的读取和开源适配；不能因为某仓库 README 声称精准识别而把它作为身份认证。** 仅四个可观察输出：协议、能力、异常信号、证据与限制。

| 组件 | 当前真实路径 | 上游与许可证 | 发布决策 |
|---|---|---|---|
| EleutherAI lm-evaluation-harness | `model_detect/adapters/lm_eval.py`；Deep 显式执行 | [EleutherAI](https://github.com/EleutherAI/lm-evaluation-harness)，MIT；项目锁定 **v0.4.13** | **保留**。能力原始任务/评分器唯一主力；本项目只负责请求适配/输出解释。未实际运行时不得标评分成功 |
| MoonshotAI Kimi-Vendor-Verifier | `kimi_official.py`、`kimi_runner.py`，固定提交 `66092cf444c97356c0e11c5078c67116390615d9` | [MoonshotAI](https://github.com/MoonshotAI/Kimi-Vendor-Verifier)，MIT | **保留专项**。官方来源的参数/工具/Token 协议测试，用供应商 API 执行；不覆盖所有模型和所有 Benchmark |
| promptfoo | `adapters/promptfoo.py`、`regression_promptfoo.py`、`promptfoo_results.py`；旧 YAML 回归仍依赖 | [promptfoo](https://github.com/promptfoo/promptfoo)，MIT | **兼容隔离**：Quick/Standard 默认不需要；旧 regression YAML/历史导入仍有独有可复现价值。不要删除仍被调用的实现；以后要移除必须先替代该能力并迁移数据 |
| proxy-sleuth | `adapters/proxy_sleuth.py`、`audit.py`、CLI 标志、旧历史证据 | [Babapei](https://github.com/Babapei/proxy-sleuth)，MIT | **实验性隔离**：Web 默认入口已移除；CLI 旧显式 opt-in 保留兼容。其知识/路由/指纹“真假”推断尚未对五型号提供受控真值校准，因此不进入正式身份判断 |
| llm-fingerprint | `adapters/fingerprint.py`、CLI/Reference 历史入口 | [dreamor](https://github.com/dreamor/llm-fingerprint)，工具 MIT；参考数据 CC-BY-4.0 | **实验性隔离**：现有 176 模型参考库来自 2026-07，不能自动覆盖之后的 GLM-5.3/Kimi-K3/DeepSeek V4.1。没有与被测官方版本同条件真值，不做身份认证或准入拒绝 |
| 自研 capability_lite | `probes/capability.py` | 本项目自有 | **仅保留 Smoke**，证明基本模型响应，不代替成熟 Benchmark 和官方能力排名 |
| 自研 Docker Coding Sandbox | 仓库主流程已移除 | N/A | **已删除功能**，不再重建；优先使用官方/社区现有评测器 |

## P0 结论

- **实际删减已完成**：旧 Docker Coding Sandbox 不在当前源码树；主 Web 移除了 proxy-sleuth 指纹猜测开关及不可信的禁止上游控件；主报告不再展示无校准身份概率。上述不等于删除所有 legacy adapter。
- **不能安全地物理删除**：promptfoo、proxy-sleuth、fingerprint 适配器尚有 CLI/YAML/旧测试/报告引用。直接 rm 会使真实使用中的已配置功能和旧历史读取损坏。合理交付决策是标为 *experimental/legacy opt-in*，从默认路径隔离，并保留只读兼容。若将来删除，需要专门迁移/等价功能回归。
- **许可证明确**：工具代码可在各自许可范围调用，第三方数据的 CC-BY 署名条件仍需遵守。采用原执行器而非复制第三方源码。
- **停止重复造轮子**：本项目不实现新 benchmark scorer、JSD 身份统计引擎或多模态 Agent benchmark。官方公开**总分**与本地同题实测不能直接相减宣告“真假”。
- **发布定义**：只有默认端到端及隔离兼容测试通过，P0 可以通过“保留/隔离理由充分”收尾。实验性功能不作为 v0.2.0 交付承诺，不能标已验收。真实供应商功能仍按单端权限和成本进行人工实测。

## 真实能力与权威等级

1. 官方 Kimi Verifier：官方**协议测试源码**权威，但该工具在我们当前测试环境没有真实调用的用例，不能说供应商通过；其公开评测成绩并不是任意供应商的身份证书。
2. lm-eval：社区成熟、公开标准任务评分；固定版本与具体题集/样本和正确生成配置下才有方法学可比性。低样本只作筛查，非模型权重认证。
3. promptfoo：成熟开源 YAML 断言/回归测试器；评测可靠性取决于具体断言和供应商行为，不保证模型身份。
4. proxy-sleuth / llm-fingerprint：辅助异常线索，有参考集时可观察变化；尚不能对本产品五型号输出确定性权重认证或经过独立校准的真假概率。
5. 官方公开聚合成绩：来源可以权威，但严格对比所需 Dataset/Harness/Sample IDs/Scorer/解码参数不足时只作背景资料。
