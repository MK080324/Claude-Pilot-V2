"""JSONL 文件监听与消息合并。"""
from __future__ import annotations

import asyncio

from config import State


async def start_watcher(
    session_id: str,
    transcript_path: str,
    chat_id: int,
    topic_id: int,
    source: str,
    pane_id: str | None,
    state: State,
    bot: object,
) -> asyncio.Task:
    """启动监听任务。"""
    raise NotImplementedError


def stop_watcher(topic_id: int) -> None:
    """停止监听任务。"""
    raise NotImplementedError
