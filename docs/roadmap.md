# 开发路线图

## Phase 概览

| Phase | 目标 | 前置依赖 | 可并行 | 预估复杂度 |
|-------|------|---------|--------|-----------|
| 0 | 脚手架搭建 | 无 | 否 | 低 |
| 1 | 核心基础模块（config + renderer + session tmux 封装） | Phase 0 | 是（3 路并行） | 中 |
| 2 | Bot 骨架与 HTTP API（bot.py + api.py + hooks） | Phase 1 | 是（2 路并行） | 中 |
| 3 | JSONL 监听与消息推送（watcher.py） | Phase 2 | 否 | 高 |
| 4 | Telegram 命令与消息处理（handlers/*） | Phase 3 | 是（3 路并行） | 高 |
| 5 | 可观测性（crash_reporter + CLI + launchd） | Phase 4 | 是（2 路并行） | 中 |
| 6 | 安装脚本与端到端集成 | Phase 5 | 否 | 中 |

---

## Phase 0: 基础设施搭建

### 目标

项目脚手架、依赖安装、开发环境就位，所有模块文件创建为空壳（含接口签名），确保 import 链完整。

### 任务列表

| 任务 | 说明 |
|------|------|
| 创建目录结构 | 创建 `~/.claude-pilot/`（开发期使用项目内 `src/` 目录，部署时映射到 `~/.claude-pilot/`）、`handlers/`、`hooks/`、`tests/` 目录 |
| 创建 requirements.txt | 写入 `python-telegram-bot>=22.0,<23.0`、`aiohttp>=3.9,<4.0`、`mistune>=3.0,<4.0`，开发依赖加入 `pytest>=8.0`、`pytest-asyncio>=0.24` |
| 安装依赖 | `pip install -r requirements.txt` |
| 创建所有模块空壳文件 | bot.py、config.py、session.py、watcher.py、renderer.py、api.py、handlers/__init__.py、handlers/commands.py、handlers/messages.py、handlers/callbacks.py、hooks/_common.py、hooks/session_start.py、hooks/permission.py、hooks/notification.py、hooks/stop.py、crash_reporter.py、claude-pilot（CLI 脚本） |
| 填充接口签名 | 每个模块填入 structure.md 中定义的类、函数签名和 docstring，函数体为 `raise NotImplementedError` 或 `pass` |
| 创建 pytest 配置 | 创建 `pyproject.toml` 或 `pytest.ini`，配置 pytest-asyncio |
| 创建空测试文件 | tests/__init__.py、tests/test_config.py、tests/test_session.py、tests/test_watcher.py、tests/test_renderer.py、tests/test_api.py |

### 验收标准

| 验收项 | 验证命令/方式 | 通过标准 |
|--------|-------------|---------|
| 依赖安装成功 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -c "import telegram; import aiohttp; import mistune; print('OK')"` | 输出 `OK` |
| 模块 import 链完整 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "import config; import session; import watcher; import renderer; import api; import handlers.commands; import handlers.messages; import handlers.callbacks; print('OK')"` | 输出 `OK` |
| hooks 脚本可解析 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "import hooks._common; print('OK')"` | 输出 `OK` |
| pytest 可发现测试 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest --collect-only tests/` | 退出码 0，显示 collected 条目 |
| 接口签名存在 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "from config import Config, State, SessionInfo, load_env, load_state, save_state; from session import TuiState, launch_session, inject_message, detect_tui_state; from watcher import start_watcher, stop_watcher; from renderer import render_markdown, split_message, format_tool_use; from api import create_api_app, PermissionRequest; print('OK')"` | 输出 `OK` |
| 每个文件行数 < 200 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "import os; files=[f for f in os.listdir('.') if f.endswith('.py')]+[os.path.join('handlers',f) for f in os.listdir('handlers') if f.endswith('.py')]+[os.path.join('hooks',f) for f in os.listdir('hooks') if f.endswith('.py')]; violations=[f for f in files if sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"` | 输出 `OK` |

### 负责人

Lead 独立完成（Phase 0 不需要 Team）

---

## Phase 1: 核心基础模块

### 目标

实现三个无外部交互依赖的底层模块：config.py（配置加载与状态持久化）、renderer.py（Markdown 渲染与智能分段）、session.py 的 tmux 封装层（底层 tmux 命令执行、TUI 状态检测、控制字符过滤）。这三个模块是后续所有功能的基础。

### 任务列表

| 任务 | 说明 | 负责 Agent |
|------|------|-----------|
| 实现 config.py | Config/State/SessionInfo 数据类、load_env 解析 .env、load_state/save_state 原子读写 .state.json | agent-config |
| 实现 renderer.py | TelegramHTMLRenderer（继承 mistune.HTMLRenderer）、render_markdown、split_message 智能分段、format_tool_use 工具摘要 | agent-renderer |
| 实现 session.py tmux 底层 | _tmux_exec 封装、_capture_pane（含控制字符/ANSI 过滤）、detect_tui_state（四种状态检测）、TUI_PATTERNS 配置常量、CONTROL_CHAR_RE/ANSI_ESCAPE_RE 正则 | agent-session |
| 编写 tests/test_config.py | 测试 load_env、load_state、save_state（含原子性验证）、Config/State 数据类 | agent-config |
| 编写 tests/test_renderer.py | 测试 render_markdown（各种 Markdown 元素）、split_message（边界切分）、format_tool_use | agent-renderer |
| 编写 tests/test_session.py 底层部分 | 测试 detect_tui_state（mock capture-pane 输出，验证四种状态识别）、控制字符过滤、TUI_PATTERNS 匹配逻辑 | agent-session |

### 并行策略

| Agent | 负责文件/目录 |
|-------|-------------|
| agent-config | src/config.py, tests/test_config.py |
| agent-renderer | src/renderer.py, tests/test_renderer.py |
| agent-session | src/session.py, tests/test_session.py |

三个 Agent 完全独立，无共享文件编辑冲突。session.py 在本 Phase 仅实现 tmux 底层封装和状态检测，不依赖 config.py（锁管理和 launch_session 在 Phase 2 实现）。

### 验收标准

#### 自动验收（阻塞后续 Phase）

| 验收项 | 验证命令/方式 | 通过标准 |
|--------|-------------|---------|
| config 单元测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_config.py -v` | 全部通过，退出码 0 |
| config load_env 解析正确 | 测试中包含：创建临时 .env 文件 -> load_env -> 验证 Config 字段值 | assert 全部通过 |
| config save_state 原子性 | 测试中包含：save_state 写入 -> 验证文件存在且 JSON 可解析 -> 验证不存在 .tmp 残留文件 | assert 全部通过 |
| config load_state 空文件处理 | 测试中包含：对不存在的文件调用 load_state -> 返回空 State 对象 | assert 全部通过 |
| renderer 单元测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_renderer.py -v` | 全部通过，退出码 0 |
| renderer Markdown 转换正确 | 测试中包含：**bold** -> `<b>bold</b>`、`code` -> `<code>code</code>`、代码块 -> `<pre>`、链接 -> `<a>` | assert 全部通过 |
| renderer split_message 边界正确 | 测试中包含：4096+ 字符文本 -> 每段 <= 4096 字符 -> 不在 HTML 标签中间切分 | assert 全部通过 |
| renderer format_tool_use 正确 | 测试中包含：Bash/Edit/Write 工具调用格式化输出验证 | assert 全部通过 |
| session tmux 底层测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_session.py -v` | 全部通过，退出码 0 |
| session detect_tui_state 四种状态 | 测试中包含：mock capture-pane 返回值 -> 验证 INPUT/GENERATING/EXITED/PERMISSION_PROMPT 四种状态 | assert 全部通过 |
| session 控制字符过滤 | 测试中包含：含控制字符和 ANSI 序列的文本 -> 过滤后不含控制字符 | assert 全部通过 |
| 每个文件行数 < 200 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "violations=[(f,sum(1 for _ in open(f))) for f in ['config.py','renderer.py','session.py'] if sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"` | 输出 `OK` |

---

## Phase 2: Bot 骨架与 HTTP API

### 目标

实现 bot.py 启动入口（Telegram polling + aiohttp server 共存）、api.py HTTP 路由（/session_start、/session_stop、/permission、/notification、/health）、hooks/ 脚本（4 个 hook + _common.py）。完成 session.py 的高层接口（launch_session、inject_message、kill_session、锁管理）。Bot 能启动并响应 /health 请求。

### 任务列表

| 任务 | 说明 | 负责 Agent |
|------|------|-----------|
| 实现 api.py | create_api_app、5 个 HTTP 路由处理函数、PermissionRequest 数据类、pending_permissions 字典、session_id 白名单校验 | agent-api |
| 实现 hooks/ 全部脚本 | _common.py（read_port、post_to_bot）、session_start.py、permission.py、notification.py、stop.py | agent-hooks |
| 完善 session.py 高层接口 | launch_session（tmux new-window）、inject_message（状态感知注入）、interrupt_session、kill_session、get_topic_lock、get_tmux_lock、list_tmux_windows | agent-api |
| 实现 bot.py | main() 异步入口、Application 构建、aiohttp server 启动、polling 启动、信号处理、优雅关闭、.pid 文件写入 | agent-api |
| 编写 tests/test_api.py | 测试 HTTP 路由（aiohttp test client）、session_id 校验、/health 响应、/permission 超时逻辑 | agent-api |
| 编写 hooks 测试 | 测试 _common.py 的 read_port 和 post_to_bot（mock HTTP） | agent-hooks |
| 补充 tests/test_session.py 高层部分 | 测试 launch_session（mock tmux）、inject_message（mock detect_tui_state + tmux）、锁管理 | agent-api |

### 并行策略

| Agent | 负责文件/目录 |
|-------|-------------|
| agent-api | src/bot.py, src/api.py, src/session.py（高层接口部分，追加到 Phase 1 已有代码之后）, tests/test_api.py, tests/test_session.py（高层部分追加） |
| agent-hooks | src/hooks/_common.py, src/hooks/session_start.py, src/hooks/permission.py, src/hooks/notification.py, src/hooks/stop.py, tests/test_hooks.py（新建） |

注意：agent-api 编辑 session.py 时仅追加高层接口函数，不修改 Phase 1 已实现的底层函数。

### 接口定义（跨 Agent 协作）

agent-hooks 产出的 hook 脚本通过 HTTP POST 与 agent-api 产出的 api.py 通信。接口定义参照 structure.md 3.2 节：

- `POST /session_start`：参数 `{ session_id, transcript_path, cwd, tmux_pane }`，返回 `{ status, topic_id? }`
- `POST /session_stop`：参数 `{ session_id, message, chat_id?, thread_id? }`，返回 `{ status: "ok" }`
- `POST /permission`：参数 `{ description, session_id, chat_id?, thread_id? }`，返回 `{ decision }`
- `POST /notification`：参数 `{ message, session_id, chat_id?, thread_id? }`，返回 `{ status: "ok" }`
- `GET /health`：返回 `{ status: "running" }`

### 验收标准

#### 自动验收（阻塞后续 Phase）

| 验收项 | 验证命令/方式 | 通过标准 |
|--------|-------------|---------|
| api 单元测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_api.py -v` | 全部通过，退出码 0 |
| hooks 单元测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_hooks.py -v` | 全部通过，退出码 0 |
| session 高层测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_session.py -v` | 全部通过，退出码 0 |
| /health 路由响应正确 | test_api.py 中包含：aiohttp test client GET /health -> 状态码 200 -> JSON body 包含 `status: "running"` | assert 全部通过 |
| /permission 超时返回 deny | test_api.py 中包含：POST /permission -> 不触发审批 -> 等待超时（测试中缩短为 1 秒） -> 返回 `decision: "deny"` | assert 全部通过 |
| session_id 白名单校验 | test_api.py 中包含：POST /session_start 带非法 session_id（含特殊字符） -> 返回 400 | assert 全部通过 |
| hooks _common.py read_port | test_hooks.py 中包含：创建临时 .env -> read_port -> 返回正确端口号 | assert 全部通过 |
| hooks _common.py post_to_bot | test_hooks.py 中包含：mock HTTP server -> post_to_bot -> 验证请求 body 正确 | assert 全部通过 |
| bot.py 语法正确 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "import ast; ast.parse(open('bot.py').read()); print('OK')"` | 输出 `OK` |
| launch_session mock 测试 | test_session.py 中包含：mock tmux new-window -> launch_session -> 返回 SessionInfo -> 验证 tmux_window 和 pane_id 字段 | assert 全部通过 |
| inject_message 状态感知 | test_session.py 中包含：mock detect_tui_state 返回 INPUT -> inject_message -> 验证 load-buffer + paste-buffer 被调用 | assert 全部通过 |
| inject_message GENERATING 状态 | test_session.py 中包含：mock detect_tui_state 先返回 GENERATING 再返回 INPUT -> inject_message -> 验证 Escape 被发送后再注入 | assert 全部通过 |
| per-topic Lock 互斥 | test_session.py 中包含：get_topic_lock 同一 topic_id 返回同一 Lock 实例 | assert 全部通过 |
| 127.0.0.1 绑定 | test_api.py 中包含：验证 create_api_app 配置中 host 为 "127.0.0.1" | assert 全部通过 |
| 每个文件行数 < 200 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "import os; files=['bot.py','api.py','session.py']+[os.path.join('hooks',f) for f in os.listdir('hooks') if f.endswith('.py')]; violations=[(f,sum(1 for _ in open(f))) for f in files if sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"` | 输出 `OK` |

---

## Phase 3: JSONL 监听与消息推送

### 目标

实现 watcher.py：JSONL 文件增量读取、事件解析与分发、消息合并防 429、去重逻辑（UUID 去重 + source 去重 + internal 过滤）、TUI 状态检测集成（与 JSONL 轮询共享 0.5s 节拍）。这是实现"完整对话流推送"的核心模块。

### 任务列表

| 任务 | 说明 | 负责 Agent |
|------|------|-----------|
| 实现 _watch_loop 主循环 | 0.5s 轮询间隔，串行执行 JSONL 增量读取 + TUI 状态检测 | agent-watcher |
| 实现 _read_jsonl_incremental | 基于 file.seek(last_pos) 的增量读取，解析每行 JSON | agent-watcher |
| 实现 _process_event | 解析 user/assistant 事件、UUID 去重、source 去重、internal 过滤、格式化输出 | agent-watcher |
| 实现 _flush_buffer 消息合并 | 1.5s 间隔合并发送、指数退避重试（1s/2s/4s，最多 3 次） | agent-watcher |
| 实现 _check_tui_state | 调用 session.detect_tui_state，检测到 PERMISSION_PROMPT 时发送 TG 审批按钮 | agent-watcher |
| 实现 start_watcher/stop_watcher | 创建/取消 asyncio.Task | agent-watcher |
| 编写 tests/test_watcher.py | 测试增量读取、事件解析、去重逻辑、消息合并、TUI 状态检测集成 | agent-watcher |

### 并行策略

本 Phase 不并行。watcher.py 是单一复杂模块，由一个 Agent 完成全部实现和测试。

| Agent | 负责文件/目录 |
|-------|-------------|
| agent-watcher | src/watcher.py, tests/test_watcher.py |

### 验收标准

#### 自动验收（阻塞后续 Phase）

| 验收项 | 验证命令/方式 | 通过标准 |
|--------|-------------|---------|
| watcher 单元测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_watcher.py -v` | 全部通过，退出码 0 |
| JSONL 增量读取 | 测试中包含：创建临时 JSONL 文件 -> 写入 3 行 -> _read_jsonl_incremental 返回 3 个事件 -> 追加 2 行 -> 再次调用返回 2 个新事件 | assert 全部通过 |
| UUID 去重 | 测试中包含：同一 uuid 的事件发送两次 -> _process_event 只处理一次（seen_uuids 检查） | assert 全部通过 |
| source 去重（telegram） | 测试中包含：source="telegram" 的 session -> userType="external" 的 user 事件 -> 不推送 | assert 全部通过 |
| source 不去重（terminal） | 测试中包含：source="terminal" 的 session -> userType="external" 的 user 事件 -> 正常推送 | assert 全部通过 |
| internal 事件过滤 | 测试中包含：userType="internal" 的 user 事件 -> 不推送 | assert 全部通过 |
| assistant 事件解析 | 测试中包含：assistant 事件含 text + tool_use content -> 正确提取文本和工具摘要 | assert 全部通过 |
| 消息合并机制 | 测试中包含：短时间内多个事件 -> 合并到一条消息发送 -> 验证 send 调用次数 < 事件数 | assert 全部通过 |
| 指数退避重试 | 测试中包含：mock send 失败 -> 验证重试间隔为 1s/2s/4s -> 最多 3 次 | assert 全部通过 |
| TUI 权限检测集成 | 测试中包含：mock detect_tui_state 返回 PERMISSION_PROMPT -> 验证审批按钮发送逻辑被调用 | assert 全部通过 |
| start_watcher 返回 Task | 测试中包含：start_watcher -> 返回值是 asyncio.Task -> task.cancel() 可正常取消 | assert 全部通过 |
| stop_watcher 取消任务 | 测试中包含：start_watcher -> stop_watcher -> 验证 task 已被 cancel | assert 全部通过 |
| watcher.py 行数 < 200 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "lines=sum(1 for _ in open('watcher.py')); print('OK' if lines<=200 else f'FAIL: {lines} lines')"` | 输出 `OK` |

---

## Phase 4: Telegram 命令与消息处理

### 目标

实现 handlers/ 目录下的三个模块：commands.py（全部 12 个斜杠命令）、messages.py（普通消息注入）、callbacks.py（InlineKeyboard 回调处理，含 Hook 层 + TUI 层权限审批响应）。完成全部 Telegram 交互逻辑。

### 任务列表

| 任务 | 说明 | 负责 Agent |
|------|------|-----------|
| 实现 handlers/commands.py | cmd_setup（/setup 三步引导）、cmd_start、cmd_projects（目录选择 InlineKeyboard）、cmd_resume（历史回显）、cmd_rename、cmd_interrupt、cmd_quit、cmd_delete（二次确认）、cmd_bypass、cmd_status（运行统计）、cmd_info、cmd_retry、cmd_setdir | agent-commands |
| 实现 handlers/messages.py | handle_message：鉴权检查 -> per-topic Lock -> 查找 session -> inject_message -> 异常处理（SessionDead/PermissionPending） | agent-messages |
| 实现 handlers/callbacks.py | handle_button：按 callback_data 前缀分发 -> Hook 层审批（allow:/deny: -> pending_permissions Event 设置）-> TUI 层审批（tui_allow:/tui_deny: -> session.respond_tui_permission）-> 目录选择（project:）-> 删除确认（delete_confirm:） | agent-callbacks |
| 更新 bot.py handler 注册 | 在 bot.py 中注册所有 CommandHandler、MessageHandler、CallbackQueryHandler | agent-commands |
| 编写 handlers 测试 | test_commands.py（mock Bot/Update 测试各命令）、test_messages.py、test_callbacks.py | 各 Agent 各自测试文件 |

### 并行策略

| Agent | 负责文件/目录 |
|-------|-------------|
| agent-commands | src/handlers/commands.py, src/bot.py（仅 handler 注册部分追加）, tests/test_commands.py（新建） |
| agent-messages | src/handlers/messages.py, tests/test_messages.py（新建） |
| agent-callbacks | src/handlers/callbacks.py, tests/test_callbacks.py（新建） |

三个 Agent 编辑不同文件。agent-commands 对 bot.py 的修改仅限于在已有的 handler 注册区域追加 `add_handler` 调用。

### 接口定义（跨 Agent 协作）

callbacks.py 需要访问 api.py 的 `pending_permissions` 字典和 session.py 的 `respond_tui_permission` 函数。这些接口在 Phase 2 已实现，本 Phase 仅使用。

callback_data 前缀约定（三个 Agent 共享）：
- `allow:{request_id}` / `deny:{request_id}` -- Hook 层权限审批（callbacks.py 处理）
- `tui_allow:{pane_id}` / `tui_deny:{pane_id}` -- TUI 层权限审批（callbacks.py 处理）
- `project:{path}` -- 目录选择（callbacks.py 处理，commands.py 发送按钮）
- `delete_confirm:{topic_id}` / `delete_cancel:{topic_id}` -- 删除确认（callbacks.py 处理，commands.py 发送按钮）

### 验收标准

#### 自动验收（阻塞后续 Phase）

| 验收项 | 验证命令/方式 | 通过标准 |
|--------|-------------|---------|
| commands 测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_commands.py -v` | 全部通过，退出码 0 |
| messages 测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_messages.py -v` | 全部通过，退出码 0 |
| callbacks 测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_callbacks.py -v` | 全部通过，退出码 0 |
| /status 命令输出格式 | test_commands.py 中包含：mock Bot 运行数据 -> cmd_status -> 验证输出包含"运行时长"、"活跃会话"、"今日重启" | assert 全部通过 |
| /bypass 命令切换 | test_commands.py 中包含：初始 permission_enabled=True -> cmd_bypass -> 变为 False -> 再次 cmd_bypass -> 变为 True | assert 全部通过 |
| /delete 二次确认 | test_commands.py 中包含：cmd_delete -> 发送确认按钮 -> 未点击确认 -> session 未被删除 | assert 全部通过 |
| /resume 历史回显 | test_commands.py 中包含：mock JSONL 文件含历史事件 -> cmd_resume -> 验证发送了历史摘要消息 | assert 全部通过 |
| messages 鉴权检查 | test_messages.py 中包含：非 ALLOWED_USERS 发送消息 -> 不处理（无 inject_message 调用） | assert 全部通过 |
| messages 无 session 提示 | test_messages.py 中包含：话题无关联 session -> 发送消息 -> 返回提示创建 session | assert 全部通过 |
| messages SessionDead 处理 | test_messages.py 中包含：inject_message 抛出 SessionDead -> 发送"会话已结束"提示 | assert 全部通过 |
| callbacks Hook 层审批 | test_callbacks.py 中包含：创建 pending PermissionRequest -> 模拟点击 allow:{id} -> event.is_set() 且 decision="allow" | assert 全部通过 |
| callbacks TUI 层审批 | test_callbacks.py 中包含：模拟点击 tui_allow:{pane_id} -> 验证 respond_tui_permission(pane_id, True) 被调用 | assert 全部通过 |
| callbacks 目录选择 | test_callbacks.py 中包含：模拟点击 project:{path} -> 验证 launch_session 被调用 | assert 全部通过 |
| bot.py handler 注册完整 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "import ast; tree=ast.parse(open('bot.py').read()); calls=[n for n in ast.walk(tree) if isinstance(n, ast.Call) and hasattr(n.func, 'attr') and n.func.attr=='add_handler']; print('OK' if len(calls)>=3 else f'FAIL: only {len(calls)} add_handler calls')"` | 输出 `OK` |
| 每个文件行数 < 200 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src/handlers && python3 -c "import os; violations=[(f,sum(1 for _ in open(f))) for f in os.listdir('.') if f.endswith('.py') and sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"` | 输出 `OK` |

#### 延迟人工验收（不阻塞，记录到 deferred-human-review.md）

| 验收项 | 原因（为什么不能自动化） |
|--------|----------------------|
| /setup 三步引导 UI 体验 | 需在手机 Telegram 上实际操作建群、加 Bot、设管理员，涉及 GUI 交互 |
| /projects 目录列表显示效果 | InlineKeyboard 按钮布局和目录名显示需人眼判断 |

---

## Phase 5: 可观测性

### 目标

实现 crash_reporter.py（独立守护进程）、claude-pilot CLI 脚本（start/stop/status/enable/disable/logs）、launchd plist 生成逻辑。完成三层可观测性：launchd 自动重启、crash_reporter 崩溃通知、/status 主动查询（/status 命令在 Phase 4 已实现）。

### 任务列表

| 任务 | 说明 | 负责 Agent |
|------|------|-----------|
| 实现 crash_reporter.py | _check_pid_alive、_extract_traceback、_send_telegram_message（urllib）、主循环（10s 间隔）、重启计数、连续 5 次警告 | agent-crash |
| 实现 claude-pilot CLI | argparse 子命令：start（tmux 中启动 bot.py）、stop（kill PID）、status（读取 .pid 检查存活）、enable（生成并加载 launchd plist）、disable（卸载并删除 plist）、logs（tail -f bot.log） | agent-cli |
| 编写 tests/test_crash_reporter.py | 测试 PID 检查、Traceback 提取、重启计数逻辑（mock urllib） | agent-crash |
| 编写 tests/test_cli.py | 测试 argparse 解析、status 子命令（mock .pid 文件）、enable 生成的 plist 内容正确性 | agent-cli |

### 并行策略

| Agent | 负责文件/目录 |
|-------|-------------|
| agent-crash | src/crash_reporter.py, tests/test_crash_reporter.py（新建） |
| agent-cli | src/claude-pilot（CLI 脚本）, tests/test_cli.py（新建） |

两个 Agent 完全独立，无共享文件。

### 验收标准

#### 自动验收（阻塞后续 Phase）

| 验收项 | 验证命令/方式 | 通过标准 |
|--------|-------------|---------|
| crash_reporter 测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_crash_reporter.py -v` | 全部通过，退出码 0 |
| CLI 测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_cli.py -v` | 全部通过，退出码 0 |
| crash_reporter PID 检查 | test_crash_reporter.py 中包含：mock os.kill(pid, 0) 成功 -> 返回 True；OSError -> 返回 False | assert 全部通过 |
| crash_reporter Traceback 提取 | test_crash_reporter.py 中包含：创建含 Traceback 的 log 文件 -> _extract_traceback 返回正确的错误信息 | assert 全部通过 |
| crash_reporter 重启计数 | test_crash_reporter.py 中包含：连续 5 次 PID 消失 -> 重启计数到 5 -> 触发警告逻辑 | assert 全部通过 |
| crash_reporter 零外部依赖 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "import ast; tree=ast.parse(open('crash_reporter.py').read()); imports=[n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)]+[n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]; third_party=[m for m in imports if m and m.split('.')[0] not in ('os','sys','json','time','urllib','signal','datetime','pathlib','re','traceback','tempfile','socket')]; print('OK' if not third_party else 'FAIL: '+str(third_party))"` | 输出 `OK` |
| CLI --help 输出 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 claude-pilot --help` | 退出码 0，输出包含 start/stop/status/enable/disable/logs |
| CLI status 子命令 | test_cli.py 中包含：创建 mock .pid 文件 -> 运行 status -> 输出包含"运行中"或"未运行" | assert 全部通过 |
| CLI enable plist 内容 | test_cli.py 中包含：运行 enable（mock 写入路径） -> 验证生成的 plist 包含 KeepAlive、RunAtLoad、ThrottleInterval=30 | assert 全部通过 |
| 每个文件行数 < 200 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "violations=[(f,sum(1 for _ in open(f))) for f in ['crash_reporter.py','claude-pilot'] if sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"` | 输出 `OK` |

#### 延迟人工验收（不阻塞，记录到 deferred-human-review.md）

| 验收项 | 原因（为什么不能自动化） |
|--------|----------------------|
| launchd plist 实际加载并工作 | 需要执行 `launchctl load` 系统命令，可能触发 macOS 安全提示 |
| 崩溃通知实际到达手机 | 需要真实 Telegram Bot Token 和网络连接，需手动 kill 进程后在手机确认通知 |
| Bot 崩溃后 30 秒内自动恢复 | 需要 launchd 实际运行环境验证 |

---

## Phase 6: 安装脚本与端到端集成

### 目标

实现 install.sh 一键安装脚本；运行全量测试套件确保所有模块协同工作；验证文件大小约束；确认项目交付完整性。

### 任务列表

| 任务 | 说明 | 负责 Agent |
|------|------|-----------|
| 实现 install.sh | 检测 claude/tmux/python3 依赖、克隆项目到 ~/.claude-pilot、pip install、收集 BOT_TOKEN 和 ALLOWED_USERS、写入 .env、合并 hooks 到 ~/.claude/settings.json（Python 内联 JSON 合并）、安装 CLI 到 PATH、后台启动 Bot | agent-install |
| 编写 install.sh 测试 | 验证脚本语法（bash -n）、验证各检测函数在模拟环境下的行为、验证 .env 写入格式、验证 hooks 合并逻辑 | agent-install |
| 全量集成测试 | 编写 tests/test_integration.py，测试跨模块协作流程（mock Telegram API 和 tmux） | agent-install |
| 全量回归测试 | 运行全部测试套件，确保无回归 | agent-install |

### 并行策略

本 Phase 不并行。install.sh 和集成测试需要全局视角。

| Agent | 负责文件/目录 |
|-------|-------------|
| agent-install | src/install.sh, tests/test_install.sh（Shell 测试）, tests/test_integration.py（新建） |

### 验收标准

#### 自动验收（阻塞交付）

| 验收项 | 验证命令/方式 | 通过标准 |
|--------|-------------|---------|
| install.sh 语法正确 | `bash -n /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src/install.sh` | 退出码 0 |
| install.sh shellcheck | `shellcheck /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src/install.sh` 或手动审查 | 无 error 级别问题（warning 可接受） |
| 全量测试套件通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/ -v --tb=short` | 全部通过，退出码 0 |
| 集成测试通过 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -m pytest tests/test_integration.py -v` | 全部通过，退出码 0 |
| 所有 .py 文件行数 < 200 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && python3 -c "import os; all_py=[]; [all_py.extend([os.path.join(r,f) for f in fs if f.endswith('.py')]) for r,_,fs in os.walk('.')]; violations=[(f,sum(1 for _ in open(f))) for f in all_py if sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"` | 输出 `OK` |
| requirements.txt 完整 | `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && python3 -c "import subprocess; r=subprocess.run(['pip','install','-r','requirements.txt','--dry-run'],capture_output=True,text=True); print('OK' if r.returncode==0 else 'FAIL: '+r.stderr)"` | 输出 `OK` |
| hooks JSON 合并逻辑 | test_install.sh 或 test_integration.py 中包含：模拟已有 settings.json -> install.sh 的 hooks 合并 -> 验证原有 hooks 未被覆盖且新 hooks 已添加 | assert/test 全部通过 |
| .env 格式正确 | test_integration.py 中包含：模拟 install.sh 生成的 .env -> load_env 解析成功 -> Config 字段完整 | assert 全部通过 |
| 集成测试: Hook -> API -> Watcher 链路 | test_integration.py 中包含：模拟 hook POST /session_start -> 验证 session 注册 + watcher 启动 + 话题创建 | assert 全部通过 |
| 集成测试: 消息注入链路 | test_integration.py 中包含：模拟 TG 消息 -> messages.py -> session.inject_message -> 验证 tmux 命令序列 | assert 全部通过 |
| 集成测试: 权限审批全链路 | test_integration.py 中包含：模拟 hook POST /permission -> TG 发送审批按钮 -> callbacks.py 处理 -> 返回 decision | assert 全部通过 |

#### 延迟人工验收（不阻塞，记录到 deferred-human-review.md）

| 验收项 | 原因（为什么不能自动化） |
|--------|----------------------|
| install.sh 在全新 macOS 上端到端运行 | 需要全新 macOS 环境，涉及 brew install、网络下载、Telegram API 交互 |
| /setup 到群组配置完成全流程 | 需要手机操作 Telegram：建群、加 Bot、设管理员 |
| 消息延迟 < 3 秒 | 需要真实 Telegram 环境，Claude 输出到 TG 收到的端到端延迟测量 |
| 并发安全（同话题连发 5 条消息） | 需要真实 Telegram 环境和真实 Claude 会话 |
| TUI 权限审批端到端 | 需要触发 Claude Code 修改 .claude/ 文件的真实场景，在手机上确认审批流程 |
| 完整对话流显示效果 | 需人眼判断 TG 话题中 user + assistant 消息的格式和可读性 |
| 历史回显显示效果 | /resume 后的摘要内容需人眼判断可读性和完整性 |

---

## MVP 范围

### 包含

- config.py 配置加载与状态持久化
- renderer.py Markdown 渲染与智能分段
- session.py 会话管理与 tmux 操作（含 TUI 状态感知）
- watcher.py JSONL 监听与完整对话流推送
- api.py HTTP API 路由（5 个端点）
- bot.py 启动入口（Telegram polling + aiohttp 共存）
- handlers/ 全部 12 个 Telegram 命令 + 消息处理 + 按钮回调
- hooks/ 全部 4 个 Claude Code hook 脚本 + 共享工具
- crash_reporter.py 崩溃检测与通知
- claude-pilot CLI（start/stop/status/enable/disable/logs）
- install.sh 一键安装脚本
- 两层权限审批通道（Hook 层 + TUI 层）
- 消息合并防 429 机制
- per-topic / per-pane asyncio.Lock 并发控制
- .state.json 原子持久化与重启恢复
- 完整单元测试 + 集成测试套件

### 不包含（后续版本）

- Linux 系统支持（当前仅 macOS launchd）
- Telegram Bot 内联模式（inline query）
- 多用户权限分级（当前所有 ALLOWED_USERS 权限相同）
- Web UI 仪表盘
- 会话录制与回放
- 自动更新机制（auto-update）
- Docker 容器化部署
- 多语言 i18n 支持
