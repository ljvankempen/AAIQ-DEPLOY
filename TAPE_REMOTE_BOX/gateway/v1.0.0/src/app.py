"""
TAPERC Public Gateway — Application Factory & Lifecycle
Builds the AIOHTTP web application, attaches middleware, registers signals, and manages lifecycle.
"""

import logging
from typing import Optional

from aiohttp import WSCloseCode, web

from .auth import AuthManager
from .config import GatewayConfig
from .connection_manager import ConnectionManager
from .routes import GatewayRoutes

logger = logging.getLogger("taperc.app")


@web.middleware
async def cors_middleware(request: web.Request, handler) -> web.StreamResponse:
    """Provides open CORS headers for PWA cross-origin API access if needed."""
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key, X-Device-Id, X-Device-Token"
    response.headers["Access-Control-Max-Age"] = "86400"
    return response


async def on_startup(app: web.Application) -> None:
    cm: ConnectionManager = app["connection_manager"]
    cm.start_heartbeat_monitor()
    logger.info("TAPERC Public Gateway background tasks started")


async def on_cleanup(app: web.Application) -> None:
    cm: ConnectionManager = app["connection_manager"]
    await cm.stop_heartbeat_monitor()

    # Close any open device websockets
    for dev_id, session in list(cm.devices.items()):
        if session.is_alive:
            try:
                await session.ws.close(code=WSCloseCode.GOING_AWAY, message=b"Gateway shutting down")
            except Exception:
                pass

    # Close any open client websockets
    for s_id, client in list(cm.clients.items()):
        if client.is_alive:
            try:
                await client.ws.close(code=WSCloseCode.GOING_AWAY, message=b"Gateway shutting down")
            except Exception:
                pass

    logger.info("TAPERC Public Gateway connections cleaned up")


def create_app(config: Optional[GatewayConfig] = None) -> web.Application:
    """Creates and configures the aiohttp Application instance."""
    if config is None:
        config = GatewayConfig()
        config.apply_env_overrides()

    auth_manager = AuthManager(config)
    connection_manager = ConnectionManager(config, auth_manager)
    routes = GatewayRoutes(config, auth_manager, connection_manager)

    app = web.Application(middlewares=[cors_middleware])
    app["config"] = config
    app["auth_manager"] = auth_manager
    app["connection_manager"] = connection_manager
    app["routes"] = routes

    routes.setup_routes(app)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app
