# 人工测试清单（交付前验收）

按顺序执行，每步在"结果"列标记 PASS / FAIL / SKIP。

---

## 前置条件

- [ ] 有一个可用的 Telegram Bot Token（BotFather 创建）
- [ ] BotFather 中 Group Privacy 已关闭、Allow Groups 已开启
- [ ] 本机已安装 tmux、python3、claude CLI
- [ ] 准备一个测试用 Telegram 群组（开启话题功能）

---

## 第一部分：必须通过（阻塞交付）

### 1. install.sh 全新环境安装

> 目标：验证一键安装脚本从零到可用的完整流程

| # | 操作 | 预期结果 | 结果 |
|---|------|---------|------|
| 1.1 | 如果已安装过，先清理：`rm -rf ~/.claude-pilot` | 清理完成 | |
| 1.2 | 执行 `bash src/install.sh`（或按 README 的 curl 方式） | 脚本开始运行，提示输入 BOT_TOKEN | |
| 1.3 | 按提示输入 BOT_TOKEN | 脚本继续，提示输入 ALLOWED_USERS | |
| 1.4 | 输入你的 Telegram 用户 ID | 脚本继续安装 | |
| 1.5 | 安装完成 | 输出安装成功信息，无报错 | |
| 1.6 | 运行 `claude-pilot status` | 命令可用，显示运行状态 | |
| 1.7 | 检查 `cat ~/.claude-pilot/.env` | 包含 BOT_TOKEN、ALLOWED_USERS、BOT_PORT | |
| 1.8 | 检查 `cat ~/.claude/settings.json` | hooks 部分包含 session_start/stop/notification/permission | |

测试不通过。问题：hook部分不包含permission，而且似乎settings直接默认设置成了跳过权限模式。


| 1.9 | 如有原来的 settings.json，验证原有配置未被覆盖 | 原有 hooks 条目仍在 | |

**失败时排查：** 看 install.sh 输出的错误信息，检查 Python 依赖是否安装成功。

---

### 2. /setup 全流程

> 目标：验证 Bot 启动到群组配置的核心链路

| # | 操作 | 预期结果 | 结果 |
|---|------|---------|------|
| 2.1 | `claude-pilot start` | Bot 启动成功 | |
| 2.2 | `claude-pilot status` | 显示"运行中 (PID: xxx)" | |
| 2.3 | Telegram 私聊 Bot，发 `/start` | 收到三步配置引导消息 | |
| 2.4 | 创建一个 Telegram 群组，开启话题功能 | 群组创建成功 | |
| 2.5 | 将 Bot 加入群组并设为管理员 | Bot 在群组中可见 | |
| 2.6 | 群组中发 `/setup` | 收到"群组已配置完成"+ 引导信息 | |
| 2.7 | 群组中发 `/status` | 收到运行时长、活跃会话等信息 | |
| 2.8 | 群组中发 `/setdir <你的项目父目录>` | 收到"项目目录已设置为: ..." | |

**失败时排查：** `claude-pilot logs` 查看 Bot 日志。

---

阶段二测试通过

### 3. 消息注入 + 对话流推送

> 目标：验证核心产品功能——通过 Telegram 与 Claude Code 双向通信

| # | 操作 | 预期结果 | 结果 |
|---|------|---------|------|
| 3.1 | 群组中发 `/projects` | 收到项目列表按钮 | |
| 3.2 | 点击一个项目按钮 | 群组中自动创建新话题，提示"Claude 会话已启动" | |

创建速度极慢，要点好几下才有反应

| 3.3 | 在服务器终端验证：`tmux list-windows -t cp-sessions` | 看到对应的 tmux window | |
| 3.4 | 在新话题中发一条消息，如"请列出当前目录的文件" | 消息被注入到 Claude Code（tmux 窗口中出现该文本） |
| 3.5 | 等待 Claude 响应 | Telegram 话题中收到 Claude 的回复（对话流推送） | |
| 3.6 | 再发一条消息 | 第二条消息也正常注入并收到回复 | |
| 3.7 | 在话题中发 `/info` | 收到会话详情（pane_id、cwd、transcript_path） | |

测试不通过，问题：有tmux windows，有开始Claude进程，tg输入的消息正确地出现在Claude窗口中，Claude正确地回复了，第二条消息也正常回复了，输入/info也收到了会话详情。但是tg中没有收到Claude的回复

**失败时排查：**
- 3.2 失败：检查 `claude-pilot logs`，确认 /session_start hook 是否触发
- 3.4 失败：检查 tmux 窗口状态 `tmux capture-pane -t <pane_id> -p`
- 3.5 失败：检查 JSONL 文件是否在增长 `ls -la <transcript_path>`

---

### 4. TUI 权限审批端到端

> 目标：验证两层审批通道（Hook 层 + TUI 层）

| # | 操作 | 预期结果 | 结果 |
|---|------|---------|------|
| **Hook 层审批** | | | |
| 4.1 | 在 Telegram 话题中发一条会触发权限请求的消息（如"请修改 xxx 文件"） | Claude Code 触发权限请求 | |
| 4.2 | 观察 Telegram | 收到权限审批消息，附带"允许"/"拒绝"按钮 | |
| 4.3 | 点击"允许" | Claude 继续执行操作 | |
| 4.4 | 再触发一次权限请求，这次点"拒绝" | Claude 停止该操作 | |
| **TUI 层审批** | | | |
| 4.5 | 等待 Claude Code 弹出 TUI 权限弹窗（如修改 .claude/ 文件） | watcher 检测到 TUI 弹窗 | |
| 4.6 | 观察 Telegram | 收到 TUI 审批按钮 | |
| 4.7 | 点击允许/拒绝 | tmux 中对应按键被发送 | |
| **旁路模式** | | | |
| 4.8 | 发 `/bypass` | 收到"权限审批已关闭"提示 | |
| 4.9 | 触发权限请求 | 自动通过，不发审批按钮 | |
| 4.10 | 再发 `/bypass` | 收到"权限审批已开启"提示 | |

**失败时排查：**
- 4.2 失败：检查 hooks/permission.py 是否正确 POST 到 Bot，`curl http://127.0.0.1:8266/health`
- 4.6 失败：检查 watcher 是否在运行，检查 detect_tui_state 返回值

**注意：** TUI 层审批（4.5-4.7）较难触发，如果 Claude Code 没有弹出 TUI 弹窗，可标记 SKIP 并备注原因。

---

## 第二部分：建议通过（不阻塞交付）

### 5. 崩溃通知 + 自动恢复

> 目标：验证 launchd 托管和 crash_reporter 工作正常

| # | 操作 | 预期结果 | 结果 |
|---|------|---------|------|
| 5.1 | `claude-pilot enable` | launchd plist 加载成功 | |
| 5.2 | `launchctl list \| grep claude-pilot` | 看到 claude-pilot 条目 | |
| 5.3 | 找到 Bot 的 PID：`claude-pilot status` | 显示 PID | |
| 5.4 | 强杀 Bot：`kill -9 <PID>` | 进程被杀 | |
| 5.5 | 等待 30 秒 | launchd 自动重启 Bot | |
| 5.6 | `claude-pilot status` | 显示"运行中"，PID 已变化 | |
| 5.7 | 检查 Telegram | 收到崩溃通知消息（来自 crash_reporter） | |
| 5.8 | 测试完成后：`claude-pilot disable` | launchd plist 卸载成功 | |

**失败时排查：**
- 5.5 失败：检查 plist 文件 `cat ~/Library/LaunchAgents/com.claude-pilot.plist`，确认 KeepAlive=true
- 5.7 失败：检查 crash_reporter 是否在运行，检查 .env 中 NOTIFY_CHAT_ID 是否配置

---

### 6. 消息延迟实测

> 目标：验证 Claude 输出到 Telegram 收到的延迟 < 3 秒

| # | 操作 | 预期结果 | 结果 |
|---|------|---------|------|
| 6.1 | 在 Telegram 话题中发一条简单问题 | Claude 开始响应 | |
| 6.2 | 在 tmux 窗口中观察 Claude 输出出现的时刻 | 记录时间 T1 | |
| 6.3 | 在 Telegram 中观察消息出现的时刻 | 记录时间 T2 | |
| 6.4 | T2 - T1 < 3 秒 | 延迟在可接受范围内 | |

**注意：** watcher 的轮询间隔是 0.5s，消息合并间隔是 1.5s，所以理论最大延迟约 2s + 网络延迟。

---

### 7. 并发安全

> 目标：验证同话题连发多条消息不会导致异常

| # | 操作 | 预期结果 | 结果 |
|---|------|---------|------|
| 7.1 | 在同一话题中快速连发 5 条消息（间隔 < 1 秒） | 无报错 | |
| 7.2 | 观察 tmux 窗口 | 5 条消息按序注入（可能有合并） | |
| 7.3 | 观察 Telegram | 无重复消息、无错误提示 | |
| 7.4 | 检查 `claude-pilot logs` | 无 traceback 或异常日志 | |

---

## 会话清理测试

> 附带验证——在上述测试过程中顺便检查

| # | 操作 | 预期结果 | 结果 |
|---|------|---------|------|
| C.1 | 在话题中发 `/interrupt` | 收到"已发送中断信号" | |
| C.2 | 在话题中发 `/quit` | 收到会话结束提示，tmux window 被关闭 | |
| C.3 | 在话题中再发消息 | 收到"会话已结束"提示 | |
| C.4 | 发 `/delete` | 收到二次确认按钮 | |
| C.5 | 点击"确认删除" | 会话数据被清理 | |

---

## 测试结果汇总

| 部分 | 总项数 | PASS | FAIL | SKIP | 阻塞交付？ |
|------|--------|------|------|------|-----------|
| 1. install.sh | 9 | | | | 是 |
| 2. /setup 全流程 | 8 | | | | 是 |
| 3. 消息注入+推送 | 7 | | | | 是 |
| 4. 权限审批 | 10 | | | | 是 |
| 5. 崩溃恢复 | 8 | | | | 否 |
| 6. 延迟实测 | 4 | | | | 否 |
| 7. 并发安全 | 4 | | | | 否 |
| C. 会话清理 | 5 | | | | 否 |
| **合计** | **55** | | | | |

**交付判定：** 第一部分（1-4）全部 PASS 即可交付。第二部分有 FAIL 记录在案，不阻塞。
