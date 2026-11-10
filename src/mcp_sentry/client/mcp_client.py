import asyncio
from contextlib import AsyncExitStack
from typing import Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError
from mcp_sentry.models.schemas import ToolCallResult, ToolSchema
from mcp_sentry.sandbox.docker_runner import ContainerHandle
from mcp_sentry.sandbox.docker_transport import docker_socket_client

class MCPConnectionError(RuntimeError):
    """Raised when an MCP server cannot be started or initialized."""


class MCPClient:
    def __init__(self, command: str | None = None, args: list[str] | None = None) -> None:
        self._command = command
        self._args = args
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self._initialized = False

    async def connect_to_container(self, handle: ContainerHandle) -> None:
        if self.session is not None:
            return
        self._stack = AsyncExitStack()
        try:
            read_stream, write_stream = await self._stack.enter_async_context(
                docker_socket_client(handle)
            )
            self.session = await self._stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
        except OSError as exc:
            await self.close()
            raise MCPConnectionError("Could not connect to the sandboxed container.") from exc

    async def connect(self, command: str | None = None, args: list[str] | None = None) -> None:
        if self.session is not None:
            return

        command = command or self._command
        args = args if args is not None else self._args
        if command is None or args is None:
            raise MCPConnectionError("A server command and argument list are required.")

        self._command = command
        self._args = args
        self._stack = AsyncExitStack()
        server_params = StdioServerParameters(command=command, args=args)
        try:
            read_stream, write_stream = await self._stack.enter_async_context(
                stdio_client(server_params)
            )
            self.session = await self._stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
        except (FileNotFoundError, BrokenPipeError, OSError) as exc:
            await self.close()
            raise MCPConnectionError(
                f"Could not start MCP server with command {command!r}."
            ) from exc

    async def discover_tools(self) -> list[ToolSchema]:
        if self.session is None:
            raise MCPConnectionError("Connect to an MCP server before discovering tools.")

        try:
            if not self._initialized:
                await asyncio.wait_for(self.session.initialize(), timeout=5)
                self._initialized = True
            result = await self.session.list_tools()
        except TimeoutError as exc:
            await self.close()
            raise MCPConnectionError("Timed out while initializing the MCP server.") from exc
        except (FileNotFoundError, BrokenPipeError, OSError) as exc:
            await self.close()
            raise MCPConnectionError(
                "The MCP server exited during initialization or discovery."
            ) from exc

        return [
            ToolSchema(
                name=tool.name,
                description=tool.description,
                input_schema=tool.inputSchema,
            )
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        if self.session is None:
            raise MCPConnectionError("Connect to an MCP server before calling tools.")

        try:
            if not self._initialized:
                await asyncio.wait_for(self.session.initialize(), timeout=5)
                self._initialized = True
            try:
                result = await self.session.call_tool(name, arguments)
            except McpError as exc:
                return ToolCallResult(
                    success=False,
                    content=None,
                    error=str(exc),
                    raw_exception_text=str(exc),
                )
            print(result.model_dump())
        except TimeoutError as exc:
            await self.close()
            raise MCPConnectionError("Timed out while initializing the MCP server.") from exc
        except (FileNotFoundError, BrokenPipeError, OSError) as exc:
            await self.close()
            raise MCPConnectionError(
                "The MCP server exited during initialization or discovery."
            ) from exc

        if result.isError:
            return ToolCallResult(
                success=False,
                content=result.content,
                error=result.content[0].text,
                raw_exception_text=result.content[0].text,
            )
        else:
            return ToolCallResult(
                success=True,
                content=result.content,
                error=None,
                raw_exception_text=None,
            )

    async def close(self) -> None:
        await self._stack.aclose()
        self._stack = AsyncExitStack()
        self.session = None
        self._initialized = False

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.close()