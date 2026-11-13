from typing import Literal
from pydantic import BaseModel
from mcp_sentry.models.schemas import FuzzCase

class Verdict(BaseModel):
    fuzz_case: FuzzCase
    passed: bool
    reasons: list[str]
    severity: Literal["info", "warning", "critical"]
