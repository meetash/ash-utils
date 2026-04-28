from abc import ABC, abstractmethod
from datetime import date, datetime

from pydantic import TypeAdapter, ValidationError

from ash_utils.aoe.exceptions import AoeQuestionConfigurationError
from ash_utils.aoe.types import AoeQuestionValidationInput


class AoeAnswerTypeValidator(ABC):
    @abstractmethod
    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        """Validate answer and return formatted value."""


class NumberAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        try:
            value = float(answer)
        except ValueError as exc:
            msg = f"'{answer}' is not a number"
            raise ValueError(msg) from exc
        rules = question.validation_rules or {}
        if "gte" in rules and not value >= rules["gte"]:
            msg = f"value {value} must be >= {rules['gte']}"
            raise ValueError(msg)
        if "gt" in rules and not value > rules["gt"]:
            msg = f"value {value} must be > {rules['gt']}"
            raise ValueError(msg)
        if "lte" in rules and not value <= rules["lte"]:
            msg = f"value {value} must be <= {rules['lte']}"
            raise ValueError(msg)
        if "lt" in rules and not value < rules["lt"]:
            msg = f"value {value} must be < {rules['lt']}"
            raise ValueError(msg)
        return answer


class TextAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        rules = question.validation_rules or {}
        min_length = rules.get("min_length")
        max_length = rules.get("max_length")
        if min_length is not None and len(answer) < min_length:
            msg = f"length {len(answer)} is below min_length {min_length}"
            raise ValueError(msg)
        if max_length is not None and len(answer) > max_length:
            msg = f"length {len(answer)} exceeds max_length {max_length}"
            raise ValueError(msg)
        return answer


class BooleanAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    _BOOL_ADAPTER = TypeAdapter(bool)

    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:  # noqa: ARG002
        try:
            parsed: bool = self._BOOL_ADAPTER.validate_python(answer)
        except ValidationError as exc:
            msg = f"'{answer}' is not a recognised boolean"
            raise ValueError(msg) from exc
        return "true" if parsed else "false"


class _StrftimeFormattingTypeValidator(AoeAnswerTypeValidator, ABC):
    @abstractmethod
    def _parse(self, answer: str) -> date | datetime:
        """Parse answer into date-like value."""

    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        parsed = self._parse(answer)
        rules = question.validation_rules or {}
        output_format = rules.get("format")
        if not output_format:
            msg = "validation_rules.format is required for date/datetime questions"
            raise ValueError(msg)
        return parsed.strftime(output_format)


class DateAoeAnswerTypeValidator(_StrftimeFormattingTypeValidator):
    def _parse(self, answer: str) -> date:
        try:
            return datetime.fromisoformat(answer).date()
        except ValueError as exc:
            msg = f"'{answer}' is not a valid RFC-3339 date"
            raise ValueError(msg) from exc


class DatetimeAoeAnswerTypeValidator(_StrftimeFormattingTypeValidator):
    def _parse(self, answer: str) -> datetime:
        try:
            return datetime.fromisoformat(answer)
        except ValueError as exc:
            msg = f"'{answer}' is not a valid RFC-3339 datetime"
            raise ValueError(msg) from exc


class SelectAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        options = question.options
        if not options:
            msg = "options mapping is required for select questions"
            raise AoeQuestionConfigurationError(question.question_id, msg)
        key = answer.strip().lower()
        match = next((candidate for candidate in options if candidate.strip().lower() == key), None)
        if match is None:
            msg = f"'{answer}' is not one of allowed values: {sorted(options.keys())}"
            raise ValueError(msg)
        return str(options[match])


class MultiSelectAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    MULTI_SELECT_INPUT_SEPARATOR = "|"

    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        options = question.options
        if not options:
            msg = "options mapping is required for multi_select questions"
            raise AoeQuestionConfigurationError(question.question_id, msg)
        output_delimiter = (question.validation_rules or {}).get("multi_select_delimiter")
        if not output_delimiter:
            msg = "validation_rules.multi_select_delimiter is required for multi_select questions"
            raise ValueError(msg)
        stripped_answer = answer.strip().lower()
        if not stripped_answer:
            msg = "at least one value is required"
            raise ValueError(msg)
        tokens = tuple(
            token.strip() for token in stripped_answer.split(self.MULTI_SELECT_INPUT_SEPARATOR) if token.strip()
        )
        if not tokens:
            msg = "at least one value is required"
            raise ValueError(msg)

        unknown: list[str] = []
        expanded: list[str] = []
        for token in tokens:
            key_match = next((candidate for candidate in options if candidate.strip().lower() == token), None)
            if key_match is None:
                unknown.append(token)
                continue
            expanded.append(str(options[key_match]))
        if unknown:
            msg = f"unknown value(s): {unknown}. Allowed: {sorted(options.keys())}"
            raise ValueError(msg)
        return output_delimiter.join(expanded)
