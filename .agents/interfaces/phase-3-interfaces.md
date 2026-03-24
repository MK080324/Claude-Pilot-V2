# Phase 3 接口定义

## watcher.py 接口

### 函数: start_watcher
- 签名: `async start_watcher(session_id: str, transcript_path: str, chat_id: int, topic_id: int, source: str, pane_id: str | None, state: State, bot: Bot) -> asyncio.Task`
- 行为: 创建 _watch_loop 异步任务并注册到 _active_watchers
- 返回: asyncio.Task

### 函数: stop_watcher
- 签名: `stop_watcher(topic_id: int) -> None`
- 行为: 取消并移除 _active_watchers[topic_id] 任务

### 内部: _active_watchers
- 类型: `dict[int, asyncio.Task]`

### 内部: _watch_loop
- 签名: `async _watch_loop(session_id, transcript_path, chat_id, topic_id, source, pane_id, state, bot) -> None`
- 行为: 0.5s 轮询，每个周期串行执行：
  1. _read_jsonl_incremental 增量读取
  2. 对每个事件调用 _process_event
  3. _check_tui_state（如 pane_id 存在）
  4. 检查是否需要 _flush_buffer

### 内部: _read_jsonl_incremental
- 签名: `_read_jsonl_incremental(path: str, last_pos: int) -> tuple[list[dict], int]`
- 行为: file.seek(last_pos)，逐行读取解析 JSON，返回 (事件列表, 新 position)

### 内部: _process_event
- 签名: `_process_event(event: dict, seen_uuids: set, source: str, send_buffer: list) -> None`
- 行为:
  - UUID 去重: event["uuid"] 在 seen_uuids 中则跳过
  - source 去重: source=="telegram" 且 event role=="user" 且 userType=="external" 则跳过
  - internal 过滤: role=="user" 且 userType=="internal" 则跳过
  - assistant 事件: 提取 text content 和 tool_use content，格式化后追加到 send_buffer
  - user 事件（通过过滤后）: 格式化用户消息追加到 send_buffer

### 内部: _flush_buffer
- 签名: `async _flush_buffer(send_buffer: list, chat_id: int, topic_id: int, bot: Bot, last_flush_time: float) -> float`
- 行为: 合并 buffer 为一条消息，调用 bot.send_message 发送，失败时指数退避重试（1s/2s/4s，最多 3 次）
- 返回: 新的 last_flush_time

### 内部: _check_tui_state
- 签名: `async _check_tui_state(pane_id: str, chat_id: int, topic_id: int, session_id: str, bot: Bot) -> None`
- 行为: 调用 detect_tui_state，PERMISSION_PROMPT 时发送审批消息（InlineKeyboard 按钮）

### 常量
- POLL_INTERVAL = 0.5
- FLUSH_INTERVAL = 1.5
- MAX_RETRIES = 3
- RETRY_DELAYS = [1, 2, 4]
