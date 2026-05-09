"""
Standalone YIELD INTELLIGENCE MCP server entry point.
Used by Smithery: exposes tools at POST /mcp (standard MCP discovery path).
The full ACE server mounts this at /yield — this file serves it at root.
"""
from mcp.yield_server import yield_mcp_app as app
