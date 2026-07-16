"""Single ARGUS MCP server entrypoint.

Replaces the old duplicated server_by_stdio.py / server_by_sse.py: one
ToolRegistry backs both transports, selected via Settings.transport
(ARGUS_TRANSPORT env var or --transport CLI flag).
"""

from __future__ import annotations

from typing import Sequence

from mcp.server import Server
from mcp.types import TextContent, Tool

from argus.__about__ import __version__
from argus.config.logging import configure_logging
from argus.config.settings import Settings
from argus.core.context import AppContext
from argus.mcp_server.tools.beamline_tools import TOOLS as BEAMLINE_TOOLS
from argus.mcp_server.tools.device_tools import TOOLS as DEVICE_TOOLS
from argus.mcp_server.tools.docs_tools import TOOLS as DOCS_TOOLS
from argus.mcp_server.tools.history_tools import TOOLS as HISTORY_TOOLS
from argus.mcp_server.tools.knowledge_tools import TOOLS as KNOWLEDGE_TOOLS
from argus.mcp_server.tools.logs_tools import TOOLS as LOGS_TOOLS
from argus.mcp_server.tools.ops_tools import TOOLS as OPS_TOOLS
from argus.mcp_server.tools.pv_tools import TOOLS as PV_TOOLS
from argus.mcp_server.tools.registry import ToolRegistry
from argus.mcp_server.tools.saverestore_tools import TOOLS as SAVERESTORE_TOOLS
from argus.mcp_server.transports.sse import run_sse
from argus.mcp_server.transports.stdio import run_stdio

SERVER_NAME = "argus"


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    # beamline_tools first: list_beamline_devices is the intended first call
    # for most device/IOC/zone questions, and tool list position can bias
    # model tool-selection priority, not just the description text.
    registry.register_many(BEAMLINE_TOOLS)
    registry.register_many(PV_TOOLS)
    registry.register_many(DEVICE_TOOLS)
    registry.register_many(HISTORY_TOOLS)
    registry.register_many(OPS_TOOLS)
    registry.register_many(LOGS_TOOLS)
    registry.register_many(DOCS_TOOLS)
    registry.register_many(KNOWLEDGE_TOOLS)
    registry.register_many(SAVERESTORE_TOOLS)
    return registry


def build_mcp_server(registry: ToolRegistry, ctx: AppContext) -> Server:
    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return registry.list_tools()

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> Sequence[TextContent]:
        return await registry.dispatch(name, arguments or {}, ctx)

    return server


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="argus")
    parser.add_argument("--transport", choices=["stdio", "sse"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)

    settings = Settings()
    if args.transport:
        settings.transport = args.transport
    if args.host:
        settings.sse_host = args.host
    if args.port:
        settings.sse_port = args.port

    configure_logging(settings)

    ctx = AppContext.build(settings)
    registry = build_registry()
    server = build_mcp_server(registry, ctx)

    if settings.transport == "stdio":
        import asyncio

        asyncio.run(run_stdio(server, SERVER_NAME, __version__))
    else:
        run_sse(server, settings.sse_host, settings.sse_port)


if __name__ == "__main__":
    main()
