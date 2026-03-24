# 延迟人工验收清单

本文件记录所有无法转化为机器自动验证、且不影响后续 Phase 开发的验收项。这些项在全部 Phase 完成后，由人类统一验收。

---

## Phase 4 延迟项

### DH-001: /setup 三步引导 UI 体验
- **来源**: roadmap Phase 4 延迟人工验收
- **原因**: 需在手机 Telegram 上实际操作建群、加 Bot、设管理员，涉及 GUI 交互。Bot API 不支持自动创建群组。
- **验收方式**: 人工在 Telegram 中执行 /setup，按照三步引导完成配置，验证每一步的提示文本和按钮是否正确。
- **是否影响后续 Phase**: 否。/setup 的代码逻辑已通过单元测试覆盖（mock Bot API），UI 体验不影响后续 Phase 的开发。

### DH-002: /projects 目录列表显示效果
- **来源**: roadmap Phase 4 延迟人工验收
- **原因**: InlineKeyboard 按钮布局和目录名显示需人眼判断是否美观、可读。
- **验收方式**: 人工在 Telegram 中执行 /projects，检查按钮列表的排列、目录名截断方式、按钮数量是否合理。
- **是否影响后续 Phase**: 否。功能逻辑已通过单元测试覆盖。

---

## Phase 5 延迟项

### DH-003: launchd plist 实际加载并工作
- **来源**: roadmap Phase 5 延迟人工验收
- **原因**: 需要执行 `launchctl load` 系统命令，macOS 可能弹出安全提示需人工确认。
- **验收方式**: 人工执行 `claude-pilot enable`，确认 launchd plist 写入 `~/Library/LaunchAgents/` 并加载成功。执行 `launchctl list | grep claude-pilot` 确认服务已注册。
- **是否影响后续 Phase**: 否。plist 内容生成逻辑已通过单元测试验证（检查 KeepAlive、RunAtLoad、ThrottleInterval=30）。
- **自动化尝试**: 无法自动化。launchctl 需要用户 session 上下文，且 macOS 安全策略可能要求用户确认。

### DH-004: 崩溃通知实际到达手机
- **来源**: roadmap Phase 5 延迟人工验收
- **原因**: 需要真实 Telegram Bot Token 和网络连接，需手动 kill 进程后在手机确认收到通知。
- **验收方式**: 配置真实 Bot Token 后，手动 `kill -9 $(cat .pid)` 终止 Bot 进程，在手机 Telegram 上确认收到崩溃通知（包含 Traceback 摘要）和恢复通知。
- **是否影响后续 Phase**: 否。crash_reporter 的 PID 检查、Traceback 提取、通知发送逻辑已通过单元测试覆盖（mock urllib）。

### DH-005: Bot 崩溃后 30 秒内自动恢复
- **来源**: roadmap Phase 5 延迟人工验收
- **原因**: 需要 launchd 实际运行环境，ThrottleInterval=30 的重启时间需在真实环境验证。
- **验收方式**: 在 launchd 托管状态下 kill Bot，用 `time` 命令记录从 kill 到 Bot 恢复（/health 响应 200）的时间，确认 < 60 秒。
- **是否影响后续 Phase**: 否。

---

## Phase 6 延迟项

### DH-006: install.sh 在全新 macOS 上端到端运行
- **来源**: roadmap Phase 6 延迟人工验收
- **原因**: 需要全新 macOS 环境（无 tmux、无项目依赖），涉及 brew install、网络下载、Telegram API 真实交互。
- **验收方式**: 在全新 macOS 用户账户下执行 `curl -fsSL ... | bash`，按提示输入 Bot Token 和 User ID，确认安装完成无卡住、.env 和 hooks 正确写入。
- **是否影响后续 Phase**: 否（Phase 6 是最后一个 Phase）。

### DH-007: /setup 到群组配置完成全流程
- **来源**: roadmap Phase 6 延迟人工验收
- **原因**: 需要手机操作 Telegram：建群、加 Bot、设管理员。Bot API 无法模拟此流程。
- **验收方式**: 安装完成后在 Telegram 私聊 Bot 执行 /setup，按引导完成三步配置，确认 GROUP_CHAT_ID 持久化到 .state.json。
- **是否影响后续 Phase**: 否。

### DH-008: 消息延迟 < 3 秒
- **来源**: roadmap Phase 6 延迟人工验收 + requirement.md 验收标准
- **原因**: 需要真实 Telegram 环境，Claude 输出到 TG 收到的端到端延迟测量需真实网络。
- **验收方式**: 在真实环境中触发 Claude 输出，用手机截图时间戳对比，确认 < 3 秒。
- **自动化尝试**: 理论上可通过 Bot 记录发送时间戳实现，但需真实 Telegram 环境。已在自动测试中通过 mock 验证 watcher 的 0.5s 轮询间隔 + 1.5s flush 间隔确保理论延迟 < 3s。
- **是否影响后续 Phase**: 否。

### DH-009: 并发安全（同话题连发 5 条消息）
- **来源**: roadmap Phase 6 延迟人工验收 + requirement.md 验收标准
- **原因**: 需要真实 Telegram 环境和真实 Claude 会话，验证无孤儿进程。
- **验收方式**: 在 TG 话题中快速连发 5 条消息，检查 `tmux list-windows` 无多余窗口，`ps aux | grep claude` 无孤儿进程。
- **自动化尝试**: per-topic asyncio.Lock 互斥已在单元测试中验证。端到端并发安全需真实环境。
- **是否影响后续 Phase**: 否。

### DH-010: TUI 权限审批端到端
- **来源**: roadmap Phase 6 延迟人工验收 + requirement.md 验收标准
- **原因**: 需要触发 Claude Code 修改 .claude/ 文件的真实场景，在手机上确认审批流程。
- **验收方式**: 在 TG 发起一个会引发 Claude 修改 .claude/ 配置的任务，确认 TG 收到 TUI 层审批按钮，点击后 Claude 继续执行。
- **是否影响后续 Phase**: 否。TUI 层审批逻辑（capture-pane 检测 + send-keys 响应）已通过 mock 测试覆盖。

### DH-011: 完整对话流显示效果
- **来源**: roadmap Phase 6 延迟人工验收 + requirement.md 验收标准
- **原因**: TG 话题中 user + assistant 消息的格式和可读性需人眼判断。
- **验收方式**: 在终端启动 Claude 会话，在 TG 话题中观察完整对话流，确认 user 消息和 assistant 消息都有显示、格式清晰可读。
- **是否影响后续 Phase**: 否。JSONL 解析和推送逻辑已通过单元测试覆盖。

### DH-012: 历史回显显示效果
- **来源**: roadmap Phase 6 延迟人工验收
- **原因**: /resume 后的摘要内容需人眼判断可读性和完整性。
- **验收方式**: 在 TG 中对已有会话执行 /resume，确认历史对话摘要显示完整、可读。
- **是否影响后续 Phase**: 否。

---

## 系统特权操作处理

以下操作在开发/测试过程中需要系统特权，已规避或集中处理：

| 操作 | 规避方案 |
|------|---------|
| pip install 依赖 | 使用项目本地 venv（install.sh 中处理），不需要 sudo |
| brew install tmux | install.sh 中自动执行，brew 不需要 sudo |
| launchd plist 注册 | 写入用户级 `~/Library/LaunchAgents/`，不需要 sudo |
| 安装 CLI 到 PATH | 使用 symlink 到 `~/.local/bin/` 或项目内 PATH，不需要 sudo |
| crash_reporter launchd plist | 同上，写入用户级目录 |

**结论**：本项目的所有操作均在用户级别完成，不需要 sudo。开发过程中无需系统特权操作。
