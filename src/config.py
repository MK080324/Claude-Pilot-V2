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
    raise NotImplementedError


def load_state(path: str) -> State:
    """加载 .state.json，文件不存在时返回空 State。"""
    raise NotImplementedError


def save_state(state: State, path: str) -> None:
    """原子写入 .state.json（tempfile + os.rename）。"""
    raise NotImplementedError
