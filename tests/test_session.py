"""session.py 单元测试。"""
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from session import (
    ANSI_ESCAPE_RE,
    CONTROL_CHAR_RE,
    TUI_PATTERNS,
    TuiState,
    PermissionPending,
    SessionDead,
    _capture_pane,
    detect_tui_state,
    get_tmux_lock,
    get_topic_lock,
    inject_message,
    interrupt_session,
    kill_session,
    launch_session,
    list_tmux_windows,
    respond_tui_permission,
)
from config import State


class TestControlCharFilter:
    def test_control_char_re(self):
        text = "hello\x00world\x07foo\x1fbar"
        cleaned = CONTROL_CHAR_RE.sub("", text)
        assert cleaned == "helloworldfoobar"

    def test_preserves_newline_tab(self):
        text = "line1\nline2\ttab"
        cleaned = CONTROL_CHAR_RE.sub("", text)
        assert "\n" in cleaned
        assert "\t" in cleaned

    def test_ansi_escape_re(self):
        text = "hello\x1b[32mgreen\x1b[0m normal"
        cleaned = ANSI_ESCAPE_RE.sub("", text)
        assert cleaned == "hellogreen normal"

    def test_combined_filter(self):
        text = "\x1b[1mbold\x1b[0m\x00hidden"
        text = ANSI_ESCAPE_RE.sub("", text)
        text = CONTROL_CHAR_RE.sub("", text)
        assert text == "boldhidden"


class TestTuiPatterns:
    def test_all_categories_present(self):
        assert "input_prompt" in TUI_PATTERNS
        assert "generating" in TUI_PATTERNS
        assert "exited" in TUI_PATTERNS
        assert "permission" in TUI_PATTERNS

    def test_pattern_types(self):
        for key, patterns in TUI_PATTERNS.items():
            assert isinstance(patterns, list)
            for p in patterns:
                assert isinstance(p, str)


class TestDetectTuiState:
    @pytest.mark.asyncio
    async def test_input_state(self):
        mock_output = "\n\n\nSome output\n> "
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=mock_output):
            state = await detect_tui_state("%1")
        assert state == TuiState.INPUT

    @pytest.mark.asyncio
    async def test_generating_state(self):
        mock_output = "line1\nline2\nthinking about this..."
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=mock_output):
            state = await detect_tui_state("%1")
        assert state == TuiState.GENERATING

    @pytest.mark.asyncio
    async def test_exited_state(self):
        mock_output = "Done.\nuser@host $ "
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=mock_output):
            state = await detect_tui_state("%1")
        assert state == TuiState.EXITED

    @pytest.mark.asyncio
    async def test_permission_state(self):
        mock_output = "Claude wants to run:\nrm -rf /tmp\nDo you want to allow this? (y/n)"
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=mock_output):
            state = await detect_tui_state("%1")
        assert state == TuiState.PERMISSION_PROMPT

    @pytest.mark.asyncio
    async def test_permission_priority_over_exited(self):
        mock_output = "$ prompt\nDo you want to proceed? (y/n)"
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=mock_output):
            state = await detect_tui_state("%1")
        assert state == TuiState.PERMISSION_PROMPT

    @pytest.mark.asyncio
    async def test_default_generating(self):
        mock_output = "some random output\nno patterns here"
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=mock_output):
            state = await detect_tui_state("%1")
        assert state == TuiState.GENERATING

    @pytest.mark.asyncio
    async def test_empty_output(self):
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=""):
            state = await detect_tui_state("%1")
        assert state == TuiState.GENERATING


class TestCapturPane:
    @pytest.mark.asyncio
    async def test_filters_control_chars(self):
        raw = "hello\x00\x1b[32mworld\x1b[0m\x07"
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=raw):
            result = await _capture_pane("%1")
        assert "\x00" not in result
        assert "\x1b" not in result
        assert "helloworld" in result


class TestLocks:
    def test_topic_lock_cached(self):
        lock1 = get_topic_lock(1)
        lock2 = get_topic_lock(1)
        assert lock1 is lock2

    def test_different_topic_locks(self):
        lock1 = get_topic_lock(100)
        lock2 = get_topic_lock(200)
        assert lock1 is not lock2

    def test_tmux_lock_cached(self):
        lock1 = get_tmux_lock("%1")
        lock2 = get_tmux_lock("%1")
        assert lock1 is lock2


class TestLaunchSession:
    @pytest.mark.asyncio
    async def test_returns_session_info(self):
        mock_exec = AsyncMock(side_effect=["", "%5\n"])
        with patch("session._tmux_exec", mock_exec):
            info = await launch_session("/tmp/project", State(), None)
        assert len(info.session_id) == 8
        assert info.pane_id == "%5"
        assert info.cwd == "/tmp/project"
        assert info.source == "telegram"


class TestInjectMessage:
    @pytest.mark.asyncio
    async def test_inject_in_input_state(self):
        mock_exec = AsyncMock(return_value="> \n")
        with patch("session._tmux_exec", mock_exec), \
             patch("session._load_buffer_paste", new_callable=AsyncMock) as mock_paste:
            await inject_message("%1", "hello")
        mock_paste.assert_called_once()

    @pytest.mark.asyncio
    async def test_inject_in_generating_sends_escape(self):
        call_count = 0
        async def mock_exec(*args):
            nonlocal call_count
            if args[0] == "capture-pane":
                call_count += 1
                return "thinking...\n" if call_count == 1 else "> \n"
            return ""
        with patch("session._tmux_exec", side_effect=mock_exec), \
             patch("session._load_buffer_paste", new_callable=AsyncMock):
            await inject_message("%1", "hello")

    @pytest.mark.asyncio
    async def test_inject_in_exited_raises(self):
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value="user@host $ \n"):
            with pytest.raises(SessionDead):
                await inject_message("%1", "hello")

    @pytest.mark.asyncio
    async def test_inject_in_permission_raises(self):
        with patch("session._tmux_exec", new_callable=AsyncMock,
                   return_value="Do you want to run? (y/n)\n"):
            with pytest.raises(PermissionPending):
                await inject_message("%1", "hello")


class TestInterruptSession:
    @pytest.mark.asyncio
    async def test_sends_escape(self):
        mock_exec = AsyncMock(return_value="")
        with patch("session._tmux_exec", mock_exec):
            await interrupt_session("%1")
        mock_exec.assert_called_with("send-keys", "-t", "%1", "Escape", "")


class TestKillSession:
    @pytest.mark.asyncio
    async def test_kills_window(self):
        mock_exec = AsyncMock(return_value="")
        with patch("session._tmux_exec", mock_exec):
            await kill_session("cp-abc123")
        mock_exec.assert_called_with("kill-window", "-t", "cp-abc123")


class TestRespondTuiPermission:
    @pytest.mark.asyncio
    async def test_allow(self):
        mock_exec = AsyncMock(return_value="")
        with patch("session._tmux_exec", mock_exec):
            await respond_tui_permission("%1", True)
        mock_exec.assert_called_with("send-keys", "-t", "%1", "y", "")

    @pytest.mark.asyncio
    async def test_deny(self):
        mock_exec = AsyncMock(return_value="")
        with patch("session._tmux_exec", mock_exec):
            await respond_tui_permission("%1", False)
        mock_exec.assert_called_with("send-keys", "-t", "%1", "n", "")


class TestListTmuxWindows:
    @pytest.mark.asyncio
    async def test_parses_output(self):
        output = "cp-abc1 %1\ncp-def2 %2\nbot %0\n"
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=output):
            result = await list_tmux_windows()
        assert len(result) == 2
        assert result[0]["window_name"] == "cp-abc1"
        assert result[1]["pane_id"] == "%2"

    @pytest.mark.asyncio
    async def test_empty_output(self):
        with patch("session._tmux_exec", new_callable=AsyncMock, return_value=""):
            result = await list_tmux_windows()
        assert result == []
