"""Markdown 到 Telegram HTML 渲染。"""
from __future__ import annotations

import json
import re
from html import escape

import mistune
from mistune.plugins.formatting import strikethrough


class TelegramHTMLRenderer(mistune.HTMLRenderer):
    """自定义 mistune 渲染器，输出 Telegram 支持的 HTML 子集。"""

    def text(self, text: str) -> str:
        return escape(text)

    def strong(self, text: str) -> str:
        return f"<b>{text}</b>"

    def emphasis(self, text: str) -> str:
        return f"<i>{text}</i>"

    def codespan(self, text: str) -> str:
        return f"<code>{escape(text)}</code>"

    def block_code(self, code: str, info: str | None = None) -> str:
        if info:
            return f'<pre><code class="language-{escape(info)}">{escape(code)}</code></pre>\n'
        return f"<pre>{escape(code)}</pre>\n"

    def link(self, text: str, url: str, title: str | None = None) -> str:
        return f'<a href="{escape(url)}">{text}</a>'

    def heading(self, text: str, level: int, **attrs) -> str:
        return f"<b>{text}</b>\n"

    def image(self, text: str, url: str, title: str | None = None) -> str:
        alt = text or ""
        return f'<a href="{escape(url)}">[图片] {alt}</a>'

    def thematic_break(self) -> str:
        return "\n---\n"

    def paragraph(self, text: str) -> str:
        return f"{text}\n\n"

    def list(self, text: str, ordered: bool, **attrs) -> str:
        return text

    def list_item(self, text: str) -> str:
        return f"• {text.strip()}\n"

    def linebreak(self) -> str:
        return "\n"

    def softbreak(self) -> str:
        return "\n"

    def block_quote(self, text: str) -> str:
        return f"<blockquote>{text.strip()}</blockquote>\n\n"


def _render_strikethrough(renderer: object, text: str) -> str:
    return f"<s>{text}</s>"


def render_markdown(text: str) -> str:
    """Markdown 转 Telegram HTML。"""
    renderer = TelegramHTMLRenderer(escape=False)
    md = mistune.Markdown(renderer=renderer)
    strikethrough(md)
    md.renderer.register("strikethrough", _render_strikethrough)
    result = md(text)
    return result.strip() if result else ""


def split_message(html: str, limit: int = 4096) -> list[str]:
    """智能分段，确保每段 <= limit 字符。"""
    if not html:
        return []
    if len(html) <= limit:
        return [html]
    # 按段落边界切分
    paragraphs = html.split("\n\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(para) <= limit:
                current = para
            else:
                # 单段超长，按行切分
                for line_chunk in _split_by_lines(para, limit):
                    chunks.append(line_chunk)
                current = ""
    if current:
        chunks.append(current)
    return chunks


def _split_by_lines(text: str, limit: int) -> list[str]:
    """按行切分超长段落。"""
    lines = text.split("\n")
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(line) <= limit:
                current = line
            else:
                for hard in _hard_split(line, limit):
                    chunks.append(hard)
                current = ""
    if current:
        chunks.append(current)
    return chunks


_TAG_RE = re.compile(r"<[^>]+>")


def _hard_split(text: str, limit: int) -> list[str]:
    """硬切超长行，不在 HTML 标签中间切。"""
    chunks: list[str] = []
    while len(text) > limit:
        cut = limit
        # 检查是否在标签中间
        for m in _TAG_RE.finditer(text):
            if m.start() < cut < m.end():
                cut = m.start()
                break
        if cut == 0:
            cut = limit  # 无法避免，强制切
        chunks.append(text[:cut])
        text = text[cut:]
    if text:
        chunks.append(text)
    return chunks


def format_tool_use(name: str, input_data: dict) -> str:
    """格式化工具调用为人类可读摘要。"""
    if name == "Bash":
        cmd = input_data.get("command", "")
        return f"🔧 <b>Bash</b>: <code>{escape(cmd)}</code>"
    if name in ("Edit", "Write"):
        fp = input_data.get("file_path", "")
        return f"📝 <b>{escape(name)}</b>: <code>{escape(fp)}</code>"
    if name == "Read":
        fp = input_data.get("file_path", "")
        return f"📖 <b>Read</b>: <code>{escape(fp)}</code>"
    summary = json.dumps(input_data, ensure_ascii=False)
    if len(summary) > 100:
        summary = summary[:100] + "..."
    return f"🔧 <b>{escape(name)}</b>: {escape(summary)}"
