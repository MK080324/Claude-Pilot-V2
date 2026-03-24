"""普通消息处理。"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """消息处理入口。"""
    raise NotImplementedError
