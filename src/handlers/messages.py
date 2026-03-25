"""普通消息处理。"""
from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

import session
from config import Config, State

logger = logging.getLogger(__name__)


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
                "请先完成配置，发 /start 查看完整步骤。"
            )
        return
    topic_id = update.message.message_thread_id
    logger.info("Message in topic %s, text: %s", topic_id, (update.message.text or "")[:50])
    session_id: str | None = None
    for sid, tid in state.session_topics.items():
        if tid == topic_id:
            session_id = sid
            break
    logger.info("Matched session: %s, topics: %s", session_id, state.session_topics)
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
