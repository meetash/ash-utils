from ash_utils.aoe.type_validators import (
    AoeAnswerTypeValidator,
    BooleanAoeAnswerTypeValidator,
    DateAoeAnswerTypeValidator,
    DatetimeAoeAnswerTypeValidator,
    MultiSelectAoeAnswerTypeValidator,
    NumberAoeAnswerTypeValidator,
    SelectAoeAnswerTypeValidator,
    TextAoeAnswerTypeValidator,
)
from ash_utils.aoe.types import AoeQuestionInputType, AoeQuestionValidationInput


class AoeAnswerValidator:
    """Dispatch validation/formatting by AOE question input type."""

    class AoeAnswerInvalidError(ValueError):
        """Raised when an AOE answer fails validation for a specific question."""

        def __init__(self, ash_question_id: str, message: str) -> None:
            self.ash_question_id = ash_question_id
            self.message = message
            super().__init__(f"Invalid answer for AOE question '{ash_question_id}': {message}")

    def __init__(
        self,
        type_validators: dict[AoeQuestionInputType, AoeAnswerTypeValidator] | None = None,
    ) -> None:
        self.type_validators = type_validators or self._build_default_type_validators()

    def validate_and_format(self, question: AoeQuestionValidationInput, answer: str) -> str:
        """Validate `answer` against `question` and return the lab-formatted string."""
        validator = self.type_validators.get(question.ash_question_type)
        if validator is None:
            raise self.AoeAnswerInvalidError(
                question.ash_question_id,
                f"unsupported question type '{question.ash_question_type}'",
            )
        try:
            return validator.validate_and_format(question, answer)
        except ValueError as exc:
            raise self.AoeAnswerInvalidError(question.ash_question_id, str(exc)) from exc

    @staticmethod
    def _build_default_type_validators() -> dict[AoeQuestionInputType, AoeAnswerTypeValidator]:
        return {
            AoeQuestionInputType.number: NumberAoeAnswerTypeValidator(),
            AoeQuestionInputType.text: TextAoeAnswerTypeValidator(),
            AoeQuestionInputType.boolean: BooleanAoeAnswerTypeValidator(),
            AoeQuestionInputType.date: DateAoeAnswerTypeValidator(),
            AoeQuestionInputType.datetime: DatetimeAoeAnswerTypeValidator(),
            AoeQuestionInputType.select: SelectAoeAnswerTypeValidator(),
            AoeQuestionInputType.multi_select: MultiSelectAoeAnswerTypeValidator(),
        }
