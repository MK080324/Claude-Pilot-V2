"""集成测试：跨模块端到端链路验证。"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api import PermissionRequest, create_api_app, pending_permissions
from config import State, load_env


# ──────────────────────────────────────────────
# TC-6-006: Hook -> API 链路
# ──────────────────────────────────────────────

@pytest.fixture
def state_with_group():
    return State(group_chat_id=100)


@pytest.fixture
async def api_client(state_with_group):
    app = create_api_app(state_with_group, MagicMock())
    app["permission_timeout"] = 2
    async with TestClient(TestServer(app)) as c:
        yield c


@pytest.mark.asyncio
async def test_hook_api_session_start_created(api_client):
    """POST /session_start -> 返回 status=created。"""
    resp = await api_client.post("/session_start", json={
        "session_id": "deadbeef",
        "transcript_path": "/tmp/t.jsonl",
        "cwd": "/tmp",
        "tmux_pane": None,
    })
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_hook_api_session_start_no_group():
    """无 group_chat_id 时返回 no_group。"""
    app = create_api_app(State(), MagicMock())
    async with TestClient(TestServer(app)) as c:
        resp = await c.post("/session_start", json={
            "session_id": "deadbeef",
            "transcript_path": "/tmp/t.jsonl",
            "cwd": "/tmp",
            "tmux_pane": None,
        })
        data = await resp.json()
        assert data["status"] == "no_group"


@pytest.mark.asyncio
async def test_hook_api_health(api_client):
    """GET /health 返回 running。"""
    resp = await api_client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "running"


# ──────────────────────────────────────────────
# TC-6-007: 消息注入链路
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_message_inject_pipeline():
    """TG 消息 -> messages handler -> inject_message 被调用且参数正确。"""
    from handlers.messages import handle_message
    from config import Config

    update = MagicMock()
    update.effective_user.id = 42
    update.message.message_thread_id = 77
    update.message.text = "run tests"
    update.message.reply_text = AsyncMock()

    state = State()
    state.session_topics["sess1"] = 77
    state.sessions["sess1"] = {"pane_id": "%3"}

    config = Config(bot_token="tok", allowed_users=[42])
    context = MagicMock()
    context.bot_data = {"config": config, "state": state}

    with patch("session.inject_message", new_callable=AsyncMock) as mock_inject, \
         patch("session.get_topic_lock") as mock_lock:
        lock = AsyncMock()
        lock.__aenter__ = AsyncMock(return_value=None)
        lock.__aexit__ = AsyncMock(return_value=False)
        mock_lock.return_value = lock

        await handle_message(update, context)
        mock_inject.assert_called_once_with("%3", "run tests")


@pytest.mark.asyncio
async def test_message_inject_auth_rejected():
    """未授权用户不触发 inject_message。"""
    from handlers.messages import handle_message
    from config import Config

    update = MagicMock()
    update.effective_user.id = 999
    update.message.message_thread_id = 77
    update.message.text = "hello"
    update.message.reply_text = AsyncMock()

    state = State()
    state.session_topics["sess1"] = 77
    state.sessions["sess1"] = {"pane_id": "%3"}

    config = Config(bot_token="tok", allowed_users=[42])
    context = MagicMock()
    context.bot_data = {"config": config, "state": state}

    with patch("session.inject_message", new_callable=AsyncMock) as mock_inject:
        await handle_message(update, context)
        mock_inject.assert_not_called()


# ──────────────────────────────────────────────
# TC-6-008: 权限审批全链路
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_permission_full_pipeline_allow():
    """POST /permission -> 模拟 callback allow -> 返回 decision=allow。"""
    app = create_api_app(State(group_chat_id=1), MagicMock())
    app["permission_timeout"] = 5

    async with TestClient(TestServer(app)) as c:
        async def simulate_approve():
            await asyncio.sleep(0.15)
            req = pending_permissions.get("abc12345")
            if req:
                req.decision = "allow"
                req.reason = "user approved"
                req.event.set()

        task = asyncio.create_task(simulate_approve())
        resp = await c.post("/permission", json={
            "session_id": "abc12345",
            "description": "write file /etc/hosts",
        })
        data = await resp.json()
        await task
        assert data["decision"] == "allow"
        assert data["reason"] == "user approved"


@pytest.mark.asyncio
async def test_permission_full_pipeline_deny():
    """POST /permission -> 模拟 callback deny -> 返回 decision=deny。"""
    app = create_api_app(State(group_chat_id=1), MagicMock())
    app["permission_timeout"] = 5

    async with TestClient(TestServer(app)) as c:
        async def simulate_deny():
            await asyncio.sleep(0.15)
            req = pending_permissions.get("abc12345")
            if req:
                req.decision = "deny"
                req.reason = "user denied"
                req.event.set()

        task = asyncio.create_task(simulate_deny())
        resp = await c.post("/permission", json={
            "session_id": "abc12345",
            "description": "delete /tmp/data",
        })
        data = await resp.json()
        await task
        assert data["decision"] == "deny"


@pytest.mark.asyncio
async def test_permission_timeout_returns_deny():
    """超时未审批时自动返回 deny。"""
    app = create_api_app(State(group_chat_id=1), MagicMock())
    app["permission_timeout"] = 1

    async with TestClient(TestServer(app)) as c:
        resp = await c.post("/permission", json={
            "session_id": "abc12345",
            "description": "some action",
        })
        data = await resp.json()
        assert data["decision"] == "deny"
        assert data["reason"] == "timeout"


# ──────────────────────────────────────────────
# TC-6-009: .env 格式验证
# ──────────────────────────────────────────────

def test_env_format_all_fields():
    """load_env 解析标准 .env，所有必填字段完整。"""
    env_content = (
        "BOT_TOKEN=123456:ABCDEF\n"
        "ALLOWED_USERS=111,222,333\n"
        "BOT_PORT=8266\n"
        "NOTIFY_CHAT_ID=\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(env_content)
        tmp_path = f.name
    try:
        data = load_env(tmp_path)
        assert "BOT_TOKEN" in data
        assert data["BOT_TOKEN"] == "123456:ABCDEF"
        assert "ALLOWED_USERS" in data
        assert data["ALLOWED_USERS"] == "111,222,333"
        assert "BOT_PORT" in data
        assert data["BOT_PORT"] == "8266"
    finally:
        os.unlink(tmp_path)


def test_env_format_empty_notify():
    """NOTIFY_CHAT_ID 可为空值。"""
    env_content = "BOT_TOKEN=tok\nALLOWED_USERS=1\nBOT_PORT=8266\nNOTIFY_CHAT_ID=\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(env_content)
        tmp_path = f.name
    try:
        data = load_env(tmp_path)
        assert data.get("NOTIFY_CHAT_ID", "") == ""
    finally:
        os.unlink(tmp_path)


# ──────────────────────────────────────────────
# TC-6-010: hooks JSON 合并验证
# ──────────────────────────────────────────────

def _run_merge_logic(existing: dict, install_dir: str) -> dict:
    """模拟 install.sh 中的 Python 内联合并逻辑。"""
    new_hooks = {
        "session_start": [{"command": f"python3 {install_dir}/hooks/session_start.py"}],
        "stop": [{"command": f"python3 {install_dir}/hooks/stop.py"}],
        "notification": [{"command": f"python3 {install_dir}/hooks/notification.py"}],
        "permission": [
            {"command": f"python3 {install_dir}/hooks/permission.py", "timeout": 120}
        ],
    }
    existing_hooks = existing.get("hooks", {})
    for hook_name, hook_entries in new_hooks.items():
        if hook_name not in existing_hooks:
            existing_hooks[hook_name] = hook_entries
        else:
            existing_cmds = {
                (e.get("command", "") if isinstance(e, dict) else e)
                for e in existing_hooks[hook_name]
            }
            for entry in hook_entries:
                cmd = entry.get("command", "") if isinstance(entry, dict) else entry
                if cmd not in existing_cmds:
                    existing_hooks[hook_name].append(entry)
    existing["hooks"] = existing_hooks
    return existing


def test_hooks_merge_adds_new():
    """空 settings -> 合并后所有 claude-pilot hooks 都存在。"""
    result = _run_merge_logic({}, "/home/user/.claude-pilot")
    assert "session_start" in result["hooks"]
    assert "stop" in result["hooks"]
    assert "notification" in result["hooks"]
    assert "permission" in result["hooks"]


def test_hooks_merge_preserves_existing():
    """已有 hooks 不被覆盖，新 hooks 追加。"""
    existing = {
        "hooks": {
            "session_start": [{"command": "echo existing-hook"}],
            "custom_hook": [{"command": "echo custom"}],
        }
    }
    result = _run_merge_logic(existing, "/home/user/.claude-pilot")
    # 原有条目保留
    session_start_cmds = [
        e.get("command", "") for e in result["hooks"]["session_start"]
    ]
    assert "echo existing-hook" in session_start_cmds
    # 新条目也被追加
    assert any("session_start.py" in cmd for cmd in session_start_cmds)
    # 自定义 hook 保留
    assert "custom_hook" in result["hooks"]


def test_hooks_merge_no_duplicate():
    """已存在相同 command 的条目不重复添加。"""
    install_dir = "/home/user/.claude-pilot"
    existing_cmd = f"python3 {install_dir}/hooks/stop.py"
    existing = {
        "hooks": {
            "stop": [{"command": existing_cmd}],
        }
    }
    result = _run_merge_logic(existing, install_dir)
    stop_cmds = [e.get("command", "") for e in result["hooks"]["stop"]]
    assert stop_cmds.count(existing_cmd) == 1


def test_hooks_merge_creates_from_empty():
    """原 settings.json 不含 hooks 字段时，正确创建。"""
    result = _run_merge_logic({"other_key": "value"}, "/tmp/.claude-pilot")
    assert "hooks" in result
    assert "permission" in result["hooks"]
    perm = result["hooks"]["permission"][0]
    assert perm.get("timeout") == 120
