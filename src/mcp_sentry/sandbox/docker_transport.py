import asyncio
from contextlib import asynccontextmanager
import anyio
from mcp import types
from mcp.shared.message import SessionMessage
from mcp_sentry.sandbox.docker_runner import ContainerHandle


@asynccontextmanager
async def docker_socket_client(handle: ContainerHandle):
    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)
    sock = handle.socket

    def _recv_exact(sock, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                break
            data += chunk
        return data

    async def socket_reader() -> None:
        buffer = b""
        try:
            while True:
                header = await asyncio.to_thread(_recv_exact, sock, 8)
                if len(header) < 8:
                    break
                stream_type = header[0]
                payload_size = int.from_bytes(header[4:8], "big")
                payload = await asyncio.to_thread(_recv_exact, sock, payload_size)

                if stream_type != 1:  # skip stderr(2)/stdin(0), only stdout carries JSON-RPC
                    continue

                buffer += payload
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        message = types.JSONRPCMessage.model_validate_json(line)
                    except Exception as exc:
                        await read_stream_writer.send(exc)
                        continue
                    await read_stream_writer.send(SessionMessage(message))
        finally:
            await read_stream_writer.aclose()

    async def socket_writer() -> None:
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    data = (
                        session_message.message.model_dump_json(
                            by_alias=True, exclude_none=True
                        ).encode("utf-8")
                        + b"\n"
                    )
                    await asyncio.to_thread(sock.sendall, data)
        except anyio.ClosedResourceError:
            pass

    reader_task = asyncio.create_task(socket_reader())
    writer_task = asyncio.create_task(socket_writer())
    try:
        yield read_stream, write_stream
    finally:
        reader_task.cancel()
        writer_task.cancel()
        await read_stream.aclose()
        await write_stream.aclose()
    