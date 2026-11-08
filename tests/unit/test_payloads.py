from mcp_sentry.fuzzing.payloads import MALICIOUS_PAYLOADS


def test_malicious_payload_categories_are_non_empty() -> None:
    for payloads in MALICIOUS_PAYLOADS.values():
        assert payloads


def test_malicious_payload_entries_are_strings() -> None:
    for payloads in MALICIOUS_PAYLOADS.values():
        for payload in payloads:
            assert isinstance(payload, str)