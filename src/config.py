"""配置加载与状态持久化。"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field


@dataclass
class SessionInfo:
    """单个会话的信息。"""
    session_id: str
    transcript_path: str
    cwd: str
    pane_id: str | None
    topic_id: int
    source: str  # "terminal" | "telegram"


@dataclass
class Config:
    """静态配置（从 .env 加载）。"""
    bot_token: str = ""
    allowed_users: list[int] = field(default_factory=list)
    bot_port: int = 8266
    project_dir: str = ""


@dataclass
class State:
    """运行时状态（持久化到 .state.json）。"""
    group_chat_id: int | None = None
    notify_chat_id: int | None = None
    sessions: dict[str, dict] = field(default_factory=dict)
    session_topics: dict[str, int] = field(default_factory=dict)


def load_env(path: str) -> dict[str, str]:
    """解析 .env 文件，返回键值对字典。"""
    result: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            result[key] = value
    return result


def load_state(path: str) -> State:
    """加载 .state.json，文件不存在时返回空 State。"""
    if not os.path.exists(path):
        return State()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return State(
        group_chat_id=data.get("group_chat_id"),
        notify_chat_id=data.get("notify_chat_id"),
        sessions=data.get("sessions", {}),
        session_topics=data.get("session_topics", {}),
    )


def save_state(state: State, path: str) -> None:
    """原子写入 .state.json（tempfile + os.rename）。"""
    dir_name = os.path.dirname(path) or "."
    data = {
        "group_chat_id": state.group_chat_id,
        "notify_chat_id": state.notify_chat_id,
        "sessions": state.sessions,
        "session_topics": state.session_topics,
    }
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.rename(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
