import pytest
from fastapi import FastAPI
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

    return app
