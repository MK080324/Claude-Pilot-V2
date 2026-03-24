"""SessionStart hook 处理。"""
from __future__ import annotations

import json
import os
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
        "session_id": data.get("session_id", ""),
        "transcript_path": data.get("transcript_path", ""),
        "cwd": data.get("cwd", ""),
        "tmux_pane": os.environ.get("TMUX_PANE"),
    }
    post_to_bot("/session_start", payload)


if __name__ == "__main__":
    main()
