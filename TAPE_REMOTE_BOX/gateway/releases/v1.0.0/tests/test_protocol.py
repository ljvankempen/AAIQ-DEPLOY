"""
Unit tests for TAPERC Protocol message serialization, parsing, and validation.
"""

import json
import pytest

from src.protocol import (
    ACTION_ALL_OFF,
    ACTION_PULSE,
    ACTION_RELAY,
    MSG_AUTH,
    MSG_AUTH_ACK,
    MSG_AUTH_CHALLENGE,
    MSG_AUTH_REQUEST,
    MSG_COMMAND,
    MSG_DEVICE_STATUS,
    MSG_ERROR,
    MSG_PING,
    MSG_PONG,
    MSG_RESPONSE,
    ProtocolError,
    compute_hmac_sha256,
    create_auth_ack,
    create_auth_challenge,
    create_command,
    create_device_status_event,
    create_error,
    create_ping,
    create_pong,
    create_response,
    parse_message,
    validate_pulse_duration,
    validate_relay_number,
)


def test_parse_message_valid():
    payload = json.dumps({"type": "ping", "timestamp": 1234567.89})
    parsed = parse_message(payload)
    assert parsed["type"] == "ping"
    assert parsed["timestamp"] == 1234567.89

    bytes_payload = payload.encode("utf-8")
    parsed_bytes = parse_message(bytes_payload)
    assert parsed_bytes["type"] == "ping"


def test_parse_message_invalid():
    with pytest.raises(ProtocolError) as exc_info:
        parse_message("not a valid json")
    assert exc_info.value.code == "INVALID_JSON"

    with pytest.raises(ProtocolError) as exc_info:
        parse_message(json.dumps([1, 2, 3]))
    assert exc_info.value.code == "INVALID_PAYLOAD_TYPE"

    with pytest.raises(ProtocolError) as exc_info:
        parse_message(json.dumps({"no_type_field": "val"}))
    assert exc_info.value.code == "MISSING_TYPE"


def test_message_creation_helpers():
    challenge = create_auth_challenge("abc123nonce", expires_in=30)
    assert challenge["type"] == MSG_AUTH_CHALLENGE
    assert challenge["nonce"] == "abc123nonce"
    assert challenge["expires_in"] == 30

    hmac_val = compute_hmac_sha256("secret_key", "test_payload")
    assert isinstance(hmac_val, str)
    assert len(hmac_val) == 64

    ack = create_auth_ack(True, "OK", device_id="DEV1")
    assert ack["type"] == MSG_AUTH_ACK
    assert ack["success"] is True
    assert ack["device_id"] == "DEV1"

    cmd = create_command(ACTION_RELAY, params={"relay": 1, "state": True}, request_id="req_123")
    assert cmd["type"] == MSG_COMMAND
    assert cmd["request_id"] == "req_123"
    assert cmd["action"] == ACTION_RELAY
    assert cmd["params"]["relay"] == 1

    resp = create_response("req_123", True, data={"relay1": True})
    assert resp["type"] == MSG_RESPONSE
    assert resp["request_id"] == "req_123"
    assert resp["success"] is True
    assert resp["data"] == {"relay1": True}

    evt = create_device_status_event("DEV1", True, {"relays": {"1": "active"}})
    assert evt["type"] == MSG_DEVICE_STATUS
    assert evt["device_id"] == "DEV1"
    assert evt["online"] is True

    err = create_error("Failed", code="FORBIDDEN", request_id="req_123")
    assert err["type"] == MSG_ERROR
    assert err["message"] == "Failed"
    assert err["code"] == "FORBIDDEN"
    assert err["request_id"] == "req_123"


def test_validation_helpers():
    # Relays
    assert validate_relay_number(1) == 1
    assert validate_relay_number("8") == 8

    with pytest.raises(ProtocolError):
        validate_relay_number(0)

    with pytest.raises(ProtocolError):
        validate_relay_number(9)

    with pytest.raises(ProtocolError):
        validate_relay_number("invalid")

    # Pulse duration
    assert validate_pulse_duration(250) == 250
    assert validate_pulse_duration("500") == 500

    with pytest.raises(ProtocolError):
        validate_pulse_duration(5)  # below min 10ms

    with pytest.raises(ProtocolError):
        validate_pulse_duration(15000)  # above max 10000ms
