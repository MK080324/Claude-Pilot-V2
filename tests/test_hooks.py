"""hooks 单元测试。"""
import json
import os
import sys
import tempfile
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

from src.hooks._common import read_port, post_to_bot, ENV_PATH


class TestReadPort:
    def test_reads_port_from_env(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("BOT_TOKEN=abc\nBOT_PORT=9999\n")
        with patch("src.hooks._common.ENV_PATH", str(env_file)):
            assert read_port() == "9999"

    def test_default_when_no_file(self, tmp_path):
        with patch("src.hooks._common.ENV_PATH", str(tmp_path / "missing")):
            assert read_port() == "8266"

    def test_default_when_no_port_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("BOT_TOKEN=abc\n")
        with patch("src.hooks._common.ENV_PATH", str(env_file)):
            assert read_port() == "8266"

    def test_ignores_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# BOT_PORT=1111\nBOT_PORT=2222\n")
        with patch("src.hooks._common.ENV_PATH", str(env_file)):
            assert read_port() == "2222"

    def test_ignores_blank_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("\n\nBOT_PORT=3333\n\n")
        with patch("src.hooks._common.ENV_PATH", str(env_file)):
            assert read_port() == "3333"


class TestPostToBot:
    def test_successful_post(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("BOT_PORT=8266\n")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status":"ok"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("src.hooks._common.ENV_PATH", str(env_file)), \
             patch("src.hooks._common.urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = post_to_bot("/health", {"key": "val"})
            assert result == {"status": "ok"}
            call_args = mock_open.call_args
            req = call_args[0][0]
            assert "127.0.0.1:8266" in req.full_url
            assert req.get_header("Content-type") == "application/json"

    def test_returns_none_on_error(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("BOT_PORT=8266\n")
        with patch("src.hooks._common.ENV_PATH", str(env_file)), \
             patch("src.hooks._common.urllib.request.urlopen", side_effect=OSError):
            assert post_to_bot("/health", {}) is None


class TestSessionStartHook:
    def test_main_posts_session_start(self):
        stdin_data = json.dumps({
            "session_id": "abc12345",
            "type": "start",
            "transcript_path": "/tmp/t.jsonl",
            "cwd": "/home/user",
        })
        with patch("src.hooks.session_start.post_to_bot") as mock_post, \
             patch("src.hooks.session_start.sys.stdin", StringIO(stdin_data)), \
             patch.dict(os.environ, {"TMUX_PANE": "%5"}):
            from src.hooks.session_start import main
            main()
            mock_post.assert_called_once()
            payload = mock_post.call_args[0][1]
            assert payload["session_id"] == "abc12345"
            assert payload["tmux_pane"] == "%5"

    def test_main_empty_stdin(self):
        with patch("src.hooks.session_start.post_to_bot") as mock_post, \
             patch("src.hooks.session_start.sys.stdin", StringIO("")):
            from src.hooks.session_start import main
            main()
            mock_post.assert_not_called()


class TestPermissionHook:
    def test_main_returns_allow(self):
        stdin_data = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "session_id": "abc12345",
        })
        stdout = StringIO()
        with patch("src.hooks.permission.post_to_bot", return_value={"decision": "allow"}) as mock_post, \
             patch("src.hooks.permission.sys.stdin", StringIO(stdin_data)), \
             patch("src.hooks.permission.sys.stdout", stdout):
            from src.hooks.permission import main
            main()
            mock_post.assert_called_once()
            output = json.loads(stdout.getvalue())
            assert output["decision"] == "allow"

    def test_main_returns_deny_on_failure(self):
        stdin_data = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "session_id": "abc12345",
        })
        stdout = StringIO()
        with patch("src.hooks.permission.post_to_bot", return_value=None), \
             patch("src.hooks.permission.sys.stdin", StringIO(stdin_data)), \
             patch("src.hooks.permission.sys.stdout", stdout):
            from src.hooks.permission import main
            main()
            output = json.loads(stdout.getvalue())
            assert output["decision"] == "deny"

    def test_main_empty_stdin(self):
        stdout = StringIO()
        with patch("src.hooks.permission.post_to_bot") as mock_post, \
             patch("src.hooks.permission.sys.stdin", StringIO("")), \
             patch("src.hooks.permission.sys.stdout", stdout):
            from src.hooks.permission import main
            main()
            mock_post.assert_not_called()
            output = json.loads(stdout.getvalue())
            assert output["decision"] == "deny"


class TestNotificationHook:
    def test_main_posts_notification(self):
        stdin_data = json.dumps({
            "message": "Task done",
            "session_id": "abc12345",
        })
        with patch("src.hooks.notification.post_to_bot") as mock_post, \
             patch("src.hooks.notification.sys.stdin", StringIO(stdin_data)):
            from src.hooks.notification import main
            main()
            mock_post.assert_called_once()
            payload = mock_post.call_args[0][1]
            assert payload["message"] == "Task done"

    def test_main_empty_stdin(self):
        with patch("src.hooks.notification.post_to_bot") as mock_post, \
             patch("src.hooks.notification.sys.stdin", StringIO("")):
            from src.hooks.notification import main
            main()
            mock_post.assert_not_called()


class TestStopHook:
    def test_main_posts_stop(self):
        stdin_data = json.dumps({
            "session_id": "abc12345",
            "message": "Session ended",
        })
        with patch("src.hooks.stop.post_to_bot") as mock_post, \
             patch("src.hooks.stop.sys.stdin", StringIO(stdin_data)):
            from src.hooks.stop import main
            main()
            mock_post.assert_called_once()
            payload = mock_post.call_args[0][1]
            assert payload["session_id"] == "abc12345"
            assert payload["message"] == "Session ended"

    def test_main_empty_stdin(self):
        with patch("src.hooks.stop.post_to_bot") as mock_post, \
             patch("src.hooks.stop.sys.stdin", StringIO("")):
            from src.hooks.stop import main
            main()
            mock_post.assert_not_called()
