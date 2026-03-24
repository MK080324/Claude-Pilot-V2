"""InlineKeyboard 回调处理。"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """按钮回调入口。"""
    raise NotImplementedError
