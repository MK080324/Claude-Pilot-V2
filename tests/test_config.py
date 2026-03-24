"""config.py 单元测试。"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from config import Config, SessionInfo, State, load_env, load_state, save_state


class TestLoadEnv:
    def test_parse_key_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("BOT_TOKEN=abc123\nPORT=8266\n")
        result = load_env(str(env_file))
        assert result["BOT_TOKEN"] == "abc123"
        assert result["PORT"] == "8266"

    def test_ignore_comments_and_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY=value\n  \n# another\n")
        result = load_env(str(env_file))
        assert result == {"KEY": "value"}

    def test_quoted_values(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('A="hello world"\nB=\'single\'\n')
        result = load_env(str(env_file))
        assert result["A"] == "hello world"
        assert result["B"] == "single"

    def test_value_with_equals(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("URL=http://host?a=1&b=2\n")
        result = load_env(str(env_file))
        assert result["URL"] == "http://host?a=1&b=2"

    def test_empty_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("EMPTY=\n")
        result = load_env(str(env_file))
        assert result["EMPTY"] == ""


class TestSaveState:
    def test_atomic_write(self, tmp_path):
        state = State(group_chat_id=123, sessions={"s1": {"k": "v"}})
        path = str(tmp_path / ".state.json")
        save_state(state, path)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["group_chat_id"] == 123
        assert data["sessions"] == {"s1": {"k": "v"}}
        # No .tmp residue
        tmp_files = [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
        assert tmp_files == []

    def test_overwrite_existing(self, tmp_path):
        path = str(tmp_path / ".state.json")
        save_state(State(group_chat_id=1), path)
        save_state(State(group_chat_id=2), path)
        with open(path) as f:
            data = json.load(f)
        assert data["group_chat_id"] == 2


class TestLoadState:
    def test_file_not_exist(self, tmp_path):
        state = load_state(str(tmp_path / "nonexistent.json"))
        assert state.group_chat_id is None
        assert state.notify_chat_id is None
        assert state.sessions == {}
        assert state.session_topics == {}

    def test_load_existing(self, tmp_path):
        path = tmp_path / ".state.json"
        data = {
            "group_chat_id": 42,
            "notify_chat_id": 99,
            "sessions": {"abc": {"cwd": "/tmp"}},
            "session_topics": {"abc": 1},
        }
        path.write_text(json.dumps(data))
        state = load_state(str(path))
        assert state.group_chat_id == 42
        assert state.notify_chat_id == 99
        assert state.sessions == {"abc": {"cwd": "/tmp"}}
        assert state.session_topics == {"abc": 1}


class TestDataclasses:
    def test_config_defaults(self):
        c = Config()
        assert c.bot_token == ""
        assert c.allowed_users == []
        assert c.bot_port == 8266
        assert c.project_dir == ""

    def test_state_defaults(self):
        s = State()
        assert s.group_chat_id is None
        assert s.sessions == {}

    def test_session_info_fields(self):
        si = SessionInfo(
            session_id="abc", transcript_path="/tmp/t.jsonl",
            cwd="/home", pane_id="%1", topic_id=5, source="telegram",
        )
        assert si.session_id == "abc"
        assert si.pane_id == "%1"
        assert si.topic_id == 5
