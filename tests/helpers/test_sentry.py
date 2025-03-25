import json
from re import S
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from ash_utils.helpers.sentry import (
    before_send,
    redact_exception,
    redact_logentry,
    try_parse_json,
    SentryConfig
)
from parameterized import parameterized
from sentry_sdk.types import Event


class SentryUtilitiesTestcase(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        config = SentryConfig()
        self.sentry_config = config

    def tearDown(self):
        return super().tearDown()

    def test_try_parse_json(self):
        self.assertEqual(try_parse_json(""), None)
        self.assertIsNone(try_parse_json(""))
        self.assertEqual(try_parse_json("invalid"), None)
        self.assertIsNone(try_parse_json("invalid"))
        self.assertEqual(try_parse_json("{'key': 'value'}"), {"key": "value"})
        self.assertEqual(try_parse_json('{"key": "value"}'), {"key": "value"})

    @parameterized.expand(
        [
            ("test message", "test message"),
            (
                "test message with SENSITIVE data",
                "REDACTED SENSITIVE ERROR | test-kit-id",
            ),
            ("test message with sensitive data", "test message with sensitive data"),
            (
                "test message with patient_address1",
                "REDACTED SENSITIVE ERROR | key: address | test-kit-id",
            ),
        ]
    )
    def test_redact_logentry(self, message, redacted_message):
        event = {
            "logentry": {"message": message},
            "extra": {"extra": {"kit_id": "test-kit-id"}},
        }
        redacted_event = redact_logentry(event)
        self.assertEqual(redacted_event["logentry"]["message"], redacted_message)
        self.assertEqual(redacted_event["extra"]["extra"]["kit_id"], "test-kit-id")

    @parameterized.expand(
        [
            (
                {"values": [{"value": "exception string"}]},
                {"values": [{"value": "exception string"}]},
            ),
            (
                {
                    "values": [
                        {"value": "exception string"},
                        {"value": "SENSITIVE string"},
                    ]
                },
                {"values": [{"value": "exception string"}, {"value": "REDACTED"}]},
            ),
            (
                {
                    "values": [
                        {"value": "exception string"},
                        {
                            "value": json.dumps(
                                {"test": "some string", "phone": "123-456-7890"}
                            )
                        },
                    ]
                },
                {
                    "values": [
                        {"value": "exception string"},
                        {
                            "value": json.dumps(
                                {"test": "some string", "phone": "REDACTED"}
                            )
                        },
                    ]
                },
            ),
        ]
    )
    def test_redact_exception(self, exception, redacted_exception):
        event = {
            "exception": exception,
            "extra": {"extra": {"kit_id": "test-kit-id"}},
        }
        redacted_event = redact_exception(event)
        self.assertEqual(redacted_event["exception"], redacted_exception)
        self.assertEqual(redacted_event["extra"]["extra"]["kit_id"], "test-kit-id")

    def test_redact_exception_exception(self):
        event = {
            "exception": {
                "values": [
                    {
                        "value": json.dumps(
                            {"test": "some string", "phone": "123-456-7890"}
                        )
                    }
                ]
            },
            "extra": {"extra": {"kit_id": "test-kit-id"}},
            "contexts": {"context_key": "context_value"},
            "breadcrumbs": [{"message": "breadcrumb"}],
            "tags": {"tag_key": "tag_value"},
        }
        with patch(
            "infrastructure.sentry_utilities.nested_update",
            side_effect=Exception("Mocked exception"),
        ):
            redacted_event = redact_exception(event)
            self.assertNotIn("exception", redacted_event)
            self.assertNotIn("contexts", redacted_event)
            self.assertNotIn("extra", redacted_event)
            self.assertNotIn("breadcrumbs", redacted_event)
            self.assertNotIn("tags", redacted_event)

    def test_before_send(self):
        event = {
            "logentry": {"message": "test message"},
            "exception": {"values": [{"value": "exception string"}]},
            "extra": {"extra": {"kit_id": "test-kit-id"}},
        }
        redacted_event = before_send(event, None, self.sentry_config)
        self.assertIsInstance(redacted_event, Event)
        self.assertEqual(redacted_event["logentry"]["message"], "test message")
        self.assertEqual(
            redacted_event["exception"], {"values": [{"value": "exception string"}]}
        )
        self.assertEqual(redacted_event["extra"]["extra"]["kit_id"], "test-kit-id")
