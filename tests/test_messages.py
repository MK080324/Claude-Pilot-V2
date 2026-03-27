"""messages.py 单元测试。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import Config, State
from handlers.messages import handle_message


def _make_update_context(
    user_id: int = 123, thread_id: int | None = 100, text: str = "hello",
) -> tuple:
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.message_thread_id = thread_id
    update.message.text = text
    update.message.reply_text = AsyncMock()

    config = Config(bot_token="t", allowed_users=[123])
    state = State()
    context = MagicMock()
    context.bot_data = {"config": config, "state": state}
    return update, context, config, state


@pytest.mark.asyncio
async def test_auth_rejects_unknown_user():
    update, ctx, _, _ = _make_update_context(user_id=999)
    await handle_message(update, ctx)
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_no_topic_returns_early():
    update, ctx, _, _ = _make_update_context(thread_id=None)
    await handle_message(update, ctx)
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_no_session_shows_hint():
    update, ctx, _, _ = _make_update_context()
    await handle_message(update, ctx)
    update.message.reply_text.assert_called_with("此话题无关联会话，请使用 /projects 创建")


@pytest.mark.asyncio
async def test_inject_success():
    update, ctx, _, state = _make_update_context()
    state.session_topics["s1"] = 100
    state.sessions["s1"] = {"pane_id": "%1"}
    with patch("session.inject_message", new_callable=AsyncMock) as mock_inject, \
         patch("session.get_topic_lock") as mock_lock:
        lock = AsyncMock()
        lock.__aenter__ = AsyncMock(return_value=None)
        lock.__aexit__ = AsyncMock(return_value=False)
        mock_lock.return_value = lock
        await handle_message(update, ctx)
        mock_inject.assert_called_once_with("%1", "hello")


@pytest.mark.asyncio
async def test_session_dead_message():
    update, ctx, _, state = _make_update_context()
    state.session_topics["s1"] = 100
    state.sessions["s1"] = {"pane_id": "%1"}
    from session import SessionDead
    with patch("session.inject_message", new_callable=AsyncMock, side_effect=SessionDead), \
         patch("session.get_topic_lock") as mock_lock:
        lock = AsyncMock()
        lock.__aenter__ = AsyncMock(return_value=None)
        lock.__aexit__ = AsyncMock(return_value=False)
        mock_lock.return_value = lock
        await handle_message(update, ctx)
    call_text = update.message.reply_text.call_args[0][0]
    assert "会话已结束" in call_text


@pytest.mark.asyncio
async def test_permission_pending_message():
    update, ctx, _, state = _make_update_context()
    state.session_topics["s1"] = 100
    state.sessions["s1"] = {"pane_id": "%1"}
    from session import PermissionPending
    with patch("session.inject_message", new_callable=AsyncMock, side_effect=PermissionPending), \
         patch("session.get_topic_lock") as mock_lock:
        lock = AsyncMock()
        lock.__aenter__ = AsyncMock(return_value=None)
        lock.__aexit__ = AsyncMock(return_value=False)
        mock_lock.return_value = lock
        await handle_message(update, ctx)
    call_text = update.message.reply_text.call_args[0][0]
    assert "权限请求" in call_text


@pytest.mark.asyncio
async def test_no_pane_id_returns_early():
    update, ctx, _, state = _make_update_context()
    state.session_topics["s1"] = 100
    state.sessions["s1"] = {"pane_id": None}
    await handle_message(update, ctx)
    call_text = update.message.reply_text.call_args[0][0]
    assert "pane" in call_text.lower() or "重新创建" in call_text


@pytest.mark.asyncio
async def test_inject_generic_exception():
    """inject_message 抛出未知异常时回复错误信息。"""
    update, ctx, _, state = _make_update_context()
    state.session_topics["s1"] = 100
    state.sessions["s1"] = {"pane_id": "%1"}
    with patch("session.inject_message", new_callable=AsyncMock,
               side_effect=RuntimeError("tmux broken")), \
         patch("session.get_topic_lock") as mock_lock:
        lock = AsyncMock()
        lock.__aenter__ = AsyncMock(return_value=None)
        lock.__aexit__ = AsyncMock(return_value=False)
        mock_lock.return_value = lock
        await handle_message(update, ctx)
    call_text = update.message.reply_text.call_args[0][0]
    assert "发送失败" in call_text


@pytest.mark.asyncio
async def test_inject_success_reply():
    """inject 成功后回复确认消息。"""
    update, ctx, _, state = _make_update_context()
    state.session_topics["s1"] = 100
    state.sessions["s1"] = {"pane_id": "%1"}
    with patch("session.inject_message", new_callable=AsyncMock) as mock_inject, \
         patch("session.get_topic_lock") as mock_lock:
        lock = AsyncMock()
        lock.__aenter__ = AsyncMock(return_value=None)
        lock.__aexit__ = AsyncMock(return_value=False)
        mock_lock.return_value = lock
        await handle_message(update, ctx)
    call_text = update.message.reply_text.call_args[0][0]
    assert "已发送" in call_text


@pytest.mark.asyncio
async def test_private_chat_no_topic_shows_hint():
    """私聊中无 topic 时提示先完成配置。"""
    update, ctx, _, _ = _make_update_context(thread_id=None)
    update.effective_chat.type = "private"
    await handle_message(update, ctx)
    call_text = update.message.reply_text.call_args[0][0]
    assert "/start" in call_text


@pytest.mark.asyncio
async def test_no_message_returns_early():
    """update.message 为 None 时不报错。"""
    update, ctx, _, _ = _make_update_context()
    update.message = None
    await handle_message(update, ctx)
    # 不报错即可，无 reply_text 可调用
