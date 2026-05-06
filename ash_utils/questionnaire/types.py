import typing as t
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

ValidationRules = dict[str, t.Any]
AnswerOptions = t.Iterable[str]


class QuestionInputType(StrEnum):
    number = "number"
    text = "text"
    boolean = "boolean"
    select = "select"
    multi_select = "multi_select"
    date = "date"
    datetime = "datetime"


class QuestionValidationInput(BaseModel):
    """Minimal question data required for answer validation and formatting."""

    question_id: str
    type: QuestionInputType
    validation_rules: ValidationRules | None = None
    options: AnswerOptions | None = None

    model_config = ConfigDict(frozen=True)


class QuestionOption(BaseModel):
    """Display metadata for a selectable question option."""

    value: str
    label: str

    model_config = ConfigDict(frozen=True)


class QuestionDefinition(BaseModel):
    """Generic shared question contract used across questionnaire workflows."""

    question_id: str
    label: str
    type: QuestionInputType
    required: bool = False
    options: t.Iterable["QuestionOption"] | None = None
    validation_rules: ValidationRules | None = None

    model_config = ConfigDict(frozen=True)

    def to_validation_input(self) -> QuestionValidationInput:
        option_values = None
        if self.options is not None:
            option_values = tuple(option.value for option in self.options)

        return QuestionValidationInput(
            question_id=self.question_id,
            type=self.type,
            validation_rules=self.validation_rules,
            options=option_values,
        )


class QuestionAnswer(BaseModel):
    """Generic question answer payload."""

    question_id: str
    answer: str

    model_config = ConfigDict(frozen=True)
