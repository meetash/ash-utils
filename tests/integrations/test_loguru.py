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
            "upstream https://svc:topsecret@internal.example.net/api "
            "Authorization: Bearer opaque-bearer-token "
            "LabResultRow(id=1, value='positive')"
        )

        output = self.output.getvalue()

        self.assertIn("joh...@example.com", output)
        self.assertIn("jan...@example.com", output)
        self.assertIn("KIT123", output)
        self.assertIn("https://storage.example.com/result.pdf", output)
        self.assertIn("https://example.com/results/document.pdf", output)
        self.assertIn("reference_range", output)

        self.assertNotIn("john.doe@example.com", output)
        self.assertNotIn("jane.doe@example.com", output)
        self.assertNotIn("555-123-4567", output)
        self.assertNotIn("secret-token", output)
        self.assertNotIn("secret-api-key", output)
        self.assertNotIn("topsecret", output)
        self.assertNotIn("svc:", output)
        self.assertNotIn("opaque-bearer-token", output)
        # Bearer is normalized by secret pass after bearer replacement; token must not leak.
        self.assertIn("Authorization=[REDACTED]", output)
        self.assertIn("https://[REDACTED]@internal.example.net/api", output)
        self.assertNotIn("signature=secret", output)
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
        self.assertIn("https://example.com/result.pdf", output)
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
        sensitive_exception = ValueError("john.doe@example.com token=secret")
        record: dict[str, Any] = {
            "message": "ok",
            "extra": {},
            "exception": RecordException(type(sensitive_exception), sensitive_exception, None),
        }
        with patch.object(self.redactor, "_redact_string", side_effect=RuntimeError("boom")):
            self.redactor.redact_record(record)
        self.assertEqual(record["message"], PhiPiiLogRedactor.REDACTION_ERROR)
        self.assertEqual(record["extra"], {"redaction_error": PhiPiiLogRedactor.REDACTION_ERROR})
        redacted_exception = record["exception"]
        self.assertIsInstance(redacted_exception, RecordException)
        self.assertIs(redacted_exception.type, RuntimeError)
        self.assertEqual(str(redacted_exception.value), PhiPiiLogRedactor.REDACTION_ERROR)

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
        self.assertEqual(self.redactor._normalize_key("PASSWORD"), "password")
        self.assertEqual(self.redactor._normalize_key("API_KEY"), "api_key")
        self.assertEqual(self.redactor._normalize_key("ACCESS_TOKEN"), "access_token")

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

    def test_pydantic_model_in_result_payload_keeps_payload_context(self) -> None:
        class ResultItem(BaseModel):
            result_value: str
            reference_range: str

        record: dict[str, Any] = {
            "message": "",
            "extra": {
                "results": {
                    "items": [ResultItem(result_value="positive", reference_range="negative")],
                },
            },
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        results = extra["results"]
        assert isinstance(results, dict)
        items = results["items"]
        assert isinstance(items, list)
        first_item = items[0]
        assert isinstance(first_item, dict)
        self.assertEqual(first_item["result_value"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(first_item["reference_range"], PhiPiiLogRedactor.REDACTED)

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

    def test_secret_pattern_skips_already_redacted_placeholder(self) -> None:
        """URL/bearer runs before secret; value [REDACTED] must not match partially (stray ])."""
        url_then_secret = self.redactor._redact_string("token=https://example.com/path")
        self.assertNotIn("[REDACTED]]", url_then_secret)
        self.assertIn("token=[REDACTED]", url_then_secret)

        bearer_then_secret = self.redactor._redact_string("Authorization: Bearer sometoken")
        self.assertNotIn("[REDACTED]]", bearer_then_secret)

    def test_find_value_end_when_value_start_is_eof(self) -> None:
        token = "plain="
        self.assertEqual(self.redactor._find_value_end(token, len(token)), len(token))

    def test_find_value_end_quoted_branch(self) -> None:
        self.assertEqual(self.redactor._find_value_end('"hi",x', 0), 4)

    def test_find_balanced_value_end_nested_opens_push_stack(self) -> None:
        self.assertEqual(self.redactor._find_balanced_value_end("{a:{b:1}}", 0), 9)

    def test_find_quoted_value_end_unclosed_returns_length(self) -> None:
        raw = '"unclosed'
        self.assertEqual(self.redactor._find_quoted_value_end(raw, 0), len(raw))

    def test_find_quoted_value_end_treats_even_backslashes_as_closing_quote(self) -> None:
        raw = r'"value\\", token=secret'
        self.assertEqual(self.redactor._find_quoted_value_end(raw, 0), raw.index(","))

    def test_keyed_values_bracket_quote_and_scalar(self) -> None:
        msg = self.redactor._redact_string('password={nested: {inner: 1}} token="x" api_key=abc, tail')
        self.assertNotIn("nested", msg)
        self.assertNotIn("abc", msg)
        self.assertIn("tail", msg)

    def test_email_keyed_value_redacts_non_email_identifier(self) -> None:
        msg = self.redactor._redact_string("patient_email=patient-123@example.com, safe_label=visible")
        self.assertIn(f"patient_email={PhiPiiLogRedactor.REDACTED}", msg)
        self.assertIn("safe_label=visible", msg)
        self.assertNotIn("patient-123@example.com", msg)

    def test_keyed_value_nested_brackets_push_stack(self) -> None:
        msg = self.redactor._redact_string("password={a:{b:1}}")
        self.assertNotIn("b:1", msg)

    def test_balanced_value_end_does_not_overconsume_after_double_escaped_quote(self) -> None:
        raw = r'{a:"value\\", b:1} token=secret'
        self.assertEqual(self.redactor._find_balanced_value_end(raw, 0), raw.index("}") + 1)

    def test_keyed_quoted_value_unclosed_consumes_to_eof(self) -> None:
        msg = self.redactor._redact_string('password="unclosed')
        self.assertNotIn("unclosed", msg)

    def test_url_keyed_quoted_value_unclosed_redacts_full_inner_value(self) -> None:
        msg = self.redactor._redact_string("url='https://user:secretd@api.example.com/path")
        self.assertIn("url='https://[REDACTED]@api.example.com/path", msg)
        self.assertNotIn("secretd", msg)

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

    def test_redact_email_short_local_part_is_redacted(self) -> None:
        """Local parts of 3 or fewer characters must not pass through unchanged."""
        self.assertEqual(PhiPiiLogRedactor._redact_email("ab@example.com"), "...@example.com")
        self.assertEqual(PhiPiiLogRedactor._redact_email("sue@test.com"), "...@test.com")
        self.assertEqual(PhiPiiLogRedactor._redact_email("jd@clinic.org"), "...@clinic.org")

    def test_redact_email_long_local_part_keeps_prefix(self) -> None:
        self.assertEqual(
            PhiPiiLogRedactor._redact_email("john.doe@example.com"),
            "joh...@example.com",
        )

    def test_url_userinfo_redacted_host_and_path_preserved(self) -> None:
        msg = self.redactor._redact_string("GET https://user:secret@api.example.com/v1/health failed")
        self.assertIn("https://[REDACTED]@api.example.com/v1/health", msg)
        self.assertNotIn("user:secret", msg)

    def test_mixed_separator_sensitive_keys_redact_and_exceptions_pass_through(self) -> None:
        record: dict[str, Any] = {
            "message": "",
            "extra": {
                "session_id": "sess-abc",
                "x_session_id": "hdr-xyz",
                "X-Session-ID": "hdr-hyphenated",
                "Session-Id": "sess-hyphenated",
                "requestHTTPID": "request-http-id",
                "token_count": 12,
                "Token-Count": 13,
                "password_policy": "min-8",
                "bypass_flag": False,
                "auth_failed_msg": "bad creds",
                "Session-Token": "secret-session-token",
                "Token-Value": "secret-token-value",
                "X-API-Key": "secret-api-key",
            },
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        self.assertEqual(extra["session_id"], "sess-abc")
        self.assertEqual(extra["x_session_id"], "hdr-xyz")
        self.assertEqual(extra["X-Session-ID"], "hdr-hyphenated")
        self.assertEqual(extra["Session-Id"], "sess-hyphenated")
        self.assertEqual(extra["requestHTTPID"], "request-http-id")
        self.assertEqual(extra["token_count"], 12)
        self.assertEqual(extra["Token-Count"], 13)
        self.assertEqual(extra["password_policy"], "min-8")
        self.assertFalse(extra["bypass_flag"])
        self.assertEqual(extra["auth_failed_msg"], "bad creds")
        self.assertEqual(extra["Session-Token"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(extra["Token-Value"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(extra["X-API-Key"], PhiPiiLogRedactor.REDACTED)

    def test_sensitive_key_segment_exceptions_and_lookalikes_pass_through(self) -> None:
        """Exception segment shapes stay visible; compounds and ALL_CAPS keys must not trip substring rules."""
        record: dict[str, Any] = {
            "message": "",
            "extra": {
                "session_id": "sess-core",
                "x_session_id": "hdr-core",
                "token_count": 7,
                "password_policy": "min-12",
                "bypass_flag": True,
                "auth_failed_msg": "invalid grant",
                "SESSION_ID": "env-style-session-id",
                "REQUEST_SESSION_ID": "all-caps-normalizes",
                "upstream_session_id": "trace-99",
                "oauth_token_count": 2,
                "legacy_auth_failed_code": 401,
            },
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        self.assertEqual(extra["session_id"], "sess-core")
        self.assertEqual(extra["x_session_id"], "hdr-core")
        self.assertEqual(extra["token_count"], 7)
        self.assertEqual(extra["password_policy"], "min-12")
        self.assertTrue(extra["bypass_flag"])
        self.assertEqual(extra["auth_failed_msg"], "invalid grant")
        self.assertEqual(extra["SESSION_ID"], "env-style-session-id")
        self.assertEqual(extra["REQUEST_SESSION_ID"], "all-caps-normalizes")
        self.assertEqual(extra["upstream_session_id"], "trace-99")
        self.assertEqual(extra["oauth_token_count"], 2)
        self.assertEqual(extra["legacy_auth_failed_code"], 401)

    def test_mfa_phone_key_redacted(self) -> None:
        record: dict[str, Any] = {
            "message": "",
            "extra": {"mfa_phone_number": "555-0100", "phone": "555-0200"},
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        self.assertEqual(extra["mfa_phone_number"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(extra["phone"], PhiPiiLogRedactor.REDACTED)

    def test_non_identity_email_named_extra_passes_through(self) -> None:
        """Email-adjacent keys that are not identity email/login fields stay visible (bools, strings, ids)."""
        record: dict[str, Any] = {
            "message": "",
            "extra": {
                "email_verified": True,
                "has_email": False,
                "email_verified_status": "verified",
                "email_template": "welcome_001",
            },
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        self.assertTrue(extra["email_verified"])
        self.assertFalse(extra["has_email"])
        self.assertEqual(extra["email_verified_status"], "verified")
        self.assertEqual(extra["email_template"], "welcome_001")

    def test_bearer_token_redacted_in_string(self) -> None:
        msg = self.redactor._redact_string("Authorization: Bearer aa.bb-cc/dd+ee suffix")
        self.assertNotIn("aa.bb-cc", msg)
        self.assertIn("suffix", msg)
        self.assertIn("Authorization=[REDACTED]", msg)

    def test_bearer_pattern_consumes_token_before_secret_pass(self) -> None:
        """Bearer sub runs first; odd '=' padding on tokens can leave a trailing fragment."""
        after_bearer = self.redactor.bearer_token_pattern.sub(
            repl=f"Bearer {PhiPiiLogRedactor.REDACTED}",
            string="Authorization: Bearer aa.bb-cc/dd+ee=_",
        )
        self.assertEqual(after_bearer, f"Authorization: Bearer {PhiPiiLogRedactor.REDACTED}_")

    def test_top_level_address_key_pattern_variants_redacted(self) -> None:
        record: dict[str, Any] = {
            "message": "",
            "extra": {
                "address": "1 Secret Rd",
                "address_line_1": "2 Secret Rd",
                "line_1": "3 Secret Rd",
                "line2": "4 Secret Rd",
                "pcp_address_1": "5 Secret Rd",
                "street_address": "6 Secret Rd",
                "billing_address2": "7 Secret Rd",
            },
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        for key in (
            "address",
            "address_line_1",
            "line_1",
            "line2",
            "pcp_address_1",
            "street_address",
            "billing_address2",
        ):
            self.assertEqual(extra[key], PhiPiiLogRedactor.REDACTED, msg=key)

    def test_nested_pcp_container_redacts_address_child_keys(self) -> None:
        record: dict[str, Any] = {
            "message": "",
            "extra": {"pcp": {"street": "Hidden St", "city": "Chicago"}},
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        payload = extra["pcp"]
        assert isinstance(payload, dict)
        self.assertEqual(payload["street"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(payload["city"], "Chicago")

    def test_alternate_lab_and_order_result_keys_redacted_in_payload(self) -> None:
        record: dict[str, Any] = {
            "message": "",
            "extra": {
                "lab_results": {
                    "loinc": "1234-5",
                    "units": "mg/dL",
                    "interpretation": "abnormal",
                },
                "order_result": {
                    "collection_date": "2024-01-01",
                    "reported_date": "2024-01-02",
                    "assays": ["X"],
                },
            },
        }
        self.redactor.redact_record(record)
        extra = record["extra"]
        assert isinstance(extra, dict)
        lab = extra["lab_results"]
        assert isinstance(lab, dict)
        self.assertEqual(lab["loinc"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(lab["units"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(lab["interpretation"], PhiPiiLogRedactor.REDACTED)
        order = extra["order_result"]
        assert isinstance(order, dict)
        self.assertEqual(order["collection_date"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(order["reported_date"], PhiPiiLogRedactor.REDACTED)
        self.assertEqual(order["assays"], PhiPiiLogRedactor.REDACTED)

    def test_message_keyed_secret_and_url_redacted(self) -> None:
        """Exercises keyed_value_pattern on free-text alongside secret/bearer ordering."""
        msg = self.redactor._redact_string(
            'ok api_key=nope url="https://keep.example/path" trailing',
        )
        self.assertIn("trailing", msg)
        self.assertIn("ok", msg)
        self.assertNotIn("nope", msg)
        self.assertIn("keep.example", msg)
