# ash-utils

Python library containing common utilities used across various ASH projects.

## Features

1. **CatchUnexpectedExceptionsMiddleware** - Global exception handler for unexpected errors
2. **RequestIDMiddleware** - Request ID tracking for improved logging and tracing
3. **BaseApi** - Base HTTP client with built-in error handling and request ID propagation
4. **configure_security_headers** - Function provides a pre-configured security header setup for FastAPI applications following security best practices.
5. **Initialize Sentry** - Function to initialize Sentry for error tracking and proper PII sanitization in a project.
6. **Support Ticket** - Standardized support ticket creation and logging functionality.

## Installation

### PyPi

```shell
pip install ashwelness-utils

# OR

poetry add ashwelness-utils
```

### From github
In order to install Ash DAL directly from GitHub repository, run:
```shell
pip install git+https://github.com/meetash/ash-utils.git@main

# OR

poetry add git+https://github.com/meetash/ash-utils.git@main
```

### Usage
1. CatchUnexpectedExceptionsMiddleware

*Purpose:* Catch all unexpected exceptions and return a standardized error response.

```python
from fastapi import FastAPI
from ash_utils.middlewares import CatchUnexpectedExceptionsMiddleware

app = FastAPI()

# Add middleware with custom error message
app.add_middleware(
    CatchUnexpectedExceptionsMiddleware,
    response_error_message="Internal server error",
    response_status_code=500
)

@app.get("/")
async def root():
    # This exception will be caught by the middleware
    raise ValueError("Something went wrong")
```

2. RequestIDMiddleware

*Purpose:* Add request ID tracking to headers and logs for better request correlation.

```python
from fastapi import FastAPI
from ash_utils.middlewares import RequestIDMiddleware

app = FastAPI()

# Add middleware with default header name (X-Request-ID)
app.add_middleware(RequestIDMiddleware)

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

Example Request/Response:

```http
GET / HTTP/1.1
Host: localhost:8000
X-Request-ID: 123e4567-e89b-12d3-a456-426614174000

HTTP/1.1 200 OK
X-Request-ID: 123e4567-e89b-12d3-a456-426614174000
```

3. BaseApi (HTTP Client)

*Purpose:* Make HTTP requests with automatic error handling and request ID propagation.

```python
from http import HTTPMethod
from urllib.parse import urljoin

from ash_utils.apis.base_api import BaseApi
from httpx import AsyncClient
from py_cachify import cached

import constants
from domain.entities.common import PartnerConfigEntity


class ClientManagementServiceApi(BaseApi):
    PARTNER_PATH = "/api/v1/partners/{partner_id}"

    def __init__(self, url: str, api_key: str, client: AsyncClient):
        self.token = api_key
        self.base_url = url
        self.headers = {"x-api-key": api_key}
        super().__init__(client=client)

    @cached(key=constants.PARTNER_CONFIG_CACHE_KEY, ttl=constants.PARTNER_CONFIG_CACHE_TTL)
    async def get_partner_config(self, partner_id: str) -> PartnerConfigEntity:
        url = urljoin(self.base_url, self.PARTNER_PATH.format(partner_id=partner_id))

        response = await self._send_request(
            method=HTTPMethod.GET,
            url=url,
            headers=self.headers,
        )

        response_data = response.json()

        return PartnerConfigEntity(**response_data)

```

4. Security Headers Configuration

*Purpose:* This function provides a pre-configured security header setup for FastAPI applications following security best practices.

```python
from fastapi import FastAPI
from ash_utils.middlewares import configure_security_headers

app = FastAPI()
configure_security_headers(app)

@app.get("/")
async def root():
    return {"message": "Hello Secure World!"}
```

The configure_security_headers function adds these security middlewares with safe defaults:
- Content Security Policy (CSP)
- X-Content-Type-Options
- Referrer-Policy
- X-Frame-Options
- HTTP Strict Transport Security (HSTS)
- Permissions-Policy


### Configuration
Middleware Configuration Options:
- CatchUnexpectedExceptionsMiddleware
    - `response_error_message`: Error message to return to clients
    - `response_status_code`: HTTP status code to return (default: 500)
- RequestIDMiddleware
  - `header_name`: Custom header name for request ID (default: X-Request-ID)
- BaseApi Configuration
  - `request_id_header_name`: Header name for request ID propagation (default: X-Request-ID)


### Error Handling
The BaseApi class provides two custom exceptions:

- `ThirdPartyRequestError`: For network-level errors
- `ThirdPartyHttpStatusError`: For HTTP 4xx/5xx responses


### Best Practices
- Add CatchUnexpectedExceptionsMiddleware first in the middleware chain
- Configure a meaningful error message for production environments
- Use the BaseApi for all external API calls to ensure consistent error handling

5. Sentry Initialization

*Purpose*: A standard initialization of Sentry for error tracking and proper PII sanitization across projects.

```python
from ash_utils.integrations.sentry import initialize_sentry

initialize_sentry(
    # with all defaults
    dsn="https://your-sentry-dsn",
    environment="production",
    release="1.0.0",
)

initialize_sentry(
    # with custom sample rate and additional integrations
    dsn="https://your-sentry-dsn",
    environment="staging",
    release="1.0.0",
    traces_sample_rate=0.4,
    additional_integrations=[FastAPIIntegration(), SqlalchemyIntegration()]
)
```
This implementation abstracts away much of the boilerplate code required to initialize Sentry in a project. It also ensures that PII is properly sanitized in the logs and error messages. A user will be required to pass the Sentry DSN, environment, and release version to the function, while the traces sample rate is optional but set to 0.1 by default. The function also sets up the logging integration with Sentry, so all logs will be santized and sent to Sentry as well. The helper function accepts the following parameters:
- `dsn`: The Sentry DSN for your project.
- `environment`: The environment in which your application is running (e.g., production, staging).
- `release`: The release version of your application.
- `traces_sample_rate`: The sample rate for traces (default is 0.1).
- `additional_integrations`: A list of additional Sentry integrations to include (optional) -- Loguru integration is included by default.

*NOTE* You may choose to intialize Sentry yourself if you want to use a different configuration or if you want to use a different logging library. However, if you do so it is important to ensure that PII is properly sanitized in the logs and error messages. Make sure to import the `before_send` function from the helper module and use it in your Sentry configuration. The `before_send` function is responsible for sanitizing PII in the logs and error messages. It will remove any sensitive information from the logs and error messages before they are sent to Sentry.
- `before_send`: A function that is called before sending the event to Sentry. It can be used to modify the event or filter it out. The default implementation will sanitize PII in the logs and error messages.
- `KEYS_TO_FILTER`: A custom list of keys to filter out from the event data. This is used to remove sensitive information from the logs and error messages before they are sent to Sentry. It is recommended to use this (or your own list) to extend the default Sentry DEFAULT_PII_DENYLIST which filters only the following keys: [`x_forwarded_for`, `x_real_ip`, `ip_address`, `remote_addr`]

An example implementation of this approach would look like this:
```python
from ash_utils.integrations.sentry import before_send, KEYS_TO_FILTER

import sentry_sdk
from sentry_sdk import EventScrubber, DEFAULT_PII_DENYLIST, DEFAULT_DENYLIST
from sentry_sdk.integrations.logging import LoguruIntegration

custom_pii_denylist = KEYS_TO_FILTER + DEFAULT_PII_DENYLIST

sentry_sdk.init(
    dsn="https://your-sentry-dsn",
    traces_sample_rate=0.1,
    integrations=[LoguruIntegration(
            event_format=LoguruConfigs.event_log_format,
            breadcrumb_format=LoguruConfigs.breadcrumb_log_format,
        )],
    release="1.0.0",
    environment="production",
    include_local_variables=False,
    send_default_pii=False,
    event_scrubber=EventScrubber(
        recursive=True,
        denylist=DEFAULT_DENYLIST,
        pii_denylist=custom_pii_denylist,
    ),
    before_send=before_send,
)
```

6. Support Ticket

*Purpose:* Standardized method for creating and logging support tickets across services.

```python
from ash_utils.support import create_support_ticket, LogLevel, SupportTicketDTO

# Create a support ticket DTO
ticket = SupportTicketDTO(
    kit_id="AW12345678",
    ticket_type="escalate-lab-event-kit-issue",
    partner_id="partner-123",
    subject="Issue with kit processing",
    message_body="Result is blocked by lab",
    custom_fields={"lab_id": "123", "sample_type": "blood"}
)

# Log the ticket with default ERROR level
create_support_ticket("Problem with kit processing", ticket)

# Or with a different log level
create_support_ticket(
    message="Non-critical issue with kit", 
    ticket_data=ticket, 
    log_level=LogLevel.WARNING
)
```

The support ticket functionality provides:
- Standardized ticket format with `SupportTicketDTO`
- Log level customization using the `LogLevel` enum
- Structured logging of ticket data for better searchability
- Seamless integration with Loguru for consistent log format
