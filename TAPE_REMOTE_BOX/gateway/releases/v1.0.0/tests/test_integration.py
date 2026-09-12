"""
End-to-End WebSocket Integration Tests for TAPERC Public Gateway.
Verifies bidirectional communication between Device and Client WebSockets
using HMAC-SHA256 challenge-response authentication and real-time event distribution.
"""

import asyncio
import json
import pytest
from aiohttp.test_utils import TestClient

from src.protocol import (
    MSG_AUTH,
    MSG_AUTH_ACK,
    MSG_AUTH_CHALLENGE,
    MSG_AUTH_REQUEST,
    MSG_COMMAND,
    MSG_DEVICE_STATUS,
    MSG_PING,
    MSG_PONG,
    MSG_RESPONSE,
    MSG_STATUS,
    MSG_SUBSCRIBE,
    compute_hmac_sha256,
)


@pytest.mark.asyncio
async def test_websocket_device_and_client_e2e(test_client: TestClient):
    # 1. Connect Device WS to /device/connect
    dev_ws = await test_client.ws_connect("/device/connect")

    # Gateway immediately issues HMAC challenge nonce
    challenge_msg = await dev_ws.receive_json()
    assert challenge_msg["type"] == MSG_AUTH_CHALLENGE
    nonce = challenge_msg["nonce"]
    assert len(nonce) == 64

    # Device computes HMAC-SHA256 over nonce using its secret ("secret_test_key_123")
    signature = compute_hmac_sha256("secret_test_key_123", nonce)

    await dev_ws.send_json(
        {
            "type": MSG_AUTH,
            "device_id": "AAIQ-RBP-TEST1",
            "nonce": nonce,
            "signature": signature,
            "firmware": "1.0.0",
            "relay_count": 8,
        }
    )

    # Device receives auth_ack
    auth_ack = await dev_ws.receive_json()
    assert auth_ack["type"] == MSG_AUTH_ACK
    assert auth_ack["success"] is True

    # 2. Connect Client WS to /client/connect
    client_ws = await test_client.ws_connect("/client/connect?token=test_client_token_abc")

    # Client receives auth_ack
    client_msg = await client_ws.receive_json()
    assert client_msg["type"] == MSG_AUTH_ACK
    assert client_msg["success"] is True

    # 3. Client subscribes to AAIQ-RBP-TEST1
    await client_ws.send_json({"type": MSG_SUBSCRIBE, "device_id": "AAIQ-RBP-TEST1"})

    # Client receives immediate status snapshot
    sub_msg = await client_ws.receive_json()
    assert sub_msg["type"] == MSG_DEVICE_STATUS
    assert sub_msg["device_id"] == "AAIQ-RBP-TEST1"
    assert sub_msg["online"] is True

    # 4. Device sends status broadcast
    status_payload = {
        "relays": {
            "1": "active",
            "2": "rest",
            "3": "rest",
            "4": "rest",
            "5": "rest",
            "6": "rest",
            "7": "rest",
            "8": "rest",
        }
    }
    await dev_ws.send_json({"type": MSG_STATUS, "status": status_payload})

    # Client receives real-time device_status event
    broadcast_evt = await client_ws.receive_json()
    assert broadcast_evt["type"] == MSG_DEVICE_STATUS
    assert broadcast_evt["device_id"] == "AAIQ-RBP-TEST1"
    assert broadcast_evt["status"] == status_payload

    # 5. Client sends a command to Device via WebSocket
    await client_ws.send_json(
        {
            "type": MSG_COMMAND,
            "device_id": "AAIQ-RBP-TEST1",
            "action": "relay",
            "params": {"relay": 1, "state": True},
            "request_id": "cmd_001",
        }
    )

    # Device receives forwarded command
    dev_cmd = await dev_ws.receive_json()
    assert dev_cmd["type"] == MSG_COMMAND
    assert dev_cmd["action"] == "relay"
    assert dev_cmd["params"]["relay"] == 1

    # Device responds
    await dev_ws.send_json(
        {
            "type": MSG_RESPONSE,
            "request_id": dev_cmd["request_id"],
            "success": True,
            "data": {"relay": 1, "state": True},
        }
    )

    # Client receives command result
    cmd_result = await client_ws.receive_json()
    assert cmd_result["type"] == "command_result"
    assert cmd_result["request_id"] == "cmd_001"
    assert cmd_result["success"] is True
    assert cmd_result["data"]["state"] is True

    # 6. Test Ping/Pong on Device
    await dev_ws.send_json({"type": MSG_PING})
    pong_msg = await dev_ws.receive_json()
    assert pong_msg["type"] == MSG_PONG

    # 7. Disconnect Device and verify Client is notified of offline event
    await dev_ws.close()

    offline_evt = await client_ws.receive_json()
    assert offline_evt["type"] == MSG_DEVICE_STATUS
    assert offline_evt["device_id"] == "AAIQ-RBP-TEST1"
    assert offline_evt["online"] is False

    await client_ws.close()


@pytest.mark.asyncio
async def test_websocket_device_hmac_auth_failure_wrong_secret(test_client: TestClient):
    dev_ws = await test_client.ws_connect("/device/connect")
    challenge_msg = await dev_ws.receive_json()
    nonce = challenge_msg["nonce"]

    # Wrong secret
    wrong_sig = compute_hmac_sha256("completely_wrong_secret", nonce)

    await dev_ws.send_json(
        {
            "type": MSG_AUTH,
            "device_id": "AAIQ-RBP-TEST1",
            "nonce": nonce,
            "signature": wrong_sig,
        }
    )
    ack = await dev_ws.receive_json()
    assert ack["type"] == MSG_AUTH_ACK
    assert ack["success"] is False

    # WebSocket is closed by gateway on failed challenge
    await dev_ws.close()


@pytest.mark.asyncio
async def test_websocket_device_auth_request_fresh_challenge(test_client: TestClient):
    dev_ws = await test_client.ws_connect("/device/connect")
    first_challenge = await dev_ws.receive_json()
    first_nonce = first_challenge["nonce"]

    # Device explicitly asks for a fresh challenge
    await dev_ws.send_json({"type": MSG_AUTH_REQUEST, "device_id": "AAIQ-RBP-TEST1"})
    second_challenge = await dev_ws.receive_json()
    second_nonce = second_challenge["nonce"]
    assert second_nonce != first_nonce

    # Authenticate with the second nonce
    sig = compute_hmac_sha256("secret_test_key_123", second_nonce)
    await dev_ws.send_json(
        {
            "type": MSG_AUTH,
            "device_id": "AAIQ-RBP-TEST1",
            "nonce": second_nonce,
            "signature": sig,
        }
    )
    ack = await dev_ws.receive_json()
    assert ack["type"] == MSG_AUTH_ACK
    assert ack["success"] is True

    await dev_ws.close()


@pytest.mark.asyncio
async def test_websocket_client_auth_failure(test_client: TestClient):
    client_ws = await test_client.ws_connect("/client/connect?token=invalid_client_token")
    await client_ws.send_json({"type": MSG_AUTH, "token": "invalid_client_token"})
    msg = await client_ws.receive_json()
    assert msg["type"] == MSG_AUTH_ACK
    assert msg["success"] is False
    await client_ws.close()
