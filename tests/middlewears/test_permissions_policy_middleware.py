import pytest
from fastapi.testclient import TestClient

from ash_utils.middlewares import PermissionsPolicy


def test__permissions_policy_middleware__success(app):
    app.add_middleware(
        PermissionsPolicy,
        Option={
            "geolocation": ["src"],
            "camera": ["self"],
            "microphone": ["*"],
            "gyroscope": ["http://onliner.by"],
            "magnetometer": [],
        },
    )

    resp = TestClient(app).get("/")

    assert resp.headers.get("Permissions-Policy")


def test__permissions_policy_middleware__invalid_policy__ex_raised(app):
    app.add_middleware(PermissionsPolicy, Option={"asdf": []})
    with pytest.raises(ValueError):
        TestClient(app).get("/")


def test__permissions_policy_middleware__invalid_url__ex_raised(app):
    app.add_middleware(PermissionsPolicy, Option={"gyroscope": ["sftp://onliner.by"]})
    with pytest.raises(ValueError):
        TestClient(app).get("/")
