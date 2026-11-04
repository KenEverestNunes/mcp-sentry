from mcp.server.fastmcp import FastMCP
from mcp_sentry.targets._fixtures import ORDERS
import os

os.environ.setdefault("DB_CONNECTION_STRING", "postgres://fake:fake@localhost/fakedb")
DB_CONNECTION_STRING = os.environ.get("DB_CONNECTION_STRING")

mcp = FastMCP("leaky-target")

@mcp.tool()
def debug_order(order_id: int, verbose: bool = False) -> dict:
    if verbose:
        return  {"db_connection_string": DB_CONNECTION_STRING, "file_path": "/home/user/secret.txt"}
    elif order_id in ORDERS:
        return ORDERS[order_id]
    else:
        raise ValueError(f"Order ID {order_id} not found.")

#Entry Point for the MCP server
if __name__ == "__main__":
    mcp.run(transport="stdio")