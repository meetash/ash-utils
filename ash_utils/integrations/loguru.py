import re
from collections.abc import Mapping, MutableMapping
from typing import Any, ClassVar

from loguru._recattrs import RecordException


class PhiPiiLogRedactor:
    """Loguru patcher that redacts sensitive values before sinks receive records."""

    REDACTED = "[REDACTED]"
    REDACTION_ERROR = "[REDACTION_ERROR]"
    REDACTION_DEPTH = 8
    EMAIL_LOCAL_PREFIX_VISIBLE_LEN = 3
    ACRONYM_PREFIX_MIN_LENGTH = 2

    email_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        flags=re.IGNORECASE,
    )
    url_userinfo_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=r"(https?://)([^/?#]+)@([^/?#]+)",
        flags=re.IGNORECASE,
    )
    secret_value_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=(
            r"\b(?P<secret_key>auth|authorization|api[_-]?key|token|secret|password|passwd|credential|cookie|"
            r"signature|signedheaders)\b(?P<secret_separator>\s*[:=]\s*)"
            r"(?!(?:bearer\s+)?" + re.escape(REDACTED) + r"(?:$|[\s,;}\]]))"
            r"(?P<secret_bearer>bearer\s+)?[^\s,;}\]]+"
        ),
        flags=re.IGNORECASE,
    )
    bearer_token_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=r"\bbearer\s+[a-z0-9._~+/-]+=*",
        flags=re.IGNORECASE,
    )
    test_result_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=(
            r"^(?P<container>(?:desired|expected|target|lab|kit|order|panel|specimen)_(?:result|results)|results?|"
            r"result_(?:(?:item|line|record)s?|entry|entries|payload|data))$"
            r"|^(?P<payload>result_code(?:_id)?s?|result_values?|observed_values?|"
            r"(?:numeric|qualitative|lab|panel|order|kit)_results?|interpretations?|(?:reference|normal)_ranges?|"
            r"abnormal_flags?|units|(?:collection|received|reported)_dates?|"
            r"date_reported|specimens?|panels?|assays?|analytes?|loinc|test_names?)$"
        ),
        flags=re.IGNORECASE,
    )
    result_object_head_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=r"\b[a-z_]\w{0,2048}Results?\w{0,2048}\s*\(",
        flags=re.IGNORECASE,
    )
    keyed_value_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=(
            r"(?:"
            r"(?P<quote>['\"])(?P<quoted_key>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)\s*:"
            r"|(?P<plain_key>[A-Za-z_][A-Za-z0-9_]*)\s*="
            r")\s*"
        ),
        flags=re.IGNORECASE,
    )
    # Underscore-delimited segments only (normalized keys are snake_case). Substrings like `pass`
    # inside `bypass` must not match; exceptions such as session_id use negative lookahead on segments.
    sensitive_key_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=(
            r"(?:"
            r"(?:^|_)authorization(?:$|_)"
            r"|(?:^|_)api_?key(?:$|_)"
            r"|(?:^|_)bearer(?:$|_)"
            r"|(?:^|_)cookies?(?:$|_)"
            r"|(?:^|_)credentials?(?:$|_)"
            r"|(?:^|_)private_key(?:$|_)"
            r"|(?:^|_)secrets?(?:$|_)"
            r"|(?:^|_)pass(?:word|wd)?(?!_policy(?:$|_))(?:$|_)"
            r"|(?:^|_)sessions?(?!_id(?:$|_))(?:$|_)"
            r"|(?:^|_)tokens?(?!_count(?:$|_))(?:$|_)"
            r"|(?:^|_)auth(?!_failed)(?:$|_)"
            r")"
        ),
        flags=re.IGNORECASE,
    )
    email_key_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=(
            r"^(?:patient|client|shipping|target|customer|partner|impersonated|contact)?"
            r"(?:_?user)?_?(?:e?mails?|logins?)(?:_?address)?$"
        ),
        flags=re.IGNORECASE,
    )
    phone_key_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=r"^(?:mfa_)?phone(?:_number)?$",
        flags=re.IGNORECASE,
    )
    url_key_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=r"^(?:url|urls|.*_url|.*_urls)$",
        flags=re.IGNORECASE,
    )
    address_key_patterns: ClassVar[tuple[re.Pattern[str], ...]] = (
        re.compile(pattern=r"^address(?:_line)?_?[12]?$", flags=re.IGNORECASE),
        re.compile(pattern=r"^line_?[12]$", flags=re.IGNORECASE),
        re.compile(pattern=r"^pcp_address_?[12]?$", flags=re.IGNORECASE),
        re.compile(pattern=r"^street(?:_address)?$", flags=re.IGNORECASE),
        re.compile(pattern=r"^.*_address[12]$", flags=re.IGNORECASE),
    )
    address_container_key_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=r"^(?:address|patient_address|shipping(?:_address)?|pcp)$",
        flags=re.IGNORECASE,
    )
    address_child_key_pattern: ClassVar[re.Pattern[str]] = re.compile(
        pattern=r"^(?:address_?[12]|line_?[12]|street(?:_address)?)$",
        flags=re.IGNORECASE,
    )

    def __call__(self, record: MutableMapping[str, Any]) -> None:
        self.redact_record(record=record)

    def redact_record(self, record: MutableMapping[str, Any]) -> None:
        try:
            record["message"] = self._redact_string(value=str(object=record.get("message", "")))
            record["extra"] = self._redact_value(value=record.get("extra", {}), key="", depth=0)
            self._redact_exception(record=record)
        except Exception:
            record["message"] = self.REDACTION_ERROR
            record["extra"] = {"redaction_error": self.REDACTION_ERROR}
            record["exception"] = RecordException(
                type=RuntimeError,
                value=RuntimeError(self.REDACTION_ERROR),
                traceback=None,
            )

    def _redact_value(self, value: object, *, key: str, depth: int, in_result_payload: bool = False) -> object:
        if depth > self.REDACTION_DEPTH:
            return self.REDACTED

        normalized_key = self._normalize_key(key=key)
        should_return_direct_value, direct_value = self._get_direct_redacted_value(
            normalized_key=normalized_key,
            value=value,
        )
        if should_return_direct_value:
            return direct_value
        if self._should_redact_key(normalized_key=normalized_key, in_result_payload=in_result_payload):
            return self.REDACTED

        if isinstance(value, str):
            return self.REDACTED if in_result_payload else self._redact_string(value=value)

        if isinstance(value, Mapping):
            return self._redact_mapping(
                value=value,
                depth=depth,
                parent_key=normalized_key,
                in_result_payload=in_result_payload,
            )

        return self._redact_collection_or_object(
            value=value,
            key=key,
            depth=depth,
            in_result_payload=in_result_payload,
        )

    def _redact_collection_or_object(self, value: object, *, key: str, depth: int, in_result_payload: bool) -> object:
        if isinstance(value, (list, set)):
            redacted_value = self._redact_items(
                values=value,
                key=key,
                depth=depth,
                in_result_payload=in_result_payload,
            )
        elif isinstance(value, tuple):
            redacted_value = tuple(
                self._redact_items(
                    values=value,
                    key=key,
                    depth=depth,
                    in_result_payload=in_result_payload,
                ),
            )
        else:
            redacted_value = self._redact_object(
                value=value,
                key=key,
                depth=depth,
                in_result_payload=in_result_payload,
            )

        return redacted_value

    def _redact_items(
        self,
        values: list[object] | tuple[object, ...] | set[object],
        *,
        key: str,
        depth: int,
        in_result_payload: bool,
    ) -> list[object]:
        return [
            self._redact_value(
                value=item,
                key=key,
                depth=depth + 1,
                in_result_payload=in_result_payload,
            )
            for item in values
        ]

    def _redact_object(self, value: object, *, key: str, depth: int, in_result_payload: bool) -> object:
        if isinstance(value, Exception):
            return self._redact_string(value=str(object=value))

        model_dump = getattr(value, "model_dump", None)
        if not callable(model_dump):
            return value

        try:
            return self._redact_value(
                value=model_dump(mode="python"),
                key=key,
                depth=depth + 1,
                in_result_payload=in_result_payload,
            )
        except Exception:
            return self._redact_string(value=str(object=value))

    def _redact_mapping(
        self, value: Mapping[object, object], *, depth: int, parent_key: str, in_result_payload: bool
    ) -> dict[object, object]:
        child_keys = {self._normalize_key(key=item_key) for item_key in value}
        result_payload = (
            in_result_payload
            or self._is_test_result_container_key(normalized_key=parent_key)
            or self._looks_like_result_payload(keys=child_keys)
        )
        address_payload = self._is_address_container_key(normalized_key=parent_key)

        redacted: dict[object, object] = {}
        for item_key, item_value in value.items():
            normalized_item_key = self._normalize_key(key=item_key)
            should_redact_address_child = address_payload and self._is_address_child_key(
                normalized_key=normalized_item_key,
            )
            redacted[item_key] = (
                self.REDACTED
                if should_redact_address_child
                else self._redact_value(
                    value=item_value,
                    key=str(object=item_key),
                    depth=depth + 1,
                    in_result_payload=result_payload,
                )
            )
        return redacted

    def _redact_string(self, value: str) -> str:
        redacted = self.email_pattern.sub(
            repl=lambda match: self._redact_email(email=match.group(0)),
            string=value,
        )
        redacted = self._redact_url_userinfo_in_string(value=redacted)
        redacted = self.bearer_token_pattern.sub(repl=f"Bearer {self.REDACTED}", string=redacted)
        redacted = self.secret_value_pattern.sub(
            repl=lambda match: (
                f"{match.group('secret_key')}{match.group('secret_separator')}"
                f"{match.group('secret_bearer') or ''}{self.REDACTED}"
            ),
            string=redacted,
        )
        return self._redact_keyed_values_in_string(value=self._redact_test_result_objects(value=redacted))

    def _redact_url_userinfo_in_string(self, value: str) -> str:
        return self.url_userinfo_pattern.sub(
            repl=lambda match: f"{match.group(1)}{self.REDACTED}@{match.group(3)}",
            string=value,
        )

    def _redact_url_keyed_value_fragment(self, value: str, value_start: int, value_end: int) -> str:
        raw = value[value_start:value_end]
        stripped = raw.strip()
        if not stripped:
            return self.REDACTED
        leading = raw[: len(raw) - len(raw.lstrip())]
        trailing = raw[len(raw.rstrip()) :]
        body = stripped
        first = body[0]
        if first in "'\"":
            close = self._find_quoted_value_end(value=body, value_start=0)
            has_closing_quote = close > 1 and body[close - 1] == first
            inner_end = close - 1 if has_closing_quote else close
            inner = body[1:inner_end]
            redacted_inner = self._redact_string(value=inner)
            closing_quote = body[close - 1] if has_closing_quote else ""
            return f"{leading}{first}{redacted_inner}{closing_quote}{trailing}"
        if first in "{[":
            return self.REDACTED
        return f"{leading}{self._redact_string(value=body)}{trailing}"

    def _get_direct_redacted_value(self, normalized_key: str, value: object) -> tuple[bool, object]:
        if self._is_email_key(normalized_key=normalized_key):
            return self._get_email_direct_redacted_value(value=value)

        if self._is_phone_key(normalized_key=normalized_key):
            return True, self.REDACTED if isinstance(value, str) or value else value

        if self._is_url_key(normalized_key=normalized_key):
            return self._get_url_direct_redacted_value(value=value)

        return False, value

    def _get_email_direct_redacted_value(self, value: object) -> tuple[bool, object]:
        if not isinstance(value, str):
            return False, value
        return True, self._redact_email(email=value) if self._string_is_scalar_email(value=value) else self.REDACTED

    def _get_url_direct_redacted_value(self, value: object) -> tuple[bool, object]:
        if not isinstance(value, str):
            return False, value
        if value:
            return True, self._redact_string(value=value)
        return True, value

    def _string_is_scalar_email(self, *, value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        match = self.email_pattern.search(string=stripped)
        return match is not None and match.start() == 0 and match.end() == len(stripped)

    @staticmethod
    def _redact_email(email: str) -> str:
        split_email = email.split("@")
        local = split_email[0]
        domain = split_email[-1]
        visible = PhiPiiLogRedactor.EMAIL_LOCAL_PREFIX_VISIBLE_LEN
        # If the local part is no longer than `visible`, a prefix of that length is the full local (leak).
        if len(local) > visible:
            return f"{local[:visible]}...@{domain}"
        return f"...@{domain}"

    def _redact_test_result_objects(self, value: str) -> str:
        return self._redact_balanced_calls(value=value, head_pattern=self.result_object_head_pattern)

    def _redact_balanced_calls(self, value: str, head_pattern: re.Pattern[str]) -> str:
        parts: list[str] = []
        cursor = 0
        for match in head_pattern.finditer(string=value):
            if match.start() < cursor:
                continue
            parts.append(value[cursor : match.start()])
            open_paren = value.find("(", match.start())
            if open_paren == -1:
                parts.append(match.group(0))
                cursor = match.end()
                continue
            end = self._find_balanced_call_end(value=value, open_paren_index=open_paren)
            parts.append(self.REDACTED)
            cursor = end
        parts.append(value[cursor:])
        return "".join(parts)

    @staticmethod
    def _find_balanced_call_end(value: str, open_paren_index: int) -> int:
        depth = 0
        cursor = open_paren_index
        while cursor < len(value):
            char = value[cursor]
            if char in "'\"":
                cursor = PhiPiiLogRedactor._find_quoted_value_end(value=value, value_start=cursor)
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return cursor + 1
            cursor += 1
        return len(value)

    def _redact_keyed_values_in_string(self, value: str) -> str:
        redacted_parts: list[str] = []
        output_cursor = 0
        search_cursor = 0
        while match := self.keyed_value_pattern.search(string=value, pos=search_cursor):
            key = self._normalize_key(key=match.group("quoted_key") or match.group("plain_key"))
            if not self._should_redact_string_key(normalized_key=key):
                search_cursor = match.end()
                continue

            value_end = self._find_value_end(value=value, value_start=match.end())
            redacted_parts.append(value[output_cursor : match.end()])
            if self._is_url_key(normalized_key=key):
                redacted_parts.append(
                    self._redact_url_keyed_value_fragment(
                        value=value,
                        value_start=match.end(),
                        value_end=value_end,
                    ),
                )
            else:
                redacted_parts.append(self.REDACTED)
            output_cursor = value_end
            search_cursor = value_end

        redacted_parts.append(value[output_cursor:])
        return "".join(redacted_parts)

    def _find_value_end(self, value: str, value_start: int) -> int:
        if value_start >= len(value):
            return value_start

        first_char = value[value_start]
        if first_char in "{[(":
            return self._find_balanced_value_end(value=value, value_start=value_start)
        if first_char in "'\"":
            return self._find_quoted_value_end(value=value, value_start=value_start)

        return self._find_scalar_value_end(value=value, value_start=value_start)

    def _find_balanced_value_end(self, value: str, value_start: int) -> int:
        pairs = {"{": "}", "[": "]", "(": ")"}
        stack = [pairs[value[value_start]]]
        cursor = value_start + 1
        while cursor < len(value) and stack:
            current = value[cursor]
            if current in "'\"":
                cursor = self._find_quoted_value_end(value=value, value_start=cursor)
                continue
            if current in pairs:
                stack.append(pairs[current])
            elif current == stack[-1]:
                stack.pop()
            cursor += 1
        return cursor

    @staticmethod
    def _find_quoted_value_end(value: str, value_start: int) -> int:
        quote = value[value_start]
        cursor = value_start + 1
        while cursor < len(value):
            if value[cursor] == quote and not PhiPiiLogRedactor._is_escaped(value=value, cursor=cursor):
                return cursor + 1
            cursor += 1
        return len(value)

    @staticmethod
    def _is_escaped(value: str, cursor: int) -> bool:
        backslash_count = 0
        index = cursor - 1
        while index >= 0 and value[index] == "\\":
            backslash_count += 1
            index -= 1
        return backslash_count % 2 == 1

    @staticmethod
    def _find_scalar_value_end(value: str, value_start: int) -> int:
        cursor = value_start
        while cursor < len(value) and value[cursor] not in ",}]":
            cursor += 1
        return cursor

    def _redact_exception(self, record: MutableMapping[str, Any]) -> None:
        exception = record.get("exception")
        exception_value = getattr(exception, "value", None)
        if exception is None or exception_value is None:
            return
        if not isinstance(exception, RecordException):
            return

        redacted_message = self._redact_string(value=str(object=exception_value))
        if redacted_message == str(object=exception_value):
            return

        redacted_exception = self._build_redacted_exception(
            exception=exception_value,
            redacted_message=redacted_message,
        )
        record["exception"] = RecordException(
            type=redacted_exception.__class__,
            value=redacted_exception,
            traceback=exception.traceback,
        )

    @staticmethod
    def _build_redacted_exception(exception: Exception, redacted_message: str) -> Exception:
        try:
            return exception.__class__(redacted_message)
        except (TypeError, ValueError):
            return RuntimeError(redacted_message)

    def _normalize_key(self, key: object) -> str:
        raw = str(object=key)
        split_mixed_case = self._should_split_mixed_case(raw=raw)
        normalized: list[str] = []
        for index, char in enumerate(raw):
            separator = self._separator_for_char(char=char, normalized=normalized)
            if separator is not None:
                normalized.extend(separator)
                continue

            if self._needs_mixed_case_separator(
                raw=raw,
                index=index,
                normalized=normalized,
                split_mixed_case=split_mixed_case,
            ):
                normalized.append("_")
            normalized.append(char.lower())
        return "".join(normalized).strip("_")

    @staticmethod
    def _should_split_mixed_case(raw: str) -> bool:
        letters = [char for char in raw if char.isalpha()]
        # Constant-style keys (e.g. env vars) must not be split into p_a_s_s_w_o_r_d or a_p_i__k_e_y,
        # or sensitive substring checks miss them after normalization.
        return not letters or not all(char.isupper() for char in letters)

    @staticmethod
    def _separator_for_char(char: str, normalized: list[str]) -> str | None:
        if char.isascii() and char.isalnum():
            return None
        if normalized and normalized[-1] != "_":
            return "_"
        return ""

    def _needs_mixed_case_separator(
        self,
        *,
        raw: str,
        index: int,
        normalized: list[str],
        split_mixed_case: bool,
    ) -> bool:
        if not split_mixed_case or not normalized or normalized[-1] == "_":
            return False
        if not raw[index].isupper():
            return False

        previous = raw[index - 1]
        next_char = raw[index + 1] if index + 1 < len(raw) else ""
        return self._is_mixed_case_boundary(
            previous=previous,
            next_char=next_char,
            has_acronym_prefix=self._has_acronym_prefix(raw=raw, index=index),
        )

    @staticmethod
    def _is_mixed_case_boundary(previous: str, next_char: str, *, has_acronym_prefix: bool) -> bool:
        return (
            previous.islower()
            or previous.isdigit()
            or (previous.isupper() and next_char.islower() and has_acronym_prefix)
        )

    @staticmethod
    def _has_acronym_prefix(raw: str, index: int) -> bool:
        return index >= PhiPiiLogRedactor.ACRONYM_PREFIX_MIN_LENGTH and raw[index - 2].isupper()

    def _is_sensitive_key(self, normalized_key: str) -> bool:
        return self.sensitive_key_pattern.search(string=normalized_key) is not None

    def _is_email_key(self, normalized_key: str) -> bool:
        return self.email_key_pattern.fullmatch(string=normalized_key) is not None

    def _is_phone_key(self, normalized_key: str) -> bool:
        return self.phone_key_pattern.fullmatch(string=normalized_key) is not None

    def _is_url_key(self, normalized_key: str) -> bool:
        return self.url_key_pattern.fullmatch(string=normalized_key) is not None

    def _is_address_key(self, normalized_key: str) -> bool:
        return any(pattern.fullmatch(string=normalized_key) is not None for pattern in self.address_key_patterns)

    def _is_address_container_key(self, normalized_key: str) -> bool:
        return self.address_container_key_pattern.fullmatch(string=normalized_key) is not None

    def _is_address_child_key(self, normalized_key: str) -> bool:
        return self.address_child_key_pattern.fullmatch(string=normalized_key) is not None

    def _is_test_result_container_key(self, normalized_key: str) -> bool:
        return self._matches_test_result_group(value=normalized_key, group_name="container")

    def _is_test_result_payload_key(self, normalized_key: str) -> bool:
        return self._matches_test_result_group(value=normalized_key, group_name="payload")

    def _matches_test_result_group(self, value: str, group_name: str) -> bool:
        match = self.test_result_pattern.fullmatch(string=value)
        return match is not None and match.group(group_name) is not None

    def _should_redact_key(self, normalized_key: str, *, in_result_payload: bool) -> bool:
        return (
            self._is_sensitive_key(normalized_key=normalized_key)
            or self._is_address_key(normalized_key=normalized_key)
            or (in_result_payload and self._is_test_result_payload_key(normalized_key=normalized_key))
        )

    def _should_redact_string_key(self, normalized_key: str) -> bool:
        return (
            self._should_redact_key(normalized_key=normalized_key, in_result_payload=False)
            or self._is_test_result_container_key(normalized_key=normalized_key)
            or self._is_specific_test_result_field(normalized_key=normalized_key)
            or self._is_email_key(normalized_key=normalized_key)
            or self._is_url_key(normalized_key=normalized_key)
            or self._is_phone_key(normalized_key=normalized_key)
        )

    def _looks_like_result_payload(self, keys: set[str]) -> bool:
        return (
            any(self._is_test_result_payload_key(normalized_key=key) and key != "value" for key in keys)
            and "value" in keys
        )

    def _is_specific_test_result_field(self, normalized_key: str) -> bool:
        return self._is_test_result_payload_key(normalized_key=normalized_key) and normalized_key != "value"
