# 技术调研报告

## 1. 项目技术概述

Claude Pilot v2 是一个 Telegram Bot，用于远程控制和监控 Claude Code CLI 会话。核心技术能力需求包括：

- **Telegram Bot 交互**：群组话题管理、消息收发、InlineKeyboard 权限审批
- **tmux 程序化控制**：会话/窗口管理、状态感知（capture-pane）、文本注入（load-buffer/paste-buffer）
- **Claude Code Hooks 集成**：SessionStart/PreToolUse/Notification/Stop 四类 hook 事件处理
- **JSONL 文件监听**：实时监控对话文件变化，解析 user/assistant 事件，推送完整对话流
- **本地 HTTP API**：接收 hook 脚本调用，绑定 127.0.0.1
- **Markdown 渲染**：将 Claude 输出的 Markdown 转为 Telegram 支持的 HTML 子集
- **进程管理**：macOS launchd 托管、崩溃检测与自动重启
- **并发控制**：per-topic asyncio.Lock 防止竞态

---

## 2. 技术方案分析

### 2.1 Telegram Bot 框架

#### 候选方案

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| python-telegram-bot | 全异步、类型完备、v22 支持 Bot API 9.5、原项目已验证 | v22 API 与 v21 有部分变化、run_polling 会阻塞事件循环 | 非常活跃（24k+ stars） | v22.5 (2026-01-24) | ★★★★★ |
| aiogram | 纯 asyncio 设计、性能优异、支持 FSM | 社区小于 python-telegram-bot、迁移成本高、原项目无基础 | 活跃（5k+ stars） | v3.26 | ★★★☆☆ |

#### 推荐方案

**python-telegram-bot v22.5**

理由：
1. 原项目已基于此库开发并验证可行，迁移成本为零
2. v22.5 支持 Telegram Bot API 9.5，完整覆盖 Forum Topics 管理（create_forum_topic、edit_forum_topic、close_forum_topic）
3. 官方文档完备，ApplicationBuilder 模式支持自定义启动逻辑
4. 需注意：与 aiohttp 共存时不能用 run_polling() 阻塞事件循环，需手动调用 application.initialize() + updater.start_polling() + 自行管理事件循环

关键 API：
- `ApplicationBuilder().token(TOKEN).build()` -- 构建应用
- `application.bot.create_forum_topic(chat_id, name, icon_color)` -- 创建话题
- `application.bot.send_message(chat_id, text, message_thread_id)` -- 话题内发消息
- `InlineKeyboardMarkup` / `InlineKeyboardButton` -- 权限审批按钮
- `CallbackQueryHandler` -- 按钮回调处理
- `application.bot.edit_forum_topic(chat_id, message_thread_id, name)` -- 修改话题名

版本要求：`>=22.0,<23.0`，Python `>=3.10`

---

### 2.2 tmux 程序化控制

#### 候选方案

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| asyncio.create_subprocess_exec 直接调用 tmux | 零额外依赖、完全控制命令参数、异步原生、原项目已验证 | 需自行封装、无高层抽象 | N/A（标准库） | Python 3.10+ | ★★★★★ |
| libtmux | 高层 Python API、类型完备、capture_pane 封装好 | 同步 API 需在 executor 中运行、pre-1.0 API 不稳定（2026 年仍在变）、额外依赖 | 中等（2k stars） | v0.53.1 | ★★★☆☆ |

#### 推荐方案

**asyncio.create_subprocess_exec 直接调用 tmux 命令**

理由：
1. 原项目已验证此方案可行（tmux_send_message 函数）
2. libtmux 是 pre-1.0 库，官方声明 API 将在 2026 年持续变化，引入不稳定风险
3. v2 需要精细控制 capture-pane 参数（-p 输出到 stdout、-e 保留转义序列、-S/-E 指定行范围），直接调用命令行更灵活
4. 异步 subprocess 天然适配 asyncio 事件循环，无需 executor 包装

关键 tmux 命令（v2 状态感知方案）：

```bash
# 创建窗口并启动 Claude
tmux new-window -t claude-pilot -n "cp-{short_id}" "claude -p '{prompt}' --resume {session_id}"

# 捕获 pane 可见内容（状态感知核心）
tmux capture-pane -t "{pane_id}" -p

# 多行文本注入（替代 send-keys -l 的安全方案）
echo "text" | tmux load-buffer -
tmux paste-buffer -t "{pane_id}" -d

# 发送控制键
tmux send-keys -t "{pane_id}" Escape
tmux send-keys -t "{pane_id}" Enter
tmux send-keys -t "{pane_id}" y

# 列出所有窗口
tmux list-windows -t claude-pilot -F "#{window_name} #{pane_id}"
```

**tmux capture-pane 状态感知方案的可行性分析：**

根据调研，tmux capture-pane 返回 pane 的可见屏幕内容（纯文本），可以通过正则匹配识别 Claude Code TUI 的四种状态：
- 输入模式：底部行包含 `>` 提示符特征
- 正在生成：包含 spinner 或 thinking 特征文本
- 进程退出：出现 shell prompt（`$`、`%`、`#`）
- 权限确认：包含 "Do you want to" 或 y/n 提示

已有实践验证：tmuxwatch 和 tmuxcc 两个项目使用了类似的 capture-pane + 内容解析方案来监控 TUI 应用状态。GitHub issue anthropics/claude-code#31739 也确认了 tmux paste-buffer 比 send-keys -l 更可靠。

风险与缓解：
- capture-pane 返回的是渲染后的屏幕快照，包含 ANSI 控制字符，需过滤
- Claude Code TUI 更新可能改变状态特征字符串，需提取为可配置常量
- 轮询间隔需平衡响应速度与 CPU 开销（建议 500ms，与 JSONL watcher 共用同一轮询周期，见 2.4 节）

---

### 2.3 Claude Code Hooks 系统

#### 候选方案

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| Command hooks（type: "command"） | 原项目已验证、独立 Python 脚本、通过 stdin/stdout 通信、exit code 控制决策 | 每次调用启动新进程、需依赖 urllib 与 Bot HTTP API 通信 | 官方支持 | Claude Code 最新版 | ★★★★★ |
| HTTP hooks（type: "http"） | 无需启动额外进程、直接 POST 到本地 API、更低延迟 | 需 Bot HTTP API 始终可用、配置中需写死端口、无法在 Bot 不运行时优雅降级 | 官方支持 | Claude Code 最新版 | ★★★★☆ |

#### 推荐方案

**Command hooks（与原项目一致），辅以 HTTP hooks 备选**

理由：
1. Command hooks 在 Bot 未运行时可通过 try/except 优雅降级（exit 0 不干预），HTTP hooks 会得到连接拒绝错误
2. 原项目已验证 Command hooks 方案，4 个 hook 脚本（session_start.py、permission.py、notification.py、stop.py）均工作正常
3. v2 的改进点：将 4 个文件的公共逻辑提取到 `_common.py`（read_port、post_to_bot），减少重复代码

Hook 事件与 JSON Schema：

**SessionStart**（session_start.py）：
```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "hook_event_name": "SessionStart",
  "source": "startup|resume|clear|compact",
  "model": "string"
}
```
- 用途：终端启动 Claude 时通知 Bot 创建话题并开始监听
- 决策：无需阻塞，仅通知
- v2 改进：传递 TMUX_PANE 环境变量，Bot 端注册 tmux 窗口映射

**PreToolUse**（permission.py）：
```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "hook_event_name": "PreToolUse",
  "tool_name": "string",
  "tool_input": { /* 工具参数 */ },
  "permission_mode": "string"
}
```
- 用途：权限审批，转发到 TG 让用户 allow/deny
- 决策输出：`{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow|deny"}}`
- exit code 2 = 阻止工具执行
- v2 改进：这是 Hook 层审批通道；TUI 层审批通过 capture-pane 检测实现

**Notification**（notification.py）：
```json
{
  "session_id": "string",
  "hook_event_name": "Notification",
  "message": "string",
  "notification_type": "permission_prompt|idle_prompt|auth_success|elicitation_dialog"
}
```
- 用途：转发 Claude 的通知到 TG
- v2 改进：区分 notification_type，permission_prompt 类型触发 TUI 层审批通道

**Stop**（stop.py）：
```json
{
  "session_id": "string",
  "hook_event_name": "Stop",
  "stop_hook_active": false,
  "last_assistant_message": "string"
}
```
- 用途：通知 Bot 会话结束
- v2 改进：对 tmux 交互式会话，Stop 仅表示一轮结束，不停止 watcher

settings.json 配置格式（项目级 `.claude/settings.json`）：
```json
{
  "hooks": {
    "SessionStart": [
      {"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude-pilot/hooks/session_start.py"}]}
    ],
    "PreToolUse": [
      {"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude-pilot/hooks/permission.py"}]}
    ],
    "Notification": [
      {"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude-pilot/hooks/notification.py"}]}
    ],
    "Stop": [
      {"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude-pilot/hooks/stop.py"}]}
    ]
  }
}
```

---

### 2.4 JSONL 文件监听与完整对话流推送

#### 候选方案

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| asyncio 轮询（os.path.getsize + seek/read） | 零依赖、原项目已验证、简单可靠、天然异步 | 轮询有延迟（0.5s）、CPU 空转 | N/A（标准库） | Python 3.10+ | ★★★★★ |
| watchdog（FSEvents on macOS） | 事件驱动无延迟、支持多平台 | 额外依赖、与 asyncio 集成需线程桥接、对 JSONL append 操作可能过度触发 | 活跃（6k+ stars） | v6.0+ | ★★★☆☆ |

#### 推荐方案

**asyncio 轮询方案（原项目 watch_transcript 函数的改进版）**

理由：
1. 原项目已验证可行性和性能（0.5s 轮询间隔，消息延迟 < 3 秒满足验收标准）
2. 零额外依赖，watchdog 的 FSEvents 在 macOS 上对文件 append 操作可能产生多次触发，需额外去重
3. JSONL 文件每次 append 一行，轮询方案通过 file.seek(last_pos) 精确读取增量数据，IO 开销极小
4. 轮询间隔统一为 0.5 秒（500ms），与 2.2 节 tmux capture-pane 状态感知使用相同周期。实现上两者可在同一个 asyncio 轮询任务中串行执行（先 capture-pane 检测状态，再 seek/read JSONL 增量），共享一个 `await asyncio.sleep(0.5)` 节拍，避免独立轮询任务的调度开销

**JSONL 文件事件格式与完整对话流推送方案：**

根据调研和原项目代码验证，Claude Code JSONL 文件中的关键事件类型：

```
user 事件（外部用户输入）:
{
  "type": "user",
  "userType": "external",
  "sessionId": "...",
  "uuid": "...",
  "parentUuid": "...",
  "timestamp": "...",
  "message": {
    "role": "user",
    "content": "string" | [{"type": "text", "text": "..."}]
  },
  "cwd": "..."
}

assistant 事件（Claude 回复）:
{
  "type": "assistant",
  "sessionId": "...",
  "uuid": "...",
  "message": {
    "role": "assistant",
    "content": [
      {"type": "text", "text": "..."},
      {"type": "tool_use", "name": "Bash", "input": {...}},
      {"type": "thinking", "thinking": "..."}
    ]
  }
}

user 事件（工具结果，内部）:
{
  "type": "user",
  "userType": "internal",
  "message": {
    "role": "user",
    "content": [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]
  }
}
```

**完整对话流推送的可行性：已确认可行。**

关键发现：
- user 事件的 `userType` 字段区分 `"external"`（真实用户输入）和 `"internal"`（工具结果反馈）
- watcher 只推送 `userType: "external"` 的 user 事件和 assistant 事件中的 text/tool_use 块
- 去重逻辑：通过 session 的 `source` 字段（"terminal" 或 "telegram"）判断，如果 source 为 "telegram"，跳过 user 事件推送（因为消息由 TG 发出，已在话题中显示）
- UUID 去重：每个事件有唯一 uuid，seen_uuids 集合防止重复处理

---

### 2.5 本地 HTTP API

#### 候选方案

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| aiohttp.web | 成熟、轻量、原项目已验证、与 asyncio 深度集成 | 较重（含 HTTP client），但只用 server 部分 | 非常活跃（15k+ stars） | v3.13.3 (2026-01-03) | ★★★★★ |
| FastAPI + Uvicorn | 自动文档、依赖注入、类型校验 | 引入 Uvicorn/Starlette 多层依赖、对简单内部 API 过重 | 非常活跃 | v0.115+ | ★★★☆☆ |

#### 推荐方案

**aiohttp.web**

理由：
1. 原项目已验证，Bot 内嵌 aiohttp server 监听 127.0.0.1:{PORT}
2. 与 python-telegram-bot 共享同一个 asyncio 事件循环，无需额外进程
3. 只需要 4-5 个路由（/session_start、/session_stop、/permission、/notification、/health），FastAPI 的自动文档和依赖注入在此场景下无价值

关键 API：
```python
app = web.Application()
app.router.add_post("/session_start", http_session_start)
app.router.add_post("/permission", http_permission)
runner = web.AppRunner(app)
await runner.setup()
site = web.TCPSite(runner, "127.0.0.1", port)  # 仅绑定 localhost
await site.start()
```

版本要求：`>=3.9,<4.0`

安全改进（v2 vs 原项目）：
- 绑定 `127.0.0.1` 替代 `0.0.0.0`
- session_id 参数白名单校验：`re.match(r'^[a-f0-9\-]{8,36}$', session_id)`

---

### 2.6 Markdown 渲染

#### 候选方案

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| mistune | 快速、支持自定义 renderer、原项目已实现完整 TelegramHTMLRenderer | 需手动处理 Telegram 不支持的标签 | 活跃（2.5k stars） | v3.2.0 (2025-12) | ★★★★★ |
| markdown-it-py | 更严格的 CommonMark 兼容、插件生态丰富 | 自定义 renderer 较复杂、需额外封装 | 活跃 | v3.0+ | ★★★☆☆ |

#### 推荐方案

**mistune v3**

理由：
1. 原项目已实现完整的 TelegramHTMLRenderer（约 100 行），直接复用
2. 支持 strikethrough 和 table 插件，覆盖 Claude 输出中常见的 Markdown 格式
3. 自定义 renderer 机制简洁：继承 HTMLRenderer，重写方法即可
4. v3.2.0 支持 Python 3.14，兼容性好

关键 API：
```python
renderer = TelegramHTMLRenderer(escape=False)
md = mistune.create_markdown(renderer=renderer, plugins=["strikethrough", "table"])
html = md(markdown_text)
```

Telegram 支持的 HTML 标签：`<b>`, `<i>`, `<code>`, `<pre>`, `<s>`, `<a>`, `<blockquote>`
不支持的标签降级策略（原项目已实现）：
- `<h1>`-`<h6>` -> `<b>` 加粗
- `<img>` -> `<a>` 链接
- `<hr>` -> 分割线字符
- `<table>` -> `<pre>` 等宽文本

v2 改进：renderer.py 独立模块（~80 行），包含智能分段逻辑（段落边界切分，确保每段 <= 4096 字符）

版本要求：`>=3.0,<4.0`

---

### 2.7 进程管理与崩溃恢复

#### 候选方案

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| macOS launchd | 系统原生、KeepAlive 自动重启、RunAtLoad 开机自启、无额外依赖 | macOS 专用、plist XML 格式繁琐 | Apple 官方 | macOS 原生 | ★★★★★ |
| supervisor | 跨平台、配置简单 | 需额外安装、macOS 上非标准方案 | 活跃 | v4.2+ | ★★☆☆☆ |
| pm2 | 跨平台、进程管理功能完善 | 需 Node.js 运行时、引入不相关技术栈 | 活跃 | v5+ | ★☆☆☆☆ |

#### 推荐方案

**macOS launchd**

理由：
1. 需求文档明确指定 macOS 目标平台，launchd 是系统原生方案
2. KeepAlive + RunAtLoad 完美匹配需求：崩溃自动重启 + 开机自启
3. ThrottleInterval=30 防止断网期间快速重启循环
4. 无需安装任何额外软件

plist 配置模板（`claude-pilot enable` 生成写入 `~/Library/LaunchAgents/`）：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude-pilot.bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/python3</string>
        <string>/Users/xxx/.claude-pilot/bot.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/xxx/.claude-pilot</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>StandardOutPath</key>
    <string>/Users/xxx/.claude-pilot/bot.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/xxx/.claude-pilot/bot.log</string>
</dict>
</plist>
```

**crash_reporter.py 设计：**
- 独立守护进程，自身也由 launchd 托管（单独 plist）
- 零外部依赖：仅用标准库 urllib.request 调用 Telegram Bot API
- 每 10 秒检查 Bot PID 存活状态
- 崩溃时读取 bot.log 最后 50 行提取 Traceback
- 通过私聊发送给 ALLOWED_USERS[0]

---

### 2.8 并发控制

#### 候选方案

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| asyncio.Lock（per-resource 实例） | 标准库零依赖、互斥语义精确匹配需求、async with 保证安全获取/释放、原项目已验证 | 无超时参数（需配合 asyncio.wait_for）、无可重入支持 | N/A（标准库） | Python 3.10+ | ★★★★★ |
| asyncio.Semaphore | 标准库、支持限制并发数（如限流）、适合连接池场景 | 语义不匹配：本项目需要互斥（1 对 1），Semaphore(1) 虽等价于 Lock 但语义不清晰；多余的计数器增加理解负担 | N/A（标准库） | Python 3.10+ | ★★★☆☆ |
| threading.Lock | 标准库、支持超时参数 | 不能用于保护协程临界区：asyncio 单线程模型下，threading.Lock 由同一线程多次获取不会阻塞，无法保护 await 点之间的竞态；混用会导致死锁风险 | N/A（标准库） | Python 3.10+ | ★☆☆☆☆ |

#### 推荐方案

**asyncio.Lock（per-topic / per-pane 实例）**

理由：
1. Python 标准库，零依赖
2. 本项目的并发控制需求是**互斥访问**（同一话题不能并发启动多个 Claude 进程、同一 pane 不能并发注入文本），asyncio.Lock 的语义精确匹配此需求
3. asyncio.Semaphore 虽可通过 `Semaphore(1)` 模拟互斥，但其设计意图是限制并发数（如连接池允许 N 个并发），用于互斥场景语义不清晰
4. threading.Lock 不适用于 asyncio 协程：Python 的 asyncio 在单线程中运行所有协程，threading.Lock 由同一 OS 线程获取时不会阻塞，无法保护 `await` 点之间的共享资源访问（参见 Python 官方文档：asyncio synchronization primitives are not thread-safe, and should not be used as replacements for threading primitives）
5. 原项目已验证 per-topic Lock 方案可行
6. async with 语法保证获取/释放的安全性，即使发生异常也能正确释放锁

实现模式：
```python
# per-topic 锁：防止同一话题并发操作
topic_locks: dict[int, asyncio.Lock] = {}

def get_topic_lock(topic_id: int) -> asyncio.Lock:
    if topic_id not in topic_locks:
        topic_locks[topic_id] = asyncio.Lock()
    return topic_locks[topic_id]

# per-pane 锁：防止并发 tmux 注入交叉
tmux_locks: dict[str, asyncio.Lock] = {}

def get_tmux_lock(pane_id: str) -> asyncio.Lock:
    if pane_id not in tmux_locks:
        tmux_locks[pane_id] = asyncio.Lock()
    return tmux_locks[pane_id]
```

两类锁的用途：
- `topic_locks[topic_id]`：防止同一话题连发多条消息时并发启动多个 Claude 进程
- `tmux_locks[pane_id]`：防止多个操作同时向同一 tmux pane 注入文本导致交叉

---

### 2.9 安装脚本与 CLI

#### 候选方案 A：安装脚本

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| 纯 Bash install.sh | `curl \| bash` 零依赖执行、macOS/Linux 自带 Bash、直接调用 brew/pip 等系统工具、用户对 shell 安装脚本最熟悉 | 错误处理薄弱（exit code + `\|\| true` 模式）、字符串操作繁琐、JSON 合并需调用外部 Python | N/A（系统内置） | macOS 原生 | ★★★★★ |
| Python 安装脚本 | try/except 完善的错误处理、原生 JSON 操作、跨平台一致性更好 | `curl \| bash` 无法直接执行 Python 脚本（需先确认 Python 存在）、用户需额外一步 `python3 install.py`、安装脚本本身的目的之一就是检测和安装 Python，循环依赖 | N/A（标准库） | Python 3.10+ | ★★☆☆☆ |

#### 候选方案 B：CLI 实现

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| Python 脚本 + sys.argv 手动解析 | 零依赖、CLI 只有 6 个子命令极简场景、启动速度最快、无需 pip install 额外包 | 无自动 --help 生成、无参数校验、需手动实现 usage 文本 | N/A（标准库） | Python 3.10+ | ★★★★☆ |
| Python 脚本 + argparse | 标准库自带、自动生成 --help、支持子命令（add_subparsers）、参数类型校验 | 相比 sys.argv 稍重、boilerplate 代码较多 | N/A（标准库） | Python 3.10+ | ★★★★★ |
| click | 装饰器语法简洁、自动 --help、丰富的参数类型、社区最广泛（38.7% CLI 项目使用） | 额外依赖（click 包）、对 6 个简单子命令过重、增加安装复杂度 | 非常活跃（16k+ stars） | v8.1+ | ★★★☆☆ |
| typer | 基于类型注解最简洁、自动补全、底层基于 click | 额外依赖（typer + click + rich）、依赖链长、对极简 CLI 过重 | 活跃（16k+ stars） | v0.9+ | ★★☆☆☆ |

#### 推荐方案

**纯 Bash install.sh + Python argparse CLI 脚本**

安装脚本推荐 Bash 的理由：
1. 需求文档要求 `curl -fsSL ... | bash` 一键安装，Bash 脚本是此模式的唯一自然选择
2. 安装脚本的核心任务之一是检测和安装 Python 3.10+，使用 Python 编写安装脚本会产生循环依赖（需要 Python 才能运行检测 Python 的脚本）
3. 安装脚本的主要操作（检测命令、调用 brew/pip、读取用户输入、写文件）都是 shell 的天然强项
4. 对于 JSON 合并这一 Bash 薄弱环节，脚本中内联调用 `python3 -c "import json; ..."` 即可解决，无需整个脚本用 Python 编写

CLI 推荐 argparse 的理由：
1. Python 标准库，零额外依赖，符合项目"依赖最小化"原则
2. 6 个子命令（start/stop/status/enable/disable/logs）的规模完全在 argparse 的舒适区内
3. 自动生成 `--help` 和 usage 文本，比 sys.argv 手动解析更规范
4. click/typer 引入额外依赖（click 8.1 或 typer 0.9 + click + rich），对如此简单的 CLI 收益不成比例

install.sh 技术细节：
- 纯 Bash 脚本，无额外依赖
- 通过 `command -v` 检测 claude、tmux、python3
- 使用 `python3 -c "import sys; print(sys.version_info >= (3, 10))"` 检测版本
- `brew install tmux` 自动安装 tmux
- `pip install -r requirements.txt` 安装 Python 依赖
- `read -p` 收集 BOT_TOKEN 和 ALLOWED_USERS
- Hook 合并策略：读取现有 `~/.claude/settings.json`，用 Python json 模块合并 hooks 配置，不覆盖用户已有的 hook

claude-pilot CLI（argparse 实现）：
- Python 脚本，安装到 PATH（symlink 或 ~/.local/bin/）
- 子命令：start、stop、status、enable、disable、logs
- start：在 tmux claude-pilot session 中启动 bot.py
- stop：读取 .pid 文件，kill 进程
- enable/disable：写入/删除 launchd plist
- logs：`tail -f bot.log`

---

### 2.10 配置管理

需求文档定义了两层配置：`.env` 静态配置（安装时写入，运行期不变）和 `.state.json` 运行时持久化（Bot 自动读写）。需要分别为这两层选择技术方案。

#### 候选方案 A：.env 静态配置解析

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| 手动解析（逐行 split("=", 1)） | 零依赖、逻辑透明（< 15 行代码）、完全控制解析行为、无需 pip install | 不支持引号包裹的值、不支持多行值、不支持变量插值（${VAR}） | N/A（自行实现） | N/A | ★★★★★ |
| python-dotenv | 完整 .env 规范支持（引号、多行、注释、变量插值）、自动写入 os.environ、CLI 工具 | 额外依赖（pip install python-dotenv）、v1.2.2 可选依赖 click；对本项目 4 个简单 KEY=VALUE 配置过重 | 活跃（7k+ stars） | v1.2.2 (2026-03-01) | ★★★☆☆ |

**推荐方案：手动解析**

理由：
1. 本项目的 `.env` 文件只有 4 个配置项（BOT_TOKEN、ALLOWED_USERS、BOT_PORT、PROJECT_DIR），全部是简单的 `KEY=VALUE` 格式，无引号、无多行值、无变量插值需求
2. 手动解析代码极简（约 15 行），逻辑完全透明，易于调试：

```python
def load_env(path: str) -> dict[str, str]:
    config = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            config[key.strip()] = value.strip()
    return config
```

3. python-dotenv（v1.2.2）虽然功能完善，但其核心价值（引号解析、变量插值、os.environ 自动注入）在本项目中无用，引入额外依赖不划算
4. 减少一个 pip 依赖有助于 crash_reporter.py 等仅使用标准库的模块保持独立性

#### 候选方案 B：.state.json 运行时持久化

| 方案 | 优点 | 缺点 | 社区活跃度 | 最新版本 | 推荐度 |
|------|------|------|-----------|---------|--------|
| json 标准库 + os.rename 原子写入 | 零依赖、JSON 人类可读可调试、原子写入防损坏（macOS 同文件系统 rename 是 POSIX 原子操作）、与需求文档 schema 直接对应 | 需手动实现原子写入（先写临时文件再 rename）、无内置并发写保护 | N/A（标准库） | Python 3.10+ | ★★★★★ |
| shelve（标准库） | 标准库、dict-like API 简单、自动序列化 Python 对象 | 使用 pickle 序列化（安全风险、不可人类阅读）、不支持并发读写、底层 dbm 文件格式不透明无法手动调试、跨平台兼容性差 | N/A（标准库） | Python 3.10+ | ★★☆☆☆ |
| sqlite3（标准库） | 标准库、支持并发读写（WAL 模式）、ACID 事务、查询灵活 | 对简单 key-value 结构过重、需定义 schema 和 SQL 语句、状态文件不可直接人类阅读（二进制格式）、与需求文档的 JSON schema 不直接对应 | N/A（标准库） | Python 3.10+ | ★★★☆☆ |

**推荐方案：json 标准库 + os.rename 原子写入**

理由：
1. 需求文档已明确定义了 `.state.json` 的 JSON schema（group_chat_id、sessions、session_topics），使用 json 标准库直接映射，无需转换层
2. JSON 格式人类可读，开发调试时可直接 `cat .state.json` 查看状态，问题排查效率高
3. 原子写入通过 `os.rename()` 实现：先写入临时文件 `.state.json.tmp`，再 rename 覆盖目标文件。macOS 上同文件系统的 `rename(2)` 是 POSIX 标准的原子操作，即使写入过程中 Bot 崩溃，也不会产生损坏的半写文件（Python 官方 issue #8828 及 POSIX 规范确认）
4. shelve 使用 pickle 序列化，文件格式不透明（dbm 数据库文件），无法用文本编辑器查看和修改，且 Python 官方文档明确警告"不要从不信任来源打开 shelf"
5. sqlite3 虽然功能强大，但 `.state.json` 只有 3 个顶层字段、嵌套结构简单，使用 SQL 数据库是过度工程化
6. 本项目是单进程 asyncio 应用，不需要 sqlite3 的并发写入能力；asyncio.Lock 已经在应用层保证了写入的串行化

原子写入实现：

```python
import json, os, tempfile

def save_state(state: dict, path: str = ".state.json") -> None:
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.rename(tmp_path, path)  # 同文件系统，POSIX 原子操作
    except Exception:
        os.unlink(tmp_path)  # 清理临时文件
        raise
```

---

## 3. 技术栈总结

| 层级/模块 | 技术选型 | 版本 | 用途 |
|----------|---------|------|------|
| Telegram Bot | python-telegram-bot | >=22.0,<23.0 | Bot 交互、话题管理、消息收发 |
| HTTP API | aiohttp | >=3.9,<4.0 | Hook 脚本与 Bot 通信 |
| Markdown 渲染 | mistune | >=3.0,<4.0 | Markdown -> Telegram HTML |
| tmux 控制 | asyncio.subprocess + tmux CLI | tmux >=3.0 | 会话管理、状态感知、文本注入 |
| Hook 系统 | Claude Code Command hooks | 最新版 Claude Code | 生命周期事件集成 |
| 文件监听 | asyncio 轮询 (标准库) | Python 3.10+ | JSONL 对话文件实时监控 |
| 进程管理 | macOS launchd | macOS 原生 | 自动重启、开机自启 |
| 崩溃通知 | urllib.request (标准库) | Python 3.10+ | 直接调用 TG API 发通知 |
| 并发控制 | asyncio.Lock (标准库) | Python 3.10+ | per-topic / per-pane 锁 |
| 配置管理（.env） | 手动解析（逐行 split） | Python 3.10+（标准库） | 静态配置加载 |
| 配置管理（.state.json） | json + os.rename 原子写入 | Python 3.10+（标准库） | 运行时状态持久化 |
| 安装脚本 | Bash | macOS 原生 | 一键安装（curl \| bash） |
| CLI | Python argparse | Python 3.10+（标准库） | start/stop/status/enable/disable/logs |

---

## 4. 技术风险评估

| 风险 | 概率(高/中/低) | 影响(高/中/低) | 缓解策略 |
|------|--------------|--------------|---------|
| Claude Code TUI 状态特征字符串变化导致 capture-pane 识别失败 | 中 | 高 | 将所有状态特征字符串提取为配置常量（TUI_PATTERNS），支持运行时更新；capture-pane 失败时回退到盲发模式（原项目行为） |
| Claude Code hooks API 变更 | 低 | 高 | Hook 脚本仅使用核心字段（session_id、tool_name、message），避免依赖非必要字段；关注 Claude Code changelog |
| python-telegram-bot v22 -> v23 升级引入 breaking changes | 低 | 中 | 锁定版本 `>=22.0,<23.0`，升级时逐项验证 |
| tmux paste-buffer 添加尾部换行（已知 tmux 行为，见 tmux Discussion #4098） | 中 | 中 | 使用 `paste-buffer -d -p` 参数控制；注入后 capture-pane 验证文本是否正确提交 |
| Telegram 429 限速（同一话题短时间大量消息） | 高 | 中 | watcher 实现消息合并逻辑：累积 buffer + 定时刷新（1-2 秒间隔），批量发送；失败后指数退避重试 |
| JSONL 文件在 compact/resume 时结构变化 | 中 | 中 | watcher 读取增量数据，对 JSON 解析失败的行跳过而非崩溃；监听 SessionStart hook 的 source 字段（compact/resume）重新定位文件位置 |
| Bot 与 aiohttp server 共享事件循环，长时间阻塞操作影响响应 | 低 | 高 | 所有 IO 操作使用 asyncio，tmux subprocess 调用使用 async，文件读取使用非阻塞方式；permission 审批设置 120 秒超时 |
| macOS launchd ThrottleInterval 在 Bot 代码缺陷导致启动即崩溃时仍会循环重启 | 低 | 中 | crash_reporter 记录重启次数，连续 5 次以上发送警告通知建议人工介入 |
| .state.json 写入被打断导致文件损坏 | 低 | 高 | 使用原子写入：先写临时文件，再 os.rename 覆盖（macOS 上 rename 是原子操作） |

---

## 5. 第三方依赖清单

| 依赖名 | 版本 | 用途 | License |
|--------|------|------|---------|
| python-telegram-bot | >=22.0,<23.0 | Telegram Bot API 交互 | LGPL-3.0 |
| aiohttp | >=3.9,<4.0 | 本地 HTTP API 服务器 | Apache-2.0 |
| mistune | >=3.0,<4.0 | Markdown -> Telegram HTML 转换 | BSD-3-Clause |

注：以上为全部第三方 pip 依赖。其余功能均使用 Python 标准库（asyncio、json、os、subprocess、urllib.request、re、signal、uuid、html）和系统工具（tmux、launchd）。

Python 版本要求：**>=3.10**（python-telegram-bot v22 要求 3.10+，asyncio.TaskGroup 在 3.11+ 可用但非必需）

系统依赖：
- tmux >=3.0（brew install tmux）。版本下限依据：本项目使用的 `capture-pane -p`（tmux 1.8+）、`load-buffer -`（tmux 0.7+）、`paste-buffer -d`（tmux 0.5+）等功能在更早版本即可用，但 tmux 3.0 引入了每个 pane 的唯一 ID（TMUX_PANE 环境变量，tmux 3.0 changelog 明确记载），本项目通过 SessionStart hook 读取 TMUX_PANE 建立 session 到 pane 的映射，依赖此特性。此外 Homebrew 默认安装 tmux 3.5+，>=3.0 是一个保守且实际不会遇到问题的下限
- Claude Code CLI（需用户自行安装）
- macOS（launchd 进程管理）

---

## 6. 兼容性与集成说明

### python-telegram-bot + aiohttp 共存

python-telegram-bot 的 `run_polling()` 会阻塞事件循环，与 aiohttp server 不兼容。解决方案（原项目已验证）：

```python
# 不使用 run_polling()，手动管理事件循环
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    # 注册 handlers...

    # 启动 aiohttp server
    aio_app = web.Application()
    # 注册路由...
    runner = web.AppRunner(aio_app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()

    # 手动启动 telegram polling
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # 等待停止信号
    stop_event = asyncio.Event()
    # ... signal handler ...
    await stop_event.wait()

    # 优雅关闭
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    await runner.cleanup()
```

### Claude Code hooks + Bot HTTP API

Hook 脚本（Python）通过 `urllib.request` 向 `http://127.0.0.1:{PORT}` 发送 POST 请求。通信流程：

```
Claude Code -> Hook script (stdin JSON) -> urllib POST -> aiohttp server -> Bot 处理
                                                                              |
                                                                              v
Bot 处理 -> Telegram API -> 用户手机 -> 用户操作 -> Bot -> HTTP response -> Hook script (stdout JSON)
```

permission hook 的超时设置为 120 秒（等待用户审批），需要 aiohttp 端使用 `asyncio.Event()` 挂起请求直到用户点击按钮或超时。

### 状态一致性

`.state.json` 是所有模块共享的状态文件，需要注意：
- 写入操作集中在少数几个函数中（register_session、unregister_session、save_state）
- 使用原子写入防止损坏
- Bot 启动时加载，运行时每次变更后持久化
- crash_reporter 仅读取 .pid 文件，不读写 .state.json，避免竞态
