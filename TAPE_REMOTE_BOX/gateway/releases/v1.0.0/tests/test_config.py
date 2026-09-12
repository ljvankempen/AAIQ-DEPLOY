"""
Unit tests for TAPERC Gateway Configuration Manager.
"""

import json
import os
import tempfile
import pytest

from src.config import ClientConfig, DeviceConfig, GatewayConfig, SecurityConfig, ServerConfig


def test_default_config():
    config = GatewayConfig()
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 8080
    assert config.server.public_url == "https://taperc.aaiq.nl"
    assert config.server.device_ws_path == "/device/connect"
    assert config.server.client_ws_path == "/client/connect"
    assert config.security.require_client_auth is True
    assert config.security.require_device_auth is True


def test_config_from_dict():
    data = {
        "server": {
            "host": "0.0.0.0",
            "port": 9000,
            "public_url": "https://taperc.aaiq.nl",
            "device_ws_path": "/device/connect",
            "client_ws_path": "/client/connect",
            "default_device_id": "AAIQ-DEV-1",
            "heartbeat_interval_sec": 20,
            "heartbeat_timeout_sec": 60,
            "log_level": "WARNING",
        },
        "security": {
            "master_key": "custom_master_key",
            "secrets": {"sec_dev1": "secret_abc_123"},
            "require_client_auth": False,
            "require_device_auth": False,
        },
        "devices": [
            {
                "device_id": "AAIQ-DEV-1",
                "name": "Deck 1",
                "secret_id": "sec_dev1",
                "relay_count": 8,
                "enabled": True,
            }
        ],
        "clients": [
            {
                "client_id": "cli-1",
                "token": "tok2",
                "allowed_devices": ["AAIQ-DEV-1"],
                "role": "admin",
                "enabled": True,
            }
        ],
    }
    cfg = GatewayConfig.from_dict(data)
    assert cfg.server.host == "0.0.0.0"
    assert cfg.server.port == 9000
    assert cfg.server.default_device_id == "AAIQ-DEV-1"
    assert cfg.server.heartbeat_interval_sec == 20
    assert cfg.server.heartbeat_timeout_sec == 60
    assert cfg.server.log_level == "WARNING"
    assert cfg.security.master_key == "custom_master_key"
    assert cfg.security.secrets.get("sec_dev1") == "secret_abc_123"
    assert cfg.security.require_client_auth is False
    assert cfg.security.require_device_auth is False
    assert len(cfg.devices) == 1
    assert cfg.devices[0].device_id == "AAIQ-DEV-1"
    assert cfg.devices[0].secret_id == "sec_dev1"
    assert len(cfg.clients) == 1
    assert cfg.clients[0].client_id == "cli-1"


def test_load_from_file_and_env_overrides(monkeypatch):
    data = {
        "server": {"host": "127.0.0.1", "port": 8080},
        "security": {"master_key": "file_key", "secrets": {}},
        "devices": [],
        "clients": [],
    }
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        json.dump(data, f)
        temp_path = f.name

    try:
        monkeypatch.setenv("TAPERC_PORT", "9999")
        monkeypatch.setenv("TAPERC_MASTER_KEY", "env_master_key")
        monkeypatch.setenv("TAPERC_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("TAPERC_DEFAULT_DEVICE_ID", "AAIQ-RBP-ENV")
        monkeypatch.setenv("TAPERC_SECRET_MY_SEC", "my_secret_val_123")

        cfg = GatewayConfig.load_from_file(temp_path)
        assert cfg.server.port == 9999
        assert cfg.security.master_key == "env_master_key"
        assert cfg.server.log_level == "DEBUG"
        assert cfg.server.default_device_id == "AAIQ-RBP-ENV"
        assert cfg.security.secrets.get("my_sec") == "my_secret_val_123"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
