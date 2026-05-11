import pytest

from ash_utils.questionnaire.answer_validator import (
    AnswerTypeValidator,
    AnswerValidator,
    BooleanAnswerTypeValidator,
    DateAnswerTypeValidator,
    DatetimeAnswerTypeValidator,
    MultiSelectAnswerTypeValidator,
    NumberAnswerTypeValidator,
    SelectAnswerTypeValidator,
    TextAnswerTypeValidator,
)
from ash_utils.questionnaire.exceptions import AnswerInvalidError, QuestionConfigurationError
from ash_utils.questionnaire.types import QuestionInputType, QuestionValidationInput


def _question(
    *,
    question_type: QuestionInputType,
    validation_rules: dict | None = None,
    options: dict | None = None,
) -> QuestionValidationInput:
    return QuestionValidationInput(
        question_id="q1",
        type=question_type,
        validation_rules=validation_rules,
        options=options,
    )


class TestTypeValidatorStructure:
    def test_all_type_validators_implement_common_interface(self) -> None:
        validators = (
            NumberAnswerTypeValidator(),
            TextAnswerTypeValidator(),
            BooleanAnswerTypeValidator(),
            DateAnswerTypeValidator(),
            DatetimeAnswerTypeValidator(),
            SelectAnswerTypeValidator(),
            MultiSelectAnswerTypeValidator(),
        )

        assert all(isinstance(validator, AnswerTypeValidator) for validator in validators)

    def test_dispatcher_registers_one_validator_per_question_type(self) -> None:
        validator = AnswerValidator()

        assert set(validator.type_validators.keys()) == {
            QuestionInputType.number,
            QuestionInputType.text,
            QuestionInputType.boolean,
            QuestionInputType.date,
            QuestionInputType.datetime,
            QuestionInputType.select,
            QuestionInputType.multi_select,
        }


class TestValidationBehavior:
    def test_number_validator_accepts_decimal(self) -> None:
        validator = AnswerValidator()
        question = _question(question_type=QuestionInputType.number)

        validator.validate(question, "3.14")

    def test_number_validator_rejects_invalid_number(self) -> None:
        validator = AnswerValidator()
        question = _question(question_type=QuestionInputType.number)

        with pytest.raises(AnswerInvalidError):
            validator.validate(question, "abc")

    @pytest.mark.parametrize("raw", ["true", "False", "yes", "0"])
    def test_boolean_validator_accepts_recognised_values(self, raw: str) -> None:
        validator = AnswerValidator()
        question = _question(question_type=QuestionInputType.boolean)

        validator.validate(question, raw)

    def test_date_validator_accepts_rfc3339_date(self) -> None:
        validator = AnswerValidator()
        question = _question(question_type=QuestionInputType.date)

        validator.validate(question, "2025-06-22")

    def test_date_validator_accepts_datetime_string_for_date_question(self) -> None:
        validator = AnswerValidator()
        question = _question(question_type=QuestionInputType.date)

        validator.validate(question, "2025-06-22T15:00:00+00:00")

    def test_multi_select_validator_accepts_pipe_separated_keys(self) -> None:
        validator = AnswerValidator()
        question = _question(
            question_type=QuestionInputType.multi_select,
            options=("a", "b"),
        )

        validator.validate(question, "a|b")

    def test_select_without_options_raises_configuration_error_not_wrapped(self) -> None:
        validator = AnswerValidator()
        question = _question(question_type=QuestionInputType.select, options=None)

        with pytest.raises(QuestionConfigurationError) as exc_info:
            validator.validate(question, "male")

        assert exc_info.value.question_id == "q1"
