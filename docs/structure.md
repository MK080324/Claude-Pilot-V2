# 技术架构文档

## 1. 架构概览

```
                           +-----------------------+
                           |    Telegram Cloud      |
                           |   (Bot API Server)     |
                           +----------+------------+
                                      |
                        HTTPS polling / send_message
                                      |
+---------------------+    +----------v------------+    +---------------------+
|   crash_reporter.py  |    |       bot.py           |    |    install.sh       |
|   (独立守护进程)     |    |   (启动入口 + 组装)    |    |  (一键安装脚本)     |
|                     |    |                        |    +---------------------+
| urllib 直接调       |    |  +------------------+  |    +---------------------+
| TG API 发崩溃通知   |    |  | TG polling       |  |    |  claude-pilot CLI   |
| 监控 .pid 文件      |    |  +------------------+  |    |  (argparse)         |
+---------------------+    |  | aiohttp server   |  |    | start/stop/status   |
                           |  | 127.0.0.1:PORT   |  |    | enable/disable/logs |
                           |  +------------------+  |    +---------------------+
                           +---+------+------+------+
                               |      |      |
                  +------------+  +---+---+  +------------+
                  |               |       |               |
          +-------v-------+ +----v----+ +-v-----------+ +--v-----------+
          |  handlers/    | | session | | watcher.py  | | renderer.py  |
          |  commands.py  | | .py     | |             | |              |
          |  messages.py  | |         | | JSONL 监听  | | Markdown ->  |
          |  callbacks.py | | tmux    | | 消息合并    | | TG HTML      |
          +-------+-------+ | 控制    | | TUI 状态    | | 智能分段     |
                  |         | 状态    | | 检测        | +--------------+
                  |         | 感知    | +------+------+
                  |         +----+----+        |
                  |              |             |
                  |         +----v-------------v------+
                  |         |        tmux session:     |
                  |         |        claude-pilot      |
                  +-------->|                          |
                            |  window: bot (Bot 自身)  |
                            |  window: cp-a3f2 (会话1) |
                            |  window: cp-7c9e (会话2) |
                            +-----------+--------------+
                                        |
                         capture-pane / load-buffer / paste-buffer
                                        |
                            +-----------v--------------+
                            |     Claude Code TUI      |
                            |  (每个 window 一个实例)   |
                            +--------------------------+

   +-------------------+         +-------------------+
   |   hooks/          |  HTTP   |   api.py          |
   |   _common.py      +-------->|                   |
   |   session_start.py|  POST   | /session_start    |
   |   permission.py   |  to     | /session_stop     |
   |   notification.py |  127.   | /permission       |
   |   stop.py         |  0.0.1  | /notification     |
   +-------------------+         | /health           |
                                 +-------------------+

   +-------------------+
   |  config.py        |
   |  .env (静态)      |
   |  .state.json      |
   |  (运行时持久化)   |
   +-------------------+
```

**两层权限审批通道架构：**

```
Claude Code 执行工具
        |
        +-- PreToolUse hook 触发 --> hooks/permission.py
        |                               |
        |                         HTTP POST /permission
        |                               |
        |                          api.py 接收
        |                               |
        |                    TG InlineKeyboard 审批  <-- Hook 层
        |                         (受 /bypass 控制)
        |
        +-- Claude Code 硬编码权限提示 (config files 等)
                    |
              watcher.py capture-pane 检测到
              "Do you want to..." / y/n 提示
                    |
              TG InlineKeyboard 审批             <-- TUI 层
              (始终开启, 不受 /bypass 影响)
                    |
              tmux send-keys y/n 响应
```

---

## 2. 模块划分

### 2.1 bot.py -- 启动入口与应用组装

- **职责**: 构建 Telegram Application 实例和 aiohttp server 实例，注册所有 handler 和路由，管理事件循环生命周期（启动、信号处理、优雅关闭）。写入 .pid 文件供 crash_reporter 和 CLI 使用。
- **对外接口**: 无（入口文件，不被其他模块 import）
- **内部核心组件**: `main()` 异步入口函数
- **依赖的其他模块**: config, session, watcher, renderer, api, handlers/*
- **行数上限**: ~60 行

### 2.2 config.py -- 配置加载与状态持久化

- **职责**: 加载 `.env` 静态配置；加载/保存 `.state.json` 运行时状态；提供配置值的全局访问接口。`.state.json` 采用原子写入（先写临时文件再 `os.rename`）。
- **对外接口**:
  - `load_env(path: str) -> dict[str, str]` -- 解析 .env 文件
  - `load_state(path: str) -> State` -- 加载 .state.json
  - `save_state(state: State, path: str) -> None` -- 原子写入 .state.json
  - `Config` 数据类 -- 保存 BOT_TOKEN, ALLOWED_USERS, BOT_PORT, PROJECT_DIR 等静态配置
  - `State` 数据类 -- 保存 group_chat_id, notify_chat_id, sessions, session_topics 等运行时状态
- **内部核心组件**: 原子写入逻辑（tempfile.mkstemp + os.rename）
- **依赖的其他模块**: 无（底层模块，不依赖其他项目模块）
- **行数上限**: ~50 行

**`.state.json` 读写时机：**
- 读取：Bot 启动时（`main()` 中调用 `load_state()`）
- 写入：会话注册/注销时、`/setup` 完成写入 group_chat_id 时、`/start` 私聊写入 notify_chat_id 时。每次状态变更后立即调用 `save_state()`，确保崩溃后状态不丢失。

### 2.3 session.py -- 会话状态管理与 tmux 操作

- **职责**: 管理 Claude 会话的完整生命周期（创建、查询、注入消息、中断、销毁）；封装所有 tmux 操作（创建窗口、捕获 pane、注入文本、发送控制键）；实现 TUI 状态感知的四种状态检测逻辑；管理 per-topic 和 per-pane 的 asyncio.Lock。
- **对外接口**:
  - `launch_session(project_dir: str, state: State, bot: Bot) -> SessionInfo` -- 创建 tmux 窗口并启动 Claude
  - `inject_message(pane_id: str, text: str) -> None` -- 状态感知式消息注入（先检测 TUI 状态，再操作）
  - `interrupt_session(pane_id: str) -> None` -- 中断 Claude 生成（Escape）
  - `kill_session(window_name: str) -> None` -- 销毁 tmux 窗口
  - `detect_tui_state(pane_id: str) -> TuiState` -- 捕获 pane 内容并识别 TUI 状态
  - `respond_tui_permission(pane_id: str, allow: bool) -> None` -- TUI 层权限响应（send-keys y/n）
  - `get_topic_lock(topic_id: int) -> asyncio.Lock`
  - `get_tmux_lock(pane_id: str) -> asyncio.Lock`
  - `list_tmux_windows() -> list[dict]` -- 列出所有活跃的 Claude 窗口
- **内部核心组件**:
  - `TuiState` 枚举: `INPUT`, `GENERATING`, `EXITED`, `PERMISSION_PROMPT`
  - `TUI_PATTERNS` 配置常量字典: 将四种状态的特征字符串提取为可配置项
  - `_tmux_exec(*args) -> str` -- 底层 tmux 命令执行封装
  - `_capture_pane(pane_id) -> str` -- 捕获 pane 可见内容并过滤控制字符
  - `_load_buffer_paste(pane_id, text) -> None` -- 通过 load-buffer + paste-buffer 安全注入多行文本
  - `_wait_for_state(pane_id, target_state, timeout) -> bool` -- 轮询等待目标状态
- **依赖的其他模块**: config（读取 State 中的 sessions 映射）
- **行数上限**: ~180 行

**四种 TUI 状态检测逻辑（在 `detect_tui_state` 中实现）：**

```python
TUI_PATTERNS = {
    "input_prompt": [">"],                         # 输入模式
    "generating": ["thinking", "..."],             # 正在生成
    "exited": ["$", "%", "#"],                     # 进程退出（shell prompt）
    "permission": ["Do you want to", "(y/n)"],     # 权限确认
}
```

检测算法：
1. `tmux capture-pane -t {pane_id} -p` 获取可见屏幕内容
2. 过滤控制字符 `[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]`
3. 取最后 5 行作为状态判断区域（TUI 状态特征集中在底部）
4. 按优先级匹配：permission > exited > generating > input（permission 最优先，因为误判代价最高）
5. 均未匹配时返回 `GENERATING`（保守策略：等待而非误操作）

### 2.4 watcher.py -- JSONL 文件监听与消息合并

- **职责**: 监听 Claude Code 的 JSONL 对话文件，解析 user/assistant 事件，推送完整对话流到 Telegram 话题。同时在同一轮询周期中执行 TUI 状态检测（与 JSONL 轮询共享 0.5s 节拍）。实现消息合并防 429 机制。实现去重逻辑。
- **对外接口**:
  - `start_watcher(session_id: str, transcript_path: str, chat_id: int, topic_id: int, source: str, pane_id: str | None, state: State, bot: Bot) -> asyncio.Task` -- 启动监听任务
  - `stop_watcher(topic_id: int) -> None` -- 停止监听任务
- **内部核心组件**:
  - `_watch_loop()` -- 主轮询循环（0.5s 间隔，串行执行 JSONL 读取 + TUI 状态检测）
  - `_read_jsonl_incremental()` -- 增量读取 JSONL 文件（seek + read）
  - `_process_event()` -- 解析单个 JSONL 事件并分发
  - `_flush_buffer()` -- 消息合并缓冲区刷新
  - `_check_tui_state()` -- 在轮询周期中执行 TUI 权限检测
  - `seen_uuids: set[str]` -- UUID 去重集合
  - `send_buffer: list[str]` -- 待发送消息缓冲区
  - `last_flush_time: float` -- 上次刷新时间戳
- **依赖的其他模块**: session（调用 detect_tui_state、respond_tui_permission）, renderer（消息格式化）, config（读取 State）
- **行数上限**: ~150 行

**消息合并防 429 机制（在 `_flush_buffer` 中实现）：**

```
JSONL 事件到达
       |
       v
  解析并格式化 --> 写入 send_buffer
       |
       v
  检查距上次 flush 的时间间隔
       |
  < 1.5 秒 --> 继续累积
  >= 1.5 秒 --> 合并 buffer 中所有消息为一条，调用 send_to_topic 发送
       |
  发送失败（429/其他）--> 指数退避重试（1s, 2s, 4s），最多 3 次
```

**去重逻辑（在 `_process_event` 中实现）：**

1. UUID 去重：每个 JSONL 事件有唯一 uuid，`seen_uuids` 集合防止同一事件被重复处理
2. source 去重：如果 session 的 `source` 为 `"telegram"`，跳过 `userType: "external"` 的 user 事件推送（因为消息由 TG 发出，已在话题中显示）
3. internal 过滤：`userType: "internal"` 的 user 事件（工具结果反馈）不推送

### 2.5 renderer.py -- Markdown 到 Telegram HTML 渲染

- **职责**: 将 Claude 输出的 Markdown 转为 Telegram 支持的 HTML 子集；实现智能分段（段落边界切分，确保每段 <= 4096 字符）；格式化工具调用摘要。
- **对外接口**:
  - `render_markdown(text: str) -> str` -- Markdown 转 Telegram HTML
  - `split_message(html: str, limit: int = 4096) -> list[str]` -- 智能分段
  - `format_tool_use(name: str, input_data: dict) -> str` -- 格式化工具调用为人类可读摘要
- **内部核心组件**:
  - `TelegramHTMLRenderer(mistune.HTMLRenderer)` -- 自定义 mistune 渲染器
  - 不支持标签的降级映射表（h1-h6 -> b, img -> a, hr -> 分割线, table -> pre）
- **依赖的其他模块**: 无（纯函数模块，无状态）
- **行数上限**: ~80 行

### 2.6 api.py -- HTTP API 路由

- **职责**: 提供 aiohttp HTTP 路由，接收来自 hook 脚本的请求；绑定 127.0.0.1 确保仅本地访问；实现 permission 请求的挂起/唤醒机制（asyncio.Event 等待用户审批或超时）。
- **对外接口**:
  - `create_api_app(state: State, bot: Bot) -> web.Application` -- 创建并配置 aiohttp app
  - `pending_permissions: dict[str, PermissionRequest]` -- 待审批权限请求（供 callbacks.py 读写）
- **内部核心组件**:
  - `http_session_start(request)` -- 处理 SessionStart hook
  - `http_session_stop(request)` -- 处理 Stop hook
  - `http_permission(request)` -- 处理 PreToolUse hook（挂起等待审批，120 秒超时）
  - `http_notification(request)` -- 处理 Notification hook
  - `http_health(request)` -- 健康检查
  - session_id 白名单校验：`re.match(r'^[a-f0-9\-]{8,36}$', session_id)`
- **依赖的其他模块**: config（State）, session（launch 和 register 操作）, watcher（启动/停止监听任务）
- **行数上限**: ~80 行

### 2.7 handlers/commands.py -- Telegram 命令处理

- **职责**: 处理所有 Telegram 斜杠命令。每个命令一个 async 函数。
- **对外接口**: 每个命令对应一个 handler 函数，在 bot.py 中注册到 Application
  - `cmd_setup(update, context)` -- /setup 引导配置群组
  - `cmd_start(update, context)` -- /start 初始化
  - `cmd_projects(update, context)` -- /projects 选择项目目录
  - `cmd_resume(update, context)` -- /resume 恢复历史会话（含历史回显）
  - `cmd_rename(update, context)` -- /rename 重命名会话
  - `cmd_interrupt(update, context)` -- /interrupt 中断 Claude 生成
  - `cmd_quit(update, context)` -- /quit 暂停会话
  - `cmd_delete(update, context)` -- /delete 删除会话
  - `cmd_bypass(update, context)` -- /bypass 开关 Hook 层权限审批
  - `cmd_status(update, context)` -- /status 查看运行状态
  - `cmd_info(update, context)` -- /info 查看当前会话信息
  - `cmd_retry(update, context)` -- /retry 重发最后一条回复
  - `cmd_setdir(update, context)` -- /setdir 手动设置项目目录
- **依赖的其他模块**: config（State）, session（tmux 操作）, watcher（启动/停止监听）, renderer（消息格式化）

### 2.8 handlers/messages.py -- 普通消息处理

- **职责**: 处理用户在话题中发送的非命令文本消息。根据会话 source 决定注入方式：terminal 会话通过 tmux 注入，telegram 会话通过 tmux 注入（v2 统一路径）。
- **对外接口**:
  - `handle_message(update, context)` -- 消息处理入口（注册为 MessageHandler）
- **内部核心组件**:
  - 鉴权检查（ALLOWED_USERS）
  - per-topic Lock 获取
  - 根据 session 存在性决定流程：有 session 则注入消息，无 session 则提示创建
- **依赖的其他模块**: config（State, ALLOWED_USERS）, session（inject_message, get_topic_lock）

### 2.9 handlers/callbacks.py -- InlineKeyboard 回调处理

- **职责**: 处理 InlineKeyboard 按钮点击事件。包括 Hook 层权限审批响应、TUI 层权限审批响应、/projects 目录选择回调、/delete 确认回调等。
- **对外接口**:
  - `handle_button(update, context)` -- 按钮回调入口（注册为 CallbackQueryHandler）
- **内部核心组件**:
  - 按 callback_data 前缀分发：`allow:`, `deny:`, `tui_allow:`, `tui_deny:`, `project:`, `delete_confirm:` 等
  - Hook 层审批：从 `api.pending_permissions` 中找到对应请求，设置 decision 并触发 Event
  - TUI 层审批：调用 `session.respond_tui_permission(pane_id, allow)` 发送 tmux send-keys
- **依赖的其他模块**: api（pending_permissions）, session（respond_tui_permission）, config（State）

### 2.10 hooks/_common.py -- Hook 脚本共享工具

- **职责**: 为 4 个 hook 脚本提供公共函数，避免重复代码。
- **对外接口**:
  - `read_port() -> str` -- 从 .env 文件读取 BOT_PORT
  - `post_to_bot(endpoint: str, payload: dict, timeout: int = 10) -> dict | None` -- 向 Bot HTTP API 发送 POST 请求
- **内部核心组件**: 无
- **依赖的其他模块**: 无（仅使用标准库 urllib.request、os、json）

### 2.11 hooks/session_start.py, permission.py, notification.py, stop.py

- **职责**: 分别处理 Claude Code 的 SessionStart、PreToolUse、Notification、Stop 四类 hook 事件。从 stdin 读取 JSON，通过 HTTP POST 转发给 Bot。
- **对外接口**: 无（独立脚本，由 Claude Code 调用）
- **依赖的其他模块**: hooks/_common.py

### 2.12 crash_reporter.py -- 崩溃检测与通知

- **职责**: 独立守护进程。每 10 秒检查 Bot PID 存活状态；崩溃时读取 bot.log 最后 50 行提取 Traceback，通过 urllib 直接调用 Telegram API 私聊通知管理员；Bot 恢复后发送恢复通知。
- **对外接口**: 无（独立进程）
- **内部核心组件**:
  - `_check_pid_alive(pid: int) -> bool` -- 检查进程是否存活
  - `_extract_traceback(log_path: str) -> str` -- 从日志提取最近的 Traceback
  - `_send_telegram_message(token: str, chat_id: int, text: str) -> None` -- urllib 直接调用 TG API
  - 重启计数器（今日重启次数，连续 5 次以上发送警告）
- **依赖的其他模块**: 无（仅使用标准库，读取 .env 和 .pid 文件）
- **行数上限**: ~80 行

### 2.13 install.sh -- 一键安装脚本

- **职责**: 检测依赖（claude CLI、tmux、Python 3.10+）；克隆项目到 ~/.claude-pilot；收集用户配置写入 .env；合并 hooks 到 ~/.claude/settings.json；安装 claude-pilot CLI 到 PATH；后台启动 Bot。
- **对外接口**: `curl -fsSL ... | bash`
- **依赖的其他模块**: 无（独立 Bash 脚本）

### 2.14 claude-pilot CLI -- 命令行管理工具

- **职责**: 提供 start/stop/status/enable/disable/logs 子命令管理 Bot 生命周期。
- **对外接口**: `claude-pilot <subcommand>`
- **内部核心组件**:
  - start: 在 tmux claude-pilot session 中启动 bot.py
  - stop: 读取 .pid，kill 进程
  - status: 读取 .pid 检查存活，显示基本信息
  - enable: 生成并加载 launchd plist
  - disable: 卸载并删除 launchd plist
  - logs: `tail -f bot.log`
- **依赖的其他模块**: 无（独立脚本，通过文件与 Bot 交互）

---

## 3. 模块间通信

### 3.1 通信方式总览

| 通信方式 | 使用场景 |
|---------|---------|
| Python 函数调用 | Bot 内部模块间（bot.py -> handlers -> session -> watcher -> renderer -> config） |
| HTTP POST (127.0.0.1) | hook 脚本 -> api.py（跨进程通信） |
| asyncio.Event | api.py permission 请求挂起 <-> callbacks.py 审批响应唤醒 |
| asyncio.Lock | session.py 管理的 per-topic 和 per-pane 互斥锁 |
| tmux CLI | session.py -> tmux -> Claude Code TUI（跨进程交互） |
| 文件 I/O | Claude Code -> JSONL 文件 -> watcher.py（文件轮询） |
| 文件 I/O | config.py <-> .state.json / .env（配置持久化） |
| 文件 I/O | crash_reporter.py -> .pid / bot.log（进程监控） |
| urllib HTTP | crash_reporter.py -> Telegram API（崩溃通知） |

### 3.2 接口定义

### HTTP POST: /session_start
- 方向: hooks/session_start.py -> api.py
- 参数: `{ session_id: str, transcript_path: str, cwd: str, tmux_pane: str | null }`
- 返回值: `{ status: "created" | "exists" | "no_group", topic_id?: int }`
- 错误: 400 (no session_id), 500 (创建话题失败)
- 副作用: 在 State.sessions 中注册会话，创建 TG 话题，启动 watcher 任务

### HTTP POST: /session_stop
- 方向: hooks/stop.py -> api.py
- 参数: `{ session_id: str, message: str, chat_id?: int, thread_id?: int }`
- 返回值: `{ status: "ok" }`
- 错误: 无（尽力发送通知）
- 副作用: 对非 tmux 会话停止 watcher；对 tmux 会话保持 watcher（Stop 仅表示一轮结束）

### HTTP POST: /permission
- 方向: hooks/permission.py -> api.py
- 参数: `{ description: str, session_id: str, chat_id?: int, thread_id?: int }`
- 返回值: `{ decision: "allow" | "deny", reason?: str }`
- 超时: 120 秒（超时返回 deny）
- 副作用: 向 TG 话题发送 InlineKeyboard 审批按钮，挂起 HTTP 请求直到用户点击或超时

### HTTP POST: /notification
- 方向: hooks/notification.py -> api.py
- 参数: `{ message: str, session_id: str, chat_id?: int, thread_id?: int }`
- 返回值: `{ status: "ok" }`
- 错误: 503 (无可用聊天 ID)

### HTTP GET: /health
- 方向: claude-pilot CLI / 外部监控 -> api.py
- 返回值: `{ status: "running" }`

### 内部接口: session.inject_message
- 方向: handlers/messages.py -> session.py
- 流程:
  1. 获取 per-pane asyncio.Lock
  2. 调用 `detect_tui_state(pane_id)` 获取当前 TUI 状态
  3. 根据状态决定操作：
     - `INPUT`: 直接 load-buffer + paste-buffer + Enter
     - `GENERATING`: Escape 打断，等待 INPUT，再注入
     - `EXITED`: 抛出 SessionDead 异常
     - `PERMISSION_PROMPT`: 抛出 PermissionPending 异常（需先处理权限）
  4. 注入后 capture-pane 验证文本是否成功提交

### 内部接口: watcher.start_watcher
- 方向: api.py (http_session_start) / handlers/commands.py (cmd_projects) -> watcher.py
- 参数: session_id, transcript_path, chat_id, topic_id, source, pane_id, state, bot
- 返回值: asyncio.Task（watcher 协程任务引用，存入 State.sessions）
- 副作用: 创建后台 asyncio.Task 持续轮询 JSONL 文件

### 内部接口: config.save_state
- 方向: 多个模块（api.py, commands.py）-> config.py
- 触发时机: sessions 变更、group_chat_id 写入、notify_chat_id 写入
- 原子性: tempfile.mkstemp + os.rename，崩溃安全

---

## 4. 数据流

### 场景 1: 终端用户启动 Claude，TG 自动出现话题并实时同步

```
终端用户                                      手机用户
    |
    v
tmux 中运行 claude
    |
    v
Claude Code 触发 SessionStart hook
    |
    v
hooks/session_start.py
    |  读取 stdin JSON (session_id, transcript_path, cwd)
    |  读取 TMUX_PANE 环境变量
    v
HTTP POST /session_start -> api.py
    |
    +---> config.save_state() 注册会话
    |
    +---> bot.create_forum_topic() 创建 TG 话题
    |                                              |
    +---> watcher.start_watcher() 启动监听          v
              |                              手机看到新话题
              v
         每 0.5 秒轮询:
         1. JSONL seek/read 增量数据
         2. capture-pane 检测 TUI 状态
              |
              v
         解析 assistant 事件 -> renderer.render_markdown()
              |                      -> renderer.split_message()
              v
         send_buffer 累积 -> 1.5 秒间隔 flush
              |
              v                                    |
         bot.send_message(topic_id)  ------------> v
                                             手机看到 Claude 输出

(手机用户在话题中发消息)                      <---- 手机用户
              |
              v
         handlers/messages.py
              |  获取 per-topic Lock
              |  查找 session (source="terminal")
              v
         session.inject_message(pane_id, text)
              |  获取 per-pane Lock
              |  detect_tui_state -> INPUT
              |  load-buffer + paste-buffer + Enter
              v
         tmux -> Claude Code TUI 收到输入
```

### 场景 2: 手机发起新任务（TG -> Claude）

```
手机用户
    |
    v
/projects 命令 -> handlers/commands.py
    |
    v
InlineKeyboard 列出项目目录
    |
    v
用户点选 -> handlers/callbacks.py
    |
    +---> bot.create_forum_topic() 创建话题
    |
    +---> session.launch_session(project_dir)
    |        |
    |        v
    |     tmux new-window -t claude-pilot -n "cp-{id}" "claude --resume {sid}"
    |
    +---> watcher.start_watcher() 启动监听
    |
    +---> config.save_state() 持久化
    |
    v
用户在话题中发消息 -> handlers/messages.py
    |
    v
session.inject_message(pane_id, text)
    |  detect_tui_state -> INPUT
    |  load-buffer + paste-buffer + Enter
    v
Claude Code 处理 -> JSONL 写入 -> watcher 检测
    |
    v
watcher _process_event:
    source="telegram" -> 跳过 user 事件推送（去重）
    推送 assistant 事件 -> renderer -> send_to_topic
```

### 场景 3: 权限审批（两层通道）

```
=== Hook 层（正常工具权限）===

Claude Code 执行 Bash/Edit/Write
    |
    v
PreToolUse hook -> hooks/permission.py
    |
    v
HTTP POST /permission -> api.py
    |
    +---> 检查 permission_enabled (/bypass 开关)
    |     - False: 直接返回 { decision: "allow" }
    |     - True: 继续
    |
    +---> 生成 request_id, 创建 asyncio.Event
    |
    +---> 向 TG 话题发送 InlineKeyboard [允许] [拒绝]
    |
    +---> await event.wait(timeout=120s)    <---- 手机用户
    |                                              |
    |     用户点击 -> callbacks.py                  |
    |       设置 decision, event.set()              |
    |                                              v
    +---> 返回 { decision: "allow" | "deny" }
    |
    v
hooks/permission.py 输出 JSON -> Claude Code 继续/中止

=== TUI 层（硬编码权限提示）===

Claude Code 弹出 "Do you want to modify config files? (y/n)"
    |
    v
watcher._check_tui_state()
    |  capture-pane 检测到 PERMISSION_PROMPT 状态
    v
    +---> 提取权限提示文本
    +---> 向 TG 话题发送 InlineKeyboard [允许] [拒绝]
    |     callback_data: "tui_allow:{pane_id}" / "tui_deny:{pane_id}"
    |
    +---> 等待用户点击               <---- 手机用户
    |                                       |
    v                                       v
callbacks.py handle_button:
    prefix "tui_allow:" -> session.respond_tui_permission(pane_id, True)
                              |
                              v
                        tmux send-keys -t {pane_id} y Enter
```

### 场景 4: Bot 崩溃与恢复

```
Bot 进程异常退出
    |
    v
crash_reporter.py (独立进程, 每 10 秒检查)
    |  读取 .pid 文件
    |  os.kill(pid, 0) 失败 -> Bot 已挂
    v
    +---> 读取 bot.log 最后 50 行，提取 Traceback
    +---> urllib POST Telegram API -> 私聊通知管理员
    |     "Claude Pilot 崩溃\n错误: ...\n今日重启次数: N"
    v
launchd KeepAlive=true
    |  30 秒内自动拉起 Bot
    v
Bot 重启 -> bot.py main()
    |
    +---> config.load_state() 恢复 .state.json
    +---> 遍历 sessions，对存活的 tmux 窗口重新启动 watcher
    +---> 写入新 .pid 文件
    v
crash_reporter 检测到新 PID 存活
    |
    v
urllib POST -> 私聊通知："Bot 已恢复，停机 {N} 秒"
```

### 场景 5: /setup 引导配置群组

```
手机用户私聊 Bot
    |
    v
/setup -> handlers/commands.py cmd_setup
    |
    v
发送消息："第 1 步：新建一个 Telegram 群组"
    + InlineKeyboard [点我开始建群]（deep link 跳转 TG 建群界面）
    |
    v                                    <---- 手机用户建群
用户点击 [已添加] -> callbacks.py
    |
    v
轮询 bot.get_updates() / get_my_chat_member()
    检测 Bot 是否被加入新群组
    |
    v
检测成功 -> 获取群组 chat_id
    |
    +---> state.group_chat_id = chat_id
    +---> config.save_state() 持久化
    +---> 发送："配置完成！去群里发 /help 开始使用"
```

---

## 5. 目录结构

```
~/.claude-pilot/
|-- install.sh                  # 一键安装脚本 (Bash)
|-- claude-pilot                # CLI 入口脚本 (Python + argparse)
|
|-- bot.py                      # 启动入口 + Application 组装 (~60 行)
|-- config.py                   # 配置加载 (.env) + 状态持久化 (.state.json) (~50 行)
|-- session.py                  # 会话管理 + tmux 操作 + TUI 状态感知 (~180 行)
|-- watcher.py                  # JSONL 监听 + 消息合并防 429 + TUI 权限检测 (~150 行)
|-- renderer.py                 # Markdown -> TG HTML + 智能分段 (~80 行)
|-- api.py                      # aiohttp HTTP 路由 (127.0.0.1) (~80 行)
|
|-- handlers/
|   |-- __init__.py
|   |-- commands.py             # /setup /start /projects /resume /quit /delete 等命令
|   |-- messages.py             # 普通消息处理 (文本注入)
|   +-- callbacks.py            # InlineKeyboard 回调 (权限审批等)
|
|-- hooks/
|   |-- _common.py              # 共享工具: read_port(), post_to_bot()
|   |-- session_start.py        # SessionStart hook
|   |-- permission.py           # PreToolUse hook
|   |-- notification.py         # Notification hook
|   +-- stop.py                 # Stop hook
|
|-- crash_reporter.py           # 独立守护进程 (零外部依赖, 仅标准库)
|
|-- .env                        # 静态配置 (BOT_TOKEN, ALLOWED_USERS, BOT_PORT, PROJECT_DIR)
|-- .state.json                 # 运行时持久化 (group_chat_id, sessions, session_topics)
|-- .pid                        # Bot 进程 PID
|-- bot.log                     # 运行日志
|-- requirements.txt            # pip 依赖: python-telegram-bot, aiohttp, mistune
+-- tests/                      # 测试目录
    |-- __init__.py
    |-- test_config.py
    |-- test_session.py
    |-- test_watcher.py
    |-- test_renderer.py
    +-- test_api.py
```

---

## 6. 核心接口签名

### config.py

```python
from dataclasses import dataclass, field

@dataclass
class SessionInfo:
    session_id: str
    project_dir: str
    chat_id: int
    source: str                    # "terminal" | "telegram"
    tmux_window: str               # tmux 窗口名 (如 "cp-a3f2b1")
    tmux_pane: str | None          # tmux pane ID (如 "%5")
    transcript_path: str
    watcher_task: object | None = None  # asyncio.Task 引用 (不序列化)
    last_result: str = ""          # 最后一条 assistant 文本 (供 /retry)
    bypass_permission: bool = False  # 此会话的 Hook 层权限绕过开关

@dataclass
class State:
    group_chat_id: int | None = None
    notify_chat_id: int | None = None
    sessions: dict[int, SessionInfo] = field(default_factory=dict)      # topic_id -> SessionInfo
    session_topics: dict[str, int] = field(default_factory=dict)        # session_id -> topic_id
    permission_enabled: bool = True   # 全局 Hook 层权限审批开关

@dataclass
class Config:
    bot_token: str
    allowed_users: list[int]
    bot_port: int = 5000
    project_dir: str = "~/workspace"
    base_dir: str = "~/.claude-pilot"

def load_env(path: str) -> Config:
    """解析 .env 文件, 返回 Config 实例。"""
    ...

def load_state(path: str) -> State:
    """加载 .state.json, 返回 State 实例。文件不存在返回空 State。"""
    ...

def save_state(state: State, path: str) -> None:
    """原子写入 .state.json (tempfile + os.rename)。
    仅序列化可持久化字段, 跳过 watcher_task 等运行时引用。"""
    ...
```

### session.py

```python
import enum
import asyncio

class TuiState(enum.Enum):
    INPUT = "input"                    # 底部有 > 提示符, 可直接输入
    GENERATING = "generating"          # spinner / thinking, 需等待或打断
    EXITED = "exited"                  # shell prompt, 进程已退出
    PERMISSION_PROMPT = "permission"   # "Do you want to" / y/n, 需审批

class SessionDead(Exception):
    """tmux 窗口中 Claude 进程已退出"""
    pass

class PermissionPending(Exception):
    """TUI 层权限提示待处理"""
    pass

# TUI 状态特征字符串 (可配置, 便于 Claude Code TUI 更新后调整)
TUI_PATTERNS: dict[str, list[str]] = {
    "input_prompt": [">"],
    "generating": ["thinking", "..."],
    "exited": ["$", "%", "#"],
    "permission": ["Do you want to", "(y/n)"],
}

# 控制字符过滤正则
CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
# ANSI 转义序列过滤正则
ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

async def launch_session(
    project_dir: str,
    state: "State",
    bot: "Bot",
    chat_id: int,
    topic_id: int,
    session_id: str | None = None,
) -> SessionInfo:
    """在 tmux claude-pilot session 中创建新窗口并启动 Claude。
    返回注册好的 SessionInfo。"""
    ...

async def inject_message(pane_id: str, text: str) -> None:
    """状态感知式消息注入:
    1. 获取 per-pane Lock
    2. detect_tui_state
    3. 根据状态操作 (INPUT: 直接注入, GENERATING: Escape + 等待 + 注入)
    4. capture-pane 验证注入成功
    Raises: SessionDead, PermissionPending
    """
    ...

async def interrupt_session(pane_id: str) -> None:
    """发送 Escape 打断 Claude 当前生成。"""
    ...

async def kill_session(window_name: str) -> None:
    """销毁 tmux 窗口, 终止 Claude 进程。"""
    ...

async def detect_tui_state(pane_id: str) -> TuiState:
    """capture-pane + 内容分析, 返回当前 TUI 状态。
    检测优先级: PERMISSION_PROMPT > EXITED > GENERATING > INPUT"""
    ...

async def respond_tui_permission(pane_id: str, allow: bool) -> None:
    """TUI 层权限响应: send-keys y/n + Enter。"""
    ...

def get_topic_lock(topic_id: int) -> asyncio.Lock:
    """获取或创建 per-topic Lock (防止同一话题并发操作)。"""
    ...

def get_tmux_lock(pane_id: str) -> asyncio.Lock:
    """获取或创建 per-pane Lock (防止并发 tmux 注入交叉)。"""
    ...

async def list_tmux_windows() -> list[dict[str, str]]:
    """列出 claude-pilot tmux session 下的所有窗口。
    返回: [{"window_name": "cp-a3f2", "pane_id": "%5"}, ...]"""
    ...
```

### watcher.py

```python
import asyncio

# 消息合并配置
FLUSH_INTERVAL: float = 1.5    # 合并刷新间隔 (秒)
MAX_RETRY: int = 3             # 发送失败最大重试次数
POLL_INTERVAL: float = 0.5    # 轮询间隔 (秒)

async def start_watcher(
    session_id: str,
    transcript_path: str,
    chat_id: int,
    topic_id: int,
    source: str,
    pane_id: str | None,
    state: "State",
    bot: "Bot",
) -> asyncio.Task:
    """启动 JSONL 文件监听 + TUI 状态检测任务。
    返回 asyncio.Task 引用 (存入 SessionInfo.watcher_task)。"""
    ...

def stop_watcher(topic_id: int, state: "State") -> None:
    """停止指定话题的 watcher 任务 (cancel task)。"""
    ...
```

### renderer.py

```python
def render_markdown(text: str) -> str:
    """将 Markdown 文本转为 Telegram 支持的 HTML 子集。
    使用 mistune + TelegramHTMLRenderer。"""
    ...

def split_message(html: str, limit: int = 4096) -> list[str]:
    """在段落边界处切分 HTML, 确保每段 <= limit 字符。
    不在 HTML 标签中间切分。"""
    ...

def format_tool_use(name: str, input_data: dict) -> str:
    """格式化工具调用为人类可读摘要。
    Bash -> '执行命令: {command}'
    Edit -> '编辑文件: {file_path}'
    Write -> '写入文件: {file_path}'
    其他 -> '{name}: {json[:200]}'"""
    ...
```

### api.py

```python
from aiohttp import web

@dataclass
class PermissionRequest:
    description: str
    event: asyncio.Event
    decision: str | None = None

# 模块级变量, 供 callbacks.py 访问
pending_permissions: dict[str, PermissionRequest] = {}

def create_api_app(
    state: "State",
    config: "Config",
    bot: "Bot",
) -> web.Application:
    """创建并配置 aiohttp Application, 注册所有 HTTP 路由。
    所有路由通过闭包捕获 state/config/bot 引用。"""
    ...
```

### crash_reporter.py

```python
# 独立脚本, 无项目内部依赖, 仅使用标准库
# 由 launchd 单独 plist 托管

CHECK_INTERVAL: int = 10          # 检查间隔 (秒)
MAX_LOG_LINES: int = 50           # 读取日志尾部行数
RESTART_WARN_THRESHOLD: int = 5   # 连续重启警告阈值

def main() -> None:
    """主循环: 每 CHECK_INTERVAL 秒检查 Bot PID 存活。"""
    ...
```

### hooks/_common.py

```python
def read_port() -> str:
    """从 ~/.claude-pilot/.env 读取 BOT_PORT, 默认 '5000'。"""
    ...

def post_to_bot(endpoint: str, payload: dict, timeout: int = 10) -> dict | None:
    """向 http://127.0.0.1:{PORT}/{endpoint} 发送 POST 请求。
    失败返回 None (不干预 Claude Code 流程)。"""
    ...
```
