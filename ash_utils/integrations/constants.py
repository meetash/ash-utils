# Sentry Constants
REDACTION_STRING = "REDACTED"
SENSITIVE_DATA_FLAG = "SENSITIVE"
KEYS_TO_FILTER = [
    "address",
    "address1",
    "address2",
    "city",
    "country",
    "dob",
    "email",
    "first_name",
    "firstName",
    "last_name",
    "lastName",
    "password",
    "patient_address1",
    "patient_address2",
    "patient_city",
    "patient_email",
    "patient_state",
    "patient_zip",
    "patientAddress1",
    "patientAddress2",
    "patientCity",
    "patientEmail",
    "patientState",
    "patientZip",
    "PatientZip",
    "phone",
    "searchKeyword",
    "search_keyword",
    "shipping_address1",
    "shipping_address2",
    "shipping_city",
    "shipping_email",
    "shipping_state",
    "shipping_zip",
    "shippingAddress1",
    "shippingAddress2",
    "shippingCity",
    "shippingEmail",
    "shippingState",
    "shippingZip",
    "state",
    "zip",
]


class LoguruConfigs:
    """
    Holds Loguru format methods and error code constant
    """

    ASH_SYSTEM_ERROR_CODE = "ash-system-error"

    @staticmethod
    def breadcrumb_log_format(_):
        """
        Returns the log string loguru needs to format the LogRecord
        object to generate a log message.

        :param _: The record object (UNUSED).
        """
        return "{message} | {extra}"

    @staticmethod
    def event_log_format(record):
        """
        Returns a formatted string for loguru events.
        :param record: The record object.
        """
        record["extra"]["code"] = record["extra"].get("code") or LoguruConfigs.ASH_SYSTEM_ERROR_CODE
        format_str = ""
        for key in ["code", "kit_id", "event"]:
            if value := record["extra"].get(key):
                format_str += f"[{value}] "

        format_str += "{message}"
        return format_str
