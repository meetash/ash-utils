from enum import StrEnum

from loguru import logger
from pydantic import BaseModel, Field

DEFAULT_LOG_MESSAGE = "New support ticket"


class LogLevel(StrEnum):
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PriorityLevel(StrEnum):
    """Constants that map to the priority levels in Zendesk."""

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class TicketType(StrEnum):
    """Constants that map to the ticket types in Zendesk."""

    ESCALATE_ONCALL_EVENT_TO_OPS = "escalate-oncall-event-to-ops"
    ESCALATE_LAB_EVENT_KIT_ISSUE = "escalate-lab-event-kit-issue"


class SupportTicketDTO(BaseModel):
    kit_id: str
    ticket_type: TicketType
    subject: str
    message_body: str
    custom_fields: dict = Field(default_factory=dict)
    partner_id: str | None = None
    priority: PriorityLevel = PriorityLevel.P3


def create_support_ticket(
    message: str = DEFAULT_LOG_MESSAGE,
    *,
    ticket_data: SupportTicketDTO,
    log_level: LogLevel = LogLevel.ERROR,
) -> None:
    """This function logs a message along with a support ticket data using Loguru.
    The ticket data is attached as an extra field for better log searching and analysis.

    Args:
        message: Descriptive message about the support ticket event.
        ticket_data: SupportTicketDTO containing all relevant ticket information.
        log_level: Severity level for the log entry (defaults to ERROR).
                  Must be one of the values from the LogLevel enum.

    Example:
        >>> ticket = SupportTicketDTO(
        ...     kit_id="AW12345678",
        ...     ticket_type=TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE,
        ...     partner_id="partner-123",
        ...     subject="Issue with kit processing",
        ...     message_body="Result is blocked by lab",
        ...     custom_fields={"lab_id": "123", "sample_type": "blood"},
        ... )
        >>> create_support_ticket("Some issue with the lab", ticket)

    """
    logger.log(log_level, message, support_ticket_data=ticket_data.model_dump(mode="json"))
