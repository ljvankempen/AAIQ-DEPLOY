"""
Pytest configuration and shared fixtures for TAPERC Public Gateway tests.
"""

import asyncio
import os
import sys
from typing import AsyncGenerator

import pytest
try:
    import pytest_asyncio
    async_fixture = pytest_asyncio.fixture
except ImportError:
    async_fixture = pytest.fixture
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# Add the gateway package src directory to path
GATEWAY_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(GATEWAY_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if GATEWAY_ROOT not in sys.path:
    sys.path.insert(0, GATEWAY_ROOT)

from src.app import create_app
from src.auth import AuthManager
from src.config import ClientConfig, DeviceConfig, GatewayConfig, SecurityConfig, ServerConfig
from src.connection_manager import ConnectionManager


@pytest.fixture
def sample_config() -> GatewayConfig:
    return GatewayConfig(
        server=ServerConfig(
            host="127.0.0.1",
            port=8080,
            public_url="https://taperc.aaiq.nl",
            device_ws_path="/device/connect",
            client_ws_path="/client/connect",
            default_device_id="AAIQ-RBP-TEST1",
            heartbeat_interval_sec=1,
            heartbeat_timeout_sec=3,
            log_level="DEBUG",
        ),
        security=SecurityConfig(
            master_key="test_master_secret_key",
            secrets={
                "sec_test1": "secret_test_key_123",
                "sec_test2": "secret_test_key_456",
            },
            require_client_auth=True,
            require_device_auth=True,
        ),
        devices=[
            DeviceConfig(
                device_id="AAIQ-RBP-TEST1",
                name="Revox PR99 Test Unit",
                secret_id="sec_test1",
                relay_count=8,
                enabled=True,
            ),
            DeviceConfig(
                device_id="AAIQ-RBP-TEST2",
                name="Revox B77 Test Unit",
                secret_id="sec_test2",
                relay_count=8,
                enabled=True,
            ),
        ],
        clients=[
            ClientConfig(
                client_id="test_operator",
                token="test_client_token_abc",
                allowed_devices=["*"],
                role="operator",
                enabled=True,
            ),
            ClientConfig(
                client_id="test_restricted",
                token="test_client_token_restricted",
                allowed_devices=["AAIQ-RBP-TEST1"],
                role="viewer",
                enabled=True,
            ),
        ],
    )


@pytest.fixture
def auth_manager(sample_config: GatewayConfig) -> AuthManager:
    return AuthManager(sample_config)


@pytest.fixture
def connection_manager(sample_config: GatewayConfig, auth_manager: AuthManager) -> ConnectionManager:
    return ConnectionManager(sample_config, auth_manager)


@pytest.fixture
def test_app(sample_config: GatewayConfig) -> web.Application:
    return create_app(sample_config)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


import inspect

def pytest_pyfunc_call(pyfuncitem):
    """Execute async test functions directly in an asyncio event loop."""
    testfunction = pyfuncitem.obj
    if inspect.iscoroutinefunction(testfunction):
        argnames = pyfuncitem._fixtureinfo.argnames
        funcargs = pyfuncitem.funcargs
        testargs = {arg: funcargs[arg] for arg in argnames}
        loop = funcargs.get("event_loop")
        if loop is None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(testfunction(**testargs))
            finally:
                loop.close()
        else:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(testfunction(**testargs))
        return True


@pytest.fixture
def test_client(test_app: web.Application, event_loop):
    asyncio.set_event_loop(event_loop)
    server = TestServer(test_app, loop=event_loop)
    client = TestClient(server, loop=event_loop)
    event_loop.run_until_complete(client.start_server())
    try:
        yield client
    finally:
        event_loop.run_until_complete(client.close())
