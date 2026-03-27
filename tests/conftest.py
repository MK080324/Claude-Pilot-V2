"""公共 fixture 和路径配置。

pythonpath 已在 pyproject.toml 中配置为 ["src"]，
无需 sys.path.insert。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from config import Config, State


@pytest.fixture
def config():
    """默认 Config，允许 user_id=123。"""
    return Config(bot_token="test-token", allowed_users=[123], project_dir="/tmp/proj")


@pytest.fixture
def state():
    """空 State。"""
    return State()


@pytest.fixture
def mock_bot():
    """AsyncMock bot，create_forum_topic 返回 topic_id=99。"""
    bot = AsyncMock()
    topic = MagicMock()
    topic.message_thread_id = 99
    bot.create_forum_topic.return_value = topic
    return bot


@pytest.fixture
def make_update():
    """工厂 fixture：创建 Telegram Update + Context mock。"""
    def _make(
        user_id: int = 123,
        chat_id: int = 456,
        chat_type: str = "supergroup",
        text: str = "hello",
        thread_id: int | None = None,
        callback_data: str | None = None,
    ) -> tuple[MagicMock, MagicMock]:
        update = MagicMock()
        update.effective_user.id = user_id
        update.effective_chat.id = chat_id
        update.effective_chat.type = chat_type
        update.message.text = text
        update.message.message_thread_id = thread_id
        update.message.reply_text = AsyncMock()

        if callback_data is not None:
            query = MagicMock()
            query.answer = AsyncMock()
            query.data = callback_data
            query.edit_message_text = AsyncMock()
            query.message.chat_id = chat_id
            update.callback_query = query

        context = MagicMock()
        context.bot = AsyncMock()
        return update, context

    return _make
