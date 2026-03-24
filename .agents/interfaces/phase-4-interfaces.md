# Phase 4 接口定义

## handlers/commands.py

每个命令对应一个 `async def cmd_xxx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`

### cmd_setup
- 三步引导：1) 检查是否群组消息 2) 保存 group_chat_id 3) 回复确认
- 依赖: config.save_state, context.bot_data["state"], context.bot_data["base_dir"]

### cmd_start
- 私聊初始化，保存 notify_chat_id
- 依赖: config.save_state

### cmd_projects
- 列出 PROJECT_DIR 下子目录，发送 InlineKeyboard
- callback_data: `project:{path}`
- 依赖: config (PROJECT_DIR), os.listdir

### cmd_resume
- 列出 state.sessions，选择后启动 watcher，发送历史摘要
- 依赖: state.sessions, watcher.start_watcher

### cmd_rename
- 从消息参数获取新名称，调用 bot.edit_forum_topic
- 依赖: update.message.text 解析参数

### cmd_interrupt
- 获取当前话题对应 session，调用 session.interrupt_session
- 依赖: session.interrupt_session

### cmd_quit
- 停止 watcher，保留 session 信息
- 依赖: watcher.stop_watcher

### cmd_delete
- 发送确认按钮 (delete_confirm:{topic_id} / delete_cancel:{topic_id})
- 依赖: InlineKeyboard

### cmd_bypass
- 切换 state 中的 permission_enabled 标志
- 依赖: config.save_state

### cmd_status
- 输出运行时长、活跃会话数、今日重启次数
- 依赖: state, os.getpid, time

### cmd_info
- 输出当前话题关联的会话详情
- 依赖: state.sessions

### cmd_retry
- 重发最后一条消息到当前话题
- 依赖: session.inject_message

### cmd_setdir
- 手动设置 PROJECT_DIR
- 依赖: config.save_state

## handlers/messages.py

### handle_message
- 签名: `async handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`
- 流程: 鉴权(ALLOWED_USERS) -> 获取 topic_id -> 查找 session -> get_topic_lock -> inject_message
- 异常处理: SessionDead -> "会话已结束", PermissionPending -> "请先处理权限请求"
- 无 session: 返回提示创建

## handlers/callbacks.py

### handle_button
- 签名: `async handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`
- callback_data 前缀分发:
  - `allow:{session_id}` -> pending_permissions[sid].decision="allow", event.set()
  - `deny:{session_id}` -> pending_permissions[sid].decision="deny", event.set()
  - `tui_allow:{session_id}` -> 查找 pane_id, session.respond_tui_permission(pane_id, True)
  - `tui_deny:{session_id}` -> session.respond_tui_permission(pane_id, False)
  - `project:{path}` -> session.launch_session, watcher.start_watcher, config.save_state
  - `delete_confirm:{topic_id}` -> session.kill_session, watcher.stop_watcher, 清理 state
  - `delete_cancel:{topic_id}` -> 回复"取消"

## bot.py handler 注册（dev-ext 在标记行下追加）

```python
from handlers.commands import cmd_setup, cmd_start, cmd_projects, ...
from handlers.messages import handle_message
from handlers.callbacks import handle_button
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters

tg_app.add_handler(CommandHandler("setup", cmd_setup))
tg_app.add_handler(CommandHandler("start", cmd_start))
# ... 所有命令
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
tg_app.add_handler(CallbackQueryHandler(handle_button))
```
