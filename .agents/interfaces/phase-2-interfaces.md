# Phase 2 接口定义

## api.py 接口

### 函数: create_api_app
- 签名: `create_api_app(state: State, bot: Bot) -> web.Application`
- 行为: 创建 aiohttp app，注册路由，绑定 127.0.0.1
- 路由: POST /session_start, POST /session_stop, POST /permission, POST /notification, GET /health

### HTTP POST: /session_start
- 参数: `{ session_id: str, transcript_path: str, cwd: str, tmux_pane: str | null }`
- 返回: `{ status: "created" | "exists" | "no_group", topic_id?: int }`
- session_id 校验: `re.match(r'^[a-f0-9\-]{8,36}$', session_id)`，不合法返回 400

### HTTP POST: /session_stop
- 参数: `{ session_id: str, message: str, chat_id?: int, thread_id?: int }`
- 返回: `{ status: "ok" }`

### HTTP POST: /permission
- 参数: `{ description: str, session_id: str, chat_id?: int, thread_id?: int }`
- 返回: `{ decision: "allow" | "deny", reason?: str }`
- 超时: 120 秒（测试中可缩短为 1 秒），超时返回 deny

### HTTP POST: /notification
- 参数: `{ message: str, session_id: str, chat_id?: int, thread_id?: int }`
- 返回: `{ status: "ok" }`

### HTTP GET: /health
- 返回: `{ status: "running" }`

### 数据类: PermissionRequest
- 字段: description (str), session_id (str), event (asyncio.Event), decision (str), reason (str)

### 模块级变量: pending_permissions
- 类型: dict[str, PermissionRequest]

## session.py 高层接口（追加）

### 函数: launch_session
- 签名: `async launch_session(project_dir: str, state: State, bot: object) -> SessionInfo`
- 行为: 生成 session_id (uuid4 前 8 位)，tmux new-window 启动 claude --resume，返回 SessionInfo

### 函数: inject_message
- 签名: `async inject_message(pane_id: str, text: str) -> None`
- 行为: 获取 per-pane Lock -> detect_tui_state -> INPUT 直接注入 / GENERATING 先 Escape 再注入 / EXITED 抛 SessionDead / PERMISSION_PROMPT 抛 PermissionPending

### 函数: interrupt_session
- 签名: `async interrupt_session(pane_id: str) -> None`
- 行为: send-keys Escape

### 函数: kill_session
- 签名: `async kill_session(window_name: str) -> None`
- 行为: tmux kill-window

### 函数: respond_tui_permission
- 签名: `async respond_tui_permission(pane_id: str, allow: bool) -> None`
- 行为: send-keys "y" 或 "n"

### 函数: list_tmux_windows
- 签名: `async list_tmux_windows() -> list[dict]`
- 行为: tmux list-windows 解析输出

### 异常类: SessionDead, PermissionPending
- 继承 Exception

## hooks/_common.py 接口

### 函数: read_port
- 签名: `read_port() -> str`
- 行为: 从 ~/.claude-pilot/.env 读取 BOT_PORT，默认 "8266"

### 函数: post_to_bot
- 签名: `post_to_bot(endpoint: str, payload: dict, timeout: int = 10) -> dict | None`
- 行为: urllib POST 到 http://127.0.0.1:{port}{endpoint}

## hooks 脚本接口

### session_start.py
- stdin: JSON `{ session_id, type, transcript_path, cwd }`
- 行为: 读 stdin，加 TMUX_PANE env，POST /session_start

### permission.py
- stdin: JSON `{ tool_name, tool_input, session_id }`
- stdout: JSON `{ decision }` (给 Claude Code)
- 行为: 构建 description，POST /permission，返回 decision

### notification.py
- stdin: JSON `{ message, session_id }`
- 行为: POST /notification

### stop.py
- stdin: JSON `{ session_id, message }`
- 行为: POST /session_stop

## bot.py 接口

### 函数: main
- 签名: `async main() -> None`
- 行为: 加载配置、构建 TG Application、启动 aiohttp server (127.0.0.1:port)、启动 polling、写 .pid、信号处理、优雅关闭
- handler 注册区域标记: `# --- Handler Registration (dev-ext maintains below this line) ---`
