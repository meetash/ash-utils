from ash_utils.aoe.type_validators import (
    AoeAnswerInvalidError,
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

    AoeAnswerInvalidError = AoeAnswerInvalidError

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
        return validator.validate_and_format(question, answer)

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
