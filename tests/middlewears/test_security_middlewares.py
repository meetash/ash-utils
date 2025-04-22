from ash_utils.middlewares import configure_security_headers
from fastapi.testclient import TestClient


def test__security_middlewares__success(app):
    configure_security_headers(app)

    resp = TestClient(app).get("/")

    assert resp.headers.get("Content-Security-Policy")
    assert resp.headers.get("X-Content-Type-Options")
    assert resp.headers.get("Referrer-Policy")
    assert resp.headers.get("X-Frame-Options")
    assert resp.headers.get("Strict-Transport-Security")
    assert resp.headers.get("Permissions-Policy")
