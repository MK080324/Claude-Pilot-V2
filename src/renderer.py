"""Markdown 到 Telegram HTML 渲染。"""
from __future__ import annotations

import mistune


class TelegramHTMLRenderer(mistune.HTMLRenderer):
    """自定义 mistune 渲染器，输出 Telegram 支持的 HTML 子集。"""
    pass


def render_markdown(text: str) -> str:
    """Markdown 转 Telegram HTML。"""
    raise NotImplementedError


def split_message(html: str, limit: int = 4096) -> list[str]:
    """智能分段，确保每段 <= limit 字符。"""
    raise NotImplementedError


def format_tool_use(name: str, input_data: dict) -> str:
    """格式化工具调用为人类可读摘要。"""
    raise NotImplementedError
