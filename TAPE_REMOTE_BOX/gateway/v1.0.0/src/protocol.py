"""
TAPERC Public Gateway — Protocol & Message Definitions
Defines JSON message schemas, action types, validation logic, and serialization helpers.
"""

import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional, Tuple, Union

# Message Types
MSG_AUTH = "auth"
MSG_AUTH_CHALLENGE = "auth_challenge"
MSG_AUTH_REQUEST = "auth_request"
MSG_AUTH_ACK = "auth_ack"
MSG_PING = "ping"
MSG_PONG = "pong"
MSG_STATUS = "status"
MSG_COMMAND = "command"
MSG_RESPONSE = "response"
MSG_DEVICE_STATUS = "device_status"
MSG_SUBSCRIBE = "subscribe"
MSG_ERROR = "error"

# Action Types
ACTION_RELAY = "relay"
ACTION_PULSE = "pulse"
ACTION_ALL_OFF = "all_off"
ACTION_GET_STATUS = "get_status"
ACTION_GET_INFO = "get_info"
ACTION_OTA_CHECK = "ota_check"
ACTION_OTA_STATUS = "ota_status"
ACTION_OTA_INSTALL = "ota_install"

VALID_ACTIONS = {
    ACTION_RELAY,
    ACTION_PULSE,
    ACTION_ALL_OFF,
    ACTION_GET_STATUS,
    ACTION_GET_INFO,
    ACTION_OTA_CHECK,
    ACTION_OTA_STATUS,
    ACTION_OTA_INSTALL,
}


class ProtocolError(Exception):
    def __init__(self, message: str, code: str = "PROTOCOL_ERROR", request_id: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.request_id = request_id


def generate_request_id() -> str:
    """Generates a unique request/correlation identifier."""
    return f"req_{uuid.uuid4().hex[:12]}"


def parse_message(raw_data: Union[str, bytes]) -> Dict[str, Any]:
    """Parses a JSON WebSocket payload."""
    if isinstance(raw_data, bytes):
        try:
            raw_data = raw_data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ProtocolError(f"Malformed UTF-8 message: {e}", code="MALFORMED_UTF8")

    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"Invalid JSON payload: {e}", code="INVALID_JSON")

    if not isinstance(data, dict):
        raise ProtocolError("Message payload must be a JSON object", code="INVALID_PAYLOAD_TYPE")

    msg_type = data.get("type")
    if not msg_type or not isinstance(msg_type, str):
        raise ProtocolError("Missing or invalid 'type' field in message", code="MISSING_TYPE")

    return data


def create_auth_challenge(nonce: str, expires_in: int = 60) -> Dict[str, Any]:
    """Creates an HMAC authentication challenge for connecting devices."""
    return {
        "type": MSG_AUTH_CHALLENGE,
        "nonce": nonce,
        "expires_in": expires_in,
        "timestamp": time.time(),
    }


def compute_hmac_sha256(secret: str, data: str) -> str:
    """Calculates HMAC-SHA256 hex digest for the given secret and string payload."""
    return hmac.new(
        secret.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_auth_ack(
    success: bool,
    message: str = "",
    device_id: Optional[str] = None,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": MSG_AUTH_ACK,
        "success": bool(success),
        "timestamp": time.time(),
    }
    if message:
        payload["message"] = message
    if device_id:
        payload["device_id"] = device_id
    if client_id:
        payload["client_id"] = client_id
    return payload


def create_ping() -> Dict[str, Any]:
    return {"type": MSG_PING, "timestamp": time.time()}


def create_pong() -> Dict[str, Any]:
    return {"type": MSG_PONG, "timestamp": time.time()}


def create_command(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "type": MSG_COMMAND,
        "request_id": request_id or generate_request_id(),
        "action": action,
        "params": params or {},
        "timestamp": time.time(),
    }


def create_response(
    request_id: str,
    success: bool,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    device_id: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": MSG_RESPONSE,
        "request_id": request_id,
        "success": bool(success),
        "timestamp": time.time(),
    }
    if device_id:
        payload["device_id"] = device_id
    if data is not None:
        payload["data"] = data
    if error is not None:
        payload["error"] = str(error)
    return payload


def create_device_status_event(
    device_id: str,
    online: bool,
    status: Optional[Dict[str, Any]] = None,
    name: str = "",
) -> Dict[str, Any]:
    return {
        "type": MSG_DEVICE_STATUS,
        "device_id": device_id,
        "online": bool(online),
        "name": name,
        "status": status,
        "timestamp": time.time(),
    }


def create_error(
    message: str,
    code: str = "BAD_REQUEST",
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": MSG_ERROR,
        "message": message,
        "code": code,
        "timestamp": time.time(),
    }
    if request_id:
        payload["request_id"] = request_id
    return payload


def validate_relay_number(relay: Any, max_relays: int = 8) -> int:
    try:
        r = int(relay)
    except (ValueError, TypeError):
        raise ProtocolError(f"Invalid relay number: '{relay}'. Must be an integer 1-{max_relays}", code="INVALID_RELAY")
    if r < 1 or r > max_relays:
        raise ProtocolError(f"Relay number {r} out of range (1-{max_relays})", code="RELAY_OUT_OF_RANGE")
    return r


def validate_pulse_duration(duration_ms: Any, min_ms: int = 10, max_ms: int = 10000) -> int:
    try:
        d = int(duration_ms)
    except (ValueError, TypeError):
        raise ProtocolError(f"Invalid pulse duration: '{duration_ms}'. Must be an integer", code="INVALID_DURATION")
    if d < min_ms or d > max_ms:
        raise ProtocolError(f"Pulse duration {d}ms out of range ({min_ms}-{max_ms}ms)", code="DURATION_OUT_OF_RANGE")
    return d
