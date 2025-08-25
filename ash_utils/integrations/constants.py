from pydantic.alias_generators import to_snake

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
    "pdf",
    "to",
    "from",
    "sender",
]


class LoguruConfigs:
    """Holds Loguru format methods and error code constant."""

    ASH_SYSTEM_ERROR_CODE = "ash-system-error"

    @staticmethod
    def breadcrumb_log_format(_) -> str:
        """Returns the log string loguru needs to format the LogRecord
        object to generate a log message.

        :param _: The record object (UNUSED).
        """
        return "{message} | {extra}"

    @staticmethod
    def event_log_format(record, context_keys: list[str]) -> str:
        """Returns a formatted string for loguru events.
        :param record: The record object.
        """
        if "code" not in context_keys:
            context_keys.insert(0, "code")

        if "code" not in record["extra"] and (exception_info := record.get("exception")):
            exception = exception_info[1]
            record["extra"]["code"] = getattr(exception, "code", LoguruConfigs.ASH_SYSTEM_ERROR_CODE)
        else:
            record["extra"]["code"] = record["extra"].get("code") or LoguruConfigs.ASH_SYSTEM_ERROR_CODE

        format_str = ""
        for key in context_keys:
            if value := record["extra"].get(to_snake(key)):
                format_str += f"[{value}] "

        format_str += "{message}"
        return format_str
