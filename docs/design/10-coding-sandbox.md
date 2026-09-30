# V1.1-4 Coding Sandbox 设计

## 目标

把 Coding Reasoning（代码理解）升级为真实的：

Prompt -> Model Generated Code -> Sandbox -> Unit Tests -> Score

首批语言：Python、Go。Standard 每种 2 题，Deep 每种 5 题。

## 安全边界

模型生成代码视为不可信代码。禁止任何宿主机直接执行。

只有显式开启 coding_sandbox_enabled 后才运行。Docker 不可用时返回 SKIPPED，绝不回退到宿主 Python / Go。

Docker 必须启用：network none、read-only rootfs、cap-drop ALL、no-new-privileges、非 root 用户、CPU/内存/PID/超时限制、临时 tmpfs、只读 workspace、输出大小限制。

禁止 Docker socket、宿主项目目录、用户 home、privileged、host network、host PID/IPC。

## 镜像

- Python: python:3.12-alpine
- Go: golang:1.24-alpine

可通过 MODEL_DETECT_PYTHON_IMAGE / MODEL_DETECT_GO_IMAGE 替换。

## Workspace

每个 task 使用独立临时目录，仅把 solution + test 文件只读挂载到 /workspace，执行后删除。

## 输出限制

stdout/stderr 写宿主临时文件并轮询大小；超限立即终止容器，只保留截断输出，避免恶意无限输出吃宿主内存。

## 代码提取

优先提取对应语言 Markdown fenced code，其次任意 fenced code，否则直接使用完整响应。不自动修复代码。

## 判定

- Docker exit 0: pass
- unit test failure: fail
- timeout: fail
- output limit: fail
- sandbox unavailable: skipped

聚合 Probe：capability.coding_execute，以及 python/go 两个子维度。

## 安全说明

Docker 隔离不是绝对安全边界。正式多人生产环境后续应把 Coding Worker 放独立主机，并考虑 rootless Docker / AppArmor / SELinux / microVM。