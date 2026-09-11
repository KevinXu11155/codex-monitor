# Codex Monitor CLI

让 Codex 启动后台监视器，在定时器到期或脚本输出一行时，自动在**同一会话**继续执行。等待期间不调用模型，可以照常输入消息。

这是基于 `codex app-server` 的轻量 CLI 客户端，不是原生 Codex TUI 的补丁，也不会向另一个终端模拟输入。使用它时，以 `codex-monitor` 替代 `codex` 启动会话。

## 启动

要求：macOS / Linux / WSL、Python 3.11+、已安装并登录的 Codex CLI。已针对本机 Codex CLI **0.147.0** 生成的协议验证；动态工具接口是实验性 API，旧版本可能不兼容。

在本文件所在目录运行：

```sh
./codex-monitor --check
./codex-monitor --cwd /你的项目绝对路径
```

零运行时依赖，不需要额外 API Key，使用现有 Codex 登录及默认模型配置。默认代码执行沙箱为 `workspace-write`，审批交给用户；可通过 `--sandbox read-only` 改成只读，通过 `--model` 指定模型。

也可安装为命令：

```sh
pipx install /本工具所在绝对路径
codex-monitor --cwd /你的项目绝对路径
```

不想使用 pipx，可在自己的 Python 虚拟环境中执行 `python -m pip install /本工具所在绝对路径`。

## 自然语言使用

进入 CLI 后直接说：

```text
30 秒后提醒我检查训练日志。
每 5 分钟检查 ./logs/train.log，完成时总结结果并停止 monitor。
监视 ./logs/app.log，只在出现 ERROR 时唤醒你分析；不要自动修改代码。
```

Codex 会调用三个动态工具：

- `monitor_start`：创建 timer 或 command monitor，立即返回 ID。
- `monitor_list`：查看状态、事件数、下次计时器触发时间。
- `monitor_stop`：停止 monitor，清理脚本进程组，并丢弃尚未发送的事件。

模型创建 shell monitor 时，会显示完整命令和工作目录，需要在终端输入 `/approve ID` 才运行。这是因为监视脚本使用本机用户权限，**不在 Codex 的执行沙箱内**。普通 Codex 命令及文件修改审批也会显示在这里。

## 手动控制

```text
/after 30s 检查训练日志并告诉我是否完成
/every 5m 检查当前项目测试结果，完成后停止监视
/watch 应用错误，仅分析原因 | tail -n 0 -F ./logs/app.log | awk '/ERROR/ {print; fflush()}'
/monitors
/stop 监视器ID
/interrupt
/quit
```

`/watch` 后面的命令是你直接提交执行的 shell 命令，会立即启动，不会重复询问确认。它的名称同时是交给 Codex 的监视目标，建议写清楚要做什么。

模型要求审批时：`/approve ID` 或 `/deny ID`。模型提问时：`/answer ID {"问题ID":"答案"}`。`/help` 显示完整命令。

**stdout 的每个非空行都是一个事件**，包括最后没有换行的剩余文本。脚本应只输出有意义的变化；不要直接输送高频完整日志。Python 脚本使用 `python3 -u` 或 `print(..., flush=True)`。stderr 只保存最后一行诊断，不逐行唤醒；非零退出会产生一个失败事件。

## 会话与调度语义

- 启动时打印会话 ID。使用 `codex-monitor --resume ID` 恢复对话历史。
- 本工具创建的会话会保存动态工具定义。原生 Codex 创建的旧会话可能没有这些工具，但手动 `/after`、`/every`、`/watch` 仍可使用。
- 不要同时从两个客户端操作同一个会话；退出原客户端后再恢复。
- 模型忙碌时，用户消息与 monitor 事件按到达顺序排队；只在上一轮结束后启动下一轮，不中断现有回复。
- 计时器采用相对间隔，不是 cron；系统休眠时不会执行，也不负责唤醒电脑。
- 监视器只属于本次客户端进程。退出、Ctrl+C、SIGTERM 会清理后台进程。恢复历史不会恢复监视器。强制 SIGKILL/系统崩溃不保证子进程清理，需要自行检查残留进程。
- 每个 monitor 最长存活 7 天，同时最多 32 个，本次客户端最多创建 256 个。
- 默认最多自动唤醒 100 轮，然后停止所有监视器，保留手动聊天。可通过 `--max-wakeups 500` 调整。
- 队列最多 128 个待处理条目，对脚本读取施加背压；单条输出最多保留 8192 字节并标记截断。
- 自动唤醒后的模型推理会消耗现有账号额度；后台等待本身不会调用模型。
- 模型执行失败时停止监视器，避免持续触发相同错误；解决问题后可手动重新创建。
- 发送失败不会自动重放消息，避免在无法确定服务器是否已接收时重复执行。
- 当前是文本交互 CLI，没有原生 TUI 的完整编辑器、图片输入、所有审批类型及交互体验；未知的服务器请求会明确拒绝。

## 验证

```sh
python3 -m unittest discover -s . -v
./codex-monitor --check
```

测试覆盖计时器、取消、脚本流式输出、非零退出、子进程清理、长行截断、同会话串行调度、取消待处理事件以及模型脚本审批。

实现使用官方 [App Server 接口](https://learn.chatgpt.com/docs/app-server)的动态工具、`thread/start`、`thread/resume` 和 `turn/start`。具体字段以本机 CLI 生成的 JSON Schema 为依据。

## 本机兼容性记录

当前机器的 CLI 0.147.0 启动接口正常，但服务器拒绝其默认配置中的 `gpt-6-astra`，提示该模型需要更新版 CLI。可以更新 CLI，或启动时显式选择 CLI 支持的模型，例如：

```sh
./codex-monitor --model gpt-5.6-sol --cwd /你的项目绝对路径
```

这个参数只影响本次启动，不修改你的全局默认模型。
