import pytest
from mcp_sentry.evaluation.engine import EvaluationEngine, is_clean_protocol_rejection
from mcp_sentry.models.schemas import FuzzCase, ObserverReport, ToolCallResult


@pytest.fixture
def default_observer_clean() -> ObserverReport:
    return ObserverReport(
        crashed=False,
        exit_code=0,
        timed_out=False,
        peak_memory_mb=25.0,
        peak_cpu_percent=1.5,
        stderr_tail="",
    )


def test_clean_success(default_observer_clean: ObserverReport) -> None:
    engine = EvaluationEngine()
    case = FuzzCase(
        tool_name="get_order",
        arguments={"order_id": 1},
        result=ToolCallResult(
            success=True,
            content={"order_id": 1, "status": "shipped"},
            error=None,
            raw_exception_text=None,
        ),
    )
    verdict = engine.evaluate(case, default_observer_clean)
    assert verdict.passed is True
    assert verdict.severity == "info"
    assert "tool call executed safely" in verdict.reasons


def test_target_crashed() -> None:
    engine = EvaluationEngine()
    case = FuzzCase(
        tool_name="parse_order_note",
        arguments={"note": "bad_input_no_colon"},
        result=ToolCallResult(
            success=False,
            content=None,
            error="Connection closed unexpectedly",
            raw_exception_text="BrokenPipeError",
        ),
    )
    crashed_observer = ObserverReport(
        crashed=True,
        exit_code=1,
        timed_out=False,
        peak_memory_mb=12.0,
        peak_cpu_percent=5.0,
        stderr_tail="IndexError: list index out of range",
    )
    verdict = engine.evaluate(case, crashed_observer)
    assert verdict.passed is False
    assert verdict.severity == "critical"
    assert "target crashed on input" in verdict.reasons


def test_target_timed_out() -> None:
    engine = EvaluationEngine()
    case = FuzzCase(
        tool_name="infinite_loop_tool",
        arguments={},
        result=ToolCallResult(
            success=False,
            content=None,
            error="Timeout",
            raw_exception_text="TimeoutError",
        ),
    )
    timed_out_observer = ObserverReport(
        crashed=False,
        exit_code=None,
        timed_out=True,
        peak_memory_mb=120.0,
        peak_cpu_percent=99.0,
        stderr_tail="",
    )
    verdict = engine.evaluate(case, timed_out_observer)
    assert verdict.passed is False
    assert verdict.severity == "critical"
    assert "target froze / exceeded timeout" in verdict.reasons


def test_clean_protocol_rejection(default_observer_clean: ObserverReport) -> None:
    engine = EvaluationEngine()
    case = FuzzCase(
        tool_name="get_order",
        arguments={"order_id": "not_an_int"},
        result=ToolCallResult(
            success=False,
            content=None,
            error="Invalid params for tool get_order: [-32602]",
            raw_exception_text="FastMCP error -32602: Invalid params",
        ),
    )
    assert is_clean_protocol_rejection(case.result) is True
    verdict = engine.evaluate(case, default_observer_clean)
    assert verdict.passed is True
    assert verdict.severity == "info"
    assert "target correctly rejected invalid input" in verdict.reasons


def test_unhandled_traceback_leaked(default_observer_clean: ObserverReport) -> None:
    engine = EvaluationEngine()
    traceback_sample = (
        "Traceback (most recent call last):\n"
        "  File 'server.py', line 42, in handler\n"
        "ZeroDivisionError: division by zero"
    )
    case = FuzzCase(
        tool_name="calculate_discount",
        arguments={"divisor": 0},
        result=ToolCallResult(
            success=False,
            content=None,
            error=traceback_sample,
            raw_exception_text=traceback_sample,
        ),
    )
    verdict = engine.evaluate(case, default_observer_clean)
    assert verdict.passed is False
    assert verdict.severity == "warning"
    assert "unhandled exception leaked to caller" in verdict.reasons


def test_leak_pattern_detection(default_observer_clean: ObserverReport) -> None:
    engine = EvaluationEngine(
        leak_patterns=[
            r"DB_CONNECTION_STRING",
            r"AKIA[0-9A-Z]{16}",
        ]
    )
    case = FuzzCase(
        tool_name="debug_order",
        arguments={"order_id": 1, "verbose": True},
        result=ToolCallResult(
            success=True,
            content={"env": "DB_CONNECTION_STRING=postgresql://user:secret@localhost:5432/orders"},
            error=None,
            raw_exception_text=None,
        ),
    )
    verdict = engine.evaluate(case, default_observer_clean)
    assert verdict.passed is False
    assert verdict.severity == "critical"
    assert "response contains a configured leak pattern" in verdict.reasons


@pytest.mark.parametrize(
    "crashed,timed_out,err_text,content,expected_passed,expected_severity,expected_reason",
    [
        (True, False, "", {}, False, "critical", "target crashed on input"),
        (False, True, "", {}, False, "critical", "target froze / exceeded timeout"),
        (
            False,
            False,
            "Error -32602: Invalid params",
            {},
            True,
            "info",
            "target correctly rejected invalid input",
        ),
        (
            False,
            False,
            "Traceback (most recent call last):\n  File 'a.py'",
            {},
            False,
            "warning",
            "unhandled exception leaked to caller",
        ),
        (
            False,
            False,
            "",
            {"secret": "AKIA1234567890ABCDEF"},
            False,
            "critical",
            "response contains a configured leak pattern",
        ),
        (
            False,
            False,
            "",
            {"order_id": 100, "status": "ok"},
            True,
            "info",
            "tool call executed safely",
        ),
    ],
)
def test_table_driven_verdicts(
    crashed: bool,
    timed_out: bool,
    err_text: str,
    content: dict,
    expected_passed: bool,
    expected_severity: str,
    expected_reason: str,
) -> None:
    engine = EvaluationEngine(leak_patterns=[r"AKIA[0-9A-Z]{16}"])
    observer = ObserverReport(
        crashed=crashed,
        exit_code=1 if crashed else 0,
        timed_out=timed_out,
        peak_memory_mb=10.0,
        peak_cpu_percent=1.0,
        stderr_tail="Crash stderr" if crashed else "",
    )
    case = FuzzCase(
        tool_name="table_tool",
        arguments={},
        result=ToolCallResult(
            success=(not err_text),
            content=content,
            error=err_text if err_text else None,
            raw_exception_text=err_text if err_text else None,
        ),
    )
    verdict = engine.evaluate(case, observer)
    assert verdict.passed == expected_passed
    assert verdict.severity == expected_severity
    assert expected_reason in verdict.reasons
