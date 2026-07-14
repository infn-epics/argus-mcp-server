from __future__ import annotations

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route


def build_sse_app(server: Server) -> Starlette:
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> Response:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
        # Starlette's function-endpoint wrapper always calls the returned value as
        # an ASGI response; returning None here (as the original server_by_sse.py
        # did) crashes with "'NoneType' object is not callable" once the stream
        # tears down, so return an explicit empty Response instead.
        return Response()

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )


def run_sse(server: Server, host: str, port: int) -> None:
    import uvicorn

    app = build_sse_app(server)
    uvicorn.run(app, host=host, port=port)
