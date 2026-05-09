"""
Base MCP Streamable HTTP Server
MCP spec 2025-11-25
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from .auth import require_auth

MCP_VERSION = "2025-11-25"


class MCPServer:
    def __init__(self, name: str, version: str, tools: List[Dict]):
        self.name = name
        self.version = version
        self.tools = tools
        self.sessions: Dict[str, Dict] = {}
        self.app = self._build_app()

    def _build_app(self) -> FastAPI:
        app = FastAPI(
            title=f"IntuiTek\u00b9 {self.name} MCP Server",
            docs_url=None,
            redoc_url=None,
        )
        server = self  # closure ref

        @app.get("/")
        async def server_info():
            return {
                "name": server.name,
                "version": server.version,
                "mcp_version": MCP_VERSION,
                "transport": "streamable-http",
                "tools_count": len(server.tools),
                "endpoints": {
                    "post": "/mcp",
                    "sse": "/mcp",
                    "delete": "/mcp",
                },
            }

        @app.post("/mcp")
        async def handle_post(
            request: Request,
            mcp_session_id: Optional[str] = Header(None, alias="mcp-session-id"),
            _auth: str = Depends(require_auth),
        ):
            body = await request.json()
            session_id = mcp_session_id or str(uuid.uuid4())
            response_body = await server._handle_rpc(body, session_id)
            if response_body is None:
                resp = Response(status_code=204)
                resp.headers["Mcp-Session-Id"] = session_id
                return resp
            resp = JSONResponse(content=response_body)
            resp.headers["Mcp-Session-Id"] = session_id
            return resp

        @app.get("/mcp")
        async def handle_get(
            request: Request,
            mcp_session_id: Optional[str] = Header(None, alias="mcp-session-id"),
        ):
            session_id = mcp_session_id or str(uuid.uuid4())

            async def event_stream():
                yield (
                    "data: "
                    + json.dumps({"type": "connected", "sessionId": session_id})
                    + "\n\n"
                )
                # Keep-alive
                while True:
                    import asyncio
                    await asyncio.sleep(15)
                    yield ": keep-alive\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Mcp-Session-Id": session_id},
            )

        @app.delete("/mcp")
        async def handle_delete(
            request: Request,
            mcp_session_id: Optional[str] = Header(None, alias="mcp-session-id"),
        ):
            if mcp_session_id and mcp_session_id in server.sessions:
                del server.sessions[mcp_session_id]
            return Response(status_code=204)

        return app

    async def _handle_rpc(self, body: Dict, session_id: str) -> Optional[Dict]:
        method = body.get("method", "")
        params = body.get("params", {})
        req_id = body.get("id")

        if method == "initialize":
            self.sessions[session_id] = {
                "initialized": True,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": MCP_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }

        elif method == "notifications/initialized":
            # Notification — no response
            return None

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.tools},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                result = await self.call_tool(tool_name, tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result)}],
                        "isError": False,
                    },
                }
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": str(exc)}],
                        "isError": True,
                    },
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    async def call_tool(self, tool_name: str, args: Dict) -> Any:
        raise NotImplementedError(f"Tool not implemented: {tool_name}")
