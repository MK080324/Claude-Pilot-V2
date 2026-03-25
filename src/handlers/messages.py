"""普通消息处理。"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

import session
from config import Config, State


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """消息处理入口：鉴权 -> 查 session -> 加锁 -> inject。"""
    config: Config = context.bot_data["config"]
    state: State = context.bot_data["state"]
    if not update.effective_user or update.effective_user.id not in config.allowed_users:
        return
    if not update.message:
        return
    if not update.message.message_thread_id:
        if update.effective_chat and update.effective_chat.type == "private":
            await update.message.reply_text(
                "请先完成配置：创建群组 → 加入 Bot → 群组中发 /setup\n"
                "详细步骤请发 /start"
            )
        return
    topic_id = update.message.message_thread_id
    session_id: str | None = None
    for sid, tid in state.session_topics.items():
        if tid == topic_id:
            session_id = sid
            break
    if not session_id or session_id not in state.sessions:
        await update.message.reply_text("此话题无关联会话，请使用 /projects 创建")
        return
    pane_id = state.sessions[session_id].get("pane_id")
    if not pane_id:
        return
    async with session.get_topic_lock(topic_id):
        try:
            await session.inject_message(pane_id, update.message.text)
        except session.SessionDead:
            await update.message.reply_text("会话已结束")
        except session.PermissionPending:
            await update.message.reply_text("请先处理权限请求")
