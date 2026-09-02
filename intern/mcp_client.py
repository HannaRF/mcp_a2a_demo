"""
Intern's MCP client: this is the "vertical" connection from section 2 of
the lecture. The Intern is itself the MCP host here — it owns the connection
to the product-catalog MCP server and decides when to call a tool.
"""
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_SERVER_URL = "http://127.0.0.1:8100/mcp"


@asynccontextmanager
async def mcp_session():
    """Async context manager that yields an initialized MCP ClientSession.

    Keeps the connection open for the duration of the block, so the caller
    can list tools and make multiple tool calls over a single session.
    """
    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
