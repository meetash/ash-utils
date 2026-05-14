import uuid
from http import HTTPMethod
from unittest import mock

import httpx
import pytest
from ash_utils.apis import BaseApi
from ash_utils.middlewares import request_id_var, session_id_var


async def test__base_api__success(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)
    session_id_var.set("")

    response_mock = mock.Mock(status_code=200)
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client)

    resp = await api._send_request(method=HTTPMethod.POST, url="http://ashwelness.io", headers={}, body={}, params={})

    assert client.request.call_args[1]["method"] == HTTPMethod.POST
    assert client.request.call_args[1]["headers"] == {api.request_id_header_name: request_id}
    assert client.request.call_args[1]["json"] == {}
    assert client.request.call_args[1]["params"] == {}
    assert resp.status_code == 200


async def test__base_api__success__with_data_instead_of_json(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)
    session_id_var.set("")

    response_mock = mock.Mock(status_code=200)
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client)

    resp = await api._send_request(
        method=HTTPMethod.POST, url="http://ashwelness.io", headers={}, data="<xml>data</xml>", params={}
    )

    assert client.request.call_args[1]["method"] == HTTPMethod.POST
    assert client.request.call_args[1]["headers"] == {api.request_id_header_name: request_id}
    assert client.request.call_args[1]["data"] == "<xml>data</xml>"
    assert client.request.call_args[1]["params"] == {}
    assert resp.status_code == 200


async def test__base_api__success__supports_positional_params(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)
    session_id_var.set("")

    response_mock = mock.Mock(status_code=200)
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client)
    params = {"user_id": "12"}

    resp = await api._send_request(HTTPMethod.GET, "http://ashwelness.io", None, None, params)

    assert client.request.call_args[1]["method"] == HTTPMethod.GET
    assert client.request.call_args[1]["headers"] == {api.request_id_header_name: request_id}
    assert client.request.call_args[1]["params"] == params
    assert client.request.call_args[1]["files"] is None
    assert resp.status_code == 200


async def test__base_api__success__with_files(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)
    session_id_var.set("")

    response_mock = mock.Mock(status_code=200)
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client)
    files = {"document": ("example.txt", b"file contents", "text/plain")}

    resp = await api._send_request(method=HTTPMethod.POST, url="http://ashwelness.io", headers={}, files=files)

    assert client.request.call_args[1]["method"] == HTTPMethod.POST
    assert client.request.call_args[1]["headers"] == {api.request_id_header_name: request_id}
    assert client.request.call_args[1]["files"] == files
    assert resp.status_code == 200


async def test__base_api__success__with_files_and_form_data(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)
    session_id_var.set("")

    response_mock = mock.Mock(status_code=200)
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client)
    data = {"metadata": "value"}
    files = {"document": ("example.txt", b"file contents", "text/plain")}

    resp = await api._send_request(
        method=HTTPMethod.POST,
        url="http://ashwelness.io",
        headers={},
        data=data,
        files=files,
    )

    assert client.request.call_args[1]["method"] == HTTPMethod.POST
    assert client.request.call_args[1]["headers"] == {api.request_id_header_name: request_id}
    assert client.request.call_args[1]["data"] == data
    assert client.request.call_args[1]["files"] == files
    assert resp.status_code == 200


async def test__base_api__request_error__exception_raised(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)
    session_id_var.set("")

    client = mock.AsyncMock(request=mock.AsyncMock(side_effect=httpx.RequestError(message="asdf")))

    api = BaseApi(client=client)

    with pytest.raises(api.ThirdPartyRequestError):
        await api._send_request(method=HTTPMethod.GET, url="http://ashwelness.io")


async def test__base_api__http_error__exception_raised(app):
    request_id = uuid.uuid4()
    request_id_var.set(request_id)
    session_id_var.set("")

    response_mock = mock.Mock(
        raise_for_status=mock.Mock(side_effect=httpx.HTTPStatusError(message="asdf", request=None, response=None))
    )
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client)

    with pytest.raises(api.ThirdPartyHttpStatusError):
        await api._send_request(method=HTTPMethod.GET, url="http://ashwelness.io")


async def test__base_api__session_id_present__header_is_forwarded(app):
    request_id = uuid.uuid4()
    session_id = "session-123"
    request_id_var.set(request_id)
    session_id_var.set(session_id)

    response_mock = mock.Mock(status_code=200)
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client)

    await api._send_request(method=HTTPMethod.POST, url="http://ashwelness.io", headers={}, body={}, params={})

    assert client.request.call_args[1]["headers"] == {
        api.request_id_header_name: request_id,
        api.session_id_header_name: session_id,
    }


async def test__base_api__custom_session_header_name__header_is_forwarded(app):
    request_id = uuid.uuid4()
    session_id = "custom-session-123"
    request_id_var.set(request_id)
    session_id_var.set(session_id)

    response_mock = mock.Mock(status_code=200)
    client = mock.AsyncMock(request=mock.AsyncMock(return_value=response_mock))

    api = BaseApi(client=client, session_id_header_name="X-Custom-Session-ID")

    await api._send_request(method=HTTPMethod.POST, url="http://ashwelness.io", headers={}, body={}, params={})

    assert client.request.call_args[1]["headers"] == {
        api.request_id_header_name: request_id,
        "X-Custom-Session-ID": session_id,
    }
