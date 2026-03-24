"""会话状态管理与 tmux 操作。"""
from __future__ import annotations

import asyncio
import enum
import re
from dataclasses import dataclass

from config import State


class TuiState(enum.Enum):
    """TUI 四种状态。"""
    INPUT = "input"
    GENERATING = "generating"
    EXITED = "exited"
    PERMISSION_PROMPT = "permission_prompt"


CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

TUI_PATTERNS: dict[str, list[str]] = {
    "input_prompt": [">"],
    "generating": ["thinking", "..."],
    "exited": ["$", "%", "#"],
    "permission": ["Do you want to", "(y/n)"],
}

# Lock 管理
_topic_locks: dict[int, asyncio.Lock] = {}
_tmux_locks: dict[str, asyncio.Lock] = {}


def get_topic_lock(topic_id: int) -> asyncio.Lock:
    """获取 per-topic 的 asyncio.Lock。"""
    if topic_id not in _topic_locks:
        _topic_locks[topic_id] = asyncio.Lock()
    return _topic_locks[topic_id]


def get_tmux_lock(pane_id: str) -> asyncio.Lock:
    """获取 per-pane 的 asyncio.Lock。"""
    if pane_id not in _tmux_locks:
        _tmux_locks[pane_id] = asyncio.Lock()
    return _tmux_locks[pane_id]


async def _tmux_exec(*args: str) -> str:
    """底层 tmux 命令执行封装。"""
    proc = await asyncio.create_subprocess_exec(
        "tmux", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode("utf-8", errors="replace")


async def _capture_pane(pane_id: str) -> str:
    """捕获 pane 可见内容并过滤控制字符。"""
    raw = await _tmux_exec("capture-pane", "-t", pane_id, "-p")
    text = ANSI_ESCAPE_RE.sub("", raw)
    text = CONTROL_CHAR_RE.sub("", text)
    return text


async def _load_buffer_paste(pane_id: str, text: str) -> None:
    """通过 load-buffer + paste-buffer 安全注入多行文本。"""
    raise NotImplementedError


async def _wait_for_state(
    pane_id: str, target_state: TuiState, timeout: float = 10.0
) -> bool:
    """轮询等待目标状态。"""
    raise NotImplementedError


async def detect_tui_state(pane_id: str) -> TuiState:
    """捕获 pane 内容并识别 TUI 状态。"""
    content = await _capture_pane(pane_id)
    lines = [l for l in content.splitlines() if l.strip()]
    tail = lines[-5:] if len(lines) >= 5 else lines
    text = "\n".join(tail)
    # 优先级: permission > exited > generating > input
    for pattern in TUI_PATTERNS["permission"]:
        if pattern in text:
            return TuiState.PERMISSION_PROMPT
    for pattern in TUI_PATTERNS["exited"]:
        if pattern in text:
            return TuiState.EXITED
    for pattern in TUI_PATTERNS["generating"]:
        if pattern in text:
            return TuiState.GENERATING
    for pattern in TUI_PATTERNS["input_prompt"]:
        if pattern in text:
            return TuiState.INPUT
    return TuiState.GENERATING


async def launch_session(
    project_dir: str, state: State, bot: object
) -> "SessionInfo":
    """创建 tmux 窗口并启动 Claude。"""
    raise NotImplementedError


async def inject_message(pane_id: str, text: str) -> None:
    """状态感知式消息注入。"""
    raise NotImplementedError


async def interrupt_session(pane_id: str) -> None:
    """中断 Claude 生成（Escape）。"""
    raise NotImplementedError


async def kill_session(window_name: str) -> None:
    """销毁 tmux 窗口。"""
    raise NotImplementedError


async def respond_tui_permission(pane_id: str, allow: bool) -> None:
    """TUI 层权限响应（send-keys y/n）。"""
    raise NotImplementedError


async def list_tmux_windows() -> list[dict]:
    """列出所有活跃的 Claude 窗口。"""
    raise NotImplementedError
