class LoguruConfigs:
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


class SentryConstants:
    REDACTION_STRING = "REDACTED"
    SENSITIVE_DATA_FLAG = "SENSITIVE"
