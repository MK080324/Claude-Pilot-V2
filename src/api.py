"""HTTP API 路由。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from aiohttp import web

from config import State


@dataclass
class PermissionRequest:
    """待审批权限请求。"""
    description: str
    session_id: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: str = ""  # "allow" | "deny"
    reason: str = ""


pending_permissions: dict[str, PermissionRequest] = {}


def create_api_app(state: State, bot: object) -> web.Application:
    """创建并配置 aiohttp app。"""
    raise NotImplementedError
