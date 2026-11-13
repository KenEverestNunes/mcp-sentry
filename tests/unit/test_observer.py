import pytest
from mcp_sentry.sandbox.observer import Observer


def test_parse_stats_handles_empty_stats() -> None:
    cpu_percent, memory_mb = Observer._parse_stats({})
    assert cpu_percent == 0.0
    assert memory_mb == 0.0


def test_parse_stats_handles_missing_memory_usage() -> None:
    stats = {
        "cpu_stats": {"cpu_usage": {"total_usage": 100}, "system_cpu_usage": 1000},
        "precpu_stats": {"cpu_usage": {"total_usage": 50}, "system_cpu_usage": 500},
        "memory_stats": {},
    }
    cpu_percent, memory_mb = Observer._parse_stats(stats)
    assert cpu_percent > 0.0
    assert memory_mb == 0.0


def test_parse_stats_handles_valid_stats() -> None:
    stats = {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 200},
            "system_cpu_usage": 1000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 100},
            "system_cpu_usage": 500,
        },
        "memory_stats": {
            "usage": 1024 * 1024 * 64,  # 64 MB
        },
    }
    cpu_percent, memory_mb = Observer._parse_stats(stats)
    assert cpu_percent == 40.0
    assert memory_mb == 64.0
