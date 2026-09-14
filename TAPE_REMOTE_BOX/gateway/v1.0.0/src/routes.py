"""
TAPERC Public Gateway — HTTP & WebSocket Route Handlers
Implements REST API endpoints, Phase-1 default device routes, and real-time WebSocket protocol handling.
"""

import hashlib
import json
import logging
from pathlib import Path
import re
import uuid
from typing import Any, Dict, Optional

from aiohttp import WSCloseCode, WSMsgType, web

from .auth import AuthManager
from .config import ClientConfig, GatewayConfig
from .connection_manager import ConnectionManager
from .protocol import (
    ACTION_ALL_OFF,
    ACTION_GET_INFO,
    ACTION_GET_STATUS,
    ACTION_OTA_CHECK,
    ACTION_OTA_INSTALL,
    ACTION_OTA_STATUS,
    ACTION_PULSE,
    ACTION_RELAY,
    MSG_AUTH,
    MSG_AUTH_ACK,
    MSG_AUTH_CHALLENGE,
    MSG_AUTH_REQUEST,
    MSG_COMMAND,
    MSG_ERROR,
    MSG_PING,
    MSG_PONG,
    MSG_RESPONSE,
    MSG_STATUS,
    MSG_SUBSCRIBE,
    ProtocolError,
    create_auth_ack,
    create_auth_challenge,
    create_error,
    create_ping,
    create_pong,
    parse_message,
    validate_pulse_duration,
    validate_relay_number,
)

logger = logging.getLogger("taperc.routes")


class GatewayRoutes:
    def __init__(
        self,
        config: GatewayConfig,
        auth_manager: AuthManager,
        connection_manager: ConnectionManager,
    ):
        self.config = config
        self.auth = auth_manager
        self.cm = connection_manager
        if self.config.server.static_dir:
            self.static_dir = Path(self.config.server.static_dir).resolve()
        else:
            self.static_dir = (Path(__file__).resolve().parents[1] / "static").resolve()

    def setup_routes(self, app: web.Application) -> None:
        # Health & Info
        app.router.add_get("/health", self.handle_health)
        app.router.add_get("/api/v1/info", self.handle_info)

        # Phase 1 Default Device REST routes
        app.router.add_get("/api/v1/status", self.handle_default_status)
        app.router.add_post("/api/v1/relay/{relay_id}", self.handle_default_relay)
        app.router.add_post("/api/v1/relay/{relay_id}/on", self.handle_default_relay_on)
        app.router.add_post("/api/v1/relay/{relay_id}/off", self.handle_default_relay_off)
        app.router.add_post("/api/v1/relay/{relay_id}/pulse", self.handle_default_pulse)
        app.router.add_post("/api/v1/all/off", self.handle_default_all_off)

        # Explicit Device REST Management
        app.router.add_get("/api/v1/devices", self.handle_list_devices)
        app.router.add_get("/api/v1/device/{device_id}/status", self.handle_get_device_status)
        app.router.add_get("/api/v1/device/{device_id}/info", self.handle_get_device_info)
        app.router.add_post("/api/v1/device/{device_id}/relay/{relay_id}", self.handle_post_relay)
        app.router.add_post("/api/v1/device/{device_id}/relay/{relay_id}/on", self.handle_post_relay_on)
        app.router.add_post("/api/v1/device/{device_id}/relay/{relay_id}/off", self.handle_post_relay_off)
        app.router.add_post("/api/v1/device/{device_id}/relay/{relay_id}/pulse", self.handle_post_pulse)
        app.router.add_post("/api/v1/device/{device_id}/pulse/{relay_id}", self.handle_post_pulse)
        app.router.add_post("/api/v1/device/{device_id}/all/off", self.handle_post_all_off)

        # OTA Firmware Update Endpoints
        app.router.add_get("/api/v1/ota/release", self.handle_ota_release)
        app.router.add_get("/api/v1/ota/firmware/latest", self.handle_ota_release)
        app.router.add_get("/api/v1/ota/download/{filename:.+}", self.handle_ota_download)
        app.router.add_get("/api/v1/ota/download", self.handle_ota_download_default)
        app.router.add_get("/api/v1/ota/status", self.handle_default_ota_status)
        app.router.add_post("/api/v1/ota/check", self.handle_default_ota_check)
        app.router.add_post("/api/v1/ota/install", self.handle_default_ota_install)
        app.router.add_get("/api/v1/device/{device_id}/ota/status", self.handle_device_ota_status)
        app.router.add_post("/api/v1/device/{device_id}/ota/check", self.handle_device_ota_check)
        app.router.add_post("/api/v1/device/{device_id}/ota/install", self.handle_device_ota_install)

        # WebSockets
        app.router.add_get(self.config.server.device_ws_path, self.handle_device_ws)
        app.router.add_get(self.config.server.client_ws_path, self.handle_client_ws)

        # PWA & Static Assets
        app.router.add_get("/", self.handle_pwa_index)
        app.router.add_get("/remote", self.handle_pwa_remote)
        app.router.add_get("/index.html", self.handle_pwa_index)
        app.router.add_get("/manifest.json", self.handle_pwa_manifest)
        app.router.add_get("/sw.js", self.handle_pwa_service_worker)
        app.router.add_get("/css/{filename:.+}", self.handle_pwa_css)
        app.router.add_get("/js/{filename:.+}", self.handle_pwa_js)
        app.router.add_get("/images/{filename:.+}", self.handle_pwa_images)
        app.router.add_get("/static/{filename:.+}", self.handle_pwa_static_fallback)

    def _extract_client_auth(self, request: web.Request) -> Optional[ClientConfig]:
        """Extracts and validates client credentials from headers or query params."""
        token = request.query.get("token")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
            elif auth_header:
                token = auth_header.strip()

        if not token:
            token = request.headers.get("X-API-Key", "")

        return self.auth.authenticate_client(token)

    def _resolve_default_device_id(self) -> Optional[str]:
        """Resolves target device_id for default Phase-1 routes."""
        if self.config.server.default_device_id:
            return self.config.server.default_device_id
        if self.config.devices:
            return self.config.devices[0].device_id
        if self.cm.devices:
            return next(iter(self.cm.devices.keys()))
        return None

    # --------------------------------------------------------------------------
    # REST Endpoints: General
    # --------------------------------------------------------------------------

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok",
                "service": "taperc-public-gateway",
                "version": "1.0.0",
                "public_url": self.config.server.public_url,
                "online_devices": len(self.cm.devices),
            }
        )

    async def handle_info(self, request: web.Request) -> web.Response:
        default_dev = self._resolve_default_device_id()
        return web.json_response(
            {
                "gateway": "TAPERC Public Gateway",
                "version": "1.0.0",
                "public_url": self.config.server.public_url,
                "device_ws_endpoint": f"{self.config.server.public_url.replace('http', 'ws')}{self.config.server.device_ws_path}",
                "client_ws_endpoint": f"{self.config.server.public_url.replace('http', 'ws')}{self.config.server.client_ws_path}",
                "devices_online": len(self.cm.devices),
                "default_device_id": default_dev,
            }
        )

    async def handle_list_devices(self, request: web.Request) -> web.Response:
        client = self._extract_client_auth(request)
        if not client:
            return web.json_response({"error": "Unauthorized"}, status=401)

        devices = self.cm.get_all_devices_summary()
        if "*" not in client.allowed_devices:
            devices = [d for d in devices if d["device_id"] in client.allowed_devices]

        return web.json_response({"devices": devices})

    # --------------------------------------------------------------------------
    # REST Endpoints: Phase 1 Default Device Routes
    # --------------------------------------------------------------------------

    async def handle_default_status(self, request: web.Request) -> web.Response:
        device_id = self._resolve_default_device_id()
        if not device_id:
            return web.json_response({"error": "No default device configured or found"}, status=503)
        return await self._execute_get_status(request, device_id)

    async def handle_default_relay(self, request: web.Request) -> web.Response:
        device_id = self._resolve_default_device_id()
        if not device_id:
            return web.json_response({"error": "No default device configured or found"}, status=503)
        relay_id_raw = request.match_info.get("relay_id", "")
        return await self._execute_relay_command(request, device_id, relay_id_raw)

    async def handle_default_relay_on(self, request: web.Request) -> web.Response:
        device_id = self._resolve_default_device_id()
        if not device_id:
            return web.json_response({"error": "No default device configured or found"}, status=503)
        relay_id_raw = request.match_info.get("relay_id", "")
        return await self._execute_relay_command(request, device_id, relay_id_raw, forced_state=True)

    async def handle_default_relay_off(self, request: web.Request) -> web.Response:
        device_id = self._resolve_default_device_id()
        if not device_id:
            return web.json_response({"error": "No default device configured or found"}, status=503)
        relay_id_raw = request.match_info.get("relay_id", "")
        return await self._execute_relay_command(request, device_id, relay_id_raw, forced_state=False)

    async def handle_default_pulse(self, request: web.Request) -> web.Response:
        device_id = self._resolve_default_device_id()
        if not device_id:
            return web.json_response({"error": "No default device configured or found"}, status=503)
        relay_id_raw = request.match_info.get("relay_id", "")
        return await self._execute_pulse_command(request, device_id, relay_id_raw)

    async def handle_default_all_off(self, request: web.Request) -> web.Response:
        device_id = self._resolve_default_device_id()
        if not device_id:
            return web.json_response({"error": "No default device configured or found"}, status=503)
        return await self._execute_all_off_command(request, device_id)

    # --------------------------------------------------------------------------
    # REST Endpoints: Explicit Device Routes
    # --------------------------------------------------------------------------

    async def handle_get_device_status(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        return await self._execute_get_status(request, device_id)

    async def handle_get_device_info(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        client = self._extract_client_auth(request)
        if not client:
            return web.json_response({"error": "Unauthorized"}, status=401)

        if not self.auth.is_client_authorized_for_device(client, device_id):
            return web.json_response({"error": "Forbidden: Not authorized for this device"}, status=403)

        dev_session = self.cm.get_device_session(device_id)
        if not dev_session:
            return web.json_response(
                {
                    "device_id": device_id,
                    "online": False,
                    "error": f"Device '{device_id}' is offline",
                },
                status=503,
            )

        try:
            res = await self.cm.send_command_to_device(device_id, action=ACTION_GET_INFO, timeout=3.0)
            return web.json_response({"device_id": device_id, "online": True, "info": res})
        except Exception:
            return web.json_response(
                {
                    "device_id": device_id,
                    "online": True,
                    "info": {
                        "device_id": device_id,
                        "name": dev_session.name,
                        "firmware": dev_session.firmware_version,
                        "relay_count": dev_session.relay_count,
                    },
                }
            )

    async def handle_post_relay(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        relay_id_raw = request.match_info.get("relay_id", "")
        return await self._execute_relay_command(request, device_id, relay_id_raw)

    async def handle_post_relay_on(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        relay_id_raw = request.match_info.get("relay_id", "")
        return await self._execute_relay_command(request, device_id, relay_id_raw, forced_state=True)

    async def handle_post_relay_off(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        relay_id_raw = request.match_info.get("relay_id", "")
        return await self._execute_relay_command(request, device_id, relay_id_raw, forced_state=False)

    async def handle_post_pulse(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        relay_id_raw = request.match_info.get("relay_id", "")
        return await self._execute_pulse_command(request, device_id, relay_id_raw)

    async def handle_post_all_off(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        return await self._execute_all_off_command(request, device_id)

    # --------------------------------------------------------------------------
    # REST Execution Helpers
    # --------------------------------------------------------------------------

    async def _execute_get_status(self, request: web.Request, device_id: str) -> web.Response:
        client = self._extract_client_auth(request)
        if not client:
            return web.json_response({"error": "Unauthorized"}, status=401)

        if not self.auth.is_client_authorized_for_device(client, device_id):
            return web.json_response({"error": "Forbidden: Not authorized for this device"}, status=403)

        dev_session = self.cm.get_device_session(device_id)
        if not dev_session:
            return web.json_response(
                {
                    "device_id": device_id,
                    "online": False,
                    "error": f"Device '{device_id}' is offline",
                },
                status=503,
            )

        try:
            res = await self.cm.send_command_to_device(device_id, action=ACTION_GET_STATUS, timeout=3.0)
            return web.json_response({"device_id": device_id, "online": True, "status": res})
        except Exception:
            # Fallback to cached status if direct poll fails
            return web.json_response(
                {
                    "device_id": device_id,
                    "online": True,
                    "status": dev_session.cached_status or {},
                }
            )

    async def _execute_relay_command(
        self,
        request: web.Request,
        device_id: str,
        relay_id_raw: str,
        forced_state: Optional[bool] = None,
    ) -> web.Response:
        client = self._extract_client_auth(request)
        if not client:
            return web.json_response({"error": "Unauthorized"}, status=401)

        if not self.auth.is_client_authorized_for_device(client, device_id):
            return web.json_response({"error": "Forbidden"}, status=403)

        try:
            relay = validate_relay_number(relay_id_raw)
        except ProtocolError as e:
            return web.json_response({"error": str(e)}, status=400)

        if forced_state is not None:
            state = forced_state
        else:
            try:
                data = await request.json()
            except Exception:
                data = {}
            state = bool(data.get("state", request.query.get("state", "true").lower() in ("1", "true", "yes")))

        try:
            result = await self.cm.send_command_to_device(
                device_id,
                action=ACTION_RELAY,
                params={"relay": relay, "state": state},
                timeout=4.0,
            )
            return web.json_response(
                {
                    "success": True,
                    "device_id": device_id,
                    "relay": relay,
                    "state": state,
                    "data": result,
                }
            )
        except ConnectionError as e:
            return web.json_response({"error": str(e)}, status=503)
        except TimeoutError as e:
            return web.json_response({"error": str(e)}, status=504)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _execute_pulse_command(
        self,
        request: web.Request,
        device_id: str,
        relay_id_raw: str,
    ) -> web.Response:
        client = self._extract_client_auth(request)
        if not client:
            return web.json_response({"error": "Unauthorized"}, status=401)

        if not self.auth.is_client_authorized_for_device(client, device_id):
            return web.json_response({"error": "Forbidden"}, status=403)

        try:
            relay = validate_relay_number(relay_id_raw)
        except ProtocolError as e:
            return web.json_response({"error": str(e)}, status=400)

        try:
            data = await request.json()
        except Exception:
            data = {}

        raw_duration = data.get("duration_ms", data.get("duration", request.query.get("duration_ms", 250)))
        try:
            duration_ms = validate_pulse_duration(raw_duration)
        except ProtocolError as e:
            return web.json_response({"error": str(e)}, status=400)

        try:
            result = await self.cm.send_command_to_device(
                device_id,
                action=ACTION_PULSE,
                params={"relay": relay, "duration_ms": duration_ms},
                timeout=4.0,
            )
            return web.json_response(
                {
                    "success": True,
                    "device_id": device_id,
                    "relay": relay,
                    "duration_ms": duration_ms,
                    "data": result,
                }
            )
        except ConnectionError as e:
            return web.json_response({"error": str(e)}, status=503)
        except TimeoutError as e:
            return web.json_response({"error": str(e)}, status=504)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _execute_all_off_command(self, request: web.Request, device_id: str) -> web.Response:
        client = self._extract_client_auth(request)
        if not client:
            return web.json_response({"error": "Unauthorized"}, status=401)

        if not self.auth.is_client_authorized_for_device(client, device_id):
            return web.json_response({"error": "Forbidden"}, status=403)

        try:
            result = await self.cm.send_command_to_device(
                device_id,
                action=ACTION_ALL_OFF,
                params={},
                timeout=4.0,
            )
            return web.json_response({"success": True, "device_id": device_id, "data": result})
        except ConnectionError as e:
            return web.json_response({"error": str(e)}, status=503)
        except TimeoutError as e:
            return web.json_response({"error": str(e)}, status=504)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # --------------------------------------------------------------------------
    # OTA Firmware Release & Update Endpoints
    # --------------------------------------------------------------------------

    def _get_releases_dir(self) -> Path:
        if self.config.server.releases_dir:
            return Path(self.config.server.releases_dir).resolve()

        candidates = [
            self.static_dir.parent / "releases" / "firmware",
            self.static_dir / "firmware",
            self.static_dir.parent / "releases",
            Path(__file__).resolve().parents[3] / "src",
            self.static_dir.parent / "src",
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                return c.resolve()
        return (self.static_dir / "firmware").resolve()

    def _get_latest_firmware_info(self) -> Optional[Dict[str, Any]]:
        rel_dir = self._get_releases_dir()

        manifest_paths = [
            rel_dir / "release.json",
            rel_dir / "latest.json",
            self.static_dir / "release.json",
            self.static_dir / "latest.json",
        ]
        for mp in manifest_paths:
            if mp.exists() and mp.is_file():
                try:
                    with open(mp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and "version" in data:
                        target_file = rel_dir / data.get("filename", "main.py")
                        if target_file.exists() and target_file.is_file():
                            if "sha256" not in data or not data["sha256"]:
                                file_bytes = target_file.read_bytes()
                                data["sha256"] = hashlib.sha256(file_bytes).hexdigest()
                                data["size_bytes"] = len(file_bytes)
                        if "url" not in data or not data["url"]:
                            filename = data.get("filename", "main.py")
                            data["url"] = f"{self.config.server.public_url.rstrip('/')}/api/v1/ota/download/{filename}"
                        data["success"] = True
                        return data
                except Exception as e:
                    logger.warning("Failed to parse release manifest %s: %s", mp, e)

        fw_file = None
        for candidate_file in [
            rel_dir / "main.py",
            Path(__file__).resolve().parents[3] / "src" / "main.py",
            self.static_dir.parent / "src" / "main.py",
        ]:
            if candidate_file.exists() and candidate_file.is_file():
                fw_file = candidate_file
                break

        if fw_file:
            try:
                content = fw_file.read_bytes()
                sha256_hash = hashlib.sha256(content).hexdigest()
                size_bytes = len(content)

                version = "0.5.1"
                try:
                    text = content.decode("utf-8")
                    m = re.search(r'FIRMWARE_VERSION\s*=\s*"([^"]+)"', text)
                    if m:
                        version = m.group(1)
                except Exception:
                    pass

                return {
                    "success": True,
                    "version": version,
                    "min_version": "0.1.0",
                    "filename": fw_file.name,
                    "url": f"{self.config.server.public_url.rstrip('/')}/api/v1/ota/download/{fw_file.name}",
                    "sha256": sha256_hash,
                    "size_bytes": size_bytes,
                    "release_date": "2026-09-13",
                    "changelog": "AAIQ Relay Box Pico 2 W Firmware Release",
                }
            except Exception as e:
                logger.warning("Failed to inspect firmware file %s: %s", fw_file, e)

        return None

    async def handle_ota_release(self, request: web.Request) -> web.Response:
        info = self._get_latest_firmware_info()
        if not info:
            return web.json_response({"success": False, "error": "NO_RELEASE_AVAILABLE"}, status=404)
        return web.json_response(info)

    async def handle_ota_download_default(self, request: web.Request) -> web.Response:
        return await self._serve_ota_file("main.py")

    async def handle_ota_download(self, request: web.Request) -> web.Response:
        filename = request.match_info.get("filename", "main.py")
        return await self._serve_ota_file(filename)

    async def _serve_ota_file(self, filename: str) -> web.Response:
        if not filename or ".." in filename or "/" in filename or "\\" in filename:
            return web.json_response({"error": "Invalid filename"}, status=400)

        rel_dir = self._get_releases_dir()
        candidate_files = [
            rel_dir / filename,
            self.static_dir / "firmware" / filename,
            Path(__file__).resolve().parents[3] / "src" / filename,
            self.static_dir.parent / "src" / filename,
        ]
        target_path = None
        for cp in candidate_files:
            if cp.exists() and cp.is_file():
                target_path = cp.resolve()
                break

        if not target_path or not target_path.exists():
            return web.json_response({"error": "Firmware file not found"}, status=404)

        try:
            data = target_path.read_bytes()
            sha256_hash = hashlib.sha256(data).hexdigest()
            headers = {
                "Content-Type": "text/x-python; charset=utf-8",
                "Content-Length": str(len(data)),
                "ETag": f'"{sha256_hash}"',
                "X-Checksum-SHA256": sha256_hash,
                "Cache-Control": "public, max-age=300",
                "Content-Disposition": f'attachment; filename="{target_path.name}"',
            }
            return web.Response(body=data, headers=headers)
        except Exception as e:
            logger.error("Error serving OTA file %s: %s", target_path, e)
            return web.json_response({"error": "Failed to read firmware file"}, status=500)

    async def handle_default_ota_status(self, request: web.Request) -> web.Response:
        default_dev = self._resolve_default_device_id()
        if not default_dev:
            rel_info = self._get_latest_firmware_info()
            return web.json_response({
                "success": True,
                "device_online": False,
                "release": rel_info,
                "status": "idle",
            })
        dev_session = self.cm.get_device_session(default_dev)
        if not dev_session:
            rel_info = self._get_latest_firmware_info()
            return web.json_response({
                "success": True,
                "device_id": default_dev,
                "device_online": False,
                "release": rel_info,
                "status": "offline",
            })
        try:
            res = await self.cm.send_command_to_device(default_dev, action=ACTION_OTA_STATUS, timeout=3.0)
            return web.json_response(res)
        except Exception:
            rel_info = self._get_latest_firmware_info()
            return web.json_response({
                "success": True,
                "device_id": default_dev,
                "device_online": True,
                "release": rel_info,
                "status": "idle",
            })

    async def handle_default_ota_check(self, request: web.Request) -> web.Response:
        default_dev = self._resolve_default_device_id()
        if not default_dev:
            return web.json_response({"success": False, "error": "No default device configured or online"}, status=503)
        return await self._execute_ota_check(request, default_dev)

    async def handle_default_ota_install(self, request: web.Request) -> web.Response:
        default_dev = self._resolve_default_device_id()
        if not default_dev:
            return web.json_response({"success": False, "error": "No default device configured or online"}, status=503)
        return await self._execute_ota_install(request, default_dev)

    async def handle_device_ota_status(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        client = self._extract_client_auth(request)
        if not client:
            return web.json_response({"error": "Unauthorized"}, status=401)
        if not self.auth.is_client_authorized_for_device(client, device_id):
            return web.json_response({"error": "Forbidden: Not authorized for this device"}, status=403)
        dev_session = self.cm.get_device_session(device_id)
        if not dev_session:
            rel_info = self._get_latest_firmware_info()
            return web.json_response({
                "success": True,
                "device_id": device_id,
                "device_online": False,
                "release": rel_info,
                "status": "offline",
            })
        try:
            res = await self.cm.send_command_to_device(device_id, action=ACTION_OTA_STATUS, timeout=3.0)
            return web.json_response(res)
        except Exception:
            rel_info = self._get_latest_firmware_info()
            return web.json_response({
                "success": True,
                "device_id": device_id,
                "device_online": True,
                "release": rel_info,
                "status": "idle",
            })

    async def handle_device_ota_check(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        return await self._execute_ota_check(request, device_id)

    async def handle_device_ota_install(self, request: web.Request) -> web.Response:
        device_id = request.match_info.get("device_id", "")
        return await self._execute_ota_install(request, device_id)

    async def _execute_ota_check(self, request: web.Request, device_id: str) -> web.Response:
        client = self._extract_client_auth(request)
        if not client:
            return web.json_response({"error": "Unauthorized"}, status=401)
        if not self.auth.is_client_authorized_for_device(client, device_id):
            return web.json_response({"error": "Forbidden"}, status=403)
        dev_session = self.cm.get_device_session(device_id)
        if not dev_session:
            return web.json_response({"success": False, "error": f"Device '{device_id}' is offline"}, status=503)
        try:
            res = await self.cm.send_command_to_device(device_id, action=ACTION_OTA_CHECK, timeout=5.0)
            return web.json_response(res)
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def _execute_ota_install(self, request: web.Request, device_id: str) -> web.Response:
        client = self._extract_client_auth(request)
        if not client:
            return web.json_response({"error": "Unauthorized"}, status=401)
        if not self.auth.is_client_authorized_for_device(client, device_id):
            return web.json_response({"error": "Forbidden"}, status=403)
        dev_session = self.cm.get_device_session(device_id)
        if not dev_session:
            return web.json_response({"success": False, "error": f"Device '{device_id}' is offline"}, status=503)
        try:
            res = await self.cm.send_command_to_device(device_id, action=ACTION_OTA_INSTALL, timeout=10.0)
            return web.json_response(res)
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    # --------------------------------------------------------------------------
    # WebSocket: /device/connect (wss://taperc.aaiq.nl/device/connect)
    # --------------------------------------------------------------------------

    async def handle_device_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=self.config.server.heartbeat_interval_sec)
        await ws.prepare(request)

        device_id: Optional[str] = request.query.get("device_id") or request.headers.get("X-Device-Id")
        firmware = request.query.get("firmware", "unknown")
        relay_count = int(request.query.get("relay_count", 8))
        is_authenticated = False

        if not self.config.security.require_device_auth:
            if device_id:
                is_authenticated = True
                await self.cm.register_device(
                    device_id=device_id,
                    ws=ws,
                    firmware_version=firmware,
                    relay_count=relay_count,
                )
                await ws.send_json(create_auth_ack(True, message="Device connected (auth disabled)", device_id=device_id))
        else:
            # Send initial cryptographic challenge nonce immediately upon connection
            initial_nonce = self.auth.create_challenge(device_id=device_id)
            await ws.send_json(create_auth_challenge(nonce=initial_nonce, expires_in=60))

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        payload = parse_message(msg.data)
                    except ProtocolError as e:
                        await ws.send_json(create_error(str(e), code=e.code))
                        continue

                    msg_type = payload.get("type")

                    if msg_type == MSG_AUTH_REQUEST:
                        # Device requests a fresh challenge nonce
                        req_dev_id = payload.get("device_id")
                        nonce = self.auth.create_challenge(device_id=req_dev_id)
                        await ws.send_json(create_auth_challenge(nonce=nonce, expires_in=60))
                        continue

                    elif msg_type == MSG_AUTH:
                        dev_id = payload.get("device_id", device_id or "")
                        nonce = payload.get("nonce", "")
                        signature = payload.get("signature", "")
                        dev_fw = payload.get("firmware", firmware)
                        dev_relays = int(payload.get("relay_count", relay_count))
                        dev_name = payload.get("name", "")

                        if self.auth.verify_device_challenge(dev_id, nonce, signature):
                            device_id = dev_id
                            is_authenticated = True
                            await self.cm.register_device(
                                device_id=device_id,
                                ws=ws,
                                firmware_version=dev_fw,
                                relay_count=dev_relays,
                                name=dev_name,
                            )
                            await ws.send_json(
                                create_auth_ack(True, message="Device authenticated via HMAC challenge-response", device_id=device_id)
                            )
                        else:
                            await ws.send_json(
                                create_auth_ack(False, message="Invalid HMAC challenge signature", device_id=dev_id)
                            )
                            await ws.close(code=WSCloseCode.POLICY_VIOLATION)
                            return ws

                    elif not is_authenticated or not device_id:
                        await ws.send_json(create_error("Authentication required. Please respond to challenge", code="UNAUTHORIZED"))
                        continue

                    elif msg_type == MSG_PING:
                        self.cm.record_device_heartbeat(device_id)
                        await ws.send_json(create_pong())

                    elif msg_type == MSG_PONG:
                        self.cm.record_device_heartbeat(device_id)

                    elif msg_type == MSG_STATUS:
                        status_data = payload.get("status", {})
                        await self.cm.update_device_status(device_id, status_data)

                    elif msg_type == MSG_RESPONSE:
                        req_id = payload.get("request_id")
                        success = bool(payload.get("success", True))
                        data = payload.get("data")
                        error = payload.get("error")
                        if req_id:
                            self.cm.handle_device_response(device_id, req_id, success, data, error)

                elif msg.type == WSMsgType.ERROR:
                    logger.warning("Device WS closed with exception: %s", ws.exception())

        finally:
            if device_id and is_authenticated:
                await self.cm.unregister_device(device_id)

        return ws

    # --------------------------------------------------------------------------
    # WebSocket: /client/connect (wss://taperc.aaiq.nl/client/connect)
    # --------------------------------------------------------------------------

    async def handle_client_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=self.config.server.heartbeat_interval_sec)
        await ws.prepare(request)

        session_id = f"client_{uuid.uuid4().hex[:8]}"
        client_config = self._extract_client_auth(request)

        is_authenticated = False
        if client_config:
            is_authenticated = True
            await self.cm.register_client(session_id, client_config, ws)
            await ws.send_json(create_auth_ack(True, message="Client authenticated", client_id=client_config.client_id))

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        payload = parse_message(msg.data)
                    except ProtocolError as e:
                        await ws.send_json(create_error(str(e), code=e.code))
                        continue

                    msg_type = payload.get("type")

                    if msg_type == MSG_AUTH:
                        cli_token = payload.get("token", "")
                        cfg = self.auth.authenticate_client(cli_token)
                        if cfg:
                            client_config = cfg
                            is_authenticated = True
                            await self.cm.register_client(session_id, client_config, ws)
                            await ws.send_json(
                                create_auth_ack(True, message="Client authenticated", client_id=client_config.client_id)
                            )
                        else:
                            await ws.send_json(create_auth_ack(False, message="Invalid client credentials"))
                            await ws.close(code=WSCloseCode.POLICY_VIOLATION)
                            return ws

                    elif not is_authenticated or not client_config:
                        await ws.send_json(create_error("Authentication required", code="UNAUTHORIZED"))
                        continue

                    elif msg_type == MSG_PING:
                        await ws.send_json(create_pong())

                    elif msg_type == MSG_SUBSCRIBE:
                        dev_id = payload.get("device_id", "")
                        if not dev_id:
                            await ws.send_json(create_error("device_id is required for subscribe", code="BAD_REQUEST"))
                            continue

                        ok = await self.cm.subscribe_client(session_id, dev_id)
                        if not ok:
                            await ws.send_json(create_error(f"Unauthorized or failed subscribe to {dev_id}", code="FORBIDDEN"))

                    elif msg_type == MSG_COMMAND:
                        dev_id = payload.get("device_id", "")
                        action = payload.get("action", "")
                        params = payload.get("params", {})
                        req_id = payload.get("request_id")

                        if not dev_id or not action:
                            await ws.send_json(create_error("device_id and action required", code="BAD_REQUEST", request_id=req_id))
                            continue

                        if not self.auth.is_client_authorized_for_device(client_config, dev_id):
                            await ws.send_json(create_error("Not authorized for this device", code="FORBIDDEN", request_id=req_id))
                            continue

                        try:
                            res = await self.cm.send_command_to_device(
                                device_id=dev_id,
                                action=action,
                                params=params,
                                timeout=5.0,
                            )
                            await ws.send_json(
                                {
                                    "type": "command_result",
                                    "request_id": req_id,
                                    "device_id": dev_id,
                                    "success": True,
                                    "data": res,
                                }
                            )
                        except Exception as e:
                            await ws.send_json(
                                {
                                    "type": "command_result",
                                    "request_id": req_id,
                                    "device_id": dev_id,
                                    "success": False,
                                    "error": str(e),
                                }
                            )

                elif msg.type == WSMsgType.ERROR:
                    logger.warning("Client WS closed with exception: %s", ws.exception())

        finally:
            await self.cm.unregister_client(session_id)

        return ws

    # --------------------------------------------------------------------------
    # PWA & Static File Serving
    # --------------------------------------------------------------------------

    def _serve_file_safely(
        self,
        target_path: Path,
        content_type: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> web.StreamResponse:
        """Helper to securely serve a static file within the static directory."""
        try:
            resolved = target_path.resolve()
            # Security check: ensure path is inside self.static_dir
            if not resolved.is_relative_to(self.static_dir.resolve()):
                raise web.HTTPForbidden(text="403: Forbidden")
            if not resolved.exists() or not resolved.is_file():
                raise web.HTTPNotFound(text="404: Not Found")
        except (web.HTTPForbidden, web.HTTPNotFound):
            raise
        except Exception as e:
            logger.warning("Error resolving static file %s: %s", target_path, e)
            raise web.HTTPNotFound(text="404: Not Found")

        headers = dict(extra_headers or {})
        if content_type:
            headers["Content-Type"] = content_type

        return web.FileResponse(resolved, headers=headers)

    async def handle_pwa_index(self, request: web.Request) -> web.StreamResponse:
        """Serves PWA index.html for root GET / and /index.html."""
        return self._serve_file_safely(
            self.static_dir / "index.html",
            content_type="text/html; charset=utf-8",
        )

    async def handle_pwa_remote(self, request: web.Request) -> web.StreamResponse:
        """Serves PWA index.html for SPA route GET /remote."""
        return self._serve_file_safely(
            self.static_dir / "index.html",
            content_type="text/html; charset=utf-8",
        )

    async def handle_pwa_manifest(self, request: web.Request) -> web.StreamResponse:
        """Serves PWA manifest.json."""
        return self._serve_file_safely(
            self.static_dir / "manifest.json",
            content_type="application/manifest+json; charset=utf-8",
        )

    async def handle_pwa_service_worker(self, request: web.Request) -> web.StreamResponse:
        """Serves PWA Service Worker sw.js with appropriate scope and caching headers."""
        return self._serve_file_safely(
            self.static_dir / "sw.js",
            content_type="application/javascript; charset=utf-8",
            extra_headers={
                "Service-Worker-Allowed": "/",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )

    async def handle_pwa_css(self, request: web.Request) -> web.StreamResponse:
        """Serves CSS assets from static/css/."""
        filename = request.match_info.get("filename", "")
        return self._serve_file_safely(
            self.static_dir / "css" / filename,
            content_type="text/css; charset=utf-8",
        )

    async def handle_pwa_js(self, request: web.Request) -> web.StreamResponse:
        """Serves JS assets from static/js/."""
        filename = request.match_info.get("filename", "")
        return self._serve_file_safely(
            self.static_dir / "js" / filename,
            content_type="application/javascript; charset=utf-8",
        )

    async def handle_pwa_images(self, request: web.Request) -> web.StreamResponse:
        """Serves image assets from static/images/."""
        filename = request.match_info.get("filename", "")
        return self._serve_file_safely(self.static_dir / "images" / filename)

    async def handle_pwa_static_fallback(self, request: web.Request) -> web.StreamResponse:
        """Fallback for any static file under /static/*."""
        filename = request.match_info.get("filename", "")
        return self._serve_file_safely(self.static_dir / filename)
