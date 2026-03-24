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
    _capture_pane,
    detect_tui_state,
    get_tmux_lock,
    get_topic_lock,
)


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
