from typing import Any
from pydantic import BaseModel

class ToolSchema(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any]
