from mcp_sentry.fuzzing.generators import (
    DEFAULT_VALUES,
    MAX_FUZZ_STRING_LEN,
    _array_edge_cases,
    _boolean_edge_cases,
    _integer_edge_cases,
    _object_edge_cases,
    _string_edge_cases,
    generate_edge_cases,
)


def test_string_edge_cases() -> None:
    assert _string_edge_cases() == [
        "",
        "a" * MAX_FUZZ_STRING_LEN,
        "特殊字符",
        "null\0byte",
        "newline\ncharacter",
        "tab\tcharacter",
        "emoji😊",
        "\x00",
    ]


def test_integer_edge_cases() -> None:
    assert _integer_edge_cases() == [
        0,
        -1,
        1,
        -(2**31),
        2**31 - 1,
        -(2**63),
        2**63 - 1,
    ]


def test_boolean_edge_cases() -> None:
    assert _boolean_edge_cases() == [True, False, "true", "false", 1, 0, None]


def test_object_edge_cases() -> None:
    nested = "leaf"
    for _ in range(10):
        nested = {"nested": nested}

    assert _object_edge_cases() == [{}, nested]


def test_array_edge_cases() -> None:
    assert _array_edge_cases() == [[], list(range(MAX_FUZZ_STRING_LEN))]


def test_generate_edge_cases_mutates_one_property_at_a_time() -> None:
    schema = {
        "properties": {
            "count": {"type": "integer"},
            "enabled": {"type": "boolean"},
        }
    }

    cases = generate_edge_cases(schema)
    baseline = {"count": DEFAULT_VALUES["integer"], "enabled": DEFAULT_VALUES["boolean"]}
    expected_mutations = [
        ("count", value) for value in _integer_edge_cases()
    ] + [("enabled", value) for value in _boolean_edge_cases()]

    assert isinstance(cases, list)
    assert len(cases) == len(expected_mutations)
    for case, (mutated_property, edge_value) in zip(cases, expected_mutations):
        assert isinstance(case, dict)
        assert set(case) == set(baseline)
        assert case[mutated_property] == edge_value
        changed_properties = {
            property_name
            for property_name in baseline
            if case[property_name] != baseline[property_name]
        }
        assert changed_properties == (
            {mutated_property}
            if edge_value != baseline[mutated_property]
            else set()
        )
        assert all(
            case[property_name] == baseline[property_name]
            for property_name in baseline
            if property_name != mutated_property
        )


def test_generate_edge_cases_skips_properties_without_supported_types(caplog) -> None:
    schema = {
        "properties": {
            "count": {"type": "integer"},
            "missing_type": {},
            "unsupported_type": {"type": "number"},
        }
    }

    cases = generate_edge_cases(schema)

    assert len(cases) == len(_integer_edge_cases())
    assert all(case["missing_type"] is None for case in cases)
    assert all(case["unsupported_type"] is None for case in cases)
    assert "Skipping property 'missing_type'" in caplog.text
    assert "Skipping property 'unsupported_type'" in caplog.text