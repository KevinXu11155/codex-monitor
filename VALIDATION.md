# 验证记录：0.3.0

- 本地平台：macOS，Python 3.12，Codex CLI 0.147.0，WebSocket 库 17.1。
- 20 项自动化测试通过，覆盖旧版独立客户端和新增 attach 模式。
- 双客户端真实接口验证：连接同一个临时 App Server；副客户端不调用 resume，直接向已加载会话提交 turn/start；主客户端收到两轮完成事件及命令审批，副客户端没有接管审批。
- 真实模型自启动验证：gpt-5.6-sol 在原会话 shell 中启动 attach --detach；自动读取 CODEX_THREAD_ID；沙箱首次阻止 socket 连接，主客户端批准正常权限请求后成功；同一会话先回复 READY，再被定时器唤醒回复 WOKE。
- 后台生命周期验证：detach 创建成功、通过私有控制 socket 查询状态、停止并清理 worker；原 App Server 与原会话仍可读且空闲，没有模型调用。
- 未连接用户的实际远程服务器，未在真实 Mac App/Remote Control 中实测 UI 显示；验证使用本地两个客户端模拟相同服务的主/副连接。
- 原生 CLI 会话的 MCP 动态注入、远程服务重启后的自动恢复，不在本版本范围内。

自启动测试摘要：

```json
{
  "passed": true,
  "turns": [
    "completed",
    "completed"
  ],
  "auto_session_id": true,
  "detached_start": true,
  "primary_approvals": 1,
  "completed_monitors": 1
}
```

## 插件分发验证

- plugin-creator 的插件格式校验通过；skill-creator 的技能校验通过。
- 独立测试 CODEX_HOME 中，本地 marketplace add 和 plugin add 成功。
- 插件安装缓存中的运行程序可执行，首次使用的隔离 Python 环境准备成功。
- 从私有 GitHub 仓库通过 SSH 实际执行 marketplace add，随后安装 codex-monitor@personal 成功，版本为 0.3.0。
- 没有修改用户当前 App 的插件配置，也没有部署到用户的远程服务器。
