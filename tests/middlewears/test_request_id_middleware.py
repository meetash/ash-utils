import uuid
from unittest.mock import patch

import pytest
from ash_utils.middlewares import RequestIDMiddleware
from fastapi.testclient import TestClient


def test__request_id_middleware__request_id_not_passed__success(app):
    app.add_middleware(RequestIDMiddleware)

    resp = TestClient(app).get("/")

    assert resp.headers.get("x-request-id")
    assert is_valid_uuid(resp.headers.get("x-request-id"))


def test__request_id_middleware__request_id_passed__success(app):
    request_id = uuid.uuid4()
    app.add_middleware(RequestIDMiddleware)

    with patch("ash_utils.middlewares.request_id.logger.contextualize") as mock_contextualize:
        resp = TestClient(app).get("/", headers={"x-request-id": f"{request_id}"})
        mock_contextualize.assert_called_once_with(request_id=f"{request_id}")

    assert resp.headers.get("x-request-id") == f"{request_id}"


def test__request_id_middleware__session_id_passed__added_to_context(app):
    request_id = uuid.uuid4()
    session_id = "session-123"
    app.add_middleware(RequestIDMiddleware)

    with patch("ash_utils.middlewares.request_id.logger.contextualize") as mock_contextualize:
        resp = TestClient(app).get(
            "/",
            headers={"x-request-id": f"{request_id}", "x-session-id": session_id},
        )
        mock_contextualize.assert_called_once_with(request_id=f"{request_id}", session_id=session_id)

    assert resp.headers.get("x-request-id") == f"{request_id}"


def test__request_id_middleware__custom_session_id_header__added_to_context(app):
    request_id = uuid.uuid4()
    session_id = "custom-session-123"
    app.add_middleware(RequestIDMiddleware, session_id_header_name="X-Custom-Session-ID")

    with patch("ash_utils.middlewares.request_id.logger.contextualize") as mock_contextualize:
        resp = TestClient(app).get(
            "/",
            headers={"x-request-id": f"{request_id}", "x-custom-session-id": session_id},
        )
        mock_contextualize.assert_called_once_with(request_id=f"{request_id}", session_id=session_id)

    assert resp.headers.get("x-request-id") == f"{request_id}"


def test__request_id_middleware__deprecated_header_name_kwarg__still_works(app):
    request_id = uuid.uuid4()
    app.add_middleware(RequestIDMiddleware, header_name="X-Custom-Request-ID")

    with pytest.deprecated_call(
        match="'header_name' is deprecated and will be removed in a future release. "
        "Use 'request_id_header_name' instead.",
    ):
        resp = TestClient(app).get("/", headers={"x-custom-request-id": f"{request_id}"})

    assert resp.headers.get("x-custom-request-id") == f"{request_id}"


def is_valid_uuid(uuid_to_test, version=4):
    try:
        uuid_obj = uuid.UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test
