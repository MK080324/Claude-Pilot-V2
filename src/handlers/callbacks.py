"""InlineKeyboard 回调处理。"""
from __future__ import annotations

import os

from telegram import Update
from telegram.ext import ContextTypes

import session
import watcher
from api import pending_permissions
from config import Config, State, save_state


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """按钮回调入口：按 callback_data 前缀分发。"""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    state: State = context.bot_data["state"]
    base_dir = context.bot_data.get("base_dir", "")

    if data.startswith("allow:"):
        await _handle_hook_allow(query, data[6:])
    elif data.startswith("deny:"):
        await _handle_hook_deny(query, data[5:])
    elif data.startswith("tui_allow:"):
        await _handle_tui(query, data[10:], state, allow=True)
    elif data.startswith("tui_deny:"):
        await _handle_tui(query, data[9:], state, allow=False)
    elif data.startswith("project:"):
        await _handle_project(query, data[8:], state, base_dir, context)
    elif data.startswith("delete_confirm:"):
        await _handle_delete_confirm(query, int(data[15:]), state, base_dir)
    elif data.startswith("delete_cancel:"):
        await query.edit_message_text("已取消删除")


async def _handle_hook_allow(query: object, sid: str) -> None:
    req = pending_permissions.get(sid)
    if req:
        req.decision = "allow"
        req.event.set()
        await query.edit_message_text("已允许")
    else:
        await query.edit_message_text("请求已过期")


async def _handle_hook_deny(query: object, sid: str) -> None:
    req = pending_permissions.get(sid)
    if req:
        req.decision = "deny"
        req.event.set()
        await query.edit_message_text("已拒绝")
    else:
        await query.edit_message_text("请求已过期")


async def _handle_tui(query: object, sid: str, state: State, *, allow: bool) -> None:
    pane_id = state.sessions.get(sid, {}).get("pane_id")
    if pane_id:
        await session.respond_tui_permission(pane_id, allow)
        label = "已允许" if allow else "已拒绝"
        await query.edit_message_text(f"TUI {label}")
    else:
        await query.edit_message_text("会话未找到")


async def _handle_project(
    query: object, dir_name: str, state: State, base_dir: str,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    config: Config = context.bot_data["config"]
    proj_dir = state.project_dir or config.project_dir
    path = os.path.realpath(os.path.join(proj_dir, dir_name))
    if not path.startswith(os.path.realpath(proj_dir) + os.sep):
        await query.edit_message_text("无效的项目路径")
        return
    chat_id = query.message.chat_id
    info = await session.launch_session(path, state, context.bot)
    topic = await context.bot.create_forum_topic(chat_id, name=f"Claude-{info.session_id}")
    info.topic_id = topic.message_thread_id
    state.sessions[info.session_id] = {
        "pane_id": info.pane_id, "cwd": info.cwd,
        "transcript_path": info.transcript_path,
    }
    state.session_topics[info.session_id] = info.topic_id
    save_state(state, os.path.join(base_dir, ".state.json"))
    await watcher.start_watcher(
        info.session_id, info.transcript_path, chat_id,
        info.topic_id, info.source, info.pane_id, state, context.bot,
    )
    await query.edit_message_text(f"会话已创建: {info.session_id}")


async def _handle_delete_confirm(
    query: object, topic_id: int, state: State, base_dir: str,
) -> None:
    sid_to_delete: str | None = None
    for sid, tid in state.session_topics.items():
        if tid == topic_id:
            sid_to_delete = sid
            break
    if not sid_to_delete:
        await query.edit_message_text("未找到关联会话")
        return
    info = state.sessions.get(sid_to_delete, {})
    if info.get("pane_id"):
        window_name = f"cp-{sid_to_delete}"
        await session.kill_session(window_name)
    watcher.stop_watcher(topic_id)
    state.sessions.pop(sid_to_delete, None)
    state.session_topics.pop(sid_to_delete, None)
    save_state(state, os.path.join(base_dir, ".state.json"))
    await query.edit_message_text("会话已删除")
