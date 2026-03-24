"""watcher.py 单元测试。"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, "src")


@pytest.fixture
def jsonl_file(tmp_path):
    """创建临时 JSONL 文件。"""
    return tmp_path / "transcript.jsonl"


def _write_events(path, events):
    with open(path, "a", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


# --- _read_jsonl_incremental ---

def test_read_jsonl_incremental_basic(jsonl_file):
    from watcher import _read_jsonl_incremental
    events_data = [{"uuid": f"u{i}", "role": "user"} for i in range(3)]
    _write_events(jsonl_file, events_data)
    events, pos = _read_jsonl_incremental(str(jsonl_file), 0)
    assert len(events) == 3
    # 追加 2 行
    _write_events(jsonl_file, [{"uuid": "u3"}, {"uuid": "u4"}])
    events2, pos2 = _read_jsonl_incremental(str(jsonl_file), pos)
    assert len(events2) == 2
    assert pos2 > pos


def test_read_jsonl_incremental_invalid_json(jsonl_file):
    from watcher import _read_jsonl_incremental
    jsonl_file.write_text('{"valid":1}\nnot-json\n{"valid":2}\n')
    events, _ = _read_jsonl_incremental(str(jsonl_file), 0)
    assert len(events) == 2


def test_read_jsonl_file_not_found():
    from watcher import _read_jsonl_incremental
    events, pos = _read_jsonl_incremental("/nonexistent/path.jsonl", 0)
    assert events == []
    assert pos == 0


# --- _process_event ---

def test_process_event_uuid_dedup():
    from watcher import _process_event
    seen = set()
    buf: list[str] = []
    ev = {"uuid": "aaa", "role": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}
    with patch("watcher.render_markdown", return_value="hi"):
        _process_event(ev, seen, "terminal", buf)
        assert len(buf) == 1
        _process_event(ev, seen, "terminal", buf)
        assert len(buf) == 1  # 去重，不追加


def test_process_event_source_telegram_skip():
    from watcher import _process_event
    seen = set()
    buf: list[str] = []
    ev = {"uuid": "bbb", "role": "user", "userType": "external", "message": "hello"}
    _process_event(ev, seen, "telegram", buf)
    assert len(buf) == 0


def test_process_event_source_terminal_no_skip():
    from watcher import _process_event
    seen = set()
    buf: list[str] = []
    ev = {"uuid": "ccc", "role": "user", "userType": "external", "message": "hello"}
    with patch("watcher.render_markdown", return_value="hello"):
        _process_event(ev, seen, "terminal", buf)
    assert len(buf) == 1


def test_process_event_internal_filter():
    from watcher import _process_event
    seen = set()
    buf: list[str] = []
    ev = {"uuid": "ddd", "role": "user", "userType": "internal", "message": "system"}
    _process_event(ev, seen, "terminal", buf)
    assert len(buf) == 0


def test_process_event_assistant_text_and_tool():
    from watcher import _process_event
    seen = set()
    buf: list[str] = []
    ev = {
        "uuid": "eee", "role": "assistant",
        "message": {"content": [
            {"type": "text", "text": "thinking..."},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
        ]},
    }
    with patch("watcher.render_markdown", return_value="thinking..."), \
         patch("watcher.format_tool_use", return_value="tool:Bash:ls"):
        _process_event(ev, seen, "terminal", buf)
    assert len(buf) == 1
    assert "thinking..." in buf[0]
    assert "tool:Bash:ls" in buf[0]


# --- _flush_buffer ---

@pytest.mark.asyncio
async def test_flush_buffer_merge_send():
    from watcher import _flush_buffer
    bot = MagicMock()
    bot.send_message = AsyncMock()
    buf = ["msg1", "msg2", "msg3"]
    with patch("watcher.split_message", return_value=["msg1\n\nmsg2\n\nmsg3"]):
        result = await _flush_buffer(buf, 123, 456, bot, 0.0)
    assert bot.send_message.call_count == 1
    assert result > 0
    assert len(buf) == 0


@pytest.mark.asyncio
async def test_flush_buffer_retry():
    from watcher import _flush_buffer, RETRY_DELAYS
    bot = MagicMock()
    call_count = 0

    async def fail_then_succeed(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise Exception("rate limited")

    bot.send_message = fail_then_succeed
    buf = ["test"]
    with patch("watcher.split_message", return_value=["test"]), \
         patch("watcher.asyncio.sleep", new_callable=AsyncMock):
        await _flush_buffer(buf, 1, 2, bot, 0.0)
    assert call_count == 3


@pytest.mark.asyncio
async def test_flush_buffer_empty():
    from watcher import _flush_buffer
    result = await _flush_buffer([], 1, 2, MagicMock(), 5.0)
    assert result == 5.0


# --- _check_tui_state ---

@pytest.mark.asyncio
async def test_check_tui_state_permission():
    from watcher import _check_tui_state
    bot = MagicMock()
    bot.send_message = AsyncMock()
    with patch("watcher.detect_tui_state", new_callable=AsyncMock) as mock_det:
        from session import TuiState
        mock_det.return_value = TuiState.PERMISSION_PROMPT
        await _check_tui_state("pane1", 100, 200, "sess1", bot)
    bot.send_message.assert_called_once()
    call_kwargs = bot.send_message.call_args.kwargs
    assert "reply_markup" in call_kwargs


@pytest.mark.asyncio
async def test_check_tui_state_no_permission():
    from watcher import _check_tui_state
    bot = MagicMock()
    bot.send_message = AsyncMock()
    with patch("watcher.detect_tui_state", new_callable=AsyncMock) as mock_det:
        from session import TuiState
        mock_det.return_value = TuiState.GENERATING
        await _check_tui_state("pane1", 100, 200, "sess1", bot)
    bot.send_message.assert_not_called()


# --- start_watcher / stop_watcher ---

@pytest.mark.asyncio
async def test_start_watcher_returns_task():
    from watcher import start_watcher, _active_watchers
    from config import State
    bot = MagicMock()
    bot.send_message = AsyncMock()
    state = State()
    with patch("watcher._read_jsonl_incremental", return_value=([], 0)):
        task = await start_watcher("s1", "/tmp/t.jsonl", 1, 100, "terminal", None, state, bot)
    assert isinstance(task, asyncio.Task)
    assert 100 in _active_watchers
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    _active_watchers.pop(100, None)


@pytest.mark.asyncio
async def test_stop_watcher_cancels():
    from watcher import start_watcher, stop_watcher, _active_watchers
    from config import State
    bot = MagicMock()
    bot.send_message = AsyncMock()
    state = State()
    with patch("watcher._read_jsonl_incremental", return_value=([], 0)):
        task = await start_watcher("s2", "/tmp/t.jsonl", 1, 200, "terminal", None, state, bot)
    stop_watcher(200)
    assert 200 not in _active_watchers
    # 让事件循环处理取消
    await asyncio.sleep(0)
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert task.cancelled() or task.done()
