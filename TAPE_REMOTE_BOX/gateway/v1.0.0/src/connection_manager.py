"""
TAPERC Public Gateway — Connection & Session Manager
Maintains real-time WebSocket sessions for remote Relay Box devices and connected PWA clients.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set

from aiohttp import WSCloseCode, web

from .auth import AuthManager
from .config import ClientConfig, GatewayConfig
from .protocol import (
    create_command,
    create_device_status_event,
    create_ping,
)

logger = logging.getLogger("taperc.connection_manager")


class DeviceSession:
    def __init__(
        self,
        device_id: str,
        name: str,
        ws: web.WebSocketResponse,
        firmware_version: str = "unknown",
        relay_count: int = 8,
    ):
        self.device_id = device_id
        self.name = name
        self.ws = ws
        self.firmware_version = firmware_version
        self.relay_count = relay_count
        self.connected_at = time.time()
        self.last_heartbeat = time.time()
        self.cached_status: Optional[Dict[str, Any]] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}

    @property
    def is_alive(self) -> bool:
        return self.ws is not None and not self.ws.closed


class ClientSession:
    def __init__(
        self,
        session_id: str,
        client_config: ClientConfig,
        ws: web.WebSocketResponse,
    ):
        self.session_id = session_id
        self.client_config = client_config
        self.ws = ws
        self.subscribed_devices: Set[str] = set()
        self.connected_at = time.time()
        self.last_seen = time.time()

    @property
    def is_alive(self) -> bool:
        return self.ws is not None and not self.ws.closed


class ConnectionManager:
    def __init__(self, config: GatewayConfig, auth_manager: AuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.devices: Dict[str, DeviceSession] = {}
        self.clients: Dict[str, ClientSession] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    def is_device_online(self, device_id: str) -> bool:
        session = self.devices.get(device_id)
        return session is not None and session.is_alive

    def get_device_session(self, device_id: str) -> Optional[DeviceSession]:
        session = self.devices.get(device_id)
        if session and session.is_alive:
            return session
        return None

    async def register_device(
        self,
        device_id: str,
        ws: web.WebSocketResponse,
        firmware_version: str = "unknown",
        relay_count: int = 8,
        name: str = "",
    ) -> DeviceSession:
        dev_info = self.auth_manager.get_device_info(device_id)
        dev_name = name or (dev_info.name if dev_info else device_id)
        if dev_info and dev_info.relay_count:
            relay_count = dev_info.relay_count

        # Close existing connection if any
        if device_id in self.devices:
            old_session = self.devices[device_id]
            if old_session.ws is not None:
                logger.info("Replacing existing connection for device %s", device_id)
                try:
                    await old_session.ws.close(code=WSCloseCode.SERVICE_RESTART, message=b"Duplicate connection")
                except Exception:
                    pass

        session = DeviceSession(
            device_id=device_id,
            name=dev_name,
            ws=ws,
            firmware_version=firmware_version,
            relay_count=relay_count,
        )
        self.devices[device_id] = session
        logger.info("Device registered: %s (name: %s, firmware: %s)", device_id, dev_name, firmware_version)

        # Notify subscribed clients that device is online
        await self.broadcast_device_status(device_id, online=True)
        return session

    async def unregister_device(self, device_id: str) -> None:
        session = self.devices.pop(device_id, None)
        if session:
            logger.info("Device unregistered: %s", device_id)
            # Cancel all pending requests for this device
            for req_id, fut in list(session.pending_requests.items()):
                if not fut.done():
                    fut.set_exception(ConnectionError(f"Device {device_id} disconnected"))
            session.pending_requests.clear()

            # Broadcast offline state to clients
            await self.broadcast_device_status(device_id, online=False)

    async def register_client(
        self,
        session_id: str,
        client_config: ClientConfig,
        ws: web.WebSocketResponse,
    ) -> ClientSession:
        session = ClientSession(session_id=session_id, client_config=client_config, ws=ws)
        self.clients[session_id] = session
        logger.info("Client registered: %s (role: %s)", session_id, client_config.role)
        return session

    async def unregister_client(self, session_id: str) -> None:
        session = self.clients.pop(session_id, None)
        if session:
            logger.info("Client unregistered: %s", session_id)

    async def subscribe_client(self, session_id: str, device_id: str) -> bool:
        client = self.clients.get(session_id)
        if not client:
            return False

        if not self.auth_manager.is_client_authorized_for_device(client.client_config, device_id):
            logger.warning("Client %s unauthorized to subscribe to device %s", session_id, device_id)
            return False

        client.subscribed_devices.add(device_id)

        # If device is currently online, send immediate status snapshot to this client
        dev_session = self.get_device_session(device_id)
        if dev_session:
            evt = create_device_status_event(
                device_id=device_id,
                online=True,
                status=dev_session.cached_status,
                name=dev_session.name,
            )
            try:
                await client.ws.send_json(evt)
            except Exception:
                pass
        else:
            evt = create_device_status_event(device_id=device_id, online=False, status=None)
            try:
                await client.ws.send_json(evt)
            except Exception:
                pass

        return True

    async def broadcast_device_status(
        self,
        device_id: str,
        online: bool,
        status: Optional[Dict[str, Any]] = None,
    ) -> None:
        session = self.devices.get(device_id)
        name = session.name if session else ""
        if session and status is not None:
            session.cached_status = status

        event = create_device_status_event(device_id=device_id, online=online, status=status, name=name)

        disconnected_clients = []
        for s_id, client in list(self.clients.items()):
            if not client.is_alive:
                disconnected_clients.append(s_id)
                continue

            if "*" in client.subscribed_devices or device_id in client.subscribed_devices:
                if self.auth_manager.is_client_authorized_for_device(client.client_config, device_id):
                    try:
                        await client.ws.send_json(event)
                    except Exception as e:
                        logger.warning("Error broadcasting to client %s: %s", s_id, e)
                        disconnected_clients.append(s_id)

        for s_id in disconnected_clients:
            await self.unregister_client(s_id)

    async def broadcast_to_clients(self, message: Dict[str, Any], device_id: Optional[str] = None) -> None:
        disconnected_clients = []
        for s_id, client in list(self.clients.items()):
            if not client.is_alive:
                disconnected_clients.append(s_id)
                continue

            if device_id is not None:
                if not (("*" in client.subscribed_devices) or (device_id in client.subscribed_devices)):
                    continue
                if not self.auth_manager.is_client_authorized_for_device(client.client_config, device_id):
                    continue

            try:
                await client.ws.send_json(message)
            except Exception as e:
                logger.warning("Error sending message to client %s: %s", s_id, e)
                disconnected_clients.append(s_id)

        for s_id in disconnected_clients:
            await self.unregister_client(s_id)

    async def send_command_to_device(
        self,
        device_id: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        dev_session = self.get_device_session(device_id)
        if not dev_session:
            raise ConnectionError(f"Device '{device_id}' is offline or disconnected")

        cmd = create_command(action=action, params=params)
        req_id = cmd["request_id"]

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        dev_session.pending_requests[req_id] = future

        try:
            await dev_session.ws.send_json(cmd)
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            dev_session.pending_requests.pop(req_id, None)
            raise TimeoutError(f"Command '{action}' to device '{device_id}' timed out after {timeout}s")
        except Exception:
            dev_session.pending_requests.pop(req_id, None)
            raise

    def handle_device_response(
        self,
        device_id: str,
        request_id: str,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        dev_session = self.devices.get(device_id)
        if not dev_session:
            return False

        fut = dev_session.pending_requests.pop(request_id, None)
        if fut and not fut.done():
            if success:
                fut.set_result(data or {})
            else:
                fut.set_exception(RuntimeError(error or "Device reported command failure"))
            return True
        return False

    def record_device_heartbeat(self, device_id: str) -> None:
        dev_session = self.devices.get(device_id)
        if dev_session:
            dev_session.last_heartbeat = time.time()

    def update_device_heartbeat(self, device_id: str) -> None:
        self.record_device_heartbeat(device_id)

    async def update_device_status(self, device_id: str, status: Dict[str, Any]) -> None:
        dev_session = self.devices.get(device_id)
        if dev_session:
            dev_session.cached_status = status
            dev_session.last_heartbeat = time.time()
            await self.broadcast_device_status(device_id, online=True, status=status)

    def get_devices_summary(self) -> List[Dict[str, Any]]:
        registered = self.auth_manager.list_registered_devices()
        summary = []
        registered_ids = set()

        for dev in registered:
            registered_ids.add(dev.device_id)
            online = self.is_device_online(dev.device_id)
            session = self.devices.get(dev.device_id) if online else None
            summary.append(
                {
                    "device_id": dev.device_id,
                    "name": dev.name,
                    "online": online,
                    "relay_count": dev.relay_count,
                    "firmware": session.firmware_version if session else "unknown",
                    "connected_at": session.connected_at if session else None,
                    "last_heartbeat": session.last_heartbeat if session else None,
                    "status": session.cached_status if session else None,
                }
            )

        # Include any connected devices not in explicit static config
        for dev_id, session in self.devices.items():
            if dev_id not in registered_ids:
                summary.append(
                    {
                        "device_id": dev_id,
                        "name": session.name,
                        "online": session.is_alive,
                        "relay_count": session.relay_count,
                        "firmware": session.firmware_version,
                        "connected_at": session.connected_at,
                        "last_heartbeat": session.last_heartbeat,
                        "status": session.cached_status,
                    }
                )

        return summary

    def get_all_devices_summary(self) -> List[Dict[str, Any]]:
        return self.get_devices_summary()

    def start_heartbeat_monitor(self) -> None:
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat monitor task started")

    async def stop_heartbeat_monitor(self) -> None:
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        logger.info("Heartbeat monitor task stopped")

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.config.server.heartbeat_interval_sec)
                now = time.time()
                timeout_threshold = self.config.server.heartbeat_timeout_sec

                dead_devices = []
                for dev_id, session in list(self.devices.items()):
                    if not session.is_alive or (now - session.last_heartbeat > timeout_threshold):
                        logger.warning(
                            "Device %s timed out (last heartbeat %.1fs ago). Closing.",
                            dev_id,
                            now - session.last_heartbeat,
                        )
                        dead_devices.append(dev_id)
                    else:
                        # Send periodic ping
                        try:
                            await session.ws.send_json(create_ping())
                        except Exception as e:
                            logger.warning("Failed to send ping to device %s: %s", dev_id, e)
                            dead_devices.append(dev_id)

                for dev_id in dead_devices:
                    session = self.devices.get(dev_id)
                    if session and session.ws and not session.ws.closed:
                        try:
                            await session.ws.close()
                        except Exception:
                            pass
                    await self.unregister_device(dev_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in heartbeat loop: %s", e)
