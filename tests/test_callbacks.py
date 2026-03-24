"""callbacks.py 单元测试。"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api import PermissionRequest, pending_permissions
from config import State
from handlers.callbacks import handle_button


def _make_update_context(callback_data: str, chat_id: int = 456) -> tuple:
    query = MagicMock()
    query.answer = AsyncMock()
    query.data = callback_data
    query.edit_message_text = AsyncMock()
    query.message.chat_id = chat_id

    update = MagicMock()
    update.callback_query = query

    state = State()
    context = MagicMock()
    context.bot_data = {"state": state, "base_dir": "/tmp"}
    context.bot = AsyncMock()
    return update, context, state, query


@pytest.mark.asyncio
async def test_hook_allow():
    update, ctx, _, query = _make_update_context("allow:req1")
    req = PermissionRequest(description="test", session_id="req1")
    pending_permissions["req1"] = req
    try:
        await handle_button(update, ctx)
        assert req.decision == "allow"
        assert req.event.is_set()
        query.edit_message_text.assert_called_with("已允许")
    finally:
        pending_permissions.pop("req1", None)


@pytest.mark.asyncio
async def test_hook_deny():
    update, ctx, _, query = _make_update_context("deny:req2")
    req = PermissionRequest(description="test", session_id="req2")
    pending_permissions["req2"] = req
    try:
        await handle_button(update, ctx)
        assert req.decision == "deny"
        assert req.event.is_set()
        query.edit_message_text.assert_called_with("已拒绝")
    finally:
        pending_permissions.pop("req2", None)


@pytest.mark.asyncio
async def test_hook_allow_expired():
    update, ctx, _, query = _make_update_context("allow:gone")
    await handle_button(update, ctx)
    query.edit_message_text.assert_called_with("请求已过期")


@pytest.mark.asyncio
async def test_tui_allow():
    update, ctx, state, query = _make_update_context("tui_allow:s1")
    state.sessions["s1"] = {"pane_id": "%5"}
    with patch("session.respond_tui_permission", new_callable=AsyncMock) as mock_resp:
        await handle_button(update, ctx)
        mock_resp.assert_called_once_with("%5", True)
    query.edit_message_text.assert_called_with("TUI 已允许")


@pytest.mark.asyncio
async def test_tui_deny():
    update, ctx, state, query = _make_update_context("tui_deny:s1")
    state.sessions["s1"] = {"pane_id": "%5"}
    with patch("session.respond_tui_permission", new_callable=AsyncMock) as mock_resp:
        await handle_button(update, ctx)
        mock_resp.assert_called_once_with("%5", False)
    query.edit_message_text.assert_called_with("TUI 已拒绝")


@pytest.mark.asyncio
async def test_tui_session_not_found():
    update, ctx, _, query = _make_update_context("tui_allow:missing")
    await handle_button(update, ctx)
    query.edit_message_text.assert_called_with("会话未找到")


@pytest.mark.asyncio
async def test_project_launches_session():
    update, ctx, state, query = _make_update_context("project:/tmp/proj")
    mock_info = MagicMock()
    mock_info.session_id = "abc"
    mock_info.pane_id = "%1"
    mock_info.cwd = "/tmp/proj"
    mock_info.transcript_path = "/tmp/proj/.claude/transcript.jsonl"
    mock_info.topic_id = 0
    mock_info.source = "telegram"
    mock_topic = MagicMock()
    mock_topic.message_thread_id = 200
    ctx.bot.create_forum_topic = AsyncMock(return_value=mock_topic)
    with patch("session.launch_session", new_callable=AsyncMock, return_value=mock_info), \
         patch("watcher.start_watcher", new_callable=AsyncMock) as mock_watcher, \
         patch("handlers.callbacks.save_state"):
        await handle_button(update, ctx)
        mock_watcher.assert_called_once()
    assert state.sessions["abc"]["pane_id"] == "%1"
    assert state.session_topics["abc"] == 200
    query.edit_message_text.assert_called_with("会话已创建: abc")


@pytest.mark.asyncio
async def test_delete_confirm():
    update, ctx, state, query = _make_update_context("delete_confirm:100")
    state.session_topics["s1"] = 100
    state.sessions["s1"] = {"pane_id": "%1"}
    with patch("session.kill_session", new_callable=AsyncMock) as mock_kill, \
         patch("watcher.stop_watcher") as mock_stop, \
         patch("handlers.callbacks.save_state"):
        await handle_button(update, ctx)
        mock_kill.assert_called_once_with("cp-s1")
        mock_stop.assert_called_once_with(100)
    assert "s1" not in state.sessions
    assert "s1" not in state.session_topics
    query.edit_message_text.assert_called_with("会话已删除")


@pytest.mark.asyncio
async def test_delete_cancel():
    update, ctx, _, query = _make_update_context("delete_cancel:100")
    await handle_button(update, ctx)
    query.edit_message_text.assert_called_with("已取消删除")
