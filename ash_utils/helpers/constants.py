from enum import StrEnum


class LoguruConstants(StrEnum):
    DEFAULT_LOGURU_FORMAT = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )


class SentryConstants(StrEnum):
    REDACTION_STRING = "REDACTED"
    SENSITIVE_DATA_FLAG = "SENSITIVE"
