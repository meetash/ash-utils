from ash_utils.aoe.exceptions import AoeAnswerInvalidError, AoeQuestionConfigurationError
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
    """Dispatch validation by AOE question input type."""

    def __init__(
        self,
        type_validators: dict[AoeQuestionInputType, AoeAnswerTypeValidator] | None = None,
    ) -> None:
        self.type_validators = type_validators or self._build_default_type_validators()

    def validate(self, question: AoeQuestionValidationInput, answer: str) -> None:
        """Validate ``answer`` against ``question``.

        User input issues are raised as `AoeAnswerInvalidError`. Missing question
        metadata (e.g. options for select) is raised as `AoeQuestionConfigurationError`
        and is not wrapped.
        """
        validator = self.type_validators.get(question.type)
        if validator is None:
            raise AoeQuestionConfigurationError(
                question.question_id,
                f"unsupported question type '{question.type}'",
            )
        try:
            validator.validate(question, answer)
        except ValueError as exc:
            raise AoeAnswerInvalidError(question.question_id, str(exc)) from exc

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
