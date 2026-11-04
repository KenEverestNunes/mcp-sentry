from mcp.server.fastmcp import FastMCP
from mcp_sentry.targets._fixtures import ORDERS

mcp = FastMCP("fragile-target")

@mcp.tool()
def get_order(order_id: int) -> dict:
    ORDERS[order_id]  # This will raise a KeyError if the order_id does not exist
    return ORDERS[order_id]


@mcp.tool()
def parse_order_note(order_id: int, note: str) -> dict:
    note.split(":")[1]  # This will raise an IndexError if the note does not contain a colon
    return {"order_id": order_id, "parsed_note": note.split(":")[1]}


# Entry Point for the MCP server
if __name__ == "__main__":
    mcp.run(transport="stdio")
