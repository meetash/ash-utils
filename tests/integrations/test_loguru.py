from io import StringIO
from unittest import TestCase

from ash_utils.integrations.loguru import sensitive_log_redactor
from loguru import logger


class SensitiveLogRedactorTestCase(TestCase):
    def setUp(self) -> None:
        logger.remove()
        logger.configure(patcher=sensitive_log_redactor)
        self.output = StringIO()
        logger.add(self.output, format="{message} | {extra}")

    def tearDown(self) -> None:
        logger.remove()

    def test_loguru_patcher_redacts_message_and_extra(self) -> None:
        logger.bind(
            patient_email="jane.doe@example.com",
            result_url="https://example.com/results/document.pdf?signature=secret",
            shipping_address={"address1": "100 Main St", "city": "New York"},
            results={"result_value": "positive", "reference_range": "negative"},
            api_key="secret-api-key",
            kit_id="KIT123",
            phone="555-123-4567",
        ).info(
            "Email john.doe@example.com url https://storage.example.com/result.pdf token=secret-token "
            "LabResultRow(id=1, value='positive')"
        )

        output = self.output.getvalue()

        self.assertIn("joh...@example.com", output)
        self.assertIn("jan...@example.com", output)
        self.assertIn("KIT123", output)
        self.assertIn("555-123-4567", output)
        self.assertIn("reference_range", output)

        self.assertNotIn("john.doe@example.com", output)
        self.assertNotIn("jane.doe@example.com", output)
        self.assertNotIn("https://storage.example.com", output)
        self.assertNotIn("https://example.com", output)
        self.assertNotIn("secret-token", output)
        self.assertNotIn("secret-api-key", output)
        self.assertNotIn("100 Main St", output)
        self.assertNotIn("positive", output)
        self.assertNotIn("LabResultRow", output)

    def test_loguru_patcher_redacts_exception_value(self) -> None:
        logger.remove()
        logger.configure(patcher=sensitive_log_redactor)
        logger.add(self.output, format="{message}\n{exception}", backtrace=False, diagnose=False)

        try:
            self._raise_sensitive_error()
        except ValueError:
            logger.exception("Failed while handling kit KIT123")

        output = self.output.getvalue()

        self.assertIn("Failed while handling kit KIT123", output)
        self.assertIn("joh...@example.com", output)
        self.assertNotIn("john.doe@example.com", output)
        self.assertNotIn("https://example.com", output)
        self.assertNotIn("positive", output)

    def _raise_sensitive_error(self) -> None:
        message = (
            "Failed for john.doe@example.com at https://example.com/result.pdf "
            "with {'results': {'result_value': 'positive'}}"
        )
        raise ValueError(message)
