"""HTTP API 路由。"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

from aiohttp import web

from config import State

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
    if not state.group_chat_id:
        return web.json_response({"status": "no_group"})
    if session_id in state.sessions:
        return web.json_response({
            "status": "exists",
            "topic_id": state.session_topics.get(session_id),
        })
    return web.json_response({"status": "created"})


async def http_session_stop(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    if not _validate_session_id(session_id):
        return web.json_response({"error": "invalid session_id"}, status=400)
    return web.json_response({"status": "ok"})


async def http_permission(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    if not _validate_session_id(session_id):
        return web.json_response({"error": "invalid session_id"}, status=400)
    description = data.get("description", "")
    timeout = request.app.get("permission_timeout", PERMISSION_TIMEOUT)
    req = PermissionRequest(description=description, session_id=session_id)
    pending_permissions[session_id] = req
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
    return web.json_response({"status": "ok"})


def create_api_app(state: State, bot: object) -> web.Application:
    """创建并配置 aiohttp app。"""
    app = web.Application()
    app["state"] = state
    app["bot"] = bot
    app["host"] = "127.0.0.1"
    app.router.add_get("/health", http_health)
    app.router.add_post("/session_start", http_session_start)
    app.router.add_post("/session_stop", http_session_stop)
    app.router.add_post("/permission", http_permission)
    app.router.add_post("/notification", http_notification)
    return app
