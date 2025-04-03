from typing import Self

from pydantic import BaseModel, Field, model_validator
from sentry_sdk.scrubber import DEFAULT_DENYLIST, DEFAULT_PII_DENYLIST


class SentryConfig(BaseModel):
    """
    Contains default configuration for Sentry Initiailization.
    This class is used to configure Sentry SDK with default settings.
    This class also sets default denylist and pii denylist by combining a
        custom keys_to_filter with the default denylist and pii denylist
        provided by Sentry SDK.
    """

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
    pii_denylist: list[str] = Field(
        default_factory=lambda: DEFAULT_PII_DENYLIST[:],
    )

    @model_validator(mode="after")
    def merge_sensitive_lists(self) -> Self:
        """
        Merges the default denylist and pii denylist with the custom keys_to_filter
        """
        self.denylist = sorted(set(self.denylist + self.keys_to_filter))
        self.pii_denylist = sorted(
            set(self.pii_denylist + self.keys_to_filter),
        )
        return self
