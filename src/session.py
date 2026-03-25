"""会话状态管理与 tmux 操作。"""
from __future__ import annotations

import asyncio
import enum
import glob
import os
import re
import tempfile
import uuid
from dataclasses import dataclass

from config import SessionInfo, State


class TuiState(enum.Enum):
    """TUI 四种状态。"""
    INPUT = "input"
    GENERATING = "generating"
    EXITED = "exited"
    PERMISSION_PROMPT = "permission_prompt"


CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

TUI_PATTERNS: dict[str, list[str]] = {
    "input_prompt": ["-- INSERT --", "❯"],
    "generating": ["thinking", "Generating", "streaming"],
    "exited": ["mserver", "fish"],
    "permission": ["Do you want to", "(y/n)", "Allow", "Deny"],
}

class SessionDead(Exception):
    """会话已退出。"""

class PermissionPending(Exception):
    """会话正在等待权限确认。"""

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


async def _tmux_exec(*args: str, check_pane: bool = False) -> str:
    """底层 tmux 命令执行封装。"""
    proc = await asyncio.create_subprocess_exec(
        "tmux", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if check_pane and proc.returncode != 0:
        raise SessionDead("pane not found")
    return stdout.decode("utf-8", errors="replace")


async def _capture_pane(pane_id: str) -> str:
    """捕获 pane 可见内容并过滤控制字符。"""
    raw = await _tmux_exec("capture-pane", "-t", pane_id, "-p", check_pane=True)
    if "Pane is dead" in raw:
        raise SessionDead("pane is dead")
    text = ANSI_ESCAPE_RE.sub("", raw)
    text = CONTROL_CHAR_RE.sub("", text)
    return text


async def _load_buffer_paste(pane_id: str, text: str) -> None:
    """通过 load-buffer + paste-buffer 安全注入多行文本。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(text)
        tmp = f.name
    try:
        await _tmux_exec("load-buffer", tmp)
        await _tmux_exec("paste-buffer", "-t", pane_id)
    finally:
        import os
        os.unlink(tmp)



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


SESSIONS_TMUX = "cp-sessions"

async def _ensure_sessions_tmux() -> None:
    """确保 Claude 会话用的 tmux session 存在。"""
    proc = await asyncio.create_subprocess_exec(
        "tmux", "has-session", "-t", SESSIONS_TMUX,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if proc.returncode != 0:
        await _tmux_exec("new-session", "-d", "-s", SESSIONS_TMUX)

async def launch_session(
    project_dir: str, state: State, bot: object
) -> SessionInfo:
    """在独立 tmux session 中创建窗口并启动 Claude。"""
    await _ensure_sessions_tmux()
    session_id = uuid.uuid4().hex[:8]
    window_name = f"cp-{session_id}"
    await _tmux_exec(
        "new-window", "-d", "-t", SESSIONS_TMUX,
        "-n", window_name,
        f"cd {project_dir} && claude",
    )
    pane_out = await _tmux_exec(
        "list-panes", "-t", f"{SESSIONS_TMUX}:{window_name}",
        "-F", "#{pane_id}",
    )
    pane_id = pane_out.strip().splitlines()[0] if pane_out.strip() else None
    transcript_path = await _find_transcript(project_dir)
    return SessionInfo(
        session_id=session_id, transcript_path=transcript_path,
        cwd=project_dir, pane_id=pane_id, topic_id=0, source="telegram",
    )


async def _find_transcript(project_dir: str, timeout: float = 15.0) -> str:
    """等待 Claude Code 创建 JSONL 并返回路径。"""
    encoded = project_dir.replace("/", "-")
    pat = os.path.expanduser(f"~/.claude/projects/{encoded}/*.jsonl")
    before = set(glob.glob(pat))
    for _ in range(int(timeout)):
        await asyncio.sleep(1.0)
        new = set(glob.glob(pat)) - before
        if new:
            return max(new, key=os.path.getmtime)
    all_f = glob.glob(pat)
    return max(all_f, key=os.path.getmtime) if all_f else ""


async def inject_message(pane_id: str, text: str) -> None:
    """状态感知式消息注入。"""
    async with get_tmux_lock(pane_id):
        state = await detect_tui_state(pane_id)
        if state == TuiState.EXITED:
            raise SessionDead("Session has exited")
        if state == TuiState.PERMISSION_PROMPT:
            raise PermissionPending("Permission prompt active")
        if state == TuiState.GENERATING:
            await _tmux_exec("send-keys", "-t", pane_id, "Escape", "")
            await asyncio.sleep(0.5)
        filtered = CONTROL_CHAR_RE.sub("", text)
        await _load_buffer_paste(pane_id, filtered)
        await _tmux_exec("send-keys", "-t", pane_id, "Enter", "")


async def interrupt_session(pane_id: str) -> None:
    """中断 Claude 生成（Escape）。"""
    await _tmux_exec("send-keys", "-t", pane_id, "Escape", "")


async def kill_session(window_name: str) -> None:
    """销毁 tmux 窗口。"""
    await _tmux_exec("kill-window", "-t", window_name)


async def respond_tui_permission(pane_id: str, allow: bool) -> None:
    """TUI 层权限响应（send-keys y/n）。"""
    key = "y" if allow else "n"
    await _tmux_exec("send-keys", "-t", pane_id, key, "")


