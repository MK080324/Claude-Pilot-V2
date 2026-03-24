"""PreToolUse hook 处理。"""
from __future__ import annotations

import json
import sys

try:
    from ._common import post_to_bot
except ImportError:
    from _common import post_to_bot


def main() -> None:
    """从 stdin 读取 JSON，转发给 Bot，输出 decision。"""
    raw = sys.stdin.read()
    if not raw.strip():
        json.dump({"decision": "deny"}, sys.stdout)
        return
    data = json.loads(raw)
    tool_name = data.get("tool_name", "unknown")
    tool_input = data.get("tool_input", {})
    session_id = data.get("session_id", "")
    description = f"{tool_name}: {json.dumps(tool_input, ensure_ascii=False)[:200]}"
    payload = {
        "description": description,
        "session_id": session_id,
    }
    result = post_to_bot("/permission", payload, timeout=130)
    if result and "decision" in result:
        json.dump({"decision": result["decision"]}, sys.stdout)
    else:
        json.dump({"decision": "deny"}, sys.stdout)


if __name__ == "__main__":
    main()
