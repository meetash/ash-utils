import json

import sentry_sdk
from loguru import logger
from nested_lookup import nested_update
from sentry_sdk.integrations.loguru import LoguruIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, DEFAULT_PII_DENYLIST, EventScrubber
from sentry_sdk.types import Event

from ash_utils.helpers.constants import KEYS_TO_FILTER, REDACTION_STRING, SENSITIVE_DATA_FLAG, LoguruConfigs


def redact_logentry(event: Event) -> Event:
    """Redacts sensitive errors from the log entry before sending to Sentry."""

    if "logentry" in event:
        logentry_string = json.dumps(event["logentry"])
        extra = event.get("extra", {}).get("extra", {})

        if SENSITIVE_DATA_FLAG in logentry_string:
            event["logentry"]["message"] = f"REDACTED SENSITIVE ERROR | {extra.get('kit_id')}"  # type: ignore[reportIndexIssue]
        else:
            for key in KEYS_TO_FILTER:
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


def redact_exception(event: Event) -> Event:
    """Redacts sensitive-tagged values or values of `keys_to_filter` in exception details."""

    for values in event.get("exception", {}).get("values", []):
        exception_value = values.get("value")
        if not exception_value:
            continue

        if SENSITIVE_DATA_FLAG in exception_value:
            values["value"] = REDACTION_STRING
            continue

        try:
            exception_value_dict = try_parse_json(exception_value)
            if exception_value_dict:
                for key in KEYS_TO_FILTER:
                    nested_update(
                        exception_value_dict,
                        key=key,
                        value=REDACTION_STRING,
                        in_place=True,
                    )
                values["value"] = json.dumps(exception_value_dict)
            elif any(key in exception_value for key in KEYS_TO_FILTER):
                values["value"] = REDACTION_STRING
        except Exception as ex:
            logger.warning(
                f"Error encountered while redacting exception in Sentry issue. Sentry Event: {event}. Exception: {ex}"
            )
            return _remove_potential_exception_pii(event)
    return event


def _remove_potential_exception_pii(event: Event) -> Event:
    """Removes potential PII from the exception context in the Sentry event.
    Only runs if the `redact_exception` function fails
    """
    if "exception" in event and isinstance(event["exception"], dict):
        error_type = event["exception"]["values"][0]["type"]
        event["exception"] = {"values": [{}]}
        event["exception"]["values"][0]["type"] = error_type
    for key in ["contexts", "extra", "breadcrumbs", "tags"]:
        event[key] = {}
    return event


def before_send(event: Event, _hint) -> Event:
    """Processes an event before sending to Sentry by redacting sensitive information.

    Args:
        event (Event): The Sentry event to be scrubbed.
        _hint (dict): optional dictionary containing information about the event (unused).

    Returns:
        Event: The redacted Sentry event
    """
    event_log_redacted = redact_logentry(event)
    return redact_exception(event_log_redacted)


def initialize_sentry(
    sentry_dsn: str,
    environment: str,
    release: str,
    traces_sample_rate: float = 0.1,
    additional_integrations: list | None = None,
):
    """Initializes the Sentry SDK with the provided configuration.

    #### Params:
        `sentry_dsn` (str): The DSN for the Sentry project.
        `environment` (str): The environment for the Sentry project.
        `release` (str): The release version for the Sentry project.
        `traces_sample_rate` (float): OPTIONAL - The sample rate for Sentry traces;
            defaults to 0.1 if not passed.
        `additional_integrations` (list): OPTIONAL - Additional Sentry integrations to include;
            integrations defaults to LoguruIntegration() if not passed.

    #### Defaults Applied Automatically:
    - `include_local_variables`: Set to `False` for security reasons.
    - `send_default_pii`: Disabled (`False`) to avoid sending user PII.
    - `Event Scrubber`: Uses an internal scrubber to filter sensitive data;
        custom denylist added to Sentry default PII denylist.
    - `before_send`: function to sanitize logs/exceptions in case EventScrubber misses anything.

    Example usage:
    ```python
    from ash_utils.helpers.sentry import initialize_sentry
    from sentry_sdk.integrations.fastapi import FastAPIIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    initialize_sentry(
        dsn="your-dsn",
        environment="staging",
        release="1.2.3",
        traces_sample_rate=0.5,
        additional_integrations=[
            FastAPIIntegration(), SqlalchemyIntegration()
        ],
    )
    ```
    """

    default_integrations = [
        LoguruIntegration(
            event_format=LoguruConfigs.event_log_format,
            breadcrumb_format=LoguruConfigs.breadcrumb_log_format,
        ),
    ]
    if additional_integrations:
        default_integrations.extend(additional_integrations)

    # EventScrubber will merge pii_denylist with the default denylist at runtime
    custom_pii_denylist = KEYS_TO_FILTER + DEFAULT_PII_DENYLIST

    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=traces_sample_rate,
        integrations=default_integrations,
        release=release,
        environment=environment,
        include_local_variables=False,
        send_default_pii=False,
        event_scrubber=EventScrubber(
            recursive=True,
            denylist=DEFAULT_DENYLIST,
            pii_denylist=custom_pii_denylist,
        ),
        before_send=before_send,
    )
