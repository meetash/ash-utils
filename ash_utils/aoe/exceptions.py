class AoeAnswerInvalidError(ValueError):
    """Raised when an AOE answer fails validation for a specific question."""

    def __init__(self, question_id: str, message: str) -> None:
        self.question_id = question_id
        self.message = message
        super().__init__(f"Invalid answer for AOE question '{question_id}': {message}")


class AoeQuestionConfigurationError(Exception):
    """Raised when question metadata is incomplete for its declared type (system/data setup issue)."""

    def __init__(self, question_id: str, message: str) -> None:
        self.question_id = question_id
        self.message = message
        super().__init__(f"AOE question '{question_id}' is misconfigured: {message}")
