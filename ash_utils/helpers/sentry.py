import json
from functools import partial
from typing import cast

import sentry_sdk
from loguru import logger
from loguru._defaults import LOGURU_FORMAT
from nested_lookup import nested_update
from pydantic import BaseModel, Field
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, DEFAULT_PII_DENYLIST, EventScrubber
from sentry_sdk.types import Event


class SentryConfig(BaseModel):
    redaction_string: str = "REDACTED"
    sensitive_data_flag: str = "SENSITIVE"
    keys_to_filter: list[str] = Field(
        default_factory=lambda: [
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
    )
    denylist: list[str] = Field(default_factory=lambda: DEFAULT_DENYLIST[:])
    pii_denylist: list[str] = Field(default_factory=lambda: DEFAULT_PII_DENYLIST[:])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.denylist = sorted(set(self.denylist + self.keys_to_filter))
        self.pii_denylist = sorted(set(self.pii_denylist + self.keys_to_filter))


def redact_logentry(event: Event, sentry_config: SentryConfig) -> Event:
    """Redacts sensitive errors from the log entry before sending to Sentry."""

    config = sentry_config
    keys_to_filter = config.keys_to_filter

    if "logentry" in event:
        logentry_string = json.dumps(event["logentry"])
        extra = event.get("extra", {}).get("extra", {})

        if config.sensitive_data_flag in logentry_string:
            event["logentry"]["message"] = f"REDACTED SENSITIVE ERROR | {extra.get('kit_id')}"  # type: ignore[reportIndexIssue]
        else:
            for key in keys_to_filter:
                if key in logentry_string:
                    event["logentry"]["message"] = f"REDACTED SENSITIVE ERROR | key: {key} | {extra.get('kit_id')}"  # type: ignore[reportIndexIssue]
                    break

    return event


def try_parse_json(data_string: str) -> dict | None:
    """Attempts to parse a string as JSON. Returns a dictionary if successful, otherwise None."""

    try:
        return json.loads(data_string.replace("'", '"'))
    except json.JSONDecodeError:
        return None


def redact_exception(event: Event, sentry_config: SentryConfig) -> Event | None:
    """Redacts sensitive-tagged values or values of keys_to_filter in exception details."""

    config = sentry_config
    keys_to_filter = config.keys_to_filter

    for values in event.get("exception", {}).get("values", []):
        exception_value = values.get("value")
        if not exception_value:
            continue

        if config.sensitive_data_flag in exception_value:
            values["value"] = config.redaction_string
            continue

        try:
            exception_value_dict = try_parse_json(exception_value)
            if exception_value_dict:
                for key in keys_to_filter:
                    nested_update(
                        exception_value_dict,
                        key=key,
                        value=config.redaction_string,
                        in_place=True,
                    )
                values["value"] = json.dumps(exception_value_dict)
            elif any(key in exception_value for key in keys_to_filter):
                values["value"] = config.redaction_string
        except Exception as ex:
            logger.warning(
                f"Error encountered while redacting exception in Sentry issue. Sentry Event: {event}. Exception: {ex}",
            )
            for key in ["exception", "contexts", "extra", "breadcrumbs", "tags"]:
                event.pop(key, None)  # type: ignore

    return event


def before_send(event: Event, _hint, sentry_config: SentryConfig) -> Event:
    """Processes an event before sending to Sentry by redacting sensitive information.

    Args:
        event (Event): The Sentry event to be scrubbed.
        _hint (dict): optional dictionary containing information about the event (unused).
        sentry_config (dict): a pydantic model of the Sentry configuration from the global config.

    Returns:
        Event: The redacted Sentry event
    """

    event_log_redacted = redact_logentry(event, sentry_config)
    return redact_exception(event_log_redacted, sentry_config)


def _log_format(_) -> str:
    return cast(str, LOGURU_FORMAT)


def initialize_sentry(
    sentry_dsn: str,
    environment: str,
    release: str,
    traces_sample_rate: float = 0.1,
):
    """Initializes the Sentry SDK with the provided configuration.

    #### Params:
        `sentry_dsn` (str): The DSN for the Sentry project.
        `traces_sample_rate` (float): The sample rate for Sentry traces;
            defaults to 0.1 if not passed.
        `environment` (str): The environment for the Sentry project.
        `release` (str): The release version for the Sentry project.

    #### Defaults Applied Automatically:
    - `Integrations`: Includes `FastApiIntegration()` and `LoguruIntegration()`.
    - `include_local_variables`: Set to `False` for security reasons.
    - `send_default_pii`: Disabled (`False`) to avoid sending user PII.
    - `Event Scrubber`: Uses an internal scrubber to filter sensitive data;
        custom denylist added to both Sentry default and PII denylist.
    - `before_send`: Pre-bound function to sanitize logs.

    Example usage:
    ```python
    initialize_sentry(
        dsn="your-dsn", traces_sample_rate=0.5, release="1.2.3", environment="staging"
    )
    ```
    """
    config = SentryConfig()
    prebound_before_send = partial(before_send, sentry_config=config)

    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=traces_sample_rate,
        integrations=(
            FastApiIntegration(),
            LoguruIntegration(
                event_format=_log_format,
                breadcrumb_format=_log_format,
            ),
        ),
        release=release,
        environment=environment,
        include_local_variables=False,
        send_default_pii=False,
        event_scrubber=EventScrubber(
            recursive=True,
            denylist=config.denylist,
            pii_denylist=config.pii_denylist,
        ),
        before_send=prebound_before_send,
    )
