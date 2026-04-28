import pytest

from ash_utils.aoe.exceptions import AoeQuestionConfigurationError
from ash_utils.aoe.type_validators import (
    BooleanAoeAnswerTypeValidator,
    DateAoeAnswerTypeValidator,
    DatetimeAoeAnswerTypeValidator,
    MultiSelectAoeAnswerTypeValidator,
    NumberAoeAnswerTypeValidator,
    SelectAoeAnswerTypeValidator,
    TextAoeAnswerTypeValidator,
)
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


class TestNumberAoeAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = NumberAoeAnswerTypeValidator()

    @pytest.mark.parametrize(
        ("answer", "rules", "expected"),
        [
            ("42", None, "42"),
            ("3.14", {"gte": 0.0, "lte": 10.0}, "3.14"),
        ],
    )
    def test_valid_cases(self, answer: str, rules: dict | None, expected: str) -> None:
        question = _question(question_type=AoeQuestionInputType.number, validation_rules=rules)
        assert self.validator.validate_and_format(question, answer) == expected

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
        question = _question(question_type=AoeQuestionInputType.number, validation_rules=rules)
        with pytest.raises(ValueError):
            self.validator.validate_and_format(question, answer)


class TestTextAoeAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = TextAoeAnswerTypeValidator()

    @pytest.mark.parametrize(
        ("answer", "rules", "expected"),
        [
            ("abc", {"min_length": 2, "max_length": 5}, "abc"),
            ("hello", None, "hello"),
        ],
    )
    def test_valid_cases(self, answer: str, rules: dict | None, expected: str) -> None:
        question = _question(question_type=AoeQuestionInputType.text, validation_rules=rules)
        assert self.validator.validate_and_format(question, answer) == expected

    @pytest.mark.parametrize(
        ("answer", "rules"),
        [
            ("a", {"min_length": 2}),
            ("abcdef", {"max_length": 5}),
        ],
    )
    def test_invalid_cases(self, answer: str, rules: dict | None) -> None:
        question = _question(question_type=AoeQuestionInputType.text, validation_rules=rules)
        with pytest.raises(ValueError):
            self.validator.validate_and_format(question, answer)


class TestBooleanAoeAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = BooleanAoeAnswerTypeValidator()

    @pytest.mark.parametrize(
        ("answer", "expected"),
        [
            ("true", "true"),
            ("False", "false"),
            ("yes", "true"),
            ("0", "false"),
        ],
    )
    def test_valid_cases(self, answer: str, expected: str) -> None:
        question = _question(question_type=AoeQuestionInputType.boolean)
        assert self.validator.validate_and_format(question, answer) == expected

    def test_invalid_case(self) -> None:
        question = _question(question_type=AoeQuestionInputType.boolean)
        with pytest.raises(ValueError):
            self.validator.validate_and_format(question, "maybe")


class TestDateAoeAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = DateAoeAnswerTypeValidator()

    @pytest.mark.parametrize(
        ("answer", "rules", "expected"),
        [
            ("2025-06-22", {"format": "%Y%m%d"}, "20250622"),
            ("2025-06-22T15:00:00+00:00", {"format": "%Y%m%d"}, "20250622"),
        ],
    )
    def test_valid_cases(self, answer: str, rules: dict, expected: str) -> None:
        question = _question(question_type=AoeQuestionInputType.date, validation_rules=rules)
        assert self.validator.validate_and_format(question, answer) == expected

    @pytest.mark.parametrize(
        ("answer", "rules"),
        [
            ("not-a-date", {"format": "%Y%m%d"}),
            ("2025-06-22", None),
        ],
    )
    def test_invalid_cases(self, answer: str, rules: dict | None) -> None:
        question = _question(question_type=AoeQuestionInputType.date, validation_rules=rules)
        with pytest.raises(ValueError):
            self.validator.validate_and_format(question, answer)


class TestDatetimeAoeAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = DatetimeAoeAnswerTypeValidator()

    @pytest.mark.parametrize(
        ("answer", "rules", "expected"),
        [
            ("2025-06-22T15:30:45+00:00", {"format": "%Y%m%d%H%M%S"}, "20250622153045"),
            ("2025-06-22T15:30:45-05:00", {"format": "%Y%m%d%H%M%S%z"}, "20250622153045-0500"),
        ],
    )
    def test_valid_cases(self, answer: str, rules: dict, expected: str) -> None:
        question = _question(question_type=AoeQuestionInputType.datetime, validation_rules=rules)
        assert self.validator.validate_and_format(question, answer) == expected

    @pytest.mark.parametrize(
        ("answer", "rules"),
        [
            ("not-a-datetime", {"format": "%Y%m%d%H%M%S"}),
            ("2025-06-22T15:30:45+00:00", None),
        ],
    )
    def test_invalid_cases(self, answer: str, rules: dict | None) -> None:
        question = _question(question_type=AoeQuestionInputType.datetime, validation_rules=rules)
        with pytest.raises(ValueError):
            self.validator.validate_and_format(question, answer)


class TestSelectAoeAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = SelectAoeAnswerTypeValidator()

    @pytest.mark.parametrize(
        ("answer", "options", "expected"),
        [
            ("male", {"male": "M", "female": "F"}, "M"),
            (" Female ", {"male": "M", "female": "F"}, "F"),
        ],
    )
    def test_valid_cases(self, answer: str, options: dict, expected: str) -> None:
        question = _question(question_type=AoeQuestionInputType.select, options=options)
        assert self.validator.validate_and_format(question, answer) == expected

    def test_invalid_answer_raises_value_error(self) -> None:
        question = _question(
            question_type=AoeQuestionInputType.select,
            options={"male": "M", "female": "F"},
        )
        with pytest.raises(ValueError):
            self.validator.validate_and_format(question, "other")

    def test_missing_options_raises_configuration_error(self) -> None:
        question = _question(question_type=AoeQuestionInputType.select, options=None)
        with pytest.raises(AoeQuestionConfigurationError):
            self.validator.validate_and_format(question, "male")


class TestMultiSelectAoeAnswerTypeValidator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.validator = MultiSelectAoeAnswerTypeValidator()

    @pytest.mark.parametrize(
        ("answer", "options", "rules", "expected"),
        [
            ("a", {"a": "A", "b": "B"}, {"multi_select_delimiter": ","}, "A"),
            ("a|b", {"a": "A", "b": "B"}, {"multi_select_delimiter": ","}, "A,B"),
            (" a | b ", {"a": "A", "b": "B"}, {"multi_select_delimiter": ";"}, "A;B"),
        ],
    )
    def test_valid_cases(self, answer: str, options: dict, rules: dict, expected: str) -> None:
        question = _question(
            question_type=AoeQuestionInputType.multi_select,
            options=options,
            validation_rules=rules,
        )
        assert self.validator.validate_and_format(question, answer) == expected

    def test_missing_options_raises_configuration_error(self) -> None:
        question = _question(
            question_type=AoeQuestionInputType.multi_select,
            options=None,
            validation_rules={"multi_select_delimiter": ","},
        )
        with pytest.raises(AoeQuestionConfigurationError):
            self.validator.validate_and_format(question, "a")

    @pytest.mark.parametrize(
        ("answer", "options", "rules"),
        [
            ("a", {"a": "A"}, None),
            ("", {"a": "A"}, {"multi_select_delimiter": ","}),
            ("a|x", {"a": "A"}, {"multi_select_delimiter": ","}),
        ],
    )
    def test_invalid_cases_value_error(self, answer: str, options: dict | None, rules: dict | None) -> None:
        question = _question(
            question_type=AoeQuestionInputType.multi_select,
            options=options,
            validation_rules=rules,
        )
        with pytest.raises(ValueError):
            self.validator.validate_and_format(question, answer)
