import json
import logging
import re
from typing import Any, Pattern, Sequence
from mcp_sentry.evaluation.verdict import Verdict
from mcp_sentry.models.schemas import FuzzCase, ObserverReport, ToolCallResult

logger = logging.getLogger(__name__)

TRACEBACK_PATTERN = re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE)
MCP_INVALID_PARAMS_PATTERN = re.compile(
    r"(?:code\s*[:=]\s*-32602|\b-32602\b|invalid\s+params\b)",
    re.IGNORECASE,
)


def _compile_patterns(patterns: Sequence[str | Pattern[str]]) -> list[Pattern[str]]:
    """Safely compile pattern sequences, skipping malformed regexes with a warning."""
    compiled: list[Pattern[str]] = []
    for p in patterns:
        if isinstance(p, Pattern):
            compiled.append(p)
        else:
            try:
                compiled.append(re.compile(p))
            except re.error as exc:
                logger.warning("Skipping invalid leak detection regex %r: %s", p, exc)
    return compiled


def _serialize_content(content: Any) -> str:
    """Serialize response content to canonical JSON format for reliable regex scanning."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, default=str)
    except Exception:
        return str(content)



def is_clean_protocol_rejection(result: ToolCallResult) -> bool:
    """
    Checks if a tool failure is a standard MCP protocol error for invalid parameters (-32602).
    A clean schema validation rejection from FastMCP/MCP is considered correct behavior, not a bug,
    provided no unhandled exception traceback is present.
    """
    if result.success:
        return False

    error_text = result.error or ""
    raw_text = result.raw_exception_text or ""
    error_blob = f"{error_text} {raw_text}"

    # If an unhandled traceback is leaked, it is NOT a clean protocol rejection
    if TRACEBACK_PATTERN.search(error_blob):
        return False

    return bool(MCP_INVALID_PARAMS_PATTERN.search(error_blob))


class EvaluationEngine:
    """
    Combines the original fuzzer request, target response, and out-of-band Observer report
    into a structured Verdict.
    """

    def __init__(self, leak_patterns: Sequence[str | Pattern[str]] | None = None) -> None:
        self.compiled_leak_patterns: list[Pattern[str]] = (
            _compile_patterns(leak_patterns) if leak_patterns else []
        )

    def evaluate(
        self,
        case: FuzzCase,
        observer_report: ObserverReport | None = None,
        leak_patterns: Sequence[str | Pattern[str]] | None = None,
    ) -> Verdict:
        """
        Evaluate a fuzz case against observer metrics and response contents.
        Priority order:
        1. observer_report.crashed -> critical ("target crashed on input")
        2. observer_report.timed_out -> critical ("target froze / exceeded timeout")
        3. Raw traceback leaked -> warning ("unhandled exception leaked to caller")
        4. Clean protocol rejection -> passed=True, info ("target correctly rejected invalid input")
        5. Configured leak pattern in content -> critical ("response contains a configured leak pattern")
        6. Otherwise -> passed=True, info ("tool call executed safely")
        """
        # 1. Container crash check
        if observer_report and observer_report.crashed:
            return Verdict(
                fuzz_case=case,
                passed=False,
                reasons=["target crashed on input"],
                severity="critical",
            )

        # 2. Timeout / freeze check
        if observer_report and observer_report.timed_out:
            return Verdict(
                fuzz_case=case,
                passed=False,
                reasons=["target froze / exceeded timeout"],
                severity="critical",
            )

        # 3. Raw traceback text in result.error or raw_exception_text
        error_blob = f"{case.result.error or ''} {case.result.raw_exception_text or ''}"
        if TRACEBACK_PATTERN.search(error_blob):
            return Verdict(
                fuzz_case=case,
                passed=False,
                reasons=["unhandled exception leaked to caller"],
                severity="warning",
            )

        # 4. Clean protocol rejection (e.g., -32602 Invalid params without traceback)
        if is_clean_protocol_rejection(case.result):
            return Verdict(
                fuzz_case=case,
                passed=True,
                reasons=["target correctly rejected invalid input"],
                severity="info",
            )

        # 5. Leak pattern detection
        patterns_to_check = (
            _compile_patterns(leak_patterns)
            if leak_patterns is not None
            else self.compiled_leak_patterns
        )

        content_str = _serialize_content(case.result.content)
        for pattern in patterns_to_check:
            if pattern.search(content_str):
                return Verdict(
                    fuzz_case=case,
                    passed=False,
                    reasons=["response contains a configured leak pattern"],
                    severity="critical",
                )

        # 6. Pass
        return Verdict(
            fuzz_case=case,
            passed=True,
            reasons=["tool call executed safely"],
            severity="info",
        )
