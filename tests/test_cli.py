"""claude-pilot CLI 单元测试。"""
from __future__ import annotations
import importlib
import os
from unittest.mock import patch, MagicMock

import pytest

# Import the CLI module (file without .py extension)
import importlib.util
import importlib.machinery
_cli_path = os.path.join(os.path.dirname(__file__), "..", "src", "claude-pilot")
_loader = importlib.machinery.SourceFileLoader("claude_pilot_cli", _cli_path)
_spec = importlib.util.spec_from_file_location("claude_pilot_cli", _cli_path, loader=_loader)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


def test_help_contains_subcommands(capsys):
    with pytest.raises(SystemExit) as exc:
        with patch("sys.argv", ["claude-pilot", "--help"]):
            cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("start", "stop", "status", "enable", "disable", "logs", "uninstall"):
        assert cmd in out


def test_status_running(capsys, tmp_path):
    pid_file = tmp_path / ".pid"
    pid_file.write_text("12345")
    with patch.object(cli, "PID_PATH", str(pid_file)), \
         patch("os.kill") as mock_kill:
        mock_kill.return_value = None
        cli.cmd_status(MagicMock())
    out = capsys.readouterr().out
    assert "运行中" in out
    assert "12345" in out


def test_status_not_running(capsys, tmp_path):
    pid_file = tmp_path / ".pid"
    # no pid file
    with patch.object(cli, "PID_PATH", str(pid_file)):
        cli.cmd_status(MagicMock())
    out = capsys.readouterr().out
    assert "未运行" in out


def test_status_dead_pid(capsys, tmp_path):
    pid_file = tmp_path / ".pid"
    pid_file.write_text("99999")
    with patch.object(cli, "PID_PATH", str(pid_file)), \
         patch("os.kill", side_effect=OSError("No such process")):
        cli.cmd_status(MagicMock())
    out = capsys.readouterr().out
    assert "未运行" in out


def test_stop_sends_sigterm(capsys, tmp_path):
    pid_file = tmp_path / ".pid"
    pid_file.write_text("12345")
    import signal
    with patch.object(cli, "PID_PATH", str(pid_file)), \
         patch("os.kill") as mock_kill:
        cli.cmd_stop(MagicMock())
        mock_kill.assert_called_once_with(12345, signal.SIGTERM)


def test_enable_writes_plist(tmp_path):
    plist_path = str(tmp_path / "com.claude-pilot.plist")
    with patch.object(cli, "PLIST_PATH", plist_path), \
         patch.object(cli, "BASE_DIR", str(tmp_path)), \
         patch.object(cli, "LOG_PATH", str(tmp_path / "bot.log")), \
         patch("subprocess.run") as mock_run:
        cli.cmd_enable(MagicMock())
        mock_run.assert_called_once()
    content = open(plist_path).read()
    assert "KeepAlive" in content
    assert "RunAtLoad" in content
    assert "ThrottleInterval" in content
    assert "<integer>30</integer>" in content


def test_disable_removes_plist(tmp_path):
    plist_path = str(tmp_path / "com.claude-pilot.plist")
    with open(plist_path, "w") as f:
        f.write("<plist/>")
    with patch.object(cli, "PLIST_PATH", plist_path), \
         patch("subprocess.run") as mock_run:
        cli.cmd_disable(MagicMock())
        mock_run.assert_called_once()
    assert not os.path.exists(plist_path)


def test_uninstall_with_backup(capsys, tmp_path):
    """卸载时从备份恢复 settings.json。"""
    import json
    base_dir = tmp_path / "claude-pilot"
    base_dir.mkdir()
    pid_file = base_dir / ".pid"

    # 准备备份文件
    backup = base_dir / "settings.json.backup"
    original_settings = {"theme": "dark"}
    backup.write_text(json.dumps(original_settings))

    # 准备当前被修改过的 settings
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_file = claude_dir / "settings.json"
    settings_file.write_text(json.dumps({"hooks": {"SessionStart": []}}))

    with patch.object(cli, "BASE_DIR", str(base_dir)), \
         patch.object(cli, "PID_PATH", str(pid_file)), \
         patch.object(cli, "PLIST_PATH", str(tmp_path / "plist")), \
         patch("os.path.expanduser", side_effect=lambda p: str(tmp_path / p.lstrip("~/"))), \
         patch("subprocess.run"):
        cli.cmd_uninstall(MagicMock())

    # settings 应被恢复为备份内容
    restored = json.loads(settings_file.read_text())
    assert restored == original_settings
    out = capsys.readouterr().out
    assert "已从备份恢复" in out


def test_uninstall_without_backup_removes_hooks(capsys, tmp_path):
    """无备份时，从 settings.json 中移除 claude-pilot hooks。"""
    import json
    base_dir = tmp_path / "claude-pilot"
    base_dir.mkdir()
    pid_file = base_dir / ".pid"

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_file = claude_dir / "settings.json"
    pilot_hook_cmd = str(base_dir / "hooks" / "session_start.py")
    settings_file.write_text(json.dumps({
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": f"python3 {pilot_hook_cmd}"}]}],
            "CustomHook": [{"hooks": [{"type": "command", "command": "echo hi"}]}],
        },
        "other": "value",
    }))

    with patch.object(cli, "BASE_DIR", str(base_dir)), \
         patch.object(cli, "PID_PATH", str(pid_file)), \
         patch.object(cli, "PLIST_PATH", str(tmp_path / "plist")), \
         patch("os.path.expanduser", side_effect=lambda p: str(tmp_path / p.lstrip("~/"))), \
         patch("subprocess.run"):
        cli.cmd_uninstall(MagicMock())

    restored = json.loads(settings_file.read_text())
    assert "SessionStart" not in restored.get("hooks", {})
    assert "CustomHook" in restored.get("hooks", {})
    assert restored["other"] == "value"


def test_uninstall_deletes_base_dir(tmp_path):
    """卸载后项目目录被删除。"""
    base_dir = tmp_path / "claude-pilot"
    base_dir.mkdir()
    (base_dir / "bot.py").write_text("# bot")

    with patch.object(cli, "BASE_DIR", str(base_dir)), \
         patch.object(cli, "PID_PATH", str(base_dir / ".pid")), \
         patch.object(cli, "PLIST_PATH", str(tmp_path / "plist")), \
         patch("os.path.expanduser", side_effect=lambda p: str(tmp_path / p.lstrip("~/"))), \
         patch("subprocess.run"):
        cli.cmd_uninstall(MagicMock())

    assert not base_dir.exists()
