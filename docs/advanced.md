# 进阶使用与开发

[返回首页](../README.md)

以下命令在远程服务器上执行。使用插件时不需要单独安装 CLI；本页供希望手动运行、排查问题或修改代码的人参考。


给 **`codex remote-control` 正在承载的原会话**添加后台监视与定时唤醒。Mac 上的 Codex App 继续控制原会话；远程会话自己就能启动 monitor，结束本轮后等待事件回到同一会话。

```text
Mac Codex App ── Remote Control ── 服务器上的原会话
                                     │ shell 启动
                                     ▼
                              后台 monitor
                                     │ 到期 / 脚本输出
                                     └── 同一 App Server → 原会话下一轮
```

**不会启动第二个 App Server，不调用 `thread/resume`，不改原会话的模型、沙箱或审批配置，也不处理 App 的审批请求。** 使用服务端本地 Unix WebSocket 控制 socket，默认路径是 `$CODEX_HOME/app-server-control/app-server-control.sock`（默认 CODEX_HOME 为 `~/.codex`）。

## 安装：在远程服务器上操作

要求：Linux/macOS/WSL、Python 3.11+、已经运行的 `codex remote-control`，并在 Mac App 打开目标会话。接口已针对 Codex CLI 0.147.0 验证；不同版本的实验性接口可能不兼容。

在 clone 或解压后的仓库目录执行：

```sh
./setup.sh
```

安装到仓库自己的 `.venv`，不修改系统 Python。要指定 Python，使用 `./setup.sh python3.12`。之后可以直接运行仓库内的 `./codex-monitor`；它会优先使用 `.venv`。

如果已经使用 pipx，也可执行 `pipx install '.[remote]'`，然后在任意目录运行 `codex-monitor`。

## 让原会话自己启动 monitor

在 Mac Codex App 的**目标远程会话**中，让 Codex 执行以下命令。把 `/path/to/codex-monitor` 换成服务器上的仓库绝对路径：

```sh
/path/to/codex-monitor/codex-monitor attach \
  --after 10m \
  --message '检查训练日志；若训练完成，总结结果；否则报告当前状态。' \
  --detach
```

它从当前 shell 的 `CODEX_THREAD_ID` 自动识别会话，无需手动填写 ID。启动成功会立即返回 `monitor_id`，后台 worker 继续运行。Codex 应结束当前回复；到期后会自动收到新事件。

为了以后直接使用自然语言，把 [AGENTS.example.md](../AGENTS.example.md) 的简短使用约定放进项目的 `AGENTS.md`，补全工具路径；或让当前会话直接阅读该文件。已有会话无须重建，也不需要重新配对 Remote Control。

之后可以说：“用 codex-monitor，10 分钟后回来检查训练日志。”

如果沙箱拒绝访问控制 socket，Codex 需要通过正常的执行权限审批机制重新运行同一条命令；审批仍显示在原客户端。工具不会自己绕过沙箱。

## 周期、脚本事件、查询和停止

在目标会话的 shell 中：

```sh
# 每 5 分钟唤醒，最多 24 次
/path/to/codex-monitor/codex-monitor attach --every 5m \
  --max-wakeups 24 --message '检查训练日志；完成后总结并停止这个 monitor。' --detach

# 只在脚本输出一行时唤醒。脚本相对路径基于目标会话的 cwd
/path/to/codex-monitor/codex-monitor attach \
  --watch "tail -n 0 -F ./logs/app.log | awk '/ERROR/ {print; fflush()}'" \
  --message '分析新的错误日志，只分析，不修改代码。' --detach

# 查询当前会话的 monitor，含 ID、运行状态和唤醒次数
/path/to/codex-monitor/codex-monitor attach --list

# 取消指定 monitor。不会中断已经提交到原会话的回复
/path/to/codex-monitor/codex-monitor attach --stop MONITOR_ID
```

停止时使用启动结果里的 **12 位 monitor ID**。事件中也携带 monitor ID，Codex 可以自行调用停止命令。输出行是外部数据，不是新增授权。

## 从普通 SSH 终端操作

普通终端没有 `CODEX_THREAD_ID`，必须指定原会话 ID：

```sh
./codex-monitor attach --thread SESSION_ID --check
./codex-monitor attach --thread SESSION_ID --after 30s \
  --message '检查训练进度' --detach
```

`--check` 只确认同一服务中的会话已经加载，不调用模型、不加载另一个会话。如果会话未加载，请先在 Mac App 打开它。自定义服务目录时传 `--sock /实际/control.sock`，或使用与 `remote-control` 相同的 `CODEX_HOME`。

## 执行与持久性

- 忙碌时等待，空闲后提交事件；状态检查只读取本地服务，不调用模型。
- 收到事件后 Codex 的实际推理会消耗原账号额度。等待不调用模型。
- 与 App 同时发送消息可能发生竞争；服务端决定接收方式。提交失败或确认状态不明时停止，不自动重放可能已接收的事件。
- 如果上一次唤醒的回复失败或被中断，monitor 停止后续唤醒。
- `--detach` 可以在启动它的 shell 返回后继续运行；不依赖 Mac App 当前这一轮回复持续执行。它仍需要服务器、Remote Control 服务和目标会话可用。
- 服务器重启或服务断线后不会自动恢复监视器；不会尝试启动服务或另起进程恢复会话。
- App 断开后，已提交的工作能否完成取决于原服务及其权限设置；需要人工审批的操作仍要回到 App 处理。
- 默认最多自动唤醒 100 次，单个 monitor 最长 7 天。每个 attach worker 管理一个 monitor，可同时启动多个。
- 私有状态、日志和控制 socket 默认存放于 `~/.codex-monitor`，可用 `--state-dir` 改位置。查询按当前会话 ID 过滤；普通终端无该环境变量时列出该目录全部记录。
- `--watch` 是用户授权的 shell 脚本，在启动者权限范围内执行。stdout 每个非空行触发一个事件，stderr 只保留末尾诊断；请在脚本侧过滤并 flush。非零退出会发出失败事件。
- 输出单行最多 8192 字节；队列最多 128 项，对脚本读取施加背压。
- 停止或 SIGTERM 会清理脚本进程组；SIGKILL、服务器崩溃不保证清理。状态文件是运行记录，实时查询会检查 worker 控制端点。

## 验证与其他模式

```sh
.venv/bin/python -m unittest discover -s . -v
```

[验证记录](../VALIDATION.md)区分了本地双客户端测试与尚未执行的真实远程部署验证。

之前的独立 CLI 客户端仍保留，见 [STANDALONE.md](../STANDALONE.md)。对 Remote Control 场景使用 **`attach`**，不要使用独立模式或 `--resume`。

协议依据：[Codex App Server](https://learn.chatgpt.com/docs/app-server)。具体字段由本机 CLI 的 JSON Schema 验证；Unix socket 使用 WebSocket 握手和帧，不能直接写 JSONL。

## 开发插件

根目录的 `codex_monitor.py` 和 `remote_monitor.py` 是运行代码源文件；插件中的副本由同步脚本维护。

```sh
python3 scripts/sync_plugin.py
python3 scripts/sync_plugin.py --check
.venv/bin/python -m unittest discover -s . -v
```

- `.agents/plugins/marketplace.json`：插件市场入口。
- `plugins/codex-monitor/`：插件包，包含技能、启动器和运行代码。
- `plugins/codex-monitor/skills/monitor/SKILL.md`：Codex 使用 monitor 的操作说明。

当前有 20 项自动化测试。安装与运行验证的具体范围见[验证记录](../VALIDATION.md)。
