from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import TypeAdapter, ValidationError

from ash_utils.questionnaire.exceptions import QuestionConfigurationError
from ash_utils.questionnaire.types import QuestionValidationInput

MULTI_SELECT_INPUT_SEPARATOR = "|"


class AnswerTypeValidator(ABC):
    @abstractmethod
    def validate(self, question: QuestionValidationInput, answer: str) -> None:
        """Validate answer; raise ``ValueError`` or ``QuestionConfigurationError`` on failure."""


class NumberAnswerTypeValidator(AnswerTypeValidator):
    def validate(self, question: QuestionValidationInput, answer: str) -> None:
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


class TextAnswerTypeValidator(AnswerTypeValidator):
    def validate(self, question: QuestionValidationInput, answer: str) -> None:
        rules = question.validation_rules or {}
        min_length = rules.get("min_length")
        max_length = rules.get("max_length")
        if min_length is not None and len(answer) < min_length:
            msg = f"length {len(answer)} is below min_length {min_length}"
            raise ValueError(msg)
        if max_length is not None and len(answer) > max_length:
            msg = f"length {len(answer)} exceeds max_length {max_length}"
            raise ValueError(msg)


class BooleanAnswerTypeValidator(AnswerTypeValidator):
    _BOOL_ADAPTER = TypeAdapter(bool)

    def validate(self, question: QuestionValidationInput, answer: str) -> None:  # noqa: ARG002
        try:
            self._BOOL_ADAPTER.validate_python(answer)
        except ValidationError as exc:
            msg = f"'{answer}' is not a recognised boolean"
            raise ValueError(msg) from exc


class DateAnswerTypeValidator(AnswerTypeValidator):
    def validate(self, question: QuestionValidationInput, answer: str) -> None:  # noqa: ARG002
        try:
            datetime.fromisoformat(answer)
        except ValueError as exc:
            msg = f"'{answer}' is not a valid RFC-3339 date"
            raise ValueError(msg) from exc


class DatetimeAnswerTypeValidator(AnswerTypeValidator):
    def validate(self, question: QuestionValidationInput, answer: str) -> None:  # noqa: ARG002
        try:
            datetime.fromisoformat(answer)
        except ValueError as exc:
            msg = f"'{answer}' is not a valid RFC-3339 datetime"
            raise ValueError(msg) from exc


class SelectAnswerTypeValidator(AnswerTypeValidator):
    def validate(self, question: QuestionValidationInput, answer: str) -> None:
        options = question.options
        if not options:
            msg = "options are required for select questions"
            raise QuestionConfigurationError(question.question_id, msg)
        key = answer.strip().lower()
        match = next((candidate for candidate in options if candidate.strip().lower() == key), None)
        if match is None:
            msg = f"'{answer}' is not one of allowed values: {sorted(options)}"
            raise ValueError(msg)


class MultiSelectAnswerTypeValidator(AnswerTypeValidator):

    def validate(self, question: QuestionValidationInput, answer: str) -> None:
        options = question.options
        if not options:
            msg = "options mapping is required for multi_select questions"
            raise QuestionConfigurationError(question.question_id, msg)
        stripped_answer = answer.strip().lower()
        if not stripped_answer:
            msg = "at least one value is required"
            raise ValueError(msg)
        tokens = tuple(
            token.strip() for token in stripped_answer.split(MULTI_SELECT_INPUT_SEPARATOR) if token.strip()
        )
        if not tokens:
            msg = "at least one value is required"
            raise ValueError(msg)

        unknown: list[str] = []
        for token in tokens:
            key_match = next((candidate for candidate in options if candidate.strip().lower() == token), None)
            if key_match is None:
                unknown.append(token)
        if unknown:
            msg = f"unknown value(s): {unknown}. Allowed: {sorted(options)}"
            raise ValueError(msg)
