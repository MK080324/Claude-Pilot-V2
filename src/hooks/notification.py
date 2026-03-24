"""Notification hook 处理。"""
from __future__ import annotations

import json
import sys

try:
    from ._common import post_to_bot
except ImportError:
    from _common import post_to_bot


def main() -> None:
    """从 stdin 读取 JSON，转发给 Bot。"""
    raw = sys.stdin.read()
    if not raw.strip():
        return
    data = json.loads(raw)
    payload = {
        "message": data.get("message", ""),
        "session_id": data.get("session_id", ""),
    }
    post_to_bot("/notification", payload)


if __name__ == "__main__":
    main()
