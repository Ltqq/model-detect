# model-detect 工程收尾与最终验收路线（2026-10-13）

> 本文是 **2026-10-13 起唯一的下一批开发任务清单**。既有 `03-development-plan.md` 的早期开发批次、`14`～`16` 号设计文档保留作为历史设计/已实现记录，不再把旧的“下一步”重复安排。
>
> 产品边界：**单机单用户的 AI 模型供应商黑盒审计**；Web + CLI + 中文 HTML/JSON/ZIP + SQLite 历史。**不做性能压测，不加 RBAC/任务队列/定时器/SaaS。**

## 0. 现状与证据级别

截至 `main` merge `3209132`，以下均已有代码：
- 原生 OpenAI-compatible Protocol、Parameter Integrity、Context Needle、Routing/Provider Probe 与 Capability Lite；
- Fingerprint、proxy-sleuth、promptfoo、lm-evaluation-harness 四类可选开源 Adapter（**存在适配器 ≠ 第三方工具在本机已安装，也 ≠ 其全部能力已覆盖**）；
- Trusted Reference、Official Quality Baseline、同套件比较契约、版本化 Model/Provider Rule；
- CLI/Web、SQLite 历史、Evidence、中文报告、受控实验 `validation run/evaluate` 与离线 `validation calibrate`；
- Python 3.11/3.12 的源码/模拟数据 CI。

**仍待补齐**：安全的 Reference 原子替换、强制失败/证据不足语义、Token/费用的真实计量与可控预算、Kimi 官方 Vendor Verifier 专项适配、真实安装与 API 端到端验证，以及真实 Kimi/GLM 数据校准。

**不得宣称**：国际权威官方认证、识别具体量化精度或权重、已实测换模检出率/误报率、第三方完整工具已覆盖、官方 Verifier 已经通过。

状态词统一：
- **已完成代码**：实现并有单元测试，但未必跑过真实外部系统。
- **集成已验收**：指定版本的 OSS/本地 Web-CLI 流程经实际运行并存有记录。
- **真实已校准**：具有可追溯官方 Reference、受控真值与重复运行统计。
- **暂不做**：明确排除，而非等待实现。

## 0A. GLM-5.3 真实 API 验收触发的临时抢修任务（2026-10-13）

> **已收到实际测试证据**，详见 [20 号 GLM-5.3 实测复盘与缺陷优先级](20-glm53-live-evidence-triage.md)。这不是新的通用需求池，也不替代本文 A～F；是在恢复 A1 前先修**已证实影响判断正确性**的 GLM/共用引擎问题。

| 顺位 | 任务 | 优先级 | 状态 | 为什么先修 |
|---|---|---|---|---|
| **临时 0** | G0.1～G0.2：Benchmark 稳定可比契约与真实 fixture 回放 | **P0** | 待开发 | GLM-5.3 04/05 双端有真实成绩，现有 hash 因 base_url/内存地址全部误判不可比 |
| **临时 1** | G0.3～G0.5：Capability 答案规范化、GLM 中文拒绝、结论降级 | **P0** | 待开发 | 03 实测存在正确答案被判错和协议误标；继续测试只会扩大脏分数 |
| **临时 2** | G1.1～G1.3：lm-eval 缺依赖/离线预检/参数生效校验 | P1（运行可靠性前置） | 待开发 | 04 首次因依赖失败；官方/客户 reasoning 的同条件仍未证实 |
| **临时 3** | G1.4～G1.5：失败保留进度、原始证据与报告可追溯 | P1 | 待开发 | 标准结果因临时目录清理丢失；应避免再次付费 |
| 常规 | A1 → A2/A3 → B1/B2/B3 | **P0** | 继续保留 | Reference 原子更新/失败语义/Token Meter 对全项目仍关键 |
| 后续 | C → D → E → F | P1/P2 | 原计划不变 | Kimi 专项、其他 OSS E2E 与真值校准不能拿本次 GLM 对照替代 |

**优先级原则：数据真实性 > 可比性 > 评分正确性 > 安装可运行 > 成本观测 > UX 与新增 Benchmark。**

20 号文档的原始用户报告是独立本地资料，不会提交仓库。其手写“已验证符合/差异属于正常波动”结论**不能原样作为权威验收结论**。25 题只能支持有限范围的观察陈述；也不等于已知换模/降智真值实验。

## 1. 执行顺序与门槛

| 顺序 | 任务组 | 优先级 | 当前状态 | 是否依赖付费官方 API | 完成产物 |
|---|---|---|---|---|---|
| A | Reference 和失败语义可靠性 | P0 | **待开发** | 否（用 Fake/Mock） | 不丢旧基准、失败不伪装成通过 |
| B | Token 计量、预算与费用 | P0 | **待开发** | 否（代码测试用 Mock；准确成本需实际用量） | 分 Probe/阶段/来源的 usage 和成本摘要 |
| C | Moonshot 官方 Kimi-Vendor-Verifier 专项接入 | P1 | **待开发** | 适配器可 Mock，真实运行需要 | 选择性官方验证、与通用检测分层 |
| D | 第三方集成 + Web/CLI 最终产品验收 | P1 | **待验收** | 部分需要 | 真实安装兼容记录、错误场景、UI/导出闭环 |
| E | Kimi-K3、GLM-5.2 真实基准和渠道校准 | 数据 P0 | **待采集** | **是** | 可追溯 Reference、已知正负实验、校准报告 |
| F | 发布与停止条件 | P2 | **待评审** | 取决于 E | 变更日志、使用说明、版本标签 |

原则：**一次一个小点、一个提交**；每组单独 PR，Python 3.11/3.12 CI 绿后合并。**先完成 G0 已证实的结果正确性缺陷，再处理 G1 评测器运行可靠性和常规 A/B，随后 C/D/E/F。** 原有 A/B 不取消；E 的真实数据继续准备，但不得阻塞纯工程修复。不能为了“跑通”而吞错误或弱化证据门槛。

## 2. A · P0：工程可靠性（先做）

### A1 Reference 覆盖操作原子化

- [ ] Web `/api/references` 覆盖时**不得先删除现有 Reference**；先在唯一临时目录完成 Baseline、Fingerprint、Manifest、报告采集。
- [ ] 所有检查和持久化成功后才原子切换版本（同磁盘 rename/backup/rollback）；失败清理临时数据并保持原有 Reference 完整可用。
- [ ] CLI 创建/覆盖路径遵循相同写入规则；重复 ID 默认拒绝覆盖，覆盖须用户显式确认，避免两套语义。
- [ ] 处理并发覆盖同 ID、磁盘写失败、Fingerprint 外部进程失败和用户中断。
- [ ] 单元/集成测试：旧 Reference 在任一阶段失败时 MD5/SHA256/文件内容保持不变；成功切换后新文件完整；不留下半成品和泄露密钥的错误文件。

**验收**：在注入失败的任何阶段，原 Baseline、Fingerprint、Manifest 和 baseline-report 仍可读取；真实环境不会静默删除可信资产。

### A2 结果有效性与错误状态

- [ ] Collector 逐轮核验 `invalid_target`、目标模型一致、核心 Probe/Evidence、Contract 可比、真实有效 run 数；失败不得生成可被正常引用的 Official Baseline。
- [ ] 供应商**显式请求** Strong Benchmark、Fingerprint 或 Regression 时，其失败在报告和 Web 任务详情显著显示 `ERROR/INSUFFICIENT/PARTIAL`，不得靠其他绿项掩盖；不必让一个可选失败把所有原生结果作废。
- [ ] `baseline_match` 只能来自**明确可比**的维度，无法进行的维度逐项标注；禁止“没跑/缺失 == 通过”。
- [ ] 校验 Profile、模型 ID、Reference 型别、任务与参数契约；错误不输出明文凭证或第三方响应内的敏感信息。
- [ ] CI 加覆盖成功、HTTP 401/403/429/HTML、部分成功、超时、旧 Reference/Benchmark 无版本的回归测试。

**验收**：用户能明确区分：`完整检测通过 / 部分检测完成 / 完全失败 / 缺失官方基准 / 不可比`。

### A3 安全边界（只覆盖单机必要范围）

- [ ] Web 仅回环监听作为默认；若外网部署在 README 明确要求额外认证/反向代理访问控制。
- [ ] 检查报告/任务/子进程错误日志的 API Key、Authorization、Cookie、Query Token 脱敏。
- [ ] 防止通过恶意 Reference ID/输出路径访问非工作目录；删除/覆盖操作受限于工作根目录。
- [ ] 不新增登录/RBAC/企业权限体系；安全防护仅限合理的单机使用边界。

## 3. B · P0：Token Meter（必须做，避免盲测）

### B1 每次 API 请求采集与规范化

- [ ] 统一 `UsageRecord`：`probe_id`、阶段、HTTP 状态、尝试次数、请求/完成时间、`prompt_tokens`、`completion_tokens`、`cached_read_tokens`、`cached_write_tokens`（若有）、`reasoning_tokens`（若有）、`usage_source`、缺失原因。
- [ ] 支持主流 OpenAI-compatible `usage`，包括 `prompt_tokens_details`、`completion_tokens_details`，以及可配置别名；流式响应要尽可能读取最后 usage chunk，不再仅为预览读取前 30 行就声称完整 usage。
- [ ] 统计实际网络请求和错误/重试；`usage` 不存在时单独记 `unknown`，可选 tokenizer 估算必须显式标注 `estimated`，绝不混成实测。
- [ ] 理清 Token 口径：`reasoning_tokens` 通常是输出总量的子集；缓存读通常是输入总量的子集，**不能重复相加计算总 Token/费用**。
- [ ] 只把必要统计写入 Evidence/Report，不存客户请求原文之外的凭据；提供单元测试覆盖缓存、reasoning、SSE usage、空字段、失败调用。

### B2 审计级账单汇总与 CSV/JSON/中文报告

- [ ] 按 `probe_id` → 阶段（Protocol/Integrity/Context/Routing/Capability/Fingerprint/Benchmark/OSS/Regression）→ 整次 Audit 聚合请求数和 Token。
- [ ] 对 Adapter 子进程要求可解析其真实 Usage 或接受导入上游日志；无数据时标 `external_unmetered`，**总计标“部分覆盖”**，不能把缺失工具记为 0 成本。
- [ ] 提供 `observed / estimated / unknown` 三栏，展示计量覆盖率及误差来源。
- [ ] 在 Web、CLI、JSON/HTML/ZIP 和 Reference 采集结束后可查阅消耗。
- [ ] 允许导出 CSV（如确有实际使用需求），优先复用现有报告结构，避免额外 DB 表。

### B3 执行前预算与可控运行

- [ ] 依据 Profile 的 Probe 清单、预计 Context 长度、Benchmark 样本上限、Baseline 重复轮数及 Fingerprint/OSS 档位显示**预计请求数与粗略 Token 范围**；区分固定上限、可变输出、不可控 Adapter。
- [ ] 用户输入价格（每百万输入/输出/缓存读/缓存写），在 **有完整 usage 或明确假设时**计算费用；不把 Sample Count 当 Token Count。
- [ ] 缺估算来源时明确“无法保证费用上限”，不伪造精确预算。
- [ ] 可按**请求数 / 已观察 usage / 可控制的原生检测模块**实现软停止；外部 subprocess 只有明确支持取消/限额时才能承诺硬上限。
- [ ] 默认继续轻量，Benchmark 默认关闭；给官方 Reference × N runs 的费用放大明确提示。

**验收**：能够回答“Standard 跑了多少个网络请求、每个 Probe 实际用多少输入/输出 Token、哪些未知、按当前价格多少钱”，并在付费运行前显示风险提示。

## 4. C · P1：官方 Kimi-Vendor-Verifier 专项（选择性集成）

> 官方项目：https://github.com/MoonshotAI/Kimi-Vendor-Verifier 。先固定官方仓库版本/Commit、检查许可证/依赖与执行方法，再确认本项目可复用的测试边界。**不把通用 Protocol Probe 叫作官方 Verifier。**

### C1 官方能力映射与差距清单

- [ ] 逐目录审核官方 Verifier 的真实测试入口、依赖、分组、断言与 Token 消耗；以实际代码为准，不靠 README 推断每项请求量。
- [ ] 对照本项目已有 `Kimi-K3` Model Rule、Protocol、Parameter Integrity、Tool Schema、`usage.prompt_tokens` 计量验证等功能，形成 `已覆盖 / 部分重叠 / 缺失 / 不适用`。
- [ ] 明确优先顺序：**参数语义 + Tool/JSON Schema + Prompt Token 正确性**；后续视需求/价格再决定是否跑视觉、百万上下文、Agent/Coding 等昂贵测试。
- [ ] 检查官方 Verifier 的许可证、CLI 输出可解析程度和实际端点协议；若无法稳妥复用，只做结果导入适配，避免重新发明全套官方用例。

### C2 轻量适配与结果归并

- [ ] `KimiVendorVerifierAdapter` 显式启用，仅适用于校验过支持范围的 Kimi 模型；未安装/无 Reference 时明确 `SKIPPED/INSUFFICIENT`。
- [ ] 提供子集选择、输入验证、超时与费用/请求量提醒；不在默认 Standard 自动跑大型官方套件。
- [ ] 官方原始 artifact 保存校验和/版本/执行参数，映射到现有 `ProbeResult`/Evidence/中文报告；**保留原始官方断言和报错，不能把未覆盖项说成通过**。
- [ ] 官方专项评分与自研通用分开展示，不冒称 Moonshot 官方认证；不混入身份强证据或原有总分。
- [ ] Mock / fixture 测试官方结果解析，实际端点 E2E 后单独记录兼容性。

**验收**：能看到“通用检查结果”与“官方专项验证结果”并列，知道官方哪些 case 跑了、哪些没跑、每类请求/Token 是否可计量。

## 5. D · P1：集成验收、文档与兼容性

- [ ] 把 `llm-fingerprint-detector`、`proxy-sleuth`、`promptfoo`、`lm-evaluation-harness` 的具体验证版本/安装命令写入 `docs/oss-compatibility.md`，运行至少一次真实 CLI 调用与解析（经用户同意产生费用时才调付费端点）。
- [ ] 强制区分：Adapter 可用、二进制已安装、运行成功、数据可比、已证实检测效果；外部命令失败也能留存无密钥的详细原因。
- [ ] Web → Reference → Supplier Audit → HTML/JSON/ZIP → History → Filter/Delete；覆盖历史升级、输出目录缺失、重复任务、403/429、SSE HTML 错误等。
- [ ] 审核 Kimi/GLM/Qwen/DeepSeek/GPT/Claude/Gemini Model Rule 的官方 URL/字段与当前 API 版本；过期、未证实来源降级标注，不为覆盖率写死错误期待值。
- [ ] 更新用户操作手册、费用说明、可复现示例和 CHANGELOG；UI 展示最终结论、关键证据、风险/待复核、Token/费用及“不足以判断”的原因。
- [ ] Python 3.11/3.12 CI + 本地真实工具验收；**不能以纯 Mock CI 代表 E2E 完成**。

## 6. E · 真实 Kimi/GLM 校准（不能以开发替代）

- [ ] Kimi K3、GLM-5.2 **官方/可信端点**的 Reference 各至少 3～5 次；记录日期、具体版本、Prompt/参数、价格、Tokenizer、运行环境。
- [ ] 受控网关真实标签：官方对自身、已知异模型、同模型不同 reasoning effort、0/10/30/50% 外部配置混路由、同模型不同 Provider（能证实来源时）。
- [ ] 必须保留网关实际命中日志；声明的混路由比例只是目标配置，不能当实测比例。
- [ ] 用 `validation evaluate/calibrate` 记录每类 **TP/TN/FP/FN/ABSTAIN**、覆盖率、Wilson 区间以及明细；按独立 Case 统计，不能把重复测试当独立渠道。
- [ ] 只有数据支持才调整 Quality 阈值/路由参数；在保留数据上回测，列误报/漏报代价。
- [ ] 不展示“智商下降 X%”“真模型概率 99%”“INT4/FP8 识别”，除非有合理、可复现、明确局限的实证定义。

**前置**：使用者提供官方 API Key（只存在自己的环境变量/连接中）和受控网关；没有凭据只能完成 E 的计划，不能勾选“真实校准完成”。

## 7. F · 发布与停止开发门槛

达到下列条件后**不再新增普通 Probe/平台化功能，转入自用与维护**：

- [ ] A：任何 Reference 更新失败不丢原基准；错误、部分完成、不可比状态表达正确。
- [ ] B：分 Probe 的 usage、覆盖率、未知量与费用估算可用；默认不会意外跑重型任务。
- [ ] C：Kimi 官方专用适配完成**明确选择的范围**，或评估有理由明确决定不接并记录原因。
- [ ] D：四个 OSS 适配器在固定版本完成真实环境联调；Web/CLI/报告/历史所有核心路径 E2E 有记录。
- [ ] E：至少 Kimi/GLM 官方 Reference + 真实正负实验记录完整；无法获得的数据明确限制，不伪造“已验收”。
- [ ] 提供版本变更说明，审计报告区分“供应商合规/身份佐证/质量保持/未知”；完成发布前复查敏感数据与费用风险。

## 8. 工作方式与非目标

**小提交顺序建议（实测后更新）**：G0.1 → G0.2 → G0.3 → G0.4 → G0.5 → G1（适度拆分）→ A1 → A2 → A3 → B1 → B2 → B3 → C1 → C2 → D → E → F；每个小任务完成后提交并运行必要的回归测试。不要一次性重构全仓。新功能先写设计和失败边界，再实现及覆盖 Mock；真数据另做分离的实测验收。

**不做**：TTFT/TPOT/ITL/TPS/RPM/TPM/并发压测；企业管理、Redis/PostgreSQL/Worker、Scheduler、告警/通知、模型量化精度推测、大规模 Benchmark 题库自研。

**重新评估触发条件**：官方 API 重大变更、用户真正需要其他 Native Protocol 或真实验收证明现有检测器不足。这些需求出现时才单独立项。
