"""
Unit & REST API route tests for TAPERC Public Gateway.
Tests health, default-device routes (Phase 1), explicit device routes, and authorization.
"""

import json
import pytest
from aiohttp.test_utils import TestClient
from unittest.mock import AsyncMock

from src.connection_manager import ConnectionManager


@pytest.mark.asyncio
async def test_health_endpoint(test_client: TestClient):
    resp = await test_client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "taperc-public-gateway"
    assert data["version"] == "1.0.0"
    assert "https://taperc.aaiq.nl" in data["public_url"]


@pytest.mark.asyncio
async def test_info_endpoint(test_client: TestClient):
    resp = await test_client.get("/api/v1/info")
    assert resp.status == 200
    data = await resp.json()
    assert data["gateway"] == "TAPERC Public Gateway"
    assert "wss://taperc.aaiq.nl/device/connect" in data["device_ws_endpoint"]
    assert data["default_device_id"] == "AAIQ-RBP-TEST1"


@pytest.mark.asyncio
async def test_list_devices_unauthorized(test_client: TestClient):
    resp = await test_client.get("/api/v1/devices")
    assert resp.status == 401


@pytest.mark.asyncio
async def test_list_devices_authorized(test_client: TestClient):
    resp = await test_client.get("/api/v1/devices", headers={"Authorization": "Bearer test_client_token_abc"})
    assert resp.status == 200
    data = await resp.json()
    assert "devices" in data
    assert len(data["devices"]) == 2


@pytest.mark.asyncio
async def test_device_status_offline(test_client: TestClient):
    resp = await test_client.get(
        "/api/v1/device/AAIQ-RBP-TEST1/status",
        headers={"Authorization": "Bearer test_client_token_abc"},
    )
    assert resp.status == 503
    data = await resp.json()
    assert data["online"] is False


@pytest.mark.asyncio
async def test_default_device_routes(test_client: TestClient):
    """Verifies that Phase-1 routes operate on TAPERC_DEFAULT_DEVICE_ID seamlessly."""
    cm: ConnectionManager = test_client.app["connection_manager"]
    mock_ws = AsyncMock()
    mock_ws.closed = False

    async def mock_send(cmd):
        req_id = cmd["request_id"]
        action = cmd["action"]
        params = cmd.get("params", {})
        if action == "get_status":
            cm.handle_device_response("AAIQ-RBP-TEST1", req_id, True, {"relay1": True, "relay2": False})
        elif action == "relay":
            cm.handle_device_response("AAIQ-RBP-TEST1", req_id, True, {"relay": params.get("relay"), "state": params.get("state")})
        elif action == "pulse":
            cm.handle_device_response("AAIQ-RBP-TEST1", req_id, True, {"relay": params.get("relay"), "duration_ms": params.get("duration_ms")})
        elif action == "all_off":
            cm.handle_device_response("AAIQ-RBP-TEST1", req_id, True, {"all_off": True})

    mock_ws.send_json.side_effect = mock_send
    await cm.register_device("AAIQ-RBP-TEST1", mock_ws)

    headers = {"Authorization": "Bearer test_client_token_abc"}

    # GET /api/v1/status (Default device)
    resp = await test_client.get("/api/v1/status", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["device_id"] == "AAIQ-RBP-TEST1"
    assert data["online"] is True

    # POST /api/v1/relay/1 (Default device)
    resp = await test_client.post("/api/v1/relay/1", json={"state": True}, headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["relay"] == 1
    assert data["state"] is True

    # POST /api/v1/relay/2/on (Default device)
    resp = await test_client.post("/api/v1/relay/2/on", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["relay"] == 2
    assert data["state"] is True

    # POST /api/v1/relay/2/off (Default device)
    resp = await test_client.post("/api/v1/relay/2/off", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["relay"] == 2
    assert data["state"] is False

    # POST /api/v1/relay/3/pulse (Default device)
    resp = await test_client.post("/api/v1/relay/3/pulse", json={"duration_ms": 350}, headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["relay"] == 3
    assert data["duration_ms"] == 350

    # POST /api/v1/all/off (Default device)
    resp = await test_client.post("/api/v1/all/off", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True

    await cm.unregister_device("AAIQ-RBP-TEST1")


@pytest.mark.asyncio
async def test_explicit_device_command_routes(test_client: TestClient):
    """Verifies that explicit device paths operate properly."""
    cm: ConnectionManager = test_client.app["connection_manager"]
    mock_ws = AsyncMock()
    mock_ws.closed = False

    async def mock_send(cmd):
        req_id = cmd["request_id"]
        action = cmd["action"]
        params = cmd.get("params", {})
        if action == "relay":
            cm.handle_device_response("AAIQ-RBP-TEST1", req_id, True, {"relay": params.get("relay"), "state": params.get("state")})
        elif action == "pulse":
            cm.handle_device_response("AAIQ-RBP-TEST1", req_id, True, {"relay": params.get("relay"), "duration_ms": params.get("duration_ms")})
        elif action == "all_off":
            cm.handle_device_response("AAIQ-RBP-TEST1", req_id, True, {"all_off": True})

    mock_ws.send_json.side_effect = mock_send
    await cm.register_device("AAIQ-RBP-TEST1", mock_ws)
    headers = {"Authorization": "Bearer test_client_token_abc"}

    # POST /api/v1/device/AAIQ-RBP-TEST1/relay/1/on
    resp = await test_client.post("/api/v1/device/AAIQ-RBP-TEST1/relay/1/on", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["state"] is True

    # POST /api/v1/device/AAIQ-RBP-TEST1/relay/1/off
    resp = await test_client.post("/api/v1/device/AAIQ-RBP-TEST1/relay/1/off", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["state"] is False

    # POST /api/v1/device/AAIQ-RBP-TEST1/relay/2/pulse
    resp = await test_client.post(
        "/api/v1/device/AAIQ-RBP-TEST1/relay/2/pulse",
        json={"duration_ms": 250},
        headers=headers,
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["duration_ms"] == 250

    # POST /api/v1/device/AAIQ-RBP-TEST1/all/off
    resp = await test_client.post(
        "/api/v1/device/AAIQ-RBP-TEST1/all/off",
        headers=headers,
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True

    await cm.unregister_device("AAIQ-RBP-TEST1")
