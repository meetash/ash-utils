import uuid
from http import HTTPMethod
from unittest import mock

import httpx
import pytest
from ash_utils.apis import BaseApi
from ash_utils.middlewares import request_id_var


async def test__base_api__success(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)

    response_mock = mock.Mock(status_code=200)
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client)

    resp = await api._send_request(method=HTTPMethod.POST, url="http://ashwelness.io", headers={}, body={}, params={})

    assert client.request.call_args[1]["method"] == HTTPMethod.POST
    assert client.request.call_args[1]["headers"] == {api.request_id_header_name: request_id}
    assert client.request.call_args[1]["json"] == {}
    assert client.request.call_args[1]["params"] == {}
    assert resp.status_code == 200


async def test__base_api__request_error__exception_raised(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)

    client = mock.AsyncMock(request=mock.AsyncMock(side_effect=httpx.RequestError(message="asdf")))

    api = BaseApi(client=client)

    with pytest.raises(api.ThirdPartyRequestError):
        await api._send_request(method=HTTPMethod.GET, url="http://ashwelness.io")


async def test__base_api__http_error__exception_raised(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)

    response_mock = mock.Mock(
        raise_for_status=mock.Mock(side_effect=httpx.HTTPStatusError(message="asdf", request=None, response=None))
    )
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client)

    with pytest.raises(api.ThirdPartyHttpStatusError):
        await api._send_request(method=HTTPMethod.GET, url="http://ashwelness.io")
