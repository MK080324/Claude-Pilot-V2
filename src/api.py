"""HTTP API 路由。"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from html import escape

from aiohttp import web

from config import State, save_state

logger = logging.getLogger(__name__)

SESSION_ID_RE = re.compile(r"^[a-f0-9\-]{8,36}$")
PERMISSION_TIMEOUT = 120


@dataclass
class PermissionRequest:
    """待审批权限请求。"""
    description: str
    session_id: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: str = ""  # "allow" | "deny"
    reason: str = ""


pending_permissions: dict[str, PermissionRequest] = {}


def _validate_session_id(session_id: str) -> bool:
    return bool(SESSION_ID_RE.match(session_id))


async def http_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "running"})


async def http_session_start(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    if not _validate_session_id(session_id):
        return web.json_response({"error": "invalid session_id"}, status=400)
    state: State = request.app["state"]
    bot = request.app["bot"]
    base_dir = request.app.get("base_dir", "")
    if not state.group_chat_id:
        return web.json_response({"status": "no_group"})
    if session_id in state.sessions:
        return web.json_response({
            "status": "exists",
            "topic_id": state.session_topics.get(session_id),
        })
    transcript_path = data.get("transcript_path", "")
    cwd = data.get("cwd", "")
    pane_id = data.get("tmux_pane")
    try:
        topic = await bot.create_forum_topic(
            state.group_chat_id, name=f"Claude-{session_id}"
        )
        topic_id = topic.message_thread_id
    except Exception:
        logger.exception("Failed to create forum topic")
        return web.json_response({"error": "topic_creation_failed"}, status=500)
    state.sessions[session_id] = {
        "pane_id": pane_id, "cwd": cwd,
        "transcript_path": transcript_path,
    }
    state.session_topics[session_id] = topic_id
    if base_dir:
        save_state(state, os.path.join(base_dir, ".state.json"))
    if transcript_path:
        # lazy import: watcher 依赖 renderer/session，避免启动时循环加载
        from watcher import start_watcher
        await start_watcher(
            session_id, transcript_path, state.group_chat_id,
            topic_id, "terminal", pane_id, state, bot,
        )
    return web.json_response({"status": "created", "topic_id": topic_id})


async def http_session_stop(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    if not _validate_session_id(session_id):
        return web.json_response({"error": "invalid session_id"}, status=400)
    state: State = request.app["state"]
    bot = request.app["bot"]
    base_dir = request.app.get("base_dir", "")
    topic_id = state.session_topics.get(session_id)
    if topic_id:
        from watcher import stop_watcher  # lazy: 避免循环加载
        stop_watcher(topic_id)
        msg = data.get("message", "Session stopped")
        try:
            await bot.send_message(
                chat_id=state.group_chat_id,
                message_thread_id=topic_id,
                text=f"<b>Session ended</b>\n{escape(msg)}",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to send stop message")
    state.sessions.pop(session_id, None)
    state.session_topics.pop(session_id, None)
    if base_dir:
        save_state(state, os.path.join(base_dir, ".state.json"))
    return web.json_response({"status": "ok"})


async def http_permission(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    if not _validate_session_id(session_id):
        return web.json_response({"error": "invalid session_id"}, status=400)
    state: State = request.app["state"]
    if state.bypass_enabled:
        return web.json_response({"decision": "allow", "reason": "bypass"})
    description = data.get("description", "")
    timeout = request.app.get("permission_timeout", PERMISSION_TIMEOUT)
    req = PermissionRequest(description=description, session_id=session_id)
    pending_permissions[session_id] = req
    bot = request.app["bot"]
    topic_id = state.session_topics.get(session_id)
    chat_id = state.group_chat_id
    if chat_id and topic_id:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup  # lazy: 避免循环加载
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Allow", callback_data=f"allow:{session_id}"),
            InlineKeyboardButton("Deny", callback_data=f"deny:{session_id}"),
        ]])
        try:
            await bot.send_message(
                chat_id=chat_id, message_thread_id=topic_id,
                text=f"<b>Permission Request</b>\n{escape(description)}",
                parse_mode="HTML", reply_markup=keyboard,
            )
        except Exception:
            logger.exception("Failed to send permission request")
    try:
        await asyncio.wait_for(req.event.wait(), timeout=timeout)
        return web.json_response({
            "decision": req.decision,
            "reason": req.reason,
        })
    except asyncio.TimeoutError:
        return web.json_response({"decision": "deny", "reason": "timeout"})
    finally:
        pending_permissions.pop(session_id, None)


async def http_notification(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    if not _validate_session_id(session_id):
        return web.json_response({"error": "invalid session_id"}, status=400)
    state: State = request.app["state"]
    bot = request.app["bot"]
    message = data.get("message", "")
    topic_id = state.session_topics.get(session_id)
    chat_id = state.group_chat_id
    if chat_id and topic_id and message:
        try:
            await bot.send_message(
                chat_id=chat_id, message_thread_id=topic_id,
                text=f"<b>Notification</b>\n{escape(message)}",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to send notification")
    return web.json_response({"status": "ok"})


def create_api_app(state: State, bot: object, base_dir: str = "") -> web.Application:
    """创建并配置 aiohttp app。"""
    app = web.Application()
    app["state"] = state
    app["bot"] = bot
    app["base_dir"] = base_dir
    app["host"] = "127.0.0.1"
    app.router.add_get("/health", http_health)
    app.router.add_post("/session_start", http_session_start)
    app.router.add_post("/session_stop", http_session_stop)
    app.router.add_post("/permission", http_permission)
    app.router.add_post("/notification", http_notification)
    return app
