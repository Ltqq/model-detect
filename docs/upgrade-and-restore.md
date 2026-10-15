# 升级、备份与恢复（单机使用）

适用范围：`model-detect` CLI/Web 单用户，SQLite 历史、`references/` Reference、`model-detect-output/` 原始报告与证据。

## 升级前

1. **先停止 Web 服务及任何运行中的审计/外部 Adapter**，避免正在写入的 SQLite、Reference、JUnit 或 ZIP 不一致。对生产数据不要直接在运行中复制数据库文件。
2. 对整个 `.model-detect/`、`references/`、`model-detect-output/` 目录做离线完整备份，并生成备份清单和 SHA-256 校验。若启动配置自定义过目录，按实际路径处理。
3. 分开存储 API Key/环境变量。不要把 `.env`、原始模型回答、未脱敏官方日志或客户密钥提交到 Git。
4. 固定当前 Git commit/版本和依赖清单，保留可回退的 Python 虚拟环境。
5. 升级依赖之前先运行当前版本本地测试并确认备份可读取。

## 升级

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
model-detect version
model-detect oss-status --json
```

默认不启动外部工具、不下载模型数据、不发起付费 API 请求。Web 默认绑定回环地址 `127.0.0.1:8787`；若使用 Nginx/外部网络访问，必须自行配置认证、TLS、访问控制和日志脱敏，不能裸露在公网。

## 数据与 Reference 行为

- 新建同 ID Reference 默认拒绝覆盖。明确使用 `reference collect --replace-existing` 才会将旧版本保留为隐藏的备份目录。
- Reference Manifest 引用的本地 JSON 会进行 SHA-256 校验；历史旧版未记录哈希时可能显示 `legacy_unverified_artifacts`，**这不是自动删除旧文件的理由**。
- 备份目录要在恢复演练成功后人工清理；不自动覆盖、删除历史可信数据。
- 用户持有的 GLM/Kimi 原始证据和测试密钥需隔离保存，不应随公开报告上传。

## 恢复

1. 停止进程，保留当前受损目录一份供审计。
2. 先恢复数据库、Reference、报告三个目录到一致的备份点。
3. 回退到备份清单中的代码 commit 和虚拟环境。
4. 检查原始 SHA-256、SQLite 历史数量、Reference Manifest 对应签名/基准及报告文件。
5. 使用离线 CLI/Web 历史查看、导出和删除回归检查恢复是否成功；不得为验证恢复自动调用付费模型。
6. 发现中断写入残留 `.reference-stage-*`、`.reference-backup-*` 或 `.*.write.lock` 时，**先核对备份与当前目标的完整性，再人工恢复并清理**。不要无条件自动删除锁或覆盖旧版本。

## 兼容性说明

`pyproject.toml` 要求 Python >=3.11；Moonshot 官方 Kimi Vendor Verifier 的独立运行环境要求 Python >=3.12。本工具和官方验证器应使用隔离的虚拟环境。

数据迁移或实际断电恢复不应在 CI Mock 通过后声称实测验收完毕；最终发布前必须在目标机器进行一次备份恢复演练。
