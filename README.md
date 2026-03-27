# Claude Pilot

用 Telegram 远程控制你的 Claude Code —— 在手机上看对话、发指令、审批权限。

## 安装

确保已装好 [Claude Code](https://claude.ai/claude-code)、tmux 和 Python 3.10+，然后一行搞定：

```bash
curl -fsSL https://raw.githubusercontent.com/MK080324/Claude-Pilot-V2/main/src/install.sh | bash
```

脚本会引导你输入 Telegram Bot Token（从 [@BotFather](https://t.me/BotFather) 获取），装完即用。

安装过程会自动备份你原有的 Claude Code 设置文件（`~/.claude/settings.json`），备份存储在 `~/.claude-pilot/settings.json.backup`。

## 使用

在 Telegram 群组中对 Bot 发 `/setup`，按提示完成配置。之后每次 Claude Code 会话都会自动推送到群组话题中。

常用命令：`/status` 查看状态、`/projects` 启动新会话、`/bypass` 跳过审批、`/quit` 结束会话。

## 管理

```bash
claude-pilot status    # 查看运行状态
claude-pilot stop      # 停止
claude-pilot start     # 启动
claude-pilot enable    # 开机自启（launchd）
claude-pilot logs      # 查看日志
claude-pilot uninstall # 完全卸载（恢复 Claude Code 设置）
```

## License

MIT
