"""Telegram 命令处理。"""
from __future__ import annotations
import os, time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from config import Config, State, save_state

_start_time = time.time()

def _auth_check(update: Update, config: Config) -> bool:
    uid = update.effective_user.id if update.effective_user else 0
    return uid in config.allowed_users

def _get_session_for_topic(state: State, topic_id: int) -> dict | None:
    for sid, tid in state.session_topics.items():
        if tid == topic_id:
            return state.sessions.get(sid)
    return None

def _ctx(context: ContextTypes.DEFAULT_TYPE) -> tuple[Config, State, str]:
    cfg = context.bot_data["config"]
    st = context.bot_data["state"]
    base = context.bot_data.get("base_dir", "")
    return cfg, st, os.path.join(base, ".state.json")

async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, state, sp = _ctx(context)
    if not _auth_check(update, config):
        return
    chat_type = update.effective_chat.type if update.effective_chat else ""
    if "group" not in chat_type and "supergroup" not in chat_type:
        await update.message.reply_text("请在超级群组中使用此命令")
        return
    state.group_chat_id = update.effective_chat.id
    save_state(state, sp)
    setup_msg = (
        "✅ <b>群组已配置完成！</b>\n\n"
        "请确认以下设置：\n"
        "1. Bot 已被设为群组管理员\n"
        "2. 群组已开启「话题」功能（群组设置 → 话题）\n\n"
        "配置就绪后，每个 Claude Code 会话将自动创建话题推送对话。\n"
        "常用命令：\n"
        "• /projects — 选择项目启动新会话\n"
        "• /status — 查看运行状态\n"
        "• /bypass — 跳过权限审批\n"
        "• 在话题中直接发消息即可向 Claude 输入"
    )
    await update.message.reply_text(setup_msg, parse_mode="HTML")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, state, sp = _ctx(context)
    if not _auth_check(update, config):
        return
    state.notify_chat_id = update.effective_chat.id
    save_state(state, sp)
    welcome = (
        "👋 欢迎使用 <b>Claude Pilot</b>！\n\n"
        "<b>一、配置 Bot（在 @BotFather 中操作）</b>\n"
        "1. 发送 /mybots → 选择本 Bot\n"
        "2. Bot Settings → Group Privacy → <b>Turn off</b>\n"
        "3. Bot Settings → Allow Groups → 确认已开启\n\n"
        "<b>二、创建群组</b>\n"
        "4. 新建一个 Telegram 群组\n"
        "5. 群组设置 → 开启「话题」功能\n"
        "6. 将本 Bot 加入群组并设为<b>管理员</b>\n\n"
        "<b>三、完成配置</b>\n"
        "7. 在群组中发送 /setup\n\n"
        "全部完成后，每个 Claude Code 会话都会自动推送到群组话题中。"
    )
    await update.message.reply_text(welcome, parse_mode="HTML")

async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, state, _ = _ctx(context)
    if not _auth_check(update, config):
        return
    proj_dir = config.project_dir
    if not proj_dir or not os.path.isdir(proj_dir):
        await update.message.reply_text("项目目录未配置或不存在，请使用 /setdir 设置")
        return
    try:
        entries = sorted(
            e for e in os.listdir(proj_dir)
            if os.path.isdir(os.path.join(proj_dir, e)) and not e.startswith(".")
        )
    except OSError:
        await update.message.reply_text("无法读取项目目录")
        return
    if not entries:
        await update.message.reply_text("项目目录为空")
        return
    buttons = [
        [InlineKeyboardButton(e, callback_data=f"project:{os.path.join(proj_dir, e)}")]
        for e in entries
    ]
    await update.message.reply_text("选择项目：", reply_markup=InlineKeyboardMarkup(buttons))

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, state, _ = _ctx(context)
    if not _auth_check(update, config):
        return
    if not state.sessions:
        await update.message.reply_text("无历史会话")
        return
    lines = [f"- {sid}: {info.get('cwd', '?')}" for sid, info in state.sessions.items()]
    await update.message.reply_text("历史会话:\n" + "\n".join(lines))

async def cmd_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, _, _ = _ctx(context)
    if not _auth_check(update, config):
        return
    parts = (update.message.text or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("用法: /rename <新名称>")
        return
    new_name = parts[1].strip()
    topic_id = update.message.message_thread_id
    if not topic_id:
        await update.message.reply_text("请在会话话题中使用")
        return
    try:
        await context.bot.edit_forum_topic(update.effective_chat.id, topic_id, name=new_name)
        await update.message.reply_text(f"已重命名为: {new_name}")
    except Exception:
        await update.message.reply_text("重命名失败")

async def cmd_interrupt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, state, _ = _ctx(context)
    if not _auth_check(update, config):
        return
    topic_id = update.message.message_thread_id
    if not topic_id:
        await update.message.reply_text("请在会话话题中使用")
        return
    sess = _get_session_for_topic(state, topic_id)
    if not sess or not sess.get("pane_id"):
        await update.message.reply_text("未找到关联会话")
        return
    from session import interrupt_session
    await interrupt_session(sess["pane_id"])
    await update.message.reply_text("已发送中断信号")

async def cmd_quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, _, _ = _ctx(context)
    if not _auth_check(update, config):
        return
    topic_id = update.message.message_thread_id
    if not topic_id:
        await update.message.reply_text("请在会话话题中使用")
        return
    from watcher import stop_watcher
    stop_watcher(topic_id)
    await update.message.reply_text("已暂停监听")

async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, _, _ = _ctx(context)
    if not _auth_check(update, config):
        return
    topic_id = update.message.message_thread_id
    if not topic_id:
        await update.message.reply_text("请在会话话题中使用")
        return
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("确认删除", callback_data=f"delete_confirm:{topic_id}"),
        InlineKeyboardButton("取消", callback_data=f"delete_cancel:{topic_id}"),
    ]])
    await update.message.reply_text("确认删除此会话？", reply_markup=keyboard)

async def cmd_bypass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, state, sp = _ctx(context)
    if not _auth_check(update, config):
        return
    current = state.sessions.get("_bypass_enabled", False)
    state.sessions["_bypass_enabled"] = not current
    save_state(state, sp)
    status = "开启" if not current else "关闭"
    await update.message.reply_text(f"Hook 权限审批已{status}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, state, _ = _ctx(context)
    if not _auth_check(update, config):
        return
    uptime = int(time.time() - _start_time)
    real = {k: v for k, v in state.sessions.items() if not k.startswith("_")}
    lines = [f"运行时长: {uptime}s", f"活跃会话: {len(real)}"]
    for sid, info in real.items():
        lines.append(f"  - {sid}: {info.get('cwd', '?')}")
    await update.message.reply_text("\n".join(lines))

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, state, _ = _ctx(context)
    if not _auth_check(update, config):
        return
    topic_id = update.message.message_thread_id
    if not topic_id:
        await update.message.reply_text("请在会话话题中使用")
        return
    sess = _get_session_for_topic(state, topic_id)
    if not sess:
        await update.message.reply_text("未找到关联会话")
        return
    await update.message.reply_text("\n".join(f"{k}: {v}" for k, v in sess.items()))

async def cmd_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, _, _ = _ctx(context)
    if not _auth_check(update, config):
        return
    await update.message.reply_text("retry 功能暂未实现")

async def cmd_setdir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, state, sp = _ctx(context)
    if not _auth_check(update, config):
        return
    parts = (update.message.text or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("用法: /setdir <目录路径>")
        return
    config.project_dir = parts[1].strip()
    save_state(state, sp)
    await update.message.reply_text(f"项目目录已设置为: {config.project_dir}")
