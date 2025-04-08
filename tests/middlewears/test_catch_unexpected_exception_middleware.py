from ash_utils.middlewares import CatchUnexpectedExceptionsMiddleware
from fastapi.testclient import TestClient


def test__catch_unexpected_exception__default_params__success(app):
    error_message = "Internal error"
    app.add_middleware(CatchUnexpectedExceptionsMiddleware, response_error_message=error_message)

    resp = TestClient(app, raise_server_exceptions=False).get("/error")

    assert resp.status_code == 500
    assert resp.json() == {"detail": error_message}


def test__catch_unexpected_exception__success(app):
    error_message = "Internal error"
    status_code = 400
    app.add_middleware(
        CatchUnexpectedExceptionsMiddleware,
        response_status_code=status_code,
        response_error_message=error_message,
    )

    resp = TestClient(app, raise_server_exceptions=False).get("/error")

    assert resp.status_code == status_code
    assert resp.json() == {"detail": error_message}
