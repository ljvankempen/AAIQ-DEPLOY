"""
Unit tests for TAPERC Connection & Session Manager.
Covers device registration, subscriptions, concurrent commands, reconnect handling,
and client cleanup.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.auth import AuthManager
from src.config import ClientConfig, GatewayConfig
from src.connection_manager import ConnectionManager, DeviceSession, ClientSession


@pytest.mark.asyncio
async def test_device_lifecycle(connection_manager: ConnectionManager):
    mock_ws = AsyncMock()
    mock_ws.closed = False

    # Register device
    session = await connection_manager.register_device(
        device_id="AAIQ-RBP-TEST1",
        ws=mock_ws,
        firmware_version="0.1.0",
        relay_count=8,
    )
    assert session.device_id == "AAIQ-RBP-TEST1"
    assert session.is_alive is True
    assert connection_manager.is_device_online("AAIQ-RBP-TEST1") is True
    assert connection_manager.get_device_session("AAIQ-RBP-TEST1") is session

    # Update status & heartbeat
    await connection_manager.update_device_status("AAIQ-RBP-TEST1", {"relay1": True})
    assert session.cached_status == {"relay1": True}

    # Summary
    summary = connection_manager.get_all_devices_summary()
    dev1 = next(d for d in summary if d["device_id"] == "AAIQ-RBP-TEST1")
    assert dev1["online"] is True
    assert dev1["firmware"] == "0.1.0"
    assert dev1["status"] == {"relay1": True}

    # Unregister
    await connection_manager.unregister_device("AAIQ-RBP-TEST1")
    assert connection_manager.is_device_online("AAIQ-RBP-TEST1") is False


@pytest.mark.asyncio
async def test_client_subscription_and_broadcast(connection_manager: ConnectionManager):
    mock_client_ws = AsyncMock()
    mock_client_ws.closed = False

    client_cfg = ClientConfig(
        client_id="test_sub_client",
        allowed_devices=["AAIQ-RBP-TEST1"],
        role="operator",
        enabled=True,
    )
    await connection_manager.register_client("s123", client_cfg, mock_client_ws)
    assert "s123" in connection_manager.clients

    ok = await connection_manager.subscribe_client("s123", "AAIQ-RBP-TEST1")
    assert ok is True

    # Broadcast device update
    await connection_manager.broadcast_device_status(
        device_id="AAIQ-RBP-TEST1",
        online=True,
        status={"relays": {"1": "pulse"}},
    )
    assert mock_client_ws.send_json.called

    await connection_manager.unregister_client("s123")
    assert "s123" not in connection_manager.clients


@pytest.mark.asyncio
async def test_send_command_to_device_success(connection_manager: ConnectionManager):
    mock_ws = AsyncMock()
    mock_ws.closed = False

    session = await connection_manager.register_device(
        device_id="AAIQ-RBP-TEST1",
        ws=mock_ws,
    )

    # Mock immediate response when send_json is called
    async def side_effect(cmd):
        req_id = cmd["request_id"]
        connection_manager.handle_device_response(
            device_id="AAIQ-RBP-TEST1",
            request_id=req_id,
            success=True,
            data={"relay": 1, "state": True},
        )

    mock_ws.send_json.side_effect = side_effect

    res = await connection_manager.send_command_to_device(
        device_id="AAIQ-RBP-TEST1",
        action="relay",
        params={"relay": 1, "state": True},
        timeout=1.0,
    )

    assert res == {"relay": 1, "state": True}
    await connection_manager.unregister_device("AAIQ-RBP-TEST1")


@pytest.mark.asyncio
async def test_send_command_device_offline(connection_manager: ConnectionManager):
    with pytest.raises(ConnectionError):
        await connection_manager.send_command_to_device("OFFLINE_DEV", action="all_off")


@pytest.mark.asyncio
async def test_concurrent_commands(connection_manager: ConnectionManager):
    """Verifies that multiple concurrent commands to the same device are correctly correlated and handled."""
    mock_ws = AsyncMock()
    mock_ws.closed = False

    await connection_manager.register_device("AAIQ-RBP-TEST1", mock_ws)

    async def side_effect(cmd):
        req_id = cmd["request_id"]
        action = cmd["action"]
        params = cmd["params"]
        # Simulate slight async processing delay
        await asyncio.sleep(0.01)
        connection_manager.handle_device_response(
            device_id="AAIQ-RBP-TEST1",
            request_id=req_id,
            success=True,
            data={"action": action, "relay": params.get("relay"), "state": params.get("state")},
        )

    mock_ws.send_json.side_effect = side_effect

    # Dispatch 5 commands in parallel
    tasks = [
        connection_manager.send_command_to_device(
            device_id="AAIQ-RBP-TEST1",
            action="relay",
            params={"relay": i, "state": True},
            timeout=2.0,
        )
        for i in range(1, 6)
    ]

    results = await asyncio.gather(*tasks)
    assert len(results) == 5
    for i, res in enumerate(results, start=1):
        assert res["relay"] == i
        assert res["state"] is True

    await connection_manager.unregister_device("AAIQ-RBP-TEST1")


@pytest.mark.asyncio
async def test_reconnect_handling(connection_manager: ConnectionManager):
    """Verifies that registering a new session for an already connected device cleanly replaces the old session."""
    old_ws = AsyncMock()
    old_ws.closed = False
    old_session = await connection_manager.register_device("AAIQ-RBP-TEST1", old_ws, firmware_version="1.0.0")

    assert connection_manager.get_device_session("AAIQ-RBP-TEST1") is old_session

    new_ws = AsyncMock()
    new_ws.closed = False
    new_session = await connection_manager.register_device("AAIQ-RBP-TEST1", new_ws, firmware_version="1.1.0")

    # Old websocket should have been closed
    assert old_ws.close.called
    assert connection_manager.get_device_session("AAIQ-RBP-TEST1") is new_session
    assert new_session.firmware_version == "1.1.0"

    await connection_manager.unregister_device("AAIQ-RBP-TEST1")


@pytest.mark.asyncio
async def test_client_disconnect_cleanup(connection_manager: ConnectionManager):
    """Verifies that dropped/failing clients are automatically cleaned up on broadcast."""
    broken_client_ws = AsyncMock()
    broken_client_ws.closed = False
    broken_client_ws.send_json.side_effect = Exception("Connection reset by peer")

    client_cfg = ClientConfig(client_id="flaky_client", allowed_devices=["*"], role="operator", enabled=True)
    await connection_manager.register_client("flaky_session", client_cfg, broken_client_ws)
    await connection_manager.subscribe_client("flaky_session", "AAIQ-RBP-TEST1")

    assert "flaky_session" in connection_manager.clients

    # Broadcasting to device status should encounter the error and clean up the client
    await connection_manager.broadcast_device_status(
        device_id="AAIQ-RBP-TEST1",
        online=True,
        status={"relay1": False},
    )

    assert "flaky_session" not in connection_manager.clients
