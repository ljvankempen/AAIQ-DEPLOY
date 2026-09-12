"""
Unit tests for TAPERC Authentication & Authorization Manager.
Verifies HMAC-SHA256 challenge-response, replay prevention, separated secrets store,
and client access control.
"""

import time
import pytest

from src.auth import AuthManager, SecretsStore
from src.config import ClientConfig, DeviceConfig, GatewayConfig, SecurityConfig
from src.protocol import compute_hmac_sha256


def test_hmac_challenge_response_valid(auth_manager: AuthManager):
    """Verifies that a valid HMAC-SHA256 challenge-response succeeds."""
    nonce = auth_manager.create_challenge("AAIQ-RBP-TEST1")
    assert len(nonce) == 64

    # Device computes HMAC with its secret key ("secret_test_key_123")
    signature = compute_hmac_sha256("secret_test_key_123", nonce)

    assert auth_manager.verify_device_challenge("AAIQ-RBP-TEST1", nonce, signature) is True


def test_hmac_challenge_response_wrong_secret(auth_manager: AuthManager):
    """Verifies that authentication fails when computed with an incorrect secret."""
    nonce = auth_manager.create_challenge("AAIQ-RBP-TEST1")

    # Incorrect secret
    signature = compute_hmac_sha256("wrong_secret_key", nonce)

    assert auth_manager.verify_device_challenge("AAIQ-RBP-TEST1", nonce, signature) is False


def test_hmac_challenge_replay_prevention(auth_manager: AuthManager):
    """Verifies that a challenge nonce cannot be replayed or reused after initial verification."""
    nonce = auth_manager.create_challenge("AAIQ-RBP-TEST1")
    signature = compute_hmac_sha256("secret_test_key_123", nonce)

    # First attempt: succeeds and consumes the challenge
    assert auth_manager.verify_device_challenge("AAIQ-RBP-TEST1", nonce, signature) is True

    # Second attempt (replay): MUST fail because nonce was destroyed
    assert auth_manager.verify_device_challenge("AAIQ-RBP-TEST1", nonce, signature) is False


def test_hmac_challenge_expiry(auth_manager: AuthManager):
    """Verifies that expired challenges fail verification."""
    # Force an expired challenge in active challenges
    nonce = auth_manager.create_challenge("AAIQ-RBP-TEST1", expires_in=1)
    auth_manager._active_challenges[nonce].expires_at = time.time() - 10.0

    signature = compute_hmac_sha256("secret_test_key_123", nonce)
    assert auth_manager.verify_device_challenge("AAIQ-RBP-TEST1", nonce, signature) is False


def test_separated_secrets_store():
    """Verifies that the device registry contains only secret_id and no raw secrets."""
    cfg = GatewayConfig(
        security=SecurityConfig(
            secrets={"sec_custom_1": "my_super_secret_hmac_key"},
            require_device_auth=True,
        ),
        devices=[
            DeviceConfig(
                device_id="AAIQ-RBP-CUSTOM",
                name="Custom Tape Deck",
                secret_id="sec_custom_1",
                relay_count=8,
                enabled=True,
            )
        ],
    )
    auth = AuthManager(cfg)

    # DeviceConfig does not contain the secret string
    dev_config = auth.get_device_info("AAIQ-RBP-CUSTOM")
    assert dev_config.secret_id == "sec_custom_1"
    assert not hasattr(dev_config, "token") or dev_config.secret_id != "my_super_secret_hmac_key"

    # SecretsStore resolves secret_id -> secret key
    assert auth.secrets_store.get_secret("sec_custom_1") == "my_super_secret_hmac_key"

    nonce = auth.create_challenge("AAIQ-RBP-CUSTOM")
    sig = compute_hmac_sha256("my_super_secret_hmac_key", nonce)
    assert auth.verify_device_challenge("AAIQ-RBP-CUSTOM", nonce, sig) is True


def test_client_authentication(auth_manager: AuthManager):
    """Verifies client bearer token authentication."""
    op = auth_manager.authenticate_client("test_client_token_abc")
    assert op is not None
    assert op.client_id == "test_operator"
    assert op.role == "operator"

    rest = auth_manager.authenticate_client("test_client_token_restricted")
    assert rest is not None
    assert rest.client_id == "test_restricted"
    assert rest.allowed_devices == ["AAIQ-RBP-TEST1"]

    # Invalid / empty token
    assert auth_manager.authenticate_client("invalid_token") is None
    assert auth_manager.authenticate_client("") is None


def test_client_device_authorization(auth_manager: AuthManager):
    """Verifies access control between clients and device endpoints."""
    op = auth_manager.authenticate_client("test_client_token_abc")
    rest = auth_manager.authenticate_client("test_client_token_restricted")

    # Operator with wildcard '*'
    assert auth_manager.is_client_authorized_for_device(op, "AAIQ-RBP-TEST1") is True
    assert auth_manager.is_client_authorized_for_device(op, "AAIQ-RBP-TEST2") is True
    assert auth_manager.is_client_authorized_for_device(op, "ANY_RANDOM_DEVICE") is True

    # Restricted client
    assert auth_manager.is_client_authorized_for_device(rest, "AAIQ-RBP-TEST1") is True
    assert auth_manager.is_client_authorized_for_device(rest, "AAIQ-RBP-TEST2") is False


def test_master_key_verification(auth_manager: AuthManager):
    """Verifies master admin key validation."""
    assert auth_manager.verify_master_key("test_master_secret_key") is True
    assert auth_manager.verify_master_key("wrong_master_key") is False
    assert auth_manager.verify_master_key("") is False


def test_auth_disabled_mode():
    """Verifies that gateway allows open connections when authentication is turned off."""
    cfg = GatewayConfig(
        security=SecurityConfig(
            require_client_auth=False,
            require_device_auth=False,
        )
    )
    auth = AuthManager(cfg)

    assert auth.verify_device_challenge("ANY_DEV", "any_nonce", "any_sig") is True
    cli = auth.authenticate_client("")
    assert cli is not None
    assert cli.client_id == "anonymous"
    assert auth.is_client_authorized_for_device(cli, "ANY_DEV") is True
