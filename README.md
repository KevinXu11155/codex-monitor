# Codex Monitor

让 Codex **过一会儿回到当前会话，继续做事**。

适用于这样的用法：服务器运行 `codex remote-control`，你在 Mac 的 Codex App 中控制远程会话。安装后，直接在这个会话里说：

> 用 $monitor，每 5 分钟检查训练进度，训练完成后总结结果并停止监控。

Codex 会在服务器上启动后台监视器，定时回到**同一个会话**检查。也支持一次性提醒，以及日志出现指定内容时唤醒。

## 安装

在**运行 `codex remote-control` 的服务器上**执行：

```sh
codex plugin marketplace add KevinXu11155/codex-monitor
codex plugin add codex-monitor@personal
```

需要 Python 3.11+ 和支持插件的 Codex CLI。安装命令及运行接口已在 **Codex CLI 0.147.0** 验证，其他版本可能需要适配。支持 Linux、macOS 和 WSL。

仓库为私有时，安装者需要仓库访问权限。如果服务器已配置 GitHub SSH，可以把第一条命令换成：

```sh
codex plugin marketplace add git@github.com:KevinXu11155/codex-monitor.git
```

首次使用会自动准备 Python 依赖，需要联网；无需额外 API Key。

## 怎么用

在 Mac App 打开的**目标远程会话**中，用自然语言调用 `$monitor`：

| 想做什么 | 发给 Codex 的话 |
| --- | --- |
| 稍后检查一次 | 用 $monitor，10 分钟后检查训练日志，告诉我结果。 |
| 持续检查 | 用 $monitor，每 5 分钟检查训练进度，完成后总结并停止。 |
| 监控日志 | 用 $monitor，监控 ./logs/app.log，出现新的 ERROR 时分析原因。 |
| 查看监控 | 用 $monitor，列出当前会话的监视器。 |
| 停止监控 | 用 $monitor，停止刚才的训练监控。 |

启动成功后，Codex 会返回一个 monitor ID，然后结束当前回复。后台监视器继续等待，到期或收到事件后发起新一轮；如果会话正在忙，会等它空闲。

周期任务最好说明**什么时候停止**。默认每个监视器最多唤醒 100 次，最长运行 7 天。

## 已有会话能直接用吗？

可以。监视器就是由原会话启动，并唤醒原会话。

不过，已经打开的会话可能暂时看不到刚安装的 `$monitor` 技能。遇到这种情况，在服务器执行：

```sh
codex plugin add codex-monitor@personal --json
```

找到输出中的 `installedPath`，把下面这句话发给原会话，将路径换成实际值：

```text
请读取 /实际的 installedPath/skills/monitor/SKILL.md，按里面的说明，
在当前会话启动一个监视器：每 5 分钟检查训练进度，完成后总结并停止。
```

这样可以继续使用当前会话，无须重新配对 Remote Control。

## 使用前知道这些就够了

- **安装在服务器上。** 只装在控制端 Mac，无法监控服务器上的会话。
- **服务器和 Remote Control 服务需要保持运行。** 服务断线或重启后，监视器不会自动恢复，需要重新创建。
- **等待不消耗模型额度，唤醒后的工作正常消耗额度。** 需要审批的操作仍在 App 中处理。
- **上一轮监控触发的回复失败或被中断时，后续唤醒会停止。** 可以让 Codex 查看监视器状态，再决定是否重建。

## 其他安装方式与文档

也可以先 clone，再安装插件：

```sh
git clone git@github.com:KevinXu11155/codex-monitor.git
cd codex-monitor
codex plugin marketplace add "$PWD"
codex plugin add codex-monitor@personal
```

插件安装不需要运行 `setup.sh`。此仓库的插件市场名是 `personal`；如果你已经有同名市场，请先在 clone 的 `.agents/plugins/marketplace.json` 中换一个名称，再按新名称安装 `codex-monitor@新名称`。

- [进阶使用与开发](docs/advanced.md)：手动 CLI、日志事件、状态排查和运行原理。
- [验证记录](VALIDATION.md)：已测试的范围与限制。
- [独立 CLI 模式](STANDALONE.md)：另一个使用方式；Remote Control 用户请使用本文的插件或 `attach`。
