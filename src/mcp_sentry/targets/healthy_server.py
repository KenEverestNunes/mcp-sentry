from mcp.server.fastmcp import FastMCP

mcp = FastMCP("healthy-target")

# Fake data for testing purposes
ORDERS: dict[int, dict] = {
    1: {"order_id": 1, "status": "pending"},
    2: {"order_id": 2, "status": "shipped"},
}

@mcp.tool()
def get_order(order_id: int) -> dict:
    """Get order details by order ID."""
    if order_id in ORDERS:
        return ORDERS[order_id]
    else:
        raise ValueError(f"Order ID {order_id} not found.")

@mcp.tool()
def list_orders(status:str | None = None) -> list[dict]:
    """List all Orders if not status is provided, else filter by status."""
    if status:
        return [order for order in ORDERS.values() if order["status"] == status]
    return list(ORDERS.values())

@mcp.tool()
def update_order_status(order_id: int, status: str) -> dict:
    """Update the status of an order."""
    if order_id in ORDERS:
        if status not in ["pending", "shipped", "delivered"]:
            raise ValueError(f"Invalid status: {status}. Must be 'pending', 'shipped', or 'delivered'.")
        ORDERS[order_id]["status"] = status
        return ORDERS[order_id]
    else:
        raise ValueError(f"Order ID {order_id} not found.")
    
#Entry Point for the MCP server
if __name__ == "__main__":
    mcp.run(transport="stdio")