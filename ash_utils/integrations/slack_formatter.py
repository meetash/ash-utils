from __future__ import annotations

import re
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from slack_logger import SlackFormatter

if TYPE_CHECKING:
    import logging

DEFAULT_REQUIRED_IDENTIFIERS = ("kit_id", "order_id", "partner_id")
DEFAULT_CONTEXT_KEYS = (
    "request_id",
    "event",
    "code",
    "path",
    "method",
    "status_code",
    "environment",
)

LEVEL_COLORS = {
    "TRACE": "#94a3b8",
    "DEBUG": "#64748b",
    "INFO": "good",
    "SUCCESS": "#14b8a6",
    "WARNING": "warning",
    "ERROR": "#e11d48",
    "CRITICAL": "danger",
}

SENSITIVE_KEY_PATTERN = re.compile(
    pattern=r"(password|token|secret|authorization|api[_-]?key|cookie|credential)",
    flags=re.IGNORECASE,
)
PYDANTIC_ERRORS_PATTERN = re.compile(r"\b(\d+)\s+validation error(?:s)?\s+for\b", flags=re.IGNORECASE)
PYDANTIC_FIELD_ERROR_PATTERN = re.compile(
    pattern=r"^([A-Za-z0-9_.\[\]-]+)\s*\n\s*([^\n]+)$",
    flags=re.MULTILINE,
)
TRACEBACK_ROOT_PATTERN = re.compile(r"^([A-Za-z_]\w*(?:Error|Exception|Warning)):\s+(.+)$", flags=re.MULTILINE)
MESSAGE_LINE_PATTERN = re.compile(r"^MESSAGE:\s*(.+)$", flags=re.MULTILINE)
TRACEBACK_START_MARKER = "Traceback (most recent call last):"


@dataclass(slots=True)
class SlackAttachmentFormatterConfig:
    service_name: str
    environment: str | None = None
    gcp_project_id: str | None = None
    gcp_resource_type: str = "cloud_run_revision"
    sentry_organization_slug: str | None = None
    required_identifiers: tuple[str, ...] = DEFAULT_REQUIRED_IDENTIFIERS
    context_keys: tuple[str, ...] = DEFAULT_CONTEXT_KEYS
    additional_context_keys: tuple[str, ...] = field(default_factory=tuple)
    max_message_length: int = 1200
    max_root_cause_length: int = 900
    max_trace_preview_length: int = 900
    max_pydantic_errors: int = 8
    include_traceback_button: bool = True


def truncate_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 1]}…"


def build_gcp_logs_explorer_url(
    *,
    project_id: str | None,
    service_name: str,
    resource_type: str,
    record_created: float | None,
    extra: dict[str, Any],
) -> str | None:
    if direct_url := first_non_empty(extra.get("logs_url"), extra.get("gcp_logs_url")):
        return str(direct_url)
    if not project_id:
        return None

    terms = [f'resource.type="{resource_type}"', f'resource.labels.service_name="{service_name}"']

    if record_created is not None:
        center = datetime.fromtimestamp(record_created, tz=UTC)
        lower_bound = center.replace(microsecond=0)
        upper_bound = lower_bound
        lower_bound = lower_bound.timestamp() - 10
        upper_bound = upper_bound.timestamp() + 10
        lower_iso = datetime.fromtimestamp(lower_bound, tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        upper_iso = datetime.fromtimestamp(upper_bound, tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        terms.append(f'timestamp>="{lower_iso}"')
        terms.append(f'timestamp<="{upper_iso}"')

    query = " AND ".join(terms)
    encoded_query = quote(query, safe="")
    return f"https://console.cloud.google.com/logs/query;query={encoded_query}?project={project_id}"


def build_sentry_issue_url(*, extra: dict[str, Any], organization_slug: str | None) -> str | None:
    if direct_url := first_non_empty(
        extra.get("sentry_url"),
        extra.get("sentry_event_url"),
        extra.get("sentry_issue_url"),
    ):
        return str(direct_url)

    sentry_event_id = extra.get("sentry_event_id")
    if not sentry_event_id or not organization_slug:
        return None

    event_query = quote(str(sentry_event_id), safe="")
    return f"https://sentry.io/organizations/{organization_slug}/issues/?query={event_query}"


def extract_root_cause(*, message: str, exception_text: str | None) -> str:
    body = exception_text or message
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return ""

    for line in lines:
        if "pydantic_core._pydantic_core.ValidationError" in line:
            return line

    traceback_matches = list(TRACEBACK_ROOT_PATTERN.finditer(body))
    if traceback_matches:
        last = traceback_matches[-1]
        return truncate_text(last.group(0), 900)

    return truncate_text(lines[-1], 900)


def extract_pydantic_errors(text: str, *, max_items: int) -> list[str]:
    if not PYDANTIC_ERRORS_PATTERN.search(text):
        return []

    matches = list(PYDANTIC_FIELD_ERROR_PATTERN.finditer(text))
    errors: list[str] = []
    for match in matches[:max_items]:
        field = match.group(1)
        reason = match.group(2)
        errors.append(f"`{field}` - {reason}")
    return errors


def first_non_empty(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        candidate = str(value).strip()
        if candidate:
            return candidate
    return None


def sanitize_extra(extra: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in extra.items():
        if SENSITIVE_KEY_PATTERN.search(key):
            continue
        safe[key] = value
    return safe


class SlackAttachmentFormatter(SlackFormatter):
    def __init__(self, config: SlackAttachmentFormatterConfig) -> None:
        super().__init__()
        self.config = config

    def format(self, record: logging.LogRecord) -> dict[str, Any]:
        level_name = record.levelname.upper()
        raw_extra = self._extract_extra(record=record)
        extra = sanitize_extra(extra=raw_extra)
        raw_message = record.getMessage()
        message, inline_traceback = self._extract_message_and_traceback(message=raw_message)
        message = truncate_text(value=message, max_length=self.config.max_message_length)
        exception_text = self._extract_exception_text(record=record) or inline_traceback
        root_cause = truncate_text(
            value=extract_root_cause(message=message, exception_text=exception_text),
            max_length=self.config.max_root_cause_length,
        )
        pydantic_errors = extract_pydantic_errors(
            text=exception_text or message,
            max_items=self.config.max_pydantic_errors,
        )
        primary_text_lines = [
            self._build_identifier_line(extra=extra),
        ]
        if root_cause and root_cause != message:
            primary_text_lines.extend(["*Root Cause*", f"```{root_cause}```"])
        else:
            primary_text_lines.extend(["*Root Cause*", f"```{message}```"])

        fields: list[dict[str, Any]] = []
        fields.append(
            {
                "title": "Message",
                "value": truncate_text(f"```{message}```", 1900),
                "short": False,
            },
        )
        if exception_text:
            traceback_preview = truncate_text(
                value=exception_text,
                max_length=self.config.max_trace_preview_length,
            )
            fields.append(
                {
                    "title": "Traceback",
                    "value": f"```{traceback_preview}```",
                    "short": False,
                },
            )
        if pydantic_errors:
            rendered_errors = "\n".join(f"- {error}" for error in pydantic_errors)
            fields.append(
                {
                    "title": "Pydantic Validation Errors",
                    "value": truncate_text(rendered_errors, 1900),
                    "short": False,
                },
            )

        links_text = self._build_links_text(extra=extra, exception_text=exception_text)
        if links_text:
            fields.append(
                {
                    "title": "Quick Links",
                    "value": links_text,
                    "short": False,
                },
            )

        return {
            "color": LEVEL_COLORS.get(level_name, "#64748b"),
            "author_name": level_name,
            "title": f"{self.config.service_name} - {level_name}",
            "ts": record.created,
            "text": "\n".join(primary_text_lines),
            "fields": fields,
            "mrkdwn_in": ["text", "fields"],
            "fallback": f"{self.config.service_name} {level_name}: {message}",
        }

    def _build_identifier_line(self, *, extra: dict[str, Any]) -> str:
        identifiers = []
        for key in self.config.required_identifiers:
            raw_value = first_non_empty(extra.get(key), "missing")
            identifiers.append(f"*{key}:* `{raw_value}`")
        return "────────────\n" + " | ".join(identifiers)

    @staticmethod
    def _extract_message_and_traceback(*, message: str) -> tuple[str, str | None]:
        traceback_text: str | None = None
        message_body = message
        if TRACEBACK_START_MARKER in message:
            message_body, traceback_text = message.split(TRACEBACK_START_MARKER, 1)
            traceback_text = f"{TRACEBACK_START_MARKER}{traceback_text}".strip()

        message_line_matches = MESSAGE_LINE_PATTERN.findall(message_body)
        if message_line_matches:
            return message_line_matches[-1].strip(), traceback_text

        stripped_lines = [line.strip() for line in message_body.splitlines() if line.strip()]
        if stripped_lines:
            return stripped_lines[-1], traceback_text
        return "", traceback_text

    def _build_context_text(self, *, extra: dict[str, Any]) -> str:
        context_pairs = []
        ordered_keys = (*self.config.context_keys, *self.config.additional_context_keys)
        for key in ordered_keys:
            value = first_non_empty(extra.get(key))
            if value:
                context_pairs.append(f"*{key}:* `{value}`")
        if self.config.environment:
            context_pairs.append(f"*environment:* `{self.config.environment}`")
        timestamp = datetime.now(tz=UTC).isoformat(timespec="seconds")
        context_pairs.append(f"*rendered_at:* `{timestamp}`")
        return " | ".join(context_pairs)

    def _build_links_text(self, *, extra: dict[str, Any], exception_text: str | None) -> str:
        link_values: list[str] = []
        if (self.config.environment or "").lower() == "local":
            return ""
        logs_url = build_gcp_logs_explorer_url(
            project_id=self.config.gcp_project_id,
            service_name=self.config.service_name,
            resource_type=self.config.gcp_resource_type,
            record_created=extra.get("created"),
            extra=extra,
        )
        if logs_url:
            link_values.append(f"<{logs_url}|Open Logs>")

        sentry_url = build_sentry_issue_url(extra=extra, organization_slug=self.config.sentry_organization_slug)
        if sentry_url:
            link_values.append(f"<{sentry_url}|Open Sentry>")

        if self.config.include_traceback_button and exception_text and logs_url:
            link_values.append(f"<{logs_url}|View Full Trace>")

        return " | ".join(link_values[:3])

    @staticmethod
    def _extract_extra(*, record: logging.LogRecord) -> dict[str, Any]:
        default_keys = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "time",
        }
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in default_keys and not key.startswith("_") and value is not None
        }
        for nested_key in ("extra", "context"):
            nested_values = extra.get(nested_key)
            if isinstance(nested_values, dict):
                for key, value in nested_values.items():
                    if key in default_keys or key.startswith("_") or value is None:
                        continue
                    extra[key] = value
                del extra[nested_key]
        extra["created"] = record.created
        return extra

    @staticmethod
    def _extract_exception_text(*, record: logging.LogRecord) -> str | None:
        if record.exc_info:
            return "".join(traceback.format_exception(*record.exc_info))
        exc_text = getattr(record, "exc_text", None)
        return str(exc_text) if exc_text else None
