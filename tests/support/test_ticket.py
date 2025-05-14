import unittest
from unittest.mock import patch

from ash_utils.support import LogLevel, create_support_ticket, TicketType
from ash_utils.support.ticket import SupportTicketDTO, DEFAULT_LOG_MESSAGE


class CreateSupportTicketTestCase(unittest.TestCase):
    def test__support_ticket_dto__all_fields_provided__creates_with_proper_attributes(self):
        kit_id = "AW12345678"
        ticket_type = TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE
        partner_id = "partner-123"
        subject = "Sample Subject"
        message_body = "Result is blocked by lab"
        custom_fields = {"lab_id": "123", "sample_type": "blood"}

        ticket = SupportTicketDTO(
            kit_id=kit_id,
            ticket_type=ticket_type,
            partner_id=partner_id,
            subject=subject,
            message_body=message_body,
            custom_fields=custom_fields,
        )

        self.assertEqual(ticket.kit_id, kit_id)
        self.assertEqual(ticket.ticket_type, ticket_type)
        self.assertEqual(ticket.partner_id, partner_id)
        self.assertEqual(ticket.subject, subject)
        self.assertEqual(ticket.message_body, message_body)
        self.assertEqual(ticket.custom_fields, custom_fields)

    def test__support_ticket_dto__only_required_fields__optional_fields_are_none(self):
        kit_id = "AW12345678"
        ticket_type = TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE

        ticket = SupportTicketDTO(
            kit_id=kit_id,
            ticket_type=ticket_type,
            subject="Sample Subject",
            message_body="Result is blocked by lab",
        )

        self.assertEqual(ticket.kit_id, kit_id)
        self.assertEqual(ticket.ticket_type, ticket_type)
        self.assertIsNone(ticket.partner_id)
        self.assertEqual(ticket.custom_fields, {})
        self.assertEqual(ticket.priority, "p3")

    @patch("ash_utils.support.ticket.logger")
    def test__create_support_ticket__default_log_level__logs_with_error_level(self, mock_logger):
        message = "Problem with kit processing"
        ticket = SupportTicketDTO(
            kit_id="AW12345678",
            ticket_type=TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE,
            subject="Sample Subject",
            message_body="Result is blocked by lab",
        )

        create_support_ticket(message, ticket_data=ticket)

        mock_logger.log.assert_called_with(
            LogLevel.ERROR,
            message,
            support_ticket_data={
                "kit_id": "AW12345678",
                "ticket_type": TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE.value,
                "partner_id": None,
                "subject": "Sample Subject",
                "message_body": "Result is blocked by lab",
                "priority": "p3",
                "custom_fields": {},
            },
        )

    @patch("ash_utils.support.ticket.logger")
    def test__create_support_ticket__custom_log_level__logs_with_provided_level(self, mock_logger):
        message = "Non-critical issue with kit"
        ticket = SupportTicketDTO(
            kit_id="AW12345678",
            ticket_type=TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE,
            subject="Sample Subject",
            message_body="Result is blocked by lab",
        )

        create_support_ticket(message, ticket_data=ticket, log_level=LogLevel.WARNING)

        mock_logger.log.assert_called_with(
            LogLevel.WARNING,
            message,
            support_ticket_data={
                "kit_id": "AW12345678",
                "ticket_type": TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE.value,
                "partner_id": None,
                "subject": "Sample Subject",
                "message_body": "Result is blocked by lab",
                "priority": "p3",
                "custom_fields": {},
            },
        )

    @patch("ash_utils.support.ticket.logger")
    def test__create_support_ticket__full_ticket_data__logs_with_correct_data(self, mock_logger):
        message = "Problem with kit processing"
        ticket = SupportTicketDTO(
            kit_id="AW12345678",
            ticket_type=TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE,
            partner_id="partner-123",
            subject="Sample Subject",
            message_body="Result is blocked by lab",
            custom_fields={"lab_id": "123", "sample_type": "blood"},
        )

        create_support_ticket(message, ticket_data=ticket)

        expected_ticket_dict = {
            "kit_id": "AW12345678",
            "ticket_type": TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE.value,
            "partner_id": "partner-123",
            "subject": "Sample Subject",
            "message_body": "Result is blocked by lab",
            "priority": "p3",
            "custom_fields": {"lab_id": "123", "sample_type": "blood"},
        }

        mock_logger.log.assert_called_with(LogLevel.ERROR, message, support_ticket_data=expected_ticket_dict)

    @patch("ash_utils.support.ticket.logger")
    def test__create_support_ticket__message_is_not_passed__default_one_is_used(self, mock_logger):
        ticket = SupportTicketDTO(
            kit_id="AW12345678",
            ticket_type=TicketType.ESCALATE_LAB_EVENT_KIT_ISSUE,
            partner_id="partner-123",
            subject="Sample Subject",
            message_body="Result is blocked by lab",
            custom_fields={"lab_id": "123", "sample_type": "blood"},
        )

        create_support_ticket(ticket_data=ticket)
        mock_logger.log.assert_called_with(LogLevel.ERROR, DEFAULT_LOG_MESSAGE, support_ticket_data=ticket.model_dump(mode="json"))

    def test__log_level_enum__all_levels__matches_expected_values(self):
        self.assertEqual(LogLevel.TRACE, "TRACE")
        self.assertEqual(LogLevel.DEBUG, "DEBUG")
        self.assertEqual(LogLevel.INFO, "INFO")
        self.assertEqual(LogLevel.SUCCESS, "SUCCESS")
        self.assertEqual(LogLevel.WARNING, "WARNING")
        self.assertEqual(LogLevel.ERROR, "ERROR")
        self.assertEqual(LogLevel.CRITICAL, "CRITICAL")
