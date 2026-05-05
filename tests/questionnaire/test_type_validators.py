import pytest

from ash_utils.questionnaire.exceptions import QuestionConfigurationError
from ash_utils.questionnaire.type_validators import (
    BooleanAnswerTypeValidator,
    DateAnswerTypeValidator,
    DatetimeAnswerTypeValidator,
    MultiSelectAnswerTypeValidator,
    NumberAnswerTypeValidator,
    SelectAnswerTypeValidator,
    TextAnswerTypeValidator,
)
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


class TestNumberAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = NumberAnswerTypeValidator()

    @pytest.mark.parametrize(
        ("answer", "rules"),
        [
            ("42", None),
            ("3.14", {"gte": 0.0, "lte": 10.0}),
        ],
    )
    def test_valid_cases(self, answer: str, rules: dict | None) -> None:
        question = _question(question_type=QuestionInputType.number, validation_rules=rules)
        self.validator.validate(question, answer)

    @pytest.mark.parametrize(
        ("answer", "rules"),
        [
            ("abc", None),
            ("9", {"gte": 10}),
            ("10", {"gt": 10}),
            ("101", {"lte": 100}),
            ("100", {"lt": 100}),
        ],
    )
    def test_invalid_cases(self, answer: str, rules: dict | None) -> None:
        question = _question(question_type=QuestionInputType.number, validation_rules=rules)
        with pytest.raises(ValueError):
            self.validator.validate(question, answer)


class TestTextAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = TextAnswerTypeValidator()

    @pytest.mark.parametrize(
        ("answer", "rules"),
        [
            ("abc", {"min_length": 2, "max_length": 5}),
            ("hello", None),
        ],
    )
    def test_valid_cases(self, answer: str, rules: dict | None) -> None:
        question = _question(question_type=QuestionInputType.text, validation_rules=rules)
        self.validator.validate(question, answer)

    @pytest.mark.parametrize(
        ("answer", "rules"),
        [
            ("a", {"min_length": 2}),
            ("abcdef", {"max_length": 5}),
        ],
    )
    def test_invalid_cases(self, answer: str, rules: dict | None) -> None:
        question = _question(question_type=QuestionInputType.text, validation_rules=rules)
        with pytest.raises(ValueError):
            self.validator.validate(question, answer)


class TestBooleanAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = BooleanAnswerTypeValidator()

    @pytest.mark.parametrize("answer", ["true", "False", "yes", "0"])
    def test_valid_cases(self, answer: str) -> None:
        question = _question(question_type=QuestionInputType.boolean)
        self.validator.validate(question, answer)

    def test_invalid_case(self) -> None:
        question = _question(question_type=QuestionInputType.boolean)
        with pytest.raises(ValueError):
            self.validator.validate(question, "maybe")


class TestDateAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = DateAnswerTypeValidator()

    @pytest.mark.parametrize(
        "answer",
        ["2025-06-22", "2025-06-22T15:00:00+00:00"],
    )
    def test_valid_rfc3339_date_strings(self, answer: str) -> None:
        question = _question(question_type=QuestionInputType.date)
        self.validator.validate(question, answer)

    @pytest.mark.parametrize("answer", ["not-a-date", ""])
    def test_invalid_cases(self, answer: str) -> None:
        question = _question(question_type=QuestionInputType.date)
        with pytest.raises(ValueError):
            self.validator.validate(question, answer)


class TestDatetimeAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = DatetimeAnswerTypeValidator()

    @pytest.mark.parametrize(
        "answer",
        [
            "2025-06-22T15:30:45+00:00",
            "2025-06-22T15:30:45-05:00",
        ],
    )
    def test_valid_rfc3339_datetime_strings(self, answer: str) -> None:
        question = _question(question_type=QuestionInputType.datetime)
        self.validator.validate(question, answer)

    def test_invalid_cases(self) -> None:
        question = _question(question_type=QuestionInputType.datetime)
        with pytest.raises(ValueError):
            self.validator.validate(question, "not-a-datetime")


class TestSelectAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = SelectAnswerTypeValidator()

    @pytest.mark.parametrize(
        "answer",
        ["male", " Female "],
    )
    def test_valid_cases(self, answer: str) -> None:
        question = _question(question_type=QuestionInputType.select, options=("male", "female"))
        self.validator.validate(question, answer)

    def test_invalid_answer_raises_value_error(self) -> None:
        question = _question(
            question_type=QuestionInputType.select,
            options={"male": "M", "female": "F"},
        )
        with pytest.raises(ValueError):
            self.validator.validate(question, "other")

    def test_missing_options_raises_configuration_error(self) -> None:
        question = _question(question_type=QuestionInputType.select, options=None)
        with pytest.raises(QuestionConfigurationError):
            self.validator.validate(question, "male")


class TestMultiSelectAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = MultiSelectAnswerTypeValidator()

    @pytest.mark.parametrize(
        "answer",
        ["a", "a|b", " a | b "],
    )
    def test_valid_cases(self, answer: str) -> None:
        question = _question(
            question_type=QuestionInputType.multi_select,
            options=("a", "b"),
        )
        self.validator.validate(question, answer)

    def test_missing_options_raises_configuration_error(self) -> None:
        question = _question(question_type=QuestionInputType.multi_select, options=None)
        with pytest.raises(QuestionConfigurationError):
            self.validator.validate(question, "a")

    @pytest.mark.parametrize(
        ("answer", "options"),
        [
            ("", ("a",)),
            ("a|x", ("a",)),
        ],
    )
    def test_invalid_cases_value_error(self, answer: str, options: tuple[str, ...] | None) -> None:
        question = _question(
            question_type=QuestionInputType.multi_select,
            options=options,
        )
        with pytest.raises(ValueError):
            self.validator.validate(question, answer)
