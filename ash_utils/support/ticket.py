import typing as t
from dataclasses import dataclass, asdict
from enum import StrEnum

from loguru import logger


class LogLevel(StrEnum):
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class SupportTicketDTO:
    kit_id: str
    issue_type: str
    partner_id: str | None = None
    message: str | None = None
    custom_fields: dict[str, t.Any] | None = None


def create_support_ticket(message: str, ticket_data: SupportTicketDTO, log_level: LogLevel = LogLevel.ERROR):
    """
    This function logs a message along with a support ticket data using Loguru.
    The ticket data is attached as an extra field for better log searching and analysis.

    Args:
        message: Descriptive message about the support ticket event.
        ticket_data: SupportTicketDTO containing all relevant ticket information.
        log_level: Severity level for the log entry (defaults to ERROR).
                  Must be one of the values from the LogLevel enum.

    Example:
        >>> ticket = SupportTicketDTO(
        ...     kit_id="AW12345678",
        ...     issue_type="kit-issue",
        ...     message="Result is blocked by lab"
        ... )
        >>> create_support_ticket("Some issue with the lab", ticket)
    """
    logger.log(log_level, message, support_ticket_data=asdict(ticket_data))
