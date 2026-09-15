"""
TAPERC Public Gateway — Server Entry Point
CLI executable to start the gateway service.
"""

import argparse
import logging
import os
import sys

from aiohttp import web

from .app import create_app
from .config import GatewayConfig


def setup_logging(log_level: str = "INFO") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TAPERC Public Gateway Server")
    parser.add_argument(
        "-c",
        "--config",
        dest="config_path",
        default=os.getenv("TAPERC_CONFIG_FILE", "config/config.json"),
        help="Path to JSON configuration file",
    )
    parser.add_argument(
        "--host",
        dest="host",
        default=None,
        help="Bind host (overrides config/env)",
    )
    parser.add_argument(
        "-p",
        "--port",
        dest="port",
        type=int,
        default=None,
        help="Bind port (overrides config/env)",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if os.path.exists(args.config_path):
        config = GatewayConfig.load_from_file(args.config_path)
    else:
        config = GatewayConfig()
        config.apply_env_overrides()

    if args.host:
        config.server.host = args.host
    if args.port:
        config.server.port = args.port
    if args.log_level:
        config.server.log_level = args.log_level

    setup_logging(config.server.log_level)
    logger = logging.getLogger("taperc.server")
    logger.info("Starting TAPERC Public Gateway v1.0.0")
    logger.info("Public URL: %s", config.server.public_url)
    logger.info("Device WebSocket: %s%s", config.server.public_url.replace("http", "ws"), config.server.device_ws_path)
    logger.info("Client WebSocket: %s%s", config.server.public_url.replace("http", "ws"), config.server.client_ws_path)
    logger.info("Listening on http://%s:%d", config.server.host, config.server.port)

    app = create_app(config)
    web.run_app(app, host=config.server.host, port=config.server.port, access_log=logger)


if __name__ == "__main__":
    main()
