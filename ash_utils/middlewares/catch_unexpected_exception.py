from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.types import ASGIApp


class CatchUnexpectedExceptionsMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        response_error_message: str,
        response_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        self.app = app
        self.response_error_message = response_error_message
        self.response_status_code = response_status_code

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":  # pragma: no cover
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        try:
            await self.app(scope, receive, send)
        except Exception:
            logger.exception(f"Unexpected exception. Url: {request.url}")
            response = JSONResponse(
                status_code=self.response_status_code,
                content={"detail": self.response_error_message},
            )
            await response(scope, receive, send)
            return
