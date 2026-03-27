"""JSONL 文件监听与消息合并。"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from config import State
from renderer import format_tool_use, render_markdown, split_message
from session import TuiState, detect_tui_state
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

POLL_INTERVAL = 0.5
FLUSH_INTERVAL = 1.5
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]

_active_watchers: dict[int, asyncio.Task] = {}


def _read_jsonl_incremental(path: str, last_pos: int) -> tuple[list[dict], int]:
    """增量读取 JSONL 文件。"""
    events: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            f.seek(last_pos)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("跳过无效 JSONL 行")
            new_pos = f.tell()
    except FileNotFoundError:
        return [], last_pos
    return events, new_pos


def _process_event(
    event: dict, seen_uuids: set, source: str, send_buffer: list
) -> None:
    """处理单个事件：去重、过滤、格式化。"""
    uid = event.get("uuid")
    if uid:
        if uid in seen_uuids:
            return
        seen_uuids.add(uid)

    role = event.get("role", "")
    user_type = event.get("userType", "")

    if role == "user":
        if user_type == "internal":
            return
        if source == "telegram" and user_type == "external":
            return
        msg = event.get("message", {})
        text = ""
        if isinstance(msg, str):
            text = msg
        elif isinstance(msg, dict):
            text = msg.get("content", str(msg))
        if text:
            send_buffer.append(f"<b>[User]</b> {render_markdown(text)}")
        return

    if role == "assistant":
        parts: list[str] = []
        content = event.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(render_markdown(block.get("text", "")))
                    elif block.get("type") == "tool_use":
                        parts.append(format_tool_use(
                            block.get("name", ""), block.get("input", {})
                        ))
        if parts:
            send_buffer.append("\n".join(parts))


async def _flush_buffer(
    send_buffer: list, chat_id: int, topic_id: int, bot: object,
    last_flush_time: float,
) -> float:
    """合并发送 buffer 内容。"""
    if not send_buffer:
        return last_flush_time
    combined = "\n\n".join(send_buffer)
    send_buffer.clear()
    chunks = split_message(combined)
    for chunk in chunks:
        for attempt in range(MAX_RETRIES):
            try:
                await bot.send_message(
                    chat_id=chat_id, message_thread_id=topic_id,
                    text=chunk, parse_mode="HTML",
                )
                break
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                else:
                    logger.error("发送失败，已达最大重试次数")
    return time.time()


async def _check_tui_state(
    pane_id: str, chat_id: int, topic_id: int, session_id: str,
    bot: object, permission_sent: set,
) -> None:
    """检测 TUI 权限提示并发送审批消息（去重）。"""
    state = await detect_tui_state(pane_id)
    if state == TuiState.PERMISSION_PROMPT:
        if session_id in permission_sent:
            return
        permission_sent.add(session_id)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Allow", callback_data=f"tui_allow:{session_id}"),
            InlineKeyboardButton("Deny", callback_data=f"tui_deny:{session_id}"),
        ]])
        await bot.send_message(
            chat_id=chat_id, message_thread_id=topic_id,
            text="<b>TUI Permission Request</b>\nClaude is requesting permission.",
            parse_mode="HTML", reply_markup=keyboard,
        )
    else:
        permission_sent.discard(session_id)


async def _watch_loop(
    session_id: str, transcript_path: str, chat_id: int, topic_id: int,
    source: str, pane_id: str | None, state: State, bot: object,
) -> None:
    """主监听循环。"""
    last_pos = 0
    seen_uuids: set = set()
    send_buffer: list[str] = []
    last_flush = time.time()
    permission_sent: set = set()
    try:
        while True:
            events, last_pos = _read_jsonl_incremental(transcript_path, last_pos)
            for ev in events:
                _process_event(ev, seen_uuids, source, send_buffer)
            if pane_id:
                await _check_tui_state(
                    pane_id, chat_id, topic_id, session_id, bot, permission_sent)
            now = time.time()
            if send_buffer and (now - last_flush >= FLUSH_INTERVAL):
                last_flush = await _flush_buffer(
                    send_buffer, chat_id, topic_id, bot, last_flush,
                )
            await asyncio.sleep(POLL_INTERVAL)
    except asyncio.CancelledError:
        if send_buffer:
            await _flush_buffer(send_buffer, chat_id, topic_id, bot, last_flush)


async def start_watcher(
    session_id: str, transcript_path: str, chat_id: int, topic_id: int,
    source: str, pane_id: str | None, state: State, bot: object,
) -> asyncio.Task:
    """启动监听任务。"""
    task = asyncio.create_task(_watch_loop(
        session_id, transcript_path, chat_id, topic_id,
        source, pane_id, state, bot,
    ))
    _active_watchers[topic_id] = task
    return task


def stop_watcher(topic_id: int) -> None:
    """停止监听任务。"""
    task = _active_watchers.pop(topic_id, None)
    if task and not task.done():
        task.cancel()
