# Phase 5 接口定义

## crash_reporter.py

### 函数: _check_pid_alive
- 签名: `_check_pid_alive(pid: int) -> bool`
- 行为: os.kill(pid, 0) 成功返回 True，OSError 返回 False

### 函数: _extract_traceback
- 签名: `_extract_traceback(log_path: str) -> str`
- 行为: 读取 log 文件最后 50 行，提取最近的 Traceback 块，返回摘要

### 函数: _send_telegram_message
- 签名: `_send_telegram_message(token: str, chat_id: int, text: str) -> None`
- 行为: urllib POST https://api.telegram.org/bot{token}/sendMessage

### 函数: main
- 签名: `main() -> None`
- 行为: 读取 .env/.pid，每 10s 检查 PID 存活，崩溃时提取 traceback 并发通知，恢复后发恢复通知
- 重启计数: 连续 5 次以上发警告

### 零外部依赖
- 仅使用标准库: os, sys, json, time, urllib, signal, datetime

## claude-pilot CLI

### 子命令: start
- 行为: tmux new-session 或 send-keys 启动 bot.py

### 子命令: stop
- 行为: 读取 .pid，os.kill(pid, signal.SIGTERM)

### 子命令: status
- 行为: 读取 .pid，检查存活，输出"运行中"或"未运行"

### 子命令: enable
- 行为: 生成 launchd plist (~/Library/LaunchAgents/com.claude-pilot.plist)
- plist 内容: Label, ProgramArguments, KeepAlive=true, RunAtLoad=true, ThrottleInterval=30, StandardOutPath, StandardErrorPath

### 子命令: disable
- 行为: launchctl unload + 删除 plist

### 子命令: logs
- 行为: os.execvp("tail", ["tail", "-f", log_path])
