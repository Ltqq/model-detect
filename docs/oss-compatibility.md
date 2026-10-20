# 开源检测方法与兼容性审计（2026-10-20）

本清单把**检测方法、开源项目、当前代码接入状态、真实运行状态和证据强度**分开记录。GitHub README、Stars、依赖安装、Mock 测试均不能单独证明检测准确。

## 1. v0.2.0 实际保留的开源核心

| 方法类别 | 开源项目 / 来源 | 许可证与版本边界 | 当前集成状态 | 当前能证明什么 |
|---|---|---|---|---|
| 通用协议 / 参数合约 | 本项目通用 HTTP/SSE probes | 自有代码；须按明确协议与模型能力规则验证 | 默认运行；已有 Mock 正反例 | 当前请求/响应符合已实现的协议断言，不证明真实权重 |
| 厂商专项协议 | [MoonshotAI/Kimi-Vendor-Verifier](https://github.com/MoonshotAI/Kimi-Vendor-Verifier) | MIT；固定源码 commit `66092cf444c97356c0e11c5078c67116390615d9) | 四组 Pytest 源码已固定；源码/运行器离线检查通过；真实端点运行未证明 | 对 Kimi 适用的协议/参数测试；不是任意模型的身份认证 |
| 通用能力 Benchmark | [EleutherAI/lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) | MIT；当前项目配置目标为 `0.4.13)，须以运行环境版本复核 | 已验证原始评分器在本地 OpenAI 兼容 Mock 上执行并输出 JSON；真实供应商成绩未验证；默认关闭 | 在具体任务、样本、评分器、生成参数可比时，测量对应能力 |
| YAML 回归 | [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | MIT；当前未固定并实证完整外部 CLI 版本 | 旧 YAML/历史路径仍被调用；不属于默认 Quick/Standard 主引擎 | 执行显式断言与回归；断言本身需要正反例校准，不识别真实权重 |
| 行为分布指纹 | [ToseaAI/llm-fingerprint-detector](https://github.com/ToseaAI/llm-fingerprint-detector) | MIT；源码版本 `0.1.0`，固定 commit `94dc44686a553595581b6d06405c17f070df9b8d`；npm registry 实测 404 | 显式源码安装；CI 真实构建、CLI 版本与参考目录 smoke 已通过。内置 11 个样例参考采集于 2026-07-08，协议为 `bruckner-zenodo-2026`，与工具 `one-token/v1` 不同 | 内置样例参考在本适配器中会因协议不匹配降为证据不足；列表没有 GLM-5.3/Flash、Kimi-K3 或 DeepSeek V4/V4.1。需同协议可信 Reference 才可比较；仍不证明权重身份 |
| 多层代理异常筛查 | [Babapei/proxy-sleuth](https://github.com/Babapei/proxy-sleuth) | MIT；上游标为 Alpha，当前版本需固定 | 旧 CLI/适配器保留、默认关闭；未对本产品五型号做受控真值校准 | 候选的参数/上下文/路由/行为信号；不能直接作为真假判决 |
| 序贯行为指纹 / 假设检验 | [Mohamed7415/fpverify](https://github.com/Mohamed7415/fpverify) | MIT；README/CITATION 标记 0.1.0；当前仓库没有 `pyproject.toml`，依赖通过 `requirements.txt` 管理；统计测试是项目自有合成分布/仿真，不能视为真实供应商 API 的独立 FPR 证明 | **未集成**；代码与统计测试值得深入评估，不能直接 pip 安装成稳定依赖 | 在行为分布指纹上增加 e-process 早停与误报控制，并做参考方差标定；README 的 FPR 数字主要来自项目自身仿真/实验，复合零假设的 `delta` 标定明确是后验预测近似，不能无条件宣称真实 API FPR 已被证明 |
| 参考校准 + 负对照的渠道审计 | [benbenlijie/llm-provider-audit](https://github.com/benbenlijie/llm-provider-audit) | MIT；Alpha，`0.1.0`；要求 Python >=3.12，与本项目 3.11 测试矩阵不兼容 | **未集成**；完成源码级方法审查，不作为运行时依赖 | 参考方差、负对照、开放集阈值值得借鉴；但相似度尾部概率来自参考样本的经验排名，阈值为校准启发式，不等于正式 FPR 保证。实现与现有功能重叠 |
| 蒸馏/模型血缘取证 | [liuxiaotong/model-audit](https://github.com/liuxiaotong/model-audit) | MIT；Alpha；README 自述 14 样本上 100% 检出，尚需独立复现 | **不进入 v0.2.0** | 面向蒸馏/血缘检测，包含需要白盒表示的路线；小样本自报准确率不足以成为 API 中转验真依据 |

| 外部统计指纹候选 | [dreamor/llm-fingerprint](https://github.com/dreamor/llm-fingerprint)；[ps4398/llm_check](https://github.com/ps4398/llm_check) | 均 MIT；dreamor 工具自述有 176 模型库，参考数据 CC-BY-4.0；上游版本/参考日期需记录 | **尚未集成到当前主流程**；仅作同类候选对比，不同时维护多个重复引擎 | 同样是行为分布方法；需评估参考库覆盖、协议差异、有效样本和误报 |
| 通用任务/Agent 评测框架候选 | [UK AI Security Institute Inspect](https://github.com/UKGovernmentBEIS/inspect_ai) | MIT；有 200+ 预构建评测 | **未集成**；作为 lm-eval 的备选，不并行引入 | 更复杂的多轮、工具和模型评分任务；需证明 lm-eval 缺口才考虑替换/补充 |
| LLM 安全红队 | [NVIDIA/garak](https://github.com/NVIDIA/garak) | Apache-2.0 | **未集成，v0.2.0 非目标** | 注入、越狱、泄露等安全弱点；不等同模型供应商/权重身份检测 |

## 2. 方法覆盖图：不要把“身份检测”缩成一种指纹

| 检测方法 | 主要信号 | 是否需要可信参考 | 常见失效/误判 | v0.2.0 决策 |
|---|---|---|---|---|
| HTTP / OpenAI-compatible 合约测试 | 状态码、JSON schema、SSE、tool calls、usage、finish_reason | 通常不需要；模型特性需来源 | HTTP 200 不等于请求被正确执行；截断/空正文不能算 PASS | **保留核心** |
| 参数完整性/差分探针 | 对比参数开启/关闭、合法/非法值的行为差异 | 某些断言需要官方文档或对照组 | 参数被接受不代表服务端生效；随机输出造成差异 | **保留，结果须分为支持/不支持/未知** |
| 厂商原始协议套件 | 官方测试源码、固定测试 ID 与原始断言 | 需要适用的官方/供应商 API | 官方测试通过只说明该套件覆盖的行为，不是身份认证 | **Kimi 专项保留** |
| 标准能力 Benchmark | 原始题集、任务版本、原始 scorer、样本级结果 | 不一定需要身份参考；比较渠道需要同条件结果 | 数据集污染、样本太少、Harness/模板/解码设置不一致 | **lm-eval 为唯一主力** |
| 行为分布指纹 | 多轮随机/选择题行为分布、JSD 等统计距离、自一致性 | **需要**可信且条件匹配的 Reference 才能比对声称身份 | 模型更新、system prompt、采样参数、推理模式、量化、路由和采样噪声都会造成偏移 | **候选；先做方法验收，不能默认启用** |
| Logprobs / token 概率 | token log probability、候选 token 概率分布 | 通常需要同 tokenizer、同提示、同解码条件的可信参考 | 很多兼容 API 不暴露 logprobs；字段可能不支持/被中转改写；跨 tokenizer 不可比 | **研究候选，不作为通用必选项** |
| 上下文检索/长度 | 随机标记、分位置检索、长上下文多点命中 | 无需官方端点，但预期长度必须有来源 | 输出预算不足、提示格式错误、检索任务太简单会误判 | **保留轻量确定性探针；成熟长上下文套件可选** |
| 路由/混合后端异常 | 多轮同题、分布聚类、响应 metadata/headers、质量差异 | 同一端点自身基线或可信参考会增强判断 | 负载、模型更新、温度和缓存也会造成方差；一次差异不能证明混路由 | **只报异常信号，需重复样本** |
| 服务商元数据 | 响应头、请求 ID、明确的结构化错误码/字段 | 不一定需要参考，但需有文档/可追溯证据 | 中转可转发/改写 Header；自然语言可随意包含品牌词 | **修正现有误报；绝不扫描生成正文来猜服务商** |
| 自我介绍/问模型“你是谁” | 模型自述 | 无 | 很容易被 system prompt 或中转指令伪造 | **不作为身份证据** |
| 安全红队 | 越狱、注入、泄露等对抗样本 | 需明确安全策略和基线 | 安全行为与模型权重身份不是同一个问题 | **v0.2.0 不接入 garak** |
| 水印/蒸馏/量化检测 | 特定算法/白盒特征或行为代理 | 常需专门方法与已知真值 | 通用 API 黑盒没有普适可靠的权重/量化证明 | **不承诺；有独立证据再研究** |

## 3. 版本、执行和可信度规则

`model-detect oss-status` 的字段含义必须保持区分：

- `adapter_exists`：仓库有适配器代码。
- `executable_found`：本机找到已安装的 `llm-fingerprint` 命令；仅找到 npx 不等于该引擎可运行。本项目禁用自动 npx 下载。
- `version_compatible`：确切版本符合已声明约束。
- `runtime_verified`：该工具在记录的环境中真实运行并产出预期结构。
- `result_trust_verified`：方法经过适用范围内的已知正反样例验证；**Mock 只验证调用/解析链路，不校准真实模型鉴别能力**。

已修正指纹适配器的可复现性：只接受显式安装、版本为 `0.1.0` 的 `llm-fingerprint` CLI；npm registry 实测返回 404，因此不再尝试 npx 回退。固定源码 commit `94dc44686a553595581b6d06405c17f070df9b8d` 已在 CI 构建并通过 `--version` 与 `references --json` smoke。该结果只证明该 CI 环境的源码构建、CLI 与 JSON 合同可运行；不代表用户本机已安装，不证明真实 API 采集成功，更不证明身份识别准确性。

### 指纹引擎的可选源码安装

只有用户主动启用统计指纹时才需要安装。该项目虽有 npm `package.json`，但在 2026-10-20 对 npm registry 的真实安装测试返回 404，因此不要使用 `npx llm-fingerprint-detector`。CI 已验证以下固定源码构建、版本和非空参考目录可用（不调用模型 API；只验证执行链路，不校准准确率）：

```bash
git clone https://github.com/ToseaAI/llm-fingerprint-detector.git
cd llm-fingerprint-detector
git checkout 94dc44686a553595581b6d06405c17f070df9b8d
npm ci
npm run build
npm link
llm-fingerprint --version  # 必须输出 0.1.0
```

此安装只验证上游 CLI 和参考目录可用。真实 API 指纹采集仍会产生额外请求费用，且必须有相同协议、可信来源的 Reference；没有参考或样本不足时不得输出身份判断。

## 4. 选型结论：少数方法真正跑起来，而不是堆更多依赖

1. **协议核心**：保留当前自有 HTTP 合约胶水和 Kimi 官方专项；修正错误的协议/身份断言。
2. **能力主力**：保留 EleutherAI lm-eval 原生任务和评分器；Inspect AI、OpenCompass、EvalScope 是候选替代/补充，不因“功能多”并行安装。仅在已证明任务覆盖缺口后再决策。
3. **身份/路由信号**：ToseaAI 使用固定样本 JSD，论文给出的阈值和错误率是其论文数据上的基线，不是本产品准确率；其 11 个内置参考与当前探针协议不一致，且不覆盖本项目最新目标型号。fpverify 的序贯 e-process 值得研究，但自动容差标定是近似且预算较高；llm-provider-audit 的负对照/参考方差是设计参考，不提供已证实的真实 API FPR。三者均完成源码级审查，但未完成真实端点正反验收，不能成为默认身份结论。dreamor/llm_check 不重复接入；proxy-sleuth 与已有探针重叠，保持实验性关闭。
4. **回归断言**：promptfoo 只承担现有 YAML 回归兼容，不与 lm-eval 争夺能力评分主线。
5. **安全扫描**：garak 不属于当前产品目标；不安装、不把安全扫描报告混进模型身份结论。
6. **新方法的准入门槛**：上游地址/许可证/固定版本 → 代码调用合同 → 已知正例/负例/未知例 → 有效样本/成本 → 误报/漏报和局限 → 报告证据来源。不能满足则保持实验性/不运行。

**权威性边界**：权威首先是原始测试、数据集、评分器和可追溯来源；开源项目只是执行这些方法的工具。方法再有名也不自动权威，官方发布的聚合分也不等于本项目实际运行结果。模型身份、换模、量化和混合路由只能根据当前证据给出分级线索，不承诺黑盒权重认证。
