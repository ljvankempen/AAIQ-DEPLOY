"""
TAPERC Public Gateway — Configuration Manager
Handles loading and validation of server, security, device, and client configurations.
"""

from dataclasses import dataclass, field
import json
import os
from typing import Any, Dict, List, Optional


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    public_url: str = "https://taperc.aaiq.nl"
    device_ws_path: str = "/device/connect"
    client_ws_path: str = "/client/connect"
    default_device_id: Optional[str] = None
    heartbeat_interval_sec: int = 15
    heartbeat_timeout_sec: int = 45
    log_level: str = "INFO"


@dataclass
class SecurityConfig:
    master_key: str = "taperc_master_secret_key_change_in_production"
    secrets_file: Optional[str] = None
    secrets: Dict[str, str] = field(default_factory=dict)
    require_client_auth: bool = True
    require_device_auth: bool = True


@dataclass
class DeviceConfig:
    device_id: str
    name: str = ""
    secret_id: str = ""
    relay_count: int = 8
    enabled: bool = True


@dataclass
class ClientConfig:
    client_id: str
    token: str = ""
    allowed_devices: List[str] = field(default_factory=lambda: ["*"])
    role: str = "operator"
    enabled: bool = True


@dataclass
class GatewayConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    devices: List[DeviceConfig] = field(default_factory=list)
    clients: List[ClientConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GatewayConfig":
        server_data = data.get("server", {})
        default_dev = server_data.get("default_device_id", data.get("default_device_id"))
        server = ServerConfig(
            host=server_data.get("host", "127.0.0.1"),
            port=int(server_data.get("port", 8080)),
            public_url=server_data.get("public_url", "https://taperc.aaiq.nl"),
            device_ws_path=server_data.get("device_ws_path", "/device/connect"),
            client_ws_path=server_data.get("client_ws_path", "/client/connect"),
            default_device_id=default_dev,
            heartbeat_interval_sec=int(server_data.get("heartbeat_interval_sec", 15)),
            heartbeat_timeout_sec=int(server_data.get("heartbeat_timeout_sec", 45)),
            log_level=server_data.get("log_level", "INFO"),
        )

        security_data = data.get("security", {})
        raw_secrets = dict(security_data.get("secrets", {}))
        security = SecurityConfig(
            master_key=security_data.get("master_key", "taperc_master_secret_key_change_in_production"),
            secrets_file=security_data.get("secrets_file"),
            secrets=raw_secrets,
            require_client_auth=security_data.get("require_client_auth", True),
            require_device_auth=security_data.get("require_device_auth", True),
        )

        devices = []
        for dev in data.get("devices", []):
            devices.append(
                DeviceConfig(
                    device_id=dev.get("device_id", ""),
                    name=dev.get("name", ""),
                    secret_id=dev.get("secret_id", dev.get("token", "")),
                    relay_count=int(dev.get("relay_count", 8)),
                    enabled=bool(dev.get("enabled", True)),
                )
            )

        clients = []
        for cli in data.get("clients", []):
            clients.append(
                ClientConfig(
                    client_id=cli.get("client_id", ""),
                    token=cli.get("token", ""),
                    allowed_devices=cli.get("allowed_devices", ["*"]),
                    role=cli.get("role", "operator"),
                    enabled=bool(cli.get("enabled", True)),
                )
            )

        return cls(server=server, security=security, devices=devices, clients=clients)

    @classmethod
    def load_from_file(cls, path: str) -> "GatewayConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = cls.from_dict(data)
        cfg.apply_env_overrides()
        return cfg

    def apply_env_overrides(self) -> None:
        """Applies environment variable overrides if present."""
        if os.getenv("TAPERC_HOST"):
            self.server.host = os.getenv("TAPERC_HOST")
        if os.getenv("TAPERC_PORT"):
            try:
                self.server.port = int(os.getenv("TAPERC_PORT"))
            except ValueError:
                pass
        if os.getenv("TAPERC_PUBLIC_URL"):
            self.server.public_url = os.getenv("TAPERC_PUBLIC_URL")
        if os.getenv("TAPERC_DEVICE_WS_PATH"):
            self.server.device_ws_path = os.getenv("TAPERC_DEVICE_WS_PATH")
        if os.getenv("TAPERC_CLIENT_WS_PATH"):
            self.server.client_ws_path = os.getenv("TAPERC_CLIENT_WS_PATH")
        if os.getenv("TAPERC_DEFAULT_DEVICE_ID"):
            self.server.default_device_id = os.getenv("TAPERC_DEFAULT_DEVICE_ID")
        if os.getenv("TAPERC_MASTER_KEY"):
            self.security.master_key = os.getenv("TAPERC_MASTER_KEY")
        if os.getenv("TAPERC_SECRETS_FILE"):
            self.security.secrets_file = os.getenv("TAPERC_SECRETS_FILE")
        if os.getenv("TAPERC_HEARTBEAT_INTERVAL"):
            try:
                self.server.heartbeat_interval_sec = int(os.getenv("TAPERC_HEARTBEAT_INTERVAL"))
            except ValueError:
                pass
        if os.getenv("TAPERC_HEARTBEAT_TIMEOUT"):
            try:
                self.server.heartbeat_timeout_sec = int(os.getenv("TAPERC_HEARTBEAT_TIMEOUT"))
            except ValueError:
                pass
        if os.getenv("TAPERC_LOG_LEVEL"):
            self.server.log_level = os.getenv("TAPERC_LOG_LEVEL")

        # Load secrets from secrets file if specified and exists
        if self.security.secrets_file and os.path.exists(self.security.secrets_file):
            try:
                with open(self.security.secrets_file, "r", encoding="utf-8") as f:
                    file_secrets = json.load(f)
                    if isinstance(file_secrets, dict):
                        if "secrets" in file_secrets and isinstance(file_secrets["secrets"], dict):
                            self.security.secrets.update(file_secrets["secrets"])
                        else:
                            self.security.secrets.update(file_secrets)
            except Exception:
                pass

        # Load secrets from env vars like TAPERC_SECRET_<ID> or TAPERC_DEVICE_SECRET_<DEVICE_ID>
        for k, v in os.environ.items():
            if k.startswith("TAPERC_SECRET_"):
                sec_id = k[len("TAPERC_SECRET_") :].lower()
                self.security.secrets[sec_id] = v
            elif k.startswith("TAPERC_DEVICE_SECRET_"):
                dev_id = k[len("TAPERC_DEVICE_SECRET_") :]
                self.security.secrets[dev_id] = v
