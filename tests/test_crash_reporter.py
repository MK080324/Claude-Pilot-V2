"""crash_reporter.py 单元测试。"""
from __future__ import annotations
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from crash_reporter import (
    _check_pid_alive, _extract_traceback, _handle_state_change, _send_telegram_message,
)


def test_check_pid_alive_success():
    with patch("os.kill") as mock_kill:
        mock_kill.return_value = None
        assert _check_pid_alive(1234) is True
        mock_kill.assert_called_once_with(1234, 0)


def test_check_pid_alive_dead():
    with patch("os.kill", side_effect=OSError("No such process")):
        assert _check_pid_alive(9999) is False


def test_extract_traceback_with_traceback(tmp_path):
    log = tmp_path / "bot.log"
    lines = ["INFO normal line\n"] * 10
    lines.append("Traceback (most recent call last):\n")
    lines.append('  File "bot.py", line 42, in main\n')
    lines.append("RuntimeError: something broke\n")
    log.write_text("".join(lines))
    result = _extract_traceback(str(log))
    assert "Traceback" in result
    assert "RuntimeError" in result


def test_extract_traceback_no_traceback(tmp_path):
    log = tmp_path / "bot.log"
    log.write_text("INFO all good\nINFO still good\n")
    result = _extract_traceback(str(log))
    assert result == ""


def test_extract_traceback_missing_file():
    result = _extract_traceback("/nonexistent/bot.log")
    assert result == ""


def test_extract_traceback_truncation(tmp_path):
    log = tmp_path / "bot.log"
    lines = ["Traceback (most recent call last):\n"]
    lines.extend(["  very long line " * 20 + "\n"] * 30)
    log.write_text("".join(lines))
    result = _extract_traceback(str(log))
    assert len(result) <= 500


def test_send_telegram_message():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = MagicMock()
        _send_telegram_message("TOKEN123", 456, "test msg")
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert "botTOKEN123/sendMessage" in req.full_url
        body = json.loads(req.data)
        assert body["chat_id"] == 456
        assert body["text"] == "test msg"
        assert body["parse_mode"] == "HTML"


def test_send_telegram_message_error_suppressed():
    with patch("urllib.request.urlopen", side_effect=Exception("network error")):
        _send_telegram_message("TOK", 1, "msg")  # should not raise


def test_restart_count_warning_at_threshold(tmp_path):
    log = tmp_path / "bot.log"
    log.write_text("INFO normal\n")
    calls: list[str] = []
    with patch("crash_reporter._send_telegram_message", side_effect=lambda t, c, msg: calls.append(msg)):
        # Simulate 5 consecutive crashes (was_alive=True, alive=False)
        count = 0
        for _ in range(5):
            count = _handle_state_change(True, False, count, "T", 1, str(log))
    assert count == 5
    # First 4 crashes: 1 message each (crash notification only)
    # 5th crash: 2 messages (crash notification + warning)
    assert len(calls) == 6  # 5 crash + 1 warning
    assert any("警告" in c for c in calls)
    assert any("5 次" in c for c in calls)


def test_restart_count_no_warning_below_threshold(tmp_path):
    log = tmp_path / "bot.log"
    log.write_text("")
    calls: list[str] = []
    with patch("crash_reporter._send_telegram_message", side_effect=lambda t, c, msg: calls.append(msg)):
        count = 0
        for _ in range(4):
            count = _handle_state_change(True, False, count, "T", 1, str(log))
    assert count == 4
    assert len(calls) == 4  # 4 crash notifications, no warning
    assert not any("警告" in c for c in calls)


def test_recovery_notification():
    calls: list[str] = []
    with patch("crash_reporter._send_telegram_message", side_effect=lambda t, c, msg: calls.append(msg)):
        _handle_state_change(False, True, 3, "T", 1, "/nonexistent")
    assert len(calls) == 1
    assert "已恢复" in calls[0]
