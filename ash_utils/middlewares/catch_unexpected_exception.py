import json
import re
from typing import cast

from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.types import ASGIApp, Receive


class CatchUnexpectedExceptionsMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        response_error_message: str,
        response_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        context_keys: list[str] | None = None,
    ):
        self.app = app
        self.response_error_message = response_error_message
        self.response_status_code = response_status_code
        self.context_keys = context_keys or []

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":  # pragma: no cover
            await self.app(scope, receive, send)
            return

        receive_proxy = ReceiveProxy(receive=receive)

        try:
            await self.app(scope, cast(Receive, receive_proxy), send)
        except Exception:
            request = Request(scope, cast(Receive, receive_proxy))
            context = await self._extract_request_info(request, receive_proxy)
            with logger.contextualize(**context):
                logger.exception(f"Unexpected exception. Url: {request.url}")
            response = JSONResponse(
                status_code=self.response_status_code,
                content={"detail": self.response_error_message},
            )
            await response(scope, receive, send)
            return

    async def _extract_request_info(self, request: Request, receive_proxy: "ReceiveProxy") -> dict[str, str]:
        """
        Extracts specified keys from the request data or query parameters.

        Args:
            request: The incoming request object.

        Returns:
            A dictionary containing the extracted key-value pairs.
        """
        try:
            body = await self._get_request_body(request, receive_proxy)
            data = json.loads(body)
        except Exception:
            data = cast(dict, request.query_params)

        context = {}
        for key in self.context_keys:
            value = _find_key_in_dict(data, key)
            if value is not None:
                context[_to_snake(key)] = value
        return context

    async def _get_request_body(self, request: Request, receive_proxy: "ReceiveProxy") -> bytes:
        """
        Returns the request body, either from the cache or by reading from the stream.
        This is necessary because the request body can only be read once.

        Args:
            request: The incoming request object.
            receive_proxy: The proxy object to handle the request body.
        """

        if not receive_proxy.has_body():
            logger.debug("Request body not cached, consuming it now.")
            return await request.body()

        logger.debug("Request body already cached, using cached value.")
        return receive_proxy.cached_body


def _find_key_in_dict(data: dict, key: str) -> str | None:
    """
    Finds the value of a specified key in a nested dictionary.

    Args:
        data: The dictionary to search.
        key: The key to find.

    Returns:
        The value associated with the key, or None if not found.
    """
    if key in data:
        return data[key]
    for value in data.values():
        if isinstance(value, dict):
            found = _find_key_in_dict(value, key)
            if found is not None:
                return found
    return None


def _to_snake(camel: str) -> str:
    """Convert a PascalCase, camelCase, or kebab-case string to snake_case.

    Args:
        camel: The string to convert.

    Returns:
        The converted string in snake_case.
    """
    # Handle the sequence of uppercase letters followed by a lowercase letter
    snake = re.sub(r"([A-Z]+)([A-Z][a-z])", lambda m: f"{m.group(1)}_{m.group(2)}", camel)
    # Insert an underscore between a lowercase letter and an uppercase letter
    snake = re.sub(r"([a-z])([A-Z])", lambda m: f"{m.group(1)}_{m.group(2)}", snake)
    # Insert an underscore between a digit and an uppercase letter
    snake = re.sub(r"([0-9])([A-Z])", lambda m: f"{m.group(1)}_{m.group(2)}", snake)
    # Insert an underscore between a lowercase letter and a digit
    snake = re.sub(r"([a-z])([0-9])", lambda m: f"{m.group(1)}_{m.group(2)}", snake)
    # Replace hyphens with underscores to handle kebab-case
    snake = snake.replace("-", "_")
    return snake.lower()


class ReceiveProxy:
    """Class that caches the request body so that it can be used later."""

    def __init__(self, receive: Receive):
        self._receive = receive
        self.cached_body = b""
        self._consumed = False

    async def __call__(self):
        message = await self._receive()
        if message["type"] == "http.request":
            chunk = message.get("body", b"")
            self.cached_body += chunk
            if not message.get("more_body", False):
                self._consumed = True
        return message

    def has_body(self) -> bool:
        """Check if the body has been consumed."""
        return self._consumed
