# Phase 1 接口定义

## config.py 接口

### 数据类: Config
- 字段: bot_token (str), allowed_users (list[int]), bot_port (int, 默认 8266), project_dir (str)

### 数据类: State
- 字段: group_chat_id (int|None), notify_chat_id (int|None), sessions (dict[str, dict]), session_topics (dict[str, int])

### 数据类: SessionInfo
- 字段: session_id (str), transcript_path (str), cwd (str), pane_id (str|None), topic_id (int), source (str)

### 函数: load_env
- 签名: `load_env(path: str) -> dict[str, str]`
- 行为: 解析 .env 文件，忽略空行和 # 注释行，支持 KEY=VALUE 格式
- 返回: 键值对字典

### 函数: load_state
- 签名: `load_state(path: str) -> State`
- 行为: 读取 JSON 文件并构造 State 对象；文件不存在时返回空 State
- 返回: State 实例

### 函数: save_state
- 签名: `save_state(state: State, path: str) -> None`
- 行为: 原子写入（tempfile.mkstemp 写入同目录临时文件，再 os.rename）
- 副作用: 写入 JSON 文件

## session.py 底层接口

### 枚举: TuiState
- 值: INPUT, GENERATING, EXITED, PERMISSION_PROMPT

### 常量: TUI_PATTERNS
- 类型: dict[str, list[str]]
- 值: input_prompt=[">"], generating=["thinking","..."], exited=["$","%","#"], permission=["Do you want to","(y/n)"]

### 常量: CONTROL_CHAR_RE, ANSI_ESCAPE_RE
- 正则表达式，用于过滤控制字符和 ANSI 转义序列

### 函数: detect_tui_state
- 签名: `async detect_tui_state(pane_id: str) -> TuiState`
- 行为: capture-pane -> 过滤 -> 取最后 5 行 -> 优先级匹配 (permission > exited > generating > input)
- 默认返回: GENERATING（均未匹配时）

### 函数: _tmux_exec
- 签名: `async _tmux_exec(*args: str) -> str`
- 行为: asyncio.create_subprocess_exec 执行 tmux 命令

### 函数: _capture_pane
- 签名: `async _capture_pane(pane_id: str) -> str`
- 行为: 调用 _tmux_exec capture-pane，过滤控制字符和 ANSI 序列

### 函数: get_topic_lock / get_tmux_lock
- 签名: `get_topic_lock(topic_id: int) -> asyncio.Lock` / `get_tmux_lock(pane_id: str) -> asyncio.Lock`
- 行为: 懒创建锁并缓存

## renderer.py 接口

### 类: TelegramHTMLRenderer(mistune.HTMLRenderer)
- 覆盖方法支持: bold->b, italic->i, code->code, codespan->code, link->a, heading->b, image->a
- 不支持标签降级: h1-h6->b, img->a, hr->分割线, table->pre

### 函数: render_markdown
- 签名: `render_markdown(text: str) -> str`
- 行为: 使用 TelegramHTMLRenderer 渲染 Markdown 为 TG HTML

### 函数: split_message
- 签名: `split_message(html: str, limit: int = 4096) -> list[str]`
- 行为: 按段落边界切分，确保每段 <= limit 字符，不在 HTML 标签中间切分

### 函数: format_tool_use
- 签名: `format_tool_use(name: str, input_data: dict) -> str`
- 行为: 格式化工具调用摘要（Bash 显示 command, Edit/Write 显示 file_path, 其他显示 JSON 摘要）
