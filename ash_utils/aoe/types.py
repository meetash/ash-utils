from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

ValidationRules = dict[str, Any]
AnswerOptions = dict[str, Any]


class AoeQuestionInputType(StrEnum):
    number = "number"
    text = "text"
    boolean = "boolean"
    select = "select"
    multi_select = "multi_select"
    date = "date"
    datetime = "datetime"


class AoeQuestionValidationInput(BaseModel):
    """Minimal question data required for answer validation and formatting."""

    question_id: str
    type: AoeQuestionInputType
    validation_rules: ValidationRules | None = None
    options: AnswerOptions | None = None

    model_config = ConfigDict(frozen=True)
