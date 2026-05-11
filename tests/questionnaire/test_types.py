from ash_utils.questionnaire.types import (
    QuestionAnswer,
    QuestionDefinition,
    QuestionInputType,
    QuestionOption,
)


def test_question_definition_supports_core_generic_fields() -> None:
    question = QuestionDefinition(
        question_id="q-country",
        label="Country",
        type=QuestionInputType.select,
        required=True,
        options=(
            QuestionOption(value="uk", label="United Kingdom"),
            QuestionOption(value="us", label="United States"),
        ),
        validation_rules={"min_length": 2},
    )

    assert question.question_id == "q-country"
    assert question.label == "Country"
    assert question.required is True
    assert [option.value for option in question.options or ()] == ["uk", "us"]


def test_question_definition_converts_to_validation_input() -> None:
    question = QuestionDefinition(
        question_id="q-country",
        label="Country",
        type=QuestionInputType.select,
        required=False,
        options=(
            QuestionOption(value="uk", label="United Kingdom"),
            QuestionOption(value="us", label="United States"),
        ),
    )

    validation_input = question.to_validation_input()

    assert validation_input.question_id == "q-country"
    assert validation_input.type == QuestionInputType.select
    assert validation_input.validation_rules is None
    assert tuple(validation_input.options or ()) == ("uk", "us")


def test_question_answer_keeps_question_mapping() -> None:
    answer = QuestionAnswer(question_id="q-country", answer="uk")

    assert answer.question_id == "q-country"
    assert answer.answer == "uk"
