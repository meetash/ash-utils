# ash-utils

Python library containing common utilities used across various ASH projects.

## Features

1. **CatchUnexpectedExceptionsMiddleware** - Global exception handler for unexpected errors
2. **RequestIDMiddleware** - Request ID tracking for improved logging and tracing
3. **BaseApi** - Base HTTP client with built-in error handling and request ID propagation
4. **configure_security_headers** - Function provides a pre-configured security header setup for FastAPI applications following security best practices.
5. **Initialize Sentry** - Function to initialize Sentry for error tracking and proper PII sanitization in a project.

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
from ash_utils.helpers.sentry import initialize_sentry

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