"""api.py 单元测试。"""
import asyncio
import os
import sys
from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from api import PermissionRequest, create_api_app, pending_permissions
from config import State


@pytest.fixture
def state():
    return State(group_chat_id=123, sessions={"abc12345": {"cwd": "/tmp"}},
                 session_topics={"abc12345": 1})


@pytest.fixture
async def client(state):
    app = create_api_app(state, MagicMock())
    app["permission_timeout"] = 1
    async with TestClient(TestServer(app)) as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_session_start_created(client):
    resp = await client.post("/session_start", json={
        "session_id": "deadbeef", "transcript_path": "/tmp/t.jsonl",
        "cwd": "/tmp", "tmux_pane": None,
    })
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_session_start_exists(client):
    resp = await client.post("/session_start", json={
        "session_id": "abc12345", "transcript_path": "/tmp/t.jsonl",
        "cwd": "/tmp", "tmux_pane": None,
    })
    data = await resp.json()
    assert data["status"] == "exists"
    assert data["topic_id"] == 1


@pytest.mark.asyncio
async def test_session_start_no_group():
    app = create_api_app(State(), MagicMock())
    async with TestClient(TestServer(app)) as c:
        resp = await c.post("/session_start", json={
            "session_id": "deadbeef", "transcript_path": "/tmp/t.jsonl",
            "cwd": "/tmp", "tmux_pane": None,
        })
        data = await resp.json()
        assert data["status"] == "no_group"


@pytest.mark.asyncio
async def test_session_id_invalid(client):
    resp = await client.post("/session_start", json={
        "session_id": "INVALID!@#", "transcript_path": "/tmp/t.jsonl",
        "cwd": "/tmp", "tmux_pane": None,
    })
    assert resp.status == 400


@pytest.mark.asyncio
async def test_session_id_valid_uuid(client):
    resp = await client.post("/session_start", json={
        "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "transcript_path": "/tmp/t.jsonl", "cwd": "/tmp", "tmux_pane": None,
    })
    assert resp.status == 200


@pytest.mark.asyncio
async def test_session_stop(client):
    resp = await client.post("/session_stop", json={
        "session_id": "abc12345", "message": "done",
    })
    data = await resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_permission_timeout(client):
    resp = await client.post("/permission", json={
        "session_id": "abc12345", "description": "run rm -rf",
    })
    data = await resp.json()
    assert data["decision"] == "deny"
    assert data["reason"] == "timeout"


@pytest.mark.asyncio
async def test_permission_allow():
    app = create_api_app(State(group_chat_id=1), MagicMock())
    app["permission_timeout"] = 5
    async with TestClient(TestServer(app)) as c:
        async def approve():
            await asyncio.sleep(0.2)
            req = pending_permissions.get("abc12345")
            if req:
                req.decision = "allow"
                req.reason = "approved"
                req.event.set()
        task = asyncio.create_task(approve())
        resp = await c.post("/permission", json={
            "session_id": "abc12345", "description": "test action",
        })
        data = await resp.json()
        assert data["decision"] == "allow"
        await task


@pytest.mark.asyncio
async def test_notification(client):
    resp = await client.post("/notification", json={
        "session_id": "abc12345", "message": "hello",
    })
    data = await resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_bind_host(state):
    app = create_api_app(state, MagicMock())
    assert app["host"] == "127.0.0.1"


def test_permission_request_dataclass():
    pr = PermissionRequest(description="test", session_id="abc")
    assert pr.decision == ""
    assert pr.reason == ""
    assert isinstance(pr.event, asyncio.Event)
