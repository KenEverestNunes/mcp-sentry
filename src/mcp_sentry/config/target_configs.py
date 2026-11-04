from dataclasses import dataclass

@dataclass
class TargetConfig:
    name: str
    command: str
    args: list[str]
    leak_patterns: list[str]

TARGET_CONFIGS = {
    "healthy": TargetConfig(
        name="healthy",
        command="uv",
        args=["run", "python", "-m", "mcp_sentry.targets.healthy_server"],
        leak_patterns=[],
    ),
    "fragile": TargetConfig(
        name="fragile",
        command="uv",
        args=["run", "python", "-m", "mcp_sentry.targets.fragile_server"],
        leak_patterns=[],
    ),
    "leaky": TargetConfig(
        name="leaky",
        command="uv",
        args=["run", "python", "-m", "mcp_sentry.targets.leaky_server"],
        leak_patterns=[
            r"DB_CONNECTION_STRING",
            r"/home/\w+",
            r"AKIA[0-9A-Z]{16}",
        ],
    ),
}