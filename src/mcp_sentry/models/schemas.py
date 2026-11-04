from typing import Any
from pydantic import BaseModel

class ToolSchema(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any]

class ToolCallResult(BaseModel):
    success: bool
    content: Any
    error: str | None
    raw_exception_text: str | None

