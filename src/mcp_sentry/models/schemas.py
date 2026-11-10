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

class FuzzCase(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result:ToolCallResult

class ObserverReport (BaseModel):
    crashed: bool
    exit_code: int | None
    timed_out: bool
    peak_memory_mb: float
    peak_cpu_percent: float
    stderr_tail: str

