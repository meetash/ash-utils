import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from loguru import logger
from starlette.types import ASGIApp

from ash_utils.constants import REQUEST_ID_HEADER_NAME, SESSION_ID_HEADER_NAME

request_id_var: ContextVar[str] = ContextVar("request_id_var", default="")
session_id_var: ContextVar[str] = ContextVar("session_id_var", default="")


class RequestIDMiddleware:
    """Middleware responsible for contextualizing logger with request_id and
    optionally session_id to help find all logs for a specific request.

    If the request and/or session headers are present in a request, they will
    be passed along in downstream requests. If the request header is not
    present, one will be generated and returned in the response, which the
    caller could use for correlation purposes. A session header is not
    automatically generated since it is assumed that the most upstream service
    will track that state.
    """

    def __init__(
        self,
        app: ASGIApp,
        request_id_header_name: str = REQUEST_ID_HEADER_NAME,
        session_id_header_name: str = SESSION_ID_HEADER_NAME,
    ) -> None:
        self.app = app
        self.request_id_header_name = request_id_header_name
        self.session_id_header_name = session_id_header_name

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":  # pragma: no cover
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        request_id = request.headers.get(self.request_id_header_name, str(uuid.uuid4()))
        session_id = request.headers.get(self.session_id_header_name)
        request_id_var.set(request_id)
        session_id_var.set(session_id or "")

        logger_context = {"request_id": request_id}
        if session_id:
            logger_context["session_id"] = session_id

        with logger.contextualize(**logger_context):
            logger.info(f"Request started | Path: {request.url.path}")
            start_time = time.monotonic()

            async def send_wrapper(message) -> None:
                if message["type"] == "http.response.start":
                    headers = message.setdefault("headers", [])
                    headers.append((self.request_id_header_name.encode(), request_id.encode()))
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                logger.info(
                    f"Request finished | Path: {request.url.path} | Duration: {time.monotonic() - start_time} s",
                )
