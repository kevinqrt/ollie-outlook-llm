import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("outlook_mcp_client")


class OutlookMcpClient:
    """Manages the connection to the local Outlook MCP Server subprocess."""

    def __init__(self) -> None:
        self._exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def start(self) -> None:
        """Starts the Outlook MCP Server subprocess and initializes the session."""
        if self.session is not None:
            logger.warning("Outlook MCP Client is already running.")
            return

        try:
            logger.info("Starting Outlook MCP Server subprocess...")

            # Using the same interpreter running this FastAPI app to execute the MCP module
            server_params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "app.services.mcp.outlook_mcp_server"],
                env={**os.environ},  # Pass environment variables like Graph API secrets
            )

            # Initialize stdio client and session within our AsyncExitStack
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            # Perform the capability handshake
            await self.session.initialize()
            logger.info("Outlook MCP Client successfully initialized and handshake completed.")

        except Exception as e:
            logger.error(f"Failed to start Outlook MCP Client: {e}")
            await self.stop()
            raise RuntimeError(f"Could not connect to Outlook MCP Server: {e}") from e

    async def stop(self) -> None:
        """Stops the session and terminates the subprocess."""
        logger.info("Stopping Outlook MCP Client and closing connections...")
        self.session = None
        await self._exit_stack.aclose()
        logger.info("Outlook MCP Client stopped.")

    async def get_available_tools(self) -> list[Any]:
        """Fetches the list of tools exposed by the MCP Server."""
        if not self.session:
            raise RuntimeError("MCP Client session is not active. Call start() first.")

        response = await self.session.list_tools()
        return response.tools

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Executes a tool on the MCP Server and returns the result string."""
        if not self.session:
            raise RuntimeError("MCP Client session is not active. Call start() first.")

        logger.info(f"Executing MCP tool '{tool_name}' with args: {arguments}")
        result = await self.session.call_tool(tool_name, arguments)

        # FastMCP tools return their result content. Typically a list of text/image elements
        # We concatenate the text elements for simple string output.
        result_texts = []
        for content in result.content:
            if hasattr(content, "text"):
                result_texts.append(content.text)
            elif isinstance(content, dict) and "text" in content:
                result_texts.append(content["text"])
            else:
                result_texts.append(str(content))

        return "\n".join(result_texts)
