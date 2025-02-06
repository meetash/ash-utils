import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from loguru import logger
from starlette.types import ASGIApp

from ash_utils.constants import REQUEST_ID_HEADER_NAME

request_id_var: ContextVar[str] = ContextVar("request_id_var", default="")


class RequestIDMiddleware:
    """
    Middleware responsible for contextualizing logger with request_id that
    helps to find all logs for a specific request.
    `request_id` is returned in the "X-Request-ID" header of the response.
    """

    def __init__(self, app: ASGIApp, header_name: str = REQUEST_ID_HEADER_NAME):
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":  # pragma: no cover
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        request_id = request.headers.get(self.header_name, str(uuid.uuid4()))
        request_id_var.set(request_id)

        with logger.contextualize(request_id=request_id):
            logger.info(f"Request started | Path: {request.url.path}")
            start_time = time.monotonic()

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = message.setdefault("headers", [])
                    headers.append((self.header_name.encode(), request_id.encode()))
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                logger.info(
                    f"Request finished | Path: {request.url.path} | Duration: {time.monotonic() - start_time} s",
                )
