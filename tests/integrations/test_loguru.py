import re
from io import StringIO
from types import SimpleNamespace
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from ash_utils.integrations import PhiPiiLogRedactor
from loguru import logger
from loguru._recattrs import RecordException
from pydantic import BaseModel


class PhiPiiLogRedactorTestCase(TestCase):
    def setUp(self) -> None:
        logger.remove()
        logger.configure(patcher=PhiPiiLogRedactor())
        self.output = StringIO()
        logger.add(self.output, format="{message} | {extra}")

    def tearDown(self) -> None:
        logger.remove()

    def test_loguru_patcher_redacts_message_and_extra(self) -> None:
        logger.bind(
            patient_email="jane.doe@example.com",
            result_url="https://example.com/results/document.pdf?signature=secret",
            shipping_address={"address1": "100 Main St", "city": "New York"},
            results={"result_value": "positive", "reference_range": "negative"},
            api_key="secret-api-key",
            kit_id="KIT123",
            phone="555-123-4567",
        ).info(
            "Email john.doe@example.com url https://storage.example.com/result.pdf token=secret-token "
            "LabResultRow(id=1, value='positive')"
        )

        output = self.output.getvalue()

        self.assertIn("joh...@example.com", output)
        self.assertIn("jan...@example.com", output)
        self.assertIn("KIT123", output)
        self.assertIn("555-123-4567", output)
        self.assertIn("reference_range", output)

        self.assertNotIn("john.doe@example.com", output)
        self.assertNotIn("jane.doe@example.com", output)
        self.assertNotIn("https://storage.example.com", output)
        self.assertNotIn("https://example.com", output)
        self.assertNotIn("secret-token", output)
        self.assertNotIn("secret-api-key", output)
        self.assertNotIn("100 Main St", output)
        self.assertNotIn("positive", output)
        self.assertNotIn("LabResultRow", output)

    def test_loguru_patcher_redacts_exception_value(self) -> None:
        logger.remove()
        logger.configure(patcher=PhiPiiLogRedactor())
        logger.add(self.output, format="{message}\n{exception}", backtrace=False, diagnose=False)

        try:
            self._raise_sensitive_error()
        except ValueError:
            logger.exception("Failed while handling kit KIT123")

        output = self.output.getvalue()

        self.assertIn("Failed while handling kit KIT123", output)
        self.assertIn("joh...@example.com", output)
        self.assertNotIn("john.doe@example.com", output)
        self.assertNotIn("https://example.com", output)
        self.assertNotIn("positive", output)

    def _raise_sensitive_error(self) -> None:
        message = (
            "Failed for john.doe@example.com at https://example.com/result.pdf "
            "with {'results': {'result_value': 'positive'}}"
        )
        raise ValueError(message)


class PhiPiiLogRedactorBranchesTestCase(TestCase):
    """Unit coverage for branches not exercised by end-to-end Loguru tests."""

    def setUp(self) -> None:
        self.redactor = PhiPiiLogRedactor()

    def test_redact_record_handles_inner_failure(self) -> None:
        record: dict[str, Any] = {"message": "ok", "extra": {}}
        with patch.object(self.redactor, "_redact_string", side_effect=RuntimeError("boom")):
            self.redactor.redact_record(record)
        self.assertEqual(record["message"], PhiPiiLogRedactor.REDACTION_ERROR)
        self.assertEqual(record["extra"], {"redaction_error": PhiPiiLogRedactor.REDACTION_ERROR})

    def test_max_redaction_depth_returns_placeholder(self) -> None:
        nested: object = "leaf"
        for _ in range(9):
            nested = {"n": nested}
        record: dict[str, Any] = {"message": "", "extra": nested}
        self.redactor.redact_record(record)
        inner: dict[str, object] = {"n": PhiPiiLogRedactor.REDACTED}
        for _ in range(8):
            inner = {"n": inner}
        self.assertEqual(record["extra"], inner)

    def test_primitive_extra_value_passes_through_object_path(self) -> None:
        record: dict[str, Any] = {"message": "", "extra": {"count": 42}}
        self.redactor.redact_record(record)
        self.assertEqual(record["extra"], {"count": 42})

    def test_normalize_key_all_caps_preserves_sensitive_tokens(self) -> None:
        self.assertEqual(PhiPiiLogRedactor._normalize_key("PASSWORD"), "password")
        self.assertEqual(PhiPiiLogRedactor._normalize_key("API_KEY"), "api_key")
        self.assertEqual(PhiPiiLogRedactor._normalize_key("ACCESS_TOKEN"), "access_token")

    def test_all_caps_extra_keys_redacted_like_mixed_case(self) -> None:
        record: dict[str, Any] = {
            "message": "",
            "extra": {"PASSWORD": "secret-pass", "API_KEY": "sk-live", "KIT_ID": "KIT123"},
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        self.assertEqual(extra["PASSWORD"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(extra["API_KEY"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(extra["KIT_ID"], "KIT123")

    def test_email_key_non_string_values_are_redacted_recursively(self) -> None:
        record: dict[str, Any] = {
            "message": "",
            "extra": {
                "patient_emails": ["alice@example.com", "charlie@example.org"],
                "contact_email": {"primary": "nested@example.com"},
            },
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        emails = extra["patient_emails"]
        assert isinstance(emails, list)
        self.assertEqual(len(emails), 2)
        self.assertNotIn("alice@example.com", str(extra))
        self.assertNotIn("charlie@example.org", str(extra))
        self.assertNotIn("nested@example.com", str(extra))

    def test_list_tuple_set_extra_redacted(self) -> None:
        record: dict[str, Any] = {
            "message": "",
            "extra": {
                "nums": [1, {"password": "x"}],
                "pair": ("a", {"token": "y"}),
                "tags": {1, 2},
            },
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        self.assertEqual(
            extra["nums"],
            [1, {"password": PhiPiiLogRedactor.REDACTED}],
        )
        self.assertEqual(
            extra["pair"],
            ("a", {"token": PhiPiiLogRedactor.REDACTED}),
        )
        # Sets are redacted via list comprehension; order follows iteration order.
        self.assertEqual(extra["tags"], [1, 2])

    def test_exception_instance_extra_is_stringified_and_redacted(self) -> None:
        record: dict[str, Any] = {"message": "", "extra": {"err": ValueError("fail token=abc")}}
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        err_str = extra["err"]
        assert isinstance(err_str, str)
        self.assertNotIn("abc", err_str)

    def test_pydantic_model_extra_redacted_via_model_dump(self) -> None:
        class User(BaseModel):
            password: str = "secret123"

        record: dict[str, Any] = {"message": "", "extra": {"user": User()}}
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        dumped = extra["user"]
        assert isinstance(dumped, dict)
        self.assertEqual(dumped["password"], PhiPiiLogRedactor.REDACTED)

    def test_model_dump_failure_falls_back_to_string_redaction(self) -> None:
        class BrokenModel(BaseModel):
            password: str = "secret"

            def model_dump(self, **kwargs: Any) -> dict[str, Any]:
                raise RuntimeError("no dump")

        record: dict[str, Any] = {"message": "", "extra": {"m": BrokenModel()}}
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        out = extra["m"]
        assert isinstance(out, str)
        self.assertNotIn("secret", out)

    def test_redact_balanced_calls_when_open_paren_not_found(self) -> None:
        # Custom head pattern matches a substring with no "(" after match.start()
        out = self.redactor._redact_balanced_calls("pre LabResult post", re.compile(r"LabResult"))
        self.assertEqual(out, "pre LabResult post")

    def test_redact_balanced_calls_nested_skips_inner_match(self) -> None:
        nested = "LabResult(inner=LabResult(x))"
        out = self.redactor._redact_balanced_calls(
            nested,
            self.redactor.result_object_head_pattern,
        )
        self.assertEqual(out, PhiPiiLogRedactor.REDACTED)
        self.assertEqual(out.count(PhiPiiLogRedactor.REDACTED), 1)

    def test_find_balanced_call_end_unbalanced_returns_length(self) -> None:
        end = PhiPiiLogRedactor._find_balanced_call_end("(abc", 0)
        self.assertEqual(end, len("(abc"))

    def test_keyed_plain_field_skipped_when_not_sensitive(self) -> None:
        msg = self.redactor._redact_string("safe_label=visible token=secret")
        self.assertIn("visible", msg)
        self.assertNotIn("secret", msg)

    def test_find_value_end_when_value_start_is_eof(self) -> None:
        token = "plain="
        self.assertEqual(self.redactor._find_value_end(token, len(token)), len(token))

    def test_find_value_end_quoted_branch(self) -> None:
        self.assertEqual(self.redactor._find_value_end('"hi",x', 0), 4)

    def test_find_balanced_value_end_nested_opens_push_stack(self) -> None:
        self.assertEqual(self.redactor._find_balanced_value_end("{a:{b:1}}", 0), 9)

    def test_find_quoted_value_end_unclosed_returns_length(self) -> None:
        raw = '"unclosed'
        self.assertEqual(PhiPiiLogRedactor._find_quoted_value_end(raw, 0), len(raw))

    def test_keyed_values_bracket_quote_and_scalar(self) -> None:
        msg = self.redactor._redact_string('password={nested: {inner: 1}} token="x" api_key=abc, tail')
        self.assertNotIn("nested", msg)
        self.assertNotIn("abc", msg)
        self.assertIn("tail", msg)

    def test_keyed_value_nested_brackets_push_stack(self) -> None:
        msg = self.redactor._redact_string("password={a:{b:1}}")
        self.assertNotIn("b:1", msg)

    def test_keyed_quoted_value_unclosed_consumes_to_eof(self) -> None:
        msg = self.redactor._redact_string('password="unclosed')
        self.assertNotIn("unclosed", msg)

    def test_redact_exception_ignores_non_record_exception_wrapper(self) -> None:
        record: dict[str, Any] = {"exception": SimpleNamespace(value=ValueError("x"))}
        self.redactor._redact_exception(record)
        self.assertIsInstance(record["exception"], SimpleNamespace)

    def test_redact_exception_noop_when_redaction_unchanged(self) -> None:
        exc = ValueError("plain")
        record: dict[str, Any] = {"exception": RecordException(type(exc), exc, None)}
        self.redactor._redact_exception(record)
        self.assertIs(record["exception"].value, exc)

    def test_build_redacted_exception_runtime_error_when_constructor_rejects_message(self) -> None:
        class FixedArgsExc(Exception):
            def __init__(self) -> None:
                super().__init__("fixed")

        out = PhiPiiLogRedactor._build_redacted_exception(FixedArgsExc(), "redacted-msg")
        self.assertIsInstance(out, RuntimeError)
        self.assertEqual(str(out), "redacted-msg")

    def test_keyed_result_value_field_redacts_via_specific_field_rule(self) -> None:
        msg = self.redactor._redact_string("result_value=positive")
        self.assertNotIn("positive", msg)
