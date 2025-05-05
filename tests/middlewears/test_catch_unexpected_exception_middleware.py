from unittest.mock import patch

import pytest
from ash_utils.middlewares import CatchUnexpectedExceptionsMiddleware
from fastapi.testclient import TestClient


def test__catch_unexpected_exception__default_params__success(app):
    error_message = "Internal error"
    app.add_middleware(
        CatchUnexpectedExceptionsMiddleware, response_error_message=error_message, context_keys=["nothing"]
    )

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
        context_keys=["myParam"],
    )

    with patch("ash_utils.middlewares.catch_unexpected_exception.logger.contextualize") as mock_contextualize:
        resp = TestClient(app, raise_server_exceptions=False).get("/error", params={"myParam": "value"})
        mock_contextualize.assert_called_once_with(my_param="value")

    assert resp.status_code == status_code
    assert resp.json() == {"detail": error_message}


@pytest.mark.parametrize("read_body", [True, False])
def test__catch_unexpected_exception__context_data__success(app, read_body):
    error_message = "Internal error"
    status_code = 400
    app.add_middleware(
        CatchUnexpectedExceptionsMiddleware,
        response_status_code=status_code,
        response_error_message=error_message,
        context_keys=["nested"],
    )

    with patch("ash_utils.middlewares.catch_unexpected_exception.logger.contextualize") as mock_contextualize:
        resp = TestClient(app, raise_server_exceptions=False).post(
            "/error-json", params={"read_body": read_body}, json={"key": {"nested": "value"}}
        )
        mock_contextualize.assert_called_once_with(nested="value")

    assert resp.status_code == status_code
    assert resp.json() == {"detail": error_message}
