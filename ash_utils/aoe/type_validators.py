from abc import ABC, abstractmethod
from datetime import date, datetime

from pydantic import TypeAdapter, ValidationError

from ash_utils.aoe.types import AoeQuestionValidationInput


class AoeAnswerInvalidError(ValueError):
    """Raised when an AOE answer fails validation for a specific question."""

    def __init__(self, ash_question_id: str, message: str) -> None:
        self.ash_question_id = ash_question_id
        self.message = message
        super().__init__(f"Invalid answer for AOE question '{ash_question_id}': {message}")


class AoeAnswerTypeValidator(ABC):
    @abstractmethod
    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        """Validate answer and return formatted value."""


class NumberAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        try:
            value = float(answer)
        except ValueError as exc:
            raise AoeAnswerInvalidError(question.ash_question_id, f"'{answer}' is not a number") from exc
        rules = question.validation_rules or {}
        if "gte" in rules and not value >= rules["gte"]:
            raise AoeAnswerInvalidError(question.ash_question_id, f"value {value} must be >= {rules['gte']}")
        if "gt" in rules and not value > rules["gt"]:
            raise AoeAnswerInvalidError(question.ash_question_id, f"value {value} must be > {rules['gt']}")
        if "lte" in rules and not value <= rules["lte"]:
            raise AoeAnswerInvalidError(question.ash_question_id, f"value {value} must be <= {rules['lte']}")
        if "lt" in rules and not value < rules["lt"]:
            raise AoeAnswerInvalidError(question.ash_question_id, f"value {value} must be < {rules['lt']}")
        return answer


class TextAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        rules = question.validation_rules or {}
        min_length = rules.get("min_length")
        max_length = rules.get("max_length")
        if min_length is not None and len(answer) < min_length:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                f"length {len(answer)} is below min_length {min_length}",
            )
        if max_length is not None and len(answer) > max_length:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                f"length {len(answer)} exceeds max_length {max_length}",
            )
        return answer


class BooleanAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    _BOOL_ADAPTER = TypeAdapter(bool)

    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        try:
            parsed: bool = self._BOOL_ADAPTER.validate_python(answer)
        except ValidationError as exc:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                f"'{answer}' is not a recognised boolean",
            ) from exc
        return "true" if parsed else "false"


class _StrftimeFormattingTypeValidator(AoeAnswerTypeValidator, ABC):
    @abstractmethod
    def _parse(self, question: AoeQuestionValidationInput, answer: str) -> date | datetime:
        """Parse answer into date-like value."""

    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        parsed = self._parse(question, answer)
        rules = question.validation_rules or {}
        output_format = rules.get("format")
        if not output_format:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                "validation_rules.format is required for date/datetime questions",
            )
        return parsed.strftime(output_format)


class DateAoeAnswerTypeValidator(_StrftimeFormattingTypeValidator):
    def _parse(self, question: AoeQuestionValidationInput, answer: str) -> date:
        try:
            return datetime.fromisoformat(answer).date()
        except ValueError as exc:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                f"'{answer}' is not a valid RFC-3339 date",
            ) from exc


class DatetimeAoeAnswerTypeValidator(_StrftimeFormattingTypeValidator):
    def _parse(self, question: AoeQuestionValidationInput, answer: str) -> datetime:
        try:
            return datetime.fromisoformat(answer)
        except ValueError as exc:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                f"'{answer}' is not a valid RFC-3339 datetime",
            ) from exc


class SelectAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        options = question.options
        if not options:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                "options mapping is required for select questions",
            )
        key = answer.strip().lower()
        match = next((candidate for candidate in options if candidate.strip().lower() == key), None)
        if match is None:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                f"'{answer}' is not one of allowed values: {sorted(options.keys())}",
            )
        return str(options[match])


class MultiSelectAoeAnswerTypeValidator(AoeAnswerTypeValidator):
    MULTI_SELECT_INPUT_SEPARATOR = "|"

    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        options = question.options
        if not options:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                "options mapping is required for multi_select questions",
            )
        output_delimiter = (question.validation_rules or {}).get("multi_select_delimiter")
        if not output_delimiter:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                "validation_rules.multi_select_delimiter is required for multi_select questions",
            )
        stripped_answer = answer.strip().lower()
        if not stripped_answer:
            raise AoeAnswerInvalidError(question.ash_question_id, "at least one value is required")
        tokens = tuple(
            token.strip().lower()
            for token in stripped_answer.split(self.MULTI_SELECT_INPUT_SEPARATOR)
            if token.strip().lower()
        )
        if not tokens:
            raise AoeAnswerInvalidError(question.ash_question_id, "at least one value is required")

        unknown: list[str] = []
        expanded: list[str] = []
        for token in tokens:
            key_match = next((candidate for candidate in options if candidate.strip().lower() == token), None)
            if key_match is None:
                unknown.append(token)
                continue
            expanded.append(str(options[key_match]))
        if unknown:
            raise AoeAnswerInvalidError(
                question.ash_question_id,
                f"unknown value(s): {unknown}. Allowed: {sorted(options.keys())}",
            )
        return output_delimiter.join(expanded)
