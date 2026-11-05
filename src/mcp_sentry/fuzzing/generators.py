import logging

logger = logging.getLogger(__name__)
MAX_FUZZ_STRING_LEN = 10_000

def generate_edge_cases(schema: dict) -> list[dict]:
    properties = schema.get("properties", {})

    baseline = {}
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type")
        baseline[prop_name] = DEFAULT_VALUES.get(prop_type)

    results = []
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type")
        generator = TYPE_TO_GENERATOR.get(prop_type)

        if generator is None:
            logger.warning(
                f"Skipping property '{prop_name}': no edge-case generator for type {prop_type!r}"
            )
            continue

        for edge_value in generator():
            case = baseline.copy()
            case[prop_name] = edge_value
            results.append(case)

    return results

DEFAULT_VALUES = {
    "string": "default",
    "integer": 1,
    "boolean": False,
    "object": {},
    "array": [],
}

def _string_edge_cases() -> list[str]:
    return [
        "",
        "a" * MAX_FUZZ_STRING_LEN,
        "特殊字符",
        "null\0byte",
        "newline\ncharacter",
        "tab\tcharacter",
        "emoji😊",
        "\x00"
    ]

def _integer_edge_cases() -> list[int]:
    return [
        0,
        -1,  
        1, 
        -(2**31),  
        2**31 - 1,   
        -(2**63), 
        2**63 - 1,   
    ]

def _boolean_edge_cases() -> list[bool]:
    return [True,False, "true", "false", 1, 0, None]

def _build_nested(depth: int):
    if depth == 0:
        return "leaf"
    return {"nested": _build_nested(depth - 1)}

def _object_edge_cases() -> list[dict]:
    nested = "leaf"
    for _ in range(10):
        nested = {"nested": nested}

    return [{},nested]

def _array_edge_cases() -> list[list]:
    return [
        [],
        [i for i in range(MAX_FUZZ_STRING_LEN)], 
    ]

TYPE_TO_GENERATOR = {
    "string": _string_edge_cases,
    "integer": _integer_edge_cases,
    "boolean": _boolean_edge_cases,
    "object": _object_edge_cases,
    "array": _array_edge_cases,
}