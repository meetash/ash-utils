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

        assert validator.validate_and_format(question, "3.14") == "3.14"

    def test_number_validator_rejects_invalid_number(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.number)

        with pytest.raises(AoeAnswerInvalidError):
            validator.validate_and_format(question, "abc")

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("true", "true"), ("False", "false"), ("yes", "true"), ("0", "false")],
    )
    def test_boolean_validator_returns_canonical_values(self, raw: str, expected: str) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.boolean)

        assert validator.validate_and_format(question, raw) == expected

    def test_date_validator_requires_format(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.date, validation_rules=None)

        with pytest.raises(AoeAnswerInvalidError):
            validator.validate_and_format(question, "2025-06-22")

    def test_multi_select_validator_maps_and_joins_values(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(
            question_type=AoeQuestionInputType.multi_select,
            options={"a": "A", "b": "B"},
            validation_rules={"multi_select_delimiter": ","},
        )

        assert validator.validate_and_format(question, "a|b") == "A,B"

    def test_select_without_options_raises_configuration_error_not_wrapped(self) -> None:
        validator = AoeAnswerValidator()
        question = _question(question_type=AoeQuestionInputType.select, options=None)

        with pytest.raises(AoeQuestionConfigurationError) as exc_info:
            validator.validate_and_format(question, "male")

        assert exc_info.value.question_id == "q1"
