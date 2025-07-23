import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from loguru import logger


@pytest.fixture(scope="session", autouse=True)
def logger_mock():
    logger.remove()


@pytest.fixture()
def app():
    app = FastAPI()

    @app.get("/")
    async def root():
        return {"message": "Hello World"}

    @app.get("/error")
    async def root():
        raise Exception

    @app.post("/error-json")
    async def root(request: Request, read_body: bool = False):
        if read_body:
            await request.json()
        raise Exception

    return app


@pytest.fixture
def temp_files():
    """Create temporary file paths for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        heartbeat_file = Path(temp_dir) / "heartbeat"
        readiness_file = Path(temp_dir) / "ready"
        yield heartbeat_file, readiness_file
