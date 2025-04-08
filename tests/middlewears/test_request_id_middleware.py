import uuid

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

    resp = TestClient(app).get("/", headers={"x-request-id": f"{request_id}"})

    assert resp.headers.get("x-request-id") == f"{request_id}"


def is_valid_uuid(uuid_to_test, version=4):
    try:
        uuid_obj = uuid.UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test
