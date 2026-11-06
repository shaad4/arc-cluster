import asyncio

import httpx
import pytest
from fastapi import HTTPException

from arc.agent import main as agent


def test_agent_authentication_and_controller_allowlist(tmp_path, monkeypatch):
    credentials = tmp_path / "token.json"
    token = "a" * 40
    credentials.write_text('{"token":"' + token + '"}')
    credentials.chmod(0o600)
    monkeypatch.setenv("ARC_AGENT_TOKEN_FILE", str(credentials))
    monkeypatch.setenv("ARC_AGENT_CONTROLLER", "100.118.85.127")

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(agent.app, client=("100.118.85.127", 1234)),
            base_url="http://agent",
        ) as client:
            assert (await client.get("/health")).status_code == 401
            headers = {"authorization": "Bearer " + token}
            assert (await client.get("/health", headers=headers)).status_code == 200
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(agent.app, client=("100.64.0.2", 1234)),
            base_url="http://agent",
        ) as client:
            assert (await client.get("/health", headers=headers)).status_code == 403

    asyncio.run(check())


def test_agent_controls_require_independent_state(monkeypatch):
    monkeypatch.setenv("ARC_AGENT_BIND", "100.124.19.50")
    monkeypatch.setenv("ARC_AGENT_ENABLE_CONTROLS", "1")
    monkeypatch.delenv("ARC_AGENT_STATE_URL", raising=False)

    async def check():
        with pytest.raises(HTTPException) as exc:
            await agent.preflight()
        assert exc.value.status_code == 409

    asyncio.run(check())


def test_recovery_does_not_restart_a_member(monkeypatch):
    async def state():
        return {"verified": True, "busy": False, "member": True, "ray_process": True}

    monkeypatch.setattr(agent, "preflight", state)

    async def check():
        with pytest.raises(HTTPException) as exc:
            await agent.control(agent.Control(action="recover", confirmed=True))
        assert exc.value.status_code == 409

    asyncio.run(check())
