"""commands.py 单元测试。"""
from __future__ import annotations

import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import Config, State
from handlers.commands import (
    cmd_bypass, cmd_delete, cmd_info, cmd_projects, cmd_quit,
    cmd_resume, cmd_setup, cmd_start, cmd_status, cmd_setdir,
)


def _make_update_context(
    user_id: int = 123, chat_id: int = 456, chat_type: str = "supergroup",
    text: str = "", thread_id: int | None = None,
) -> tuple:
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.effective_chat.type = chat_type
    update.message.text = text
    update.message.message_thread_id = thread_id
    update.message.reply_text = AsyncMock()

    config = Config(bot_token="t", allowed_users=[123], project_dir="/tmp/proj")
    state = State()
    context = MagicMock()
    context.bot_data = {"config": config, "state": state, "base_dir": "/tmp"}
    context.bot = AsyncMock()
    return update, context, config, state


@pytest.mark.asyncio
async def test_setup_in_group():
    update, ctx, _, state = _make_update_context(chat_type="supergroup")
    with patch("handlers.commands.save_state"):
        await cmd_setup(update, ctx)
    assert state.group_chat_id == 456
    update.message.reply_text.assert_called_with("群组已配置")


@pytest.mark.asyncio
async def test_setup_not_group():
    update, ctx, _, _ = _make_update_context(chat_type="private")
    await cmd_setup(update, ctx)
    update.message.reply_text.assert_called_with("请在超级群组中使用此命令")


@pytest.mark.asyncio
async def test_setup_auth_fail():
    update, ctx, _, _ = _make_update_context(user_id=999)
    await cmd_setup(update, ctx)
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_start_saves_notify():
    update, ctx, _, state = _make_update_context(chat_type="private")
    with patch("handlers.commands.save_state"):
        await cmd_start(update, ctx)
    assert state.notify_chat_id == 456
    update.message.reply_text.assert_called_with("已设置通知")


@pytest.mark.asyncio
async def test_status_output():
    update, ctx, _, state = _make_update_context()
    state.sessions["abc123"] = {"cwd": "/proj/a"}
    await cmd_status(update, ctx)
    text = update.message.reply_text.call_args[0][0]
    assert "活跃会话: 1" in text
    assert "abc123" in text


@pytest.mark.asyncio
async def test_bypass_toggle():
    update, ctx, _, state = _make_update_context()
    with patch("handlers.commands.save_state"):
        await cmd_bypass(update, ctx)
    assert state.sessions["_bypass_enabled"] is True
    update.message.reply_text.assert_called_with("Hook 权限审批已开启")
    with patch("handlers.commands.save_state"):
        await cmd_bypass(update, ctx)
    assert state.sessions["_bypass_enabled"] is False
    update.message.reply_text.assert_called_with("Hook 权限审批已关闭")


@pytest.mark.asyncio
async def test_delete_sends_confirmation():
    update, ctx, _, _ = _make_update_context(thread_id=100)
    await cmd_delete(update, ctx)
    call_args = update.message.reply_text.call_args
    assert "确认删除" in call_args[0][0]
    markup = call_args[1]["reply_markup"]
    buttons = markup.inline_keyboard[0]
    assert buttons[0].callback_data == "delete_confirm:100"
    assert buttons[1].callback_data == "delete_cancel:100"


@pytest.mark.asyncio
async def test_projects_sends_buttons(tmp_path):
    os.makedirs(tmp_path / "proj1")
    os.makedirs(tmp_path / "proj2")
    update, ctx, config, _ = _make_update_context()
    config.project_dir = str(tmp_path)
    await cmd_projects(update, ctx)
    call_args = update.message.reply_text.call_args
    markup = call_args[1]["reply_markup"]
    assert len(markup.inline_keyboard) == 2


@pytest.mark.asyncio
async def test_resume_no_sessions():
    update, ctx, _, _ = _make_update_context()
    await cmd_resume(update, ctx)
    update.message.reply_text.assert_called_with("无历史会话")


@pytest.mark.asyncio
async def test_info_no_topic():
    update, ctx, _, _ = _make_update_context(thread_id=None)
    await cmd_info(update, ctx)
    update.message.reply_text.assert_called_with("请在会话话题中使用")


@pytest.mark.asyncio
async def test_quit_stops_watcher():
    update, ctx, _, _ = _make_update_context(thread_id=100)
    with patch("watcher.stop_watcher") as mock_stop:
        await cmd_quit(update, ctx)
        mock_stop.assert_called_once_with(100)


@pytest.mark.asyncio
async def test_setdir_updates_config():
    update, ctx, config, _ = _make_update_context(text="/setdir /new/path")
    with patch("handlers.commands.save_state"):
        await cmd_setdir(update, ctx)
    assert config.project_dir == "/new/path"
