"""Hook 脚本共享工具。"""
from __future__ import annotations

import json
import os
import urllib.request


def read_port() -> str:
    """从 .env 文件读取 BOT_PORT。"""
    raise NotImplementedError


def post_to_bot(endpoint: str, payload: dict, timeout: int = 10) -> dict | None:
    """向 Bot HTTP API 发送 POST 请求。"""
    raise NotImplementedError
