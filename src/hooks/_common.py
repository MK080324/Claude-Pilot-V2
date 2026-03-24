"""Hook 脚本共享工具。"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

ENV_PATH = os.path.expanduser("~/.claude-pilot/.env")
DEFAULT_PORT = "8266"


def read_port() -> str:
    """从 .env 文件读取 BOT_PORT。"""
    try:
        with open(ENV_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    if key.strip() == "BOT_PORT":
                        return value.strip()
    except FileNotFoundError:
        pass
    return DEFAULT_PORT


def post_to_bot(endpoint: str, payload: dict, timeout: int = 10) -> dict | None:
    """向 Bot HTTP API 发送 POST 请求。"""
    port = read_port()
    url = f"http://127.0.0.1:{port}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None
