from ash_utils.questionnaire.exceptions import AnswerInvalidError, QuestionConfigurationError
from ash_utils.questionnaire.type_validators import (
    AnswerTypeValidator,
    BooleanAnswerTypeValidator,
    DateAnswerTypeValidator,
    DatetimeAnswerTypeValidator,
    MultiSelectAnswerTypeValidator,
    NumberAnswerTypeValidator,
    SelectAnswerTypeValidator,
    TextAnswerTypeValidator,
)
from ash_utils.questionnaire.types import QuestionInputType, QuestionValidationInput


class AnswerValidator:
    """Dispatch validation by question input type."""

    def __init__(
        self,
        type_validators: dict[QuestionInputType, AnswerTypeValidator] | None = None,
    ) -> None:
        self.type_validators = type_validators or self._build_default_type_validators()

    def validate(self, question: QuestionValidationInput, answer: str | None) -> None:
        """Validate ``answer`` against ``question``.

        The ``optional`` validation rule defaults to ``False``. When set to
        ``True``, an empty string or ``None`` answer is considered valid and
        skips type-specific validation.

        User input issues are raised as `AnswerInvalidError`. Missing question
        metadata (e.g. options for select) is raised as `QuestionConfigurationError`
        and is not wrapped.
        """
        rules = question.validation_rules or {}
        if rules.get("optional", False) and (answer is None or answer == ""):
            return
        if answer is None:
            raise AnswerInvalidError(question.question_id, "answer is required")
        validator = self.type_validators.get(question.type)
        if validator is None:
            raise QuestionConfigurationError(
                question.question_id,
                f"unsupported question type '{question.type}'",
            )
        try:
            validator.validate(question, answer)
        except ValueError as exc:
            raise AnswerInvalidError(question.question_id, str(exc)) from exc

    @staticmethod
    def _build_default_type_validators() -> dict[QuestionInputType, AnswerTypeValidator]:
        return {
            QuestionInputType.number: NumberAnswerTypeValidator(),
            QuestionInputType.text: TextAnswerTypeValidator(),
            QuestionInputType.boolean: BooleanAnswerTypeValidator(),
            QuestionInputType.date: DateAnswerTypeValidator(),
            QuestionInputType.datetime: DatetimeAnswerTypeValidator(),
            QuestionInputType.select: SelectAnswerTypeValidator(),
            QuestionInputType.multi_select: MultiSelectAnswerTypeValidator(),
        }
