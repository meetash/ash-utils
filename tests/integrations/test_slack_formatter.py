# ruff: noqa: PT009

import logging
from unittest import TestCase

from ash_utils.integrations import SlackAttachmentFormatter, SlackAttachmentFormatterConfig
from ash_utils.integrations.slack_formatter import build_gcp_logs_explorer_url, build_sentry_issue_url


class SlackAttachmentFormatterTestCase(TestCase):
    def test_format_builds_attachment_payload_with_prominent_identifiers(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(
                service_name="fulfillment-api",
                environment="staging",
                gcp_project_id="ash-stg",
                sentry_organization_slug="ash-wellness",
            ),
        )
        record = _build_record(
            message="Unable to cancel fulfillment",
            level=logging.ERROR,
            extras={
                "kit_id": "KIT123",
                "order_id": "ORD456",
                "partner_id": "mistr",
                "request_id": "req-789",
                "sentry_event_id": "abcdef1234",
            },
        )

        payload = formatter.format(record=record)

        self.assertEqual(payload["title"], "fulfillment-api - ERROR")
        self.assertEqual(payload["color"], "#e11d48")
        self.assertIn("fields", payload)
        self.assertIn("mrkdwn_in", payload)
        self.assertIn("text", payload)
        self.assertIn("────────────", payload["text"])
        self.assertIn("kit_id", payload["text"])
        self.assertIn("KIT123", payload["text"])
        self.assertIn("order_id", payload["text"])
        self.assertIn("partner_id", payload["text"])
        self.assertIn("Root Cause", payload["text"])

        message_field = next(field for field in payload["fields"] if field["title"] == "Message")
        self.assertIn("Unable to cancel fulfillment", message_field["value"])

        links_field = next(field for field in payload["fields"] if field["title"] == "Quick Links")
        self.assertIn("Open Logs", links_field["value"])
        self.assertIn("Open Sentry", links_field["value"])

    def test_format_truncates_long_message_and_hides_sensitive_extra_keys(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(
                service_name="notification-api",
                max_message_length=30,
            ),
        )
        record = _build_record(
            message="X" * 100,
            level=logging.WARNING,
            extras={
                "kit_id": "KIT123",
                "order_id": "ORD456",
                "partner_id": "mistr",
                "request_id": "req-999",
                "api_key": "super-secret",
            },
        )

        payload = formatter.format(record=record)
        message_text = payload["text"]
        message_field = next(field for field in payload["fields"] if field["title"] == "Message")

        self.assertIn("…", message_field["value"])
        self.assertNotIn("super-secret", str(payload))
        self.assertNotIn("api_key", message_text)

    def test_format_surfaces_multiple_pydantic_errors(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(service_name="preprocessing-api", max_pydantic_errors=5),
        )
        record = _build_record(
            message="Validation failed",
            level=logging.ERROR,
            extras={"kit_id": "KIT123", "order_id": "ORD456", "partner_id": "mistr"},
        )
        record.exc_text = (
            "2 validation errors for OrderRequest\n"
            "shippingAddress.zip\n"
            "  String should match pattern\n"
            "patientDOB\n"
            "  Input should be a valid date"
        )

        payload = formatter.format(record=record)
        pydantic_field = next(field for field in payload["fields"] if field["title"] == "Pydantic Validation Errors")
        rendered = pydantic_field["value"]
        self.assertIn("shippingAddress.zip", rendered)
        self.assertIn("patientDOB", rendered)

    def test_format_surfaces_dict_list_validation_errors(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(service_name="order-api", max_pydantic_errors=5),
        )
        validation_payload = (
            "Validation Error: "
            "[{'type': 'value_error', 'loc': (), "
            "'msg': 'Value error, partner ids and kit ids cannot be provided simultaneously'}]"
        )
        record = _build_record(
            message=validation_payload,
            level=logging.ERROR,
            extras={"kit_id": "KIT123", "order_id": "ORD456", "partner_id": "mistr"},
        )

        payload = formatter.format(record=record)
        pydantic_field = next(field for field in payload["fields"] if field["title"] == "Pydantic Validation Errors")
        rendered = pydantic_field["value"]
        self.assertIn("__root__", rendered)
        self.assertIn("partner ids and kit ids cannot be provided simultaneously", rendered)

    def test_format_surfaces_dict_list_errors_for_pydantic_core_trace(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(service_name="order-api", max_pydantic_errors=5),
        )
        validation_payload = (
            "pydantic_core._pydantic_core.ValidationError: 1 error\n"
            "[{'type': 'value_error', 'loc': ('insurance', 0, 'address'), "
            "'msg': 'Field required'}]"
        )
        record = _build_record(
            message="Validation failed",
            level=logging.ERROR,
            extras={"kit_id": "KIT123", "order_id": "ORD456", "partner_id": "mistr"},
        )
        record.exc_text = validation_payload

        payload = formatter.format(record=record)
        pydantic_field = next(field for field in payload["fields"] if field["title"] == "Pydantic Validation Errors")
        rendered = pydantic_field["value"]
        self.assertIn("insurance.0.address", rendered)
        self.assertIn("Field required", rendered)

    def test_format_does_not_surface_unrelated_dict_list_as_pydantic_errors(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(service_name="order-api", max_pydantic_errors=5),
        )
        record = _build_record(
            message="Payload debug: [{'event': 'order-received', 'kitId': 'AW123'}]",
            level=logging.ERROR,
            extras={"kit_id": "KIT123", "order_id": "ORD456", "partner_id": "mistr"},
        )

        payload = formatter.format(record=record)
        pydantic_fields = [field for field in payload["fields"] if field["title"] == "Pydantic Validation Errors"]
        self.assertEqual(pydantic_fields, [])

    def test_build_links_with_direct_overrides(self) -> None:
        sentry_url = build_sentry_issue_url(
            extra={"sentry_issue_url": "https://sentry.example/issue/1"},
            organization_slug="ash",
        )
        logs_url = build_gcp_logs_explorer_url(
            project_id="ash-dev",
            service_name="service-api",
            resource_type="cloud_run_revision",
            record_created=None,
            extra={"logs_url": "https://console.cloud.google.com/logs/query;query=abc"},
        )
        self.assertEqual(sentry_url, "https://sentry.example/issue/1")
        self.assertEqual(logs_url, "https://console.cloud.google.com/logs/query;query=abc")

    def test_build_gcp_logs_url_encodes_spaces_as_percent20(self) -> None:
        logs_url = build_gcp_logs_explorer_url(
            project_id="ash-dev",
            service_name="fulfillment-api",
            resource_type="cloud_run_revision",
            record_created=1_783_013_594.0,
            extra={"kit_id": "KIT123"},
        )
        self.assertIsNotNone(logs_url)
        if logs_url is None:
            self.fail("Expected logs_url to be populated")
        self.assertIn("%20AND%20", logs_url)
        self.assertNotIn("+AND+", logs_url)
        self.assertIn("timestamp%3E%3D", logs_url)
        self.assertIn("timestamp%3C%3D", logs_url)

    def test_format_hides_quick_links_in_local_environment(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(
                service_name="fulfillment-api",
                environment="local",
                gcp_project_id="ash-dev",
                sentry_organization_slug="ash-wellness",
            ),
        )
        record = _build_record(
            message="Local environment test",
            level=logging.ERROR,
            extras={
                "kit_id": "KIT123",
                "order_id": "ORD456",
                "partner_id": "mistr",
                "sentry_event_id": "abcdef1234",
            },
        )

        payload = formatter.format(record=record)
        link_fields = [field for field in payload["fields"] if field["title"] == "Quick Links"]
        self.assertEqual(link_fields, [])

    def test_format_reads_identifiers_from_nested_extra_dict(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(service_name="fulfillment-api"),
        )
        record = _build_record(
            message="Nested extra fields test",
            level=logging.ERROR,
            extras={
                "extra": {
                    "kit_id": "AWNEST123",
                    "order_id": "ORDERNEST123",
                    "partner_id": "mistr",
                    "request_id": "req-nested-1",
                }
            },
        )

        payload = formatter.format(record=record)
        self.assertIn("AWNEST123", payload["text"])
        self.assertIn("ORDERNEST123", payload["text"])
        self.assertIn("mistr", payload["text"])

    def test_format_extracts_message_line_and_traceback_into_separate_fields(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(service_name="fulfillment-api"),
        )
        record = _build_record(
            message=(
                "LEVEL: ERROR\n"
                "MESSAGE: Unexpected exception while processing fulfillment task\n\n"
                "Traceback (most recent call last):\n"
                '  File "<stdin>", line 1, in <module>\n'
                "ValueError: invalid literal for int() with base 10: 'abc'\n"
            ),
            level=logging.ERROR,
            extras={"kit_id": "KIT123", "order_id": "ORD456", "partner_id": "mistr"},
        )

        payload = formatter.format(record=record)
        message_field = next(field for field in payload["fields"] if field["title"] == "Message")
        traceback_field = next(field for field in payload["fields"] if field["title"] == "Traceback")
        self.assertIn("Unexpected exception while processing fulfillment task", message_field["value"])
        self.assertIn("Traceback (most recent call last):", traceback_field["value"])

    def test_format_reads_identifiers_from_nested_context_dict(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(service_name="fulfillment-api"),
        )
        record = _build_record(
            message="Nested context fields test",
            level=logging.ERROR,
            extras={
                "context": {
                    "kit_id": "AWCTX123",
                    "order_id": "ORDERCTX123",
                    "partner_id": "mistr",
                    "request_id": "req-context-1",
                }
            },
        )

        payload = formatter.format(record=record)
        self.assertIn("AWCTX123", payload["text"])
        self.assertIn("ORDERCTX123", payload["text"])
        self.assertIn("mistr", payload["text"])

    def test_format_includes_context_field_from_configured_context_keys(self) -> None:
        formatter = SlackAttachmentFormatter(
            config=SlackAttachmentFormatterConfig(
                service_name="fulfillment-api",
                environment="staging",
            ),
        )
        record = _build_record(
            message="Context rendering test",
            level=logging.ERROR,
            extras={
                "kit_id": "AWCTX123",
                "order_id": "ORDERCTX123",
                "partner_id": "mistr",
                "request_id": "req-ctx-123",
            },
        )

        payload = formatter.format(record=record)
        context_field = next(field for field in payload["fields"] if field["title"] == "Context")
        self.assertIn("request_id", context_field["value"])
        self.assertIn("req-ctx-123", context_field["value"])
        self.assertIn("environment", context_field["value"])
        self.assertIn("staging", context_field["value"])


def _build_record(message: str, level: int, extras: dict[str, object]) -> logging.LogRecord:
    record = logging.LogRecord(
        name="unit-test",
        level=level,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extras.items():
        setattr(record, key, value)
    return record
