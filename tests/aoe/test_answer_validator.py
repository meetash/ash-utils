import pytest

from ash_utils.aoe.answer_validator import (
    AoeAnswerTypeValidator,
    AoeAnswerValidator,
    BooleanAoeAnswerTypeValidator,
    DateAoeAnswerTypeValidator,
    DatetimeAoeAnswerTypeValidator,
    MultiSelectAoeAnswerTypeValidator,
    NumberAoeAnswerTypeValidator,
    SelectAoeAnswerTypeValidator,
    TextAoeAnswerTypeValidator,
)
from ash_utils.aoe.exceptions import AoeAnswerInvalidError, AoeQuestionConfigurationError
from ash_utils.aoe.types import AoeQuestionInputType, AoeQuestionValidationInput


def _question(
    *,
    question_type: AoeQuestionInputType,
    validation_rules: dict | None = None,
    options: dict | None = None,
) -> AoeQuestionValidationInput:
    return AoeQuestionValidationInput(
        question_id="q1",
        type=question_type,
        validation_rules=validation_rules,
        options=options,
    )


class TestTypeValidatorStructure:
    def test_all_type_validators_implement_common_interface(self) -> None:
        validators = (
            NumberAoeAnswerTypeValidator(),
            TextAoeAnswerTypeValidator(),
            BooleanAoeAnswerTypeValidator(),
            DateAoeAnswerTypeValidator(),
            DatetimeAoeAnswerTypeValidator(),
            SelectAoeAnswerTypeValidator(),
            MultiSelectAoeAnswerTypeValidator(),
        )

        assert all(isinstance(validator, AoeAnswerTypeValidator) for validator in validators)

    def test_dispatcher_registers_one_validator_per_question_type(self) -> None:
        validator = AoeAnswerValidator()

        assert set(validator.type_validators.keys()) == {
            AoeQuestionInputType.number,
            AoeQuestionInputType.text,
            AoeQuestionInputType.boolean,
            AoeQuestionInputType.date,
            AoeQuestionInputType.datetime,
            AoeQuestionInputType.select,
            AoeQuestionInputType.multi_select,
        }


class TestValidationBehavior:
    def test_number_validator_accepts_decimal(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.number)

        validator.validate(question, "3.14")

    def test_number_validator_rejects_invalid_number(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.number)

        with pytest.raises(AoeAnswerInvalidError):
            validator.validate(question, "abc")

    @pytest.mark.parametrize("raw", ["true", "False", "yes", "0"])
    def test_boolean_validator_accepts_recognised_values(self, raw: str) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.boolean)

        validator.validate(question, raw)

    def test_date_validator_accepts_rfc3339_date(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.date)

        validator.validate(question, "2025-06-22")

    def test_date_validator_accepts_datetime_string_for_date_question(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.date)

        validator.validate(question, "2025-06-22T15:00:00+00:00")

    def test_multi_select_validator_accepts_pipe_separated_keys(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(
            question_type=AoeQuestionInputType.multi_select,
            options=("a", "b"),
        )

        validator.validate(question, "a|b")

    def test_select_without_options_raises_configuration_error_not_wrapped(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.select, options=None)

        with pytest.raises(AoeQuestionConfigurationError) as exc_info:
            validator.validate(question, "male")

        assert exc_info.value.question_id == "q1"
