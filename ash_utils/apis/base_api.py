import typing as t
from http import HTTPMethod

from httpx import AsyncClient, HTTPStatusError, RequestError, Response
from loguru import logger

from ash_utils import constants
from ash_utils.middlewares import request_id_var


class BaseApi:
    class ThirdPartyRequestError(Exception):
        def __init__(self, message: str) -> None:
            self.message = message

    class ThirdPartyHttpStatusError(Exception):
        def __init__(self, status_code: int, text: str, response: Response) -> None:
            self.status_code = status_code
            self.text = text
            self.response = response

    def __init__(self, client: AsyncClient, request_id_header_name: str = constants.REQUEST_ID_HEADER_NAME) -> None:
        self.client = client
        self.request_id_header_name = request_id_header_name

    async def _send_request(
        self,
        method: HTTPMethod,
        url: str,
        body: dict[str, t.Any] | t.Collection | None = None,
        data: t.Mapping[str, t.Any] | None = None,
        params: dict[str, t.Any] | None = None,
        headers: dict | None = None,
    ) -> Response:
        with logger.contextualize(url=url, method=method):
            if headers is None:
                headers = {self.request_id_header_name: request_id_var.get()}
            else:
                headers[self.request_id_header_name] = request_id_var.get()

            logger.info("Send request")

            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    json=body,
                    data=data,
                    params=params,
                    headers=headers,
                    follow_redirects=True,
                )
            except RequestError as ex:
                raise self.ThirdPartyRequestError(message=str(ex)) from ex

            try:
                response.raise_for_status()
            except HTTPStatusError as ex:
                raise self.ThirdPartyHttpStatusError(
                    status_code=response.status_code,
                    text=response.text,
                    response=response,
                ) from ex

            logger.info(f"Response received | {response.status_code=}")

            return response
