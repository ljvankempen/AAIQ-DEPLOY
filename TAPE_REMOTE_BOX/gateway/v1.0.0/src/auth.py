"""
TAPERC Public Gateway — Authentication & Authorization
Provides secure HMAC-SHA256 challenge-response for devices, separated secrets store,
and client token authorization.
"""

from dataclasses import dataclass
import hmac
import json
import logging
import os
import secrets
import time
from typing import Dict, List, Optional, Tuple

from .config import ClientConfig, DeviceConfig, GatewayConfig
from .protocol import compute_hmac_sha256

logger = logging.getLogger("taperc.auth")


class SecretsStore:
    """
    Separate secrets storage to prevent exposing secret keys in the device registry.
    Maps secret_id / device_id to raw HMAC secrets.
    """

    def __init__(self, initial_secrets: Optional[Dict[str, str]] = None):
        self._secrets: Dict[str, str] = dict(initial_secrets or {})

    def get_secret(self, secret_id: str) -> Optional[str]:
        if not secret_id:
            return None
        # Try direct match or lowercase match
        return self._secrets.get(secret_id) or self._secrets.get(secret_id.lower())

    def set_secret(self, secret_id: str, secret: str) -> None:
        if secret_id and secret:
            self._secrets[secret_id] = secret

    def load_from_dict(self, d: Dict[str, str]) -> None:
        self._secrets.update(d)

    def load_from_file(self, path: str) -> None:
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "secrets" in data and isinstance(data["secrets"], dict):
                        self._secrets.update(data["secrets"])
                    else:
                        self._secrets.update(data)
        except Exception as e:
            logger.warning("Failed to load secrets from %s: %s", path, e)

    def all_secret_ids(self) -> List[str]:
        return list(self._secrets.keys())


@dataclass
class ActiveChallenge:
    nonce: str
    expires_at: float
    bound_device_id: Optional[str] = None


class AuthManager:
    """
    Manages HMAC challenge-response authentications for devices,
    client token verifications, and access control.
    """

    def __init__(self, config: GatewayConfig):
        self.config = config
        self.secrets_store = SecretsStore(config.security.secrets)
        self._devices: Dict[str, DeviceConfig] = {}
        self._clients_by_token: Dict[str, ClientConfig] = {}
        self._active_challenges: Dict[str, ActiveChallenge] = {}
        self.reload_config(config)

    def reload_config(self, config: GatewayConfig) -> None:
        """Reloads internal lookup tables from the given configuration."""
        self.config = config
        self.secrets_store = SecretsStore(config.security.secrets)
        if config.security.secrets_file:
            self.secrets_store.load_from_file(config.security.secrets_file)

        self._devices.clear()
        self._clients_by_token.clear()

        for dev in config.devices:
            if dev.device_id:
                self._devices[dev.device_id] = dev

        for cli in config.clients:
            if cli.token:
                self._clients_by_token[cli.token] = cli

    def create_challenge(self, device_id: Optional[str] = None, expires_in: int = 60) -> str:
        """
        Generates a cryptographically random 32-byte (64 hex characters) nonce.
        Stores the nonce with expiration and optional device binding.
        """
        self._cleanup_expired_challenges()

        nonce = secrets.token_hex(32)
        expires_at = time.time() + max(10, expires_in)
        self._active_challenges[nonce] = ActiveChallenge(
            nonce=nonce,
            expires_at=expires_at,
            bound_device_id=device_id,
        )
        return nonce

    def verify_device_challenge(self, device_id: str, nonce: str, signature: str) -> bool:
        """
        Validates HMAC-SHA256 signature for a previously issued challenge nonce.
        CRITICAL: Nonce is immediately deleted upon check to prevent replay attacks.
        Uses constant-time comparison.
        """
        if not device_id:
            return False

        if not self.config.security.require_device_auth:
            return True

        if not nonce or not signature:
            return False

        # Retrieve and immediately consume challenge (single-use guarantee)
        challenge = self._active_challenges.pop(nonce, None)
        if not challenge:
            logger.warning("HMAC auth failed for device %s: challenge nonce not found or already consumed", device_id)
            return False

        if time.time() > challenge.expires_at:
            logger.warning("HMAC auth failed for device %s: challenge nonce expired", device_id)
            return False

        if challenge.bound_device_id and challenge.bound_device_id != device_id:
            logger.warning(
                "HMAC auth failed: challenge bound to %s but used by %s",
                challenge.bound_device_id,
                device_id,
            )
            return False

        device = self._devices.get(device_id)
        if not device or not device.enabled:
            logger.warning("HMAC auth failed: device %s not registered or disabled", device_id)
            return False

        # Look up secret from separate SecretsStore by secret_id or device_id
        secret = self.secrets_store.get_secret(device.secret_id) or self.secrets_store.get_secret(device_id)
        if not secret:
            logger.warning("HMAC auth failed: no secret found for device %s (secret_id: %s)", device_id, device.secret_id)
            return False

        expected_signature = compute_hmac_sha256(secret, nonce)
        valid = hmac.compare_digest(expected_signature.lower(), signature.lower())

        if not valid:
            logger.warning("HMAC auth failed for device %s: invalid signature", device_id)

        return valid

    def _cleanup_expired_challenges(self) -> None:
        """Removes expired challenges to avoid memory accumulation."""
        now = time.time()
        expired = [k for k, v in self._active_challenges.items() if now > v.expires_at]
        for k in expired:
            self._active_challenges.pop(k, None)

    def authenticate_client(self, token: str) -> Optional[ClientConfig]:
        """Validates client token. If require_client_auth is False, returns a default operator client."""
        if not self.config.security.require_client_auth:
            return ClientConfig(
                client_id="anonymous",
                token="",
                allowed_devices=["*"],
                role="operator",
                enabled=True,
            )

        if not token:
            return None

        for registered_token, client in self._clients_by_token.items():
            if hmac.compare_digest(registered_token, token) and client.enabled:
                return client

        return None

    def is_client_authorized_for_device(self, client: ClientConfig, device_id: str) -> bool:
        """Checks if a client has permissions to access/command a specific device."""
        if not client or not client.enabled:
            return False

        if "*" in client.allowed_devices:
            return True

        return device_id in client.allowed_devices

    def verify_master_key(self, key: str) -> bool:
        """Verifies admin / master key for privileged gateway operations."""
        if not key or not self.config.security.master_key:
            return False
        return hmac.compare_digest(self.config.security.master_key, key)

    def get_device_info(self, device_id: str) -> Optional[DeviceConfig]:
        """Retrieves registered device configuration if present."""
        return self._devices.get(device_id)

    def list_registered_devices(self) -> List[DeviceConfig]:
        """Returns list of registered device configurations."""
        return list(self._devices.values())
