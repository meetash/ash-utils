import json
from unittest import IsolatedAsyncioTestCase, mock
from unittest.mock import patch

from ash_utils.helpers.constants import SentryConstants
from ash_utils.helpers.sentry import (
    before_send,
    redact_exception,
    redact_logentry,
    try_parse_json,
    SentryConfig,
    initialize_sentry,
)

from sentry_sdk.integrations.loguru import LoguruIntegration
from parameterized import parameterized


class SentryUtilitiesTestcase(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.sentry_config = SentryConfig()

    def test_try_parse_json_returns_None_with_invalid_json(self):
        self.assertIsNone(try_parse_json(""))
        self.assertIsNone(try_parse_json("invalid"))

    @parameterized.expand(
        [
            ("{'key': 'value'}", {"key": "value"}),
            ('{"key": "value"}', {"key": "value"}),
            ('{"key": "value", "nested": {"key2": "value2"}}', {"key": "value", "nested": {"key2": "value2"}}),
            ('{"key": ["value1", "value2"]}', {"key": ["value1", "value2"]}),
        ]
    )
    def test_try_parse_json_returns_dict_with_valid_json(self, json_to_parse, expected_result):
        self.assertEqual(try_parse_json(json_to_parse), expected_result)

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
        redacted_event = redact_logentry(event, self.sentry_config)
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
                        {"value": json.dumps({"test": "some string", "phone": "123-456-7890"})},
                    ]
                },
                {
                    "values": [
                        {"value": "exception string"},
                        {"value": json.dumps({"test": "some string", "phone": "REDACTED"})},
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
        redacted_event = redact_exception(event, self.sentry_config)
        self.assertEqual(redacted_event["exception"], redacted_exception)
        self.assertEqual(redacted_event["extra"]["extra"]["kit_id"], "test-kit-id")
        exception_values = redacted_event["exception"]["values"]
        for value in exception_values:
            try:
                parsed_val = json.loads(value["value"])
            except json.JSONDecodeError:
                parsed_val = value["value"]
            if isinstance(parsed_val, dict):
                for key, val in parsed_val.items():
                    if key in self.sentry_config.keys_to_filter:
                        self.assertEqual(val, SentryConstants.REDACTION_STRING)

    def test_redact_exception_exception(self):
        event = {
            "exception": {
                "values": [
                    {
                        "value": json.dumps({"test": "some string", "phone": "123-456-7890"}),
                        "type": "TestErrorType",
                    }
                ]
            },
            "extra": {"extra": {"kit_id": "test-kit-id"}},
            "contexts": {"context_key": "context_value"},
            "breadcrumbs": [{"message": "breadcrumb"}],
            "tags": {"tag_key": "tag_value"},
        }
        with patch(
            "ash_utils.helpers.sentry.nested_update",
            side_effect=Exception("Mocked exception"),
        ):
            redacted_event = redact_exception(event, self.sentry_config)
            self.assertIn("exception", redacted_event)
            self.assertIsInstance(redacted_event["exception"], dict)
            self.assertEqual(redacted_event["exception"], {"values": [{"type": "TestErrorType"}]})
            self.assertEqual(redacted_event["exception"]["values"][0]["type"], "TestErrorType")
            for key in ["extra", "contexts", "breadcrumbs", "tags"]:
                self.assertIn(key, redacted_event)
                self.assertEqual(redacted_event[key], {})

    def test_before_send__no_sensitive_data__information_unchanged(self):
        """
        Test the before_send function when no sensitive data is present to ensure that the event is unchanged.
        """
        event = {
            "logentry": {"message": "test message"},
            "exception": {"values": [{"value": "exception string"}]},
            "extra": {"extra": {"kit_id": "test-kit-id"}},
        }
        redacted_event = before_send(event, None, self.sentry_config)
        self.assertEqual(redacted_event["logentry"]["message"], "test message")
        self.assertEqual(redacted_event["exception"], {"values": [{"value": "exception string"}]})
        self.assertEqual(redacted_event["extra"]["extra"]["kit_id"], "test-kit-id")

    def test_before_send__sensitive_data_present__data_redacted(self):
        """
        Test the before_send function when sensitive data is present to ensure that the event is redacted
        """
        event = {
            "logentry": {"message": "test message with SENSITIVE data"},
            "exception": {"values": [{"value": json.dumps({"test": "some string", "phone": "123-456-7890"})}]},
            "extra": {"extra": {"kit_id": "test-kit-id"}},
        }
        redacted_event = before_send(event, None, self.sentry_config)
        self.assertEqual(redacted_event["logentry"]["message"], "REDACTED SENSITIVE ERROR | test-kit-id")
        self.assertEqual(
            redacted_event["exception"]["values"][0]["value"],
            json.dumps({"test": "some string", "phone": SentryConstants.REDACTION_STRING}),
        )
        self.assertEqual(redacted_event["extra"]["extra"]["kit_id"], "test-kit-id")

    def test_initialize_sentry_default_params(self):
        """
        Test the initialize_sentry function with default parameters.
        """
        with patch("ash_utils.helpers.sentry.sentry_sdk.init") as mock_init:
            test_sentry_dsn = "https://test-dsn.com"
            test_release = "0.2.0"
            test_environment = "staging"

            initialize_sentry(
                sentry_dsn=test_sentry_dsn,
                release=test_release,
                environment=test_environment,
            )

            mock_init.assert_called_once()
            mock_init.assert_called_once_with(
                dsn=test_sentry_dsn,
                traces_sample_rate=0.1,
                integrations=mock.ANY,
                release=test_release,
                environment=test_environment,
                include_local_variables=False,
                send_default_pii=False,
                event_scrubber=mock.ANY,
                before_send=mock.ANY,
            )
            self.assertEqual(mock_init.call_args[1]["traces_sample_rate"], 0.1)
            default_ints = mock_init.call_args[1]["integrations"]
            self.assertEqual(len(default_ints), 1)
            self.assertIsInstance(default_ints[0], LoguruIntegration)

    def test_intialize_custom_traces_sample_rate(self):
        """
        Test the initialize_sentry function with a user passed traces_sample_rate.
        """
        with patch("ash_utils.helpers.sentry.sentry_sdk.init") as mock_init:
            test_sentry_dsn = "https://test-dsn.com"
            test_release = "0.2.0"
            test_environment = "staging"
            test_traces_sample_rate = 0.5

            initialize_sentry(
                sentry_dsn=test_sentry_dsn,
                release=test_release,
                environment=test_environment,
                traces_sample_rate=test_traces_sample_rate,
            )

            mock_init.assert_called_once()
            mock_init.assert_called_once_with(
                dsn=test_sentry_dsn,
                traces_sample_rate=test_traces_sample_rate,
                integrations=mock.ANY,
                release=test_release,
                environment=test_environment,
                include_local_variables=False,
                send_default_pii=False,
                event_scrubber=mock.ANY,
                before_send=mock.ANY,
            )
            self.assertNotEqual(mock_init.call_args[1]["traces_sample_rate"], 0.1)

    def test_initialize_sentry_with_additional_integrations(self):
        """
        Test the initialize_sentry function with additional integrations.
        """
        with patch("ash_utils.helpers.sentry.sentry_sdk.init") as mock_init:
            test_sentry_dsn = "https://test-dsn.com"
            test_release = "0.2.0"
            test_environment = "staging"
            mock_sqlalchemy_integration = mock.MagicMock(name="SqlalchemyIntegration")
            mock_loguru_integration = mock.MagicMock(name="LoguruIntegration")
            test_additional_integrations = [mock_sqlalchemy_integration, mock_loguru_integration]

            initialize_sentry(
                sentry_dsn=test_sentry_dsn,
                release=test_release,
                environment=test_environment,
                additional_integrations=test_additional_integrations,
            )

            mock_init.assert_called_once()
            self.assertIn(test_additional_integrations[0], mock_init.call_args[1]["integrations"])
            actual_integrations = mock_init.call_args[1]["integrations"]
            self.assertEqual(len(actual_integrations), 3)
            expected_types = {LoguruIntegration}
            actual_types = {type(i) for i in actual_integrations}
            self.assertTrue(
                expected_types.issubset(actual_types),
                f"Missing expected integrations. Found only: {actual_types}",
            )
