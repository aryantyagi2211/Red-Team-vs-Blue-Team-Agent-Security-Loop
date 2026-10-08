import asyncio
import json

import httpx
import pytest

from core.attacker import TargetRequestError
from core.nasiko_client import NasikoClient


def test_client_sends_a2a_10_and_extracts_task_artifact() -> None:
    captured: dict[str, object] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        body = json.loads(request.content)
        captured["body"] = body
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "task": {
                        "artifacts": [
                            {
                                "artifactId": "reply-1",
                                "parts": [{"text": "Local sandbox "}, {"text": "answer."}],
                            }
                        ]
                    }
                },
            },
        )

    async def call() -> str:
        async with NasikoClient(
            {"calendar_assistant": "http://localhost:8080/api/agents/id/"},
            auth_token="local-test-token",
            transport=httpx.MockTransport(respond),
        ) as client:
            return await client.send("calendar_assistant", "Safe local request")

    result = asyncio.run(call())

    assert result == "Local sandbox answer."
    request = captured["request"]
    assert isinstance(request, httpx.Request)
    assert request.url.path == "/api/agents/id"
    assert request.headers["A2A-Version"] == "1.0"
    assert request.headers["Authorization"] == "Bearer local-test-token"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["jsonrpc"] == "2.0"
    assert body["method"] == "SendMessage"
    message = body["params"]["message"]
    assert message["role"] == "ROLE_USER"
    assert message["parts"] == [{"text": "Safe local request"}]
    assert message["contextId"]
    assert message["messageId"]


def test_client_extracts_direct_message_text() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": json.loads(request.content)["id"],
                "result": {"message": {"parts": [{"text": "Direct reply"}]}},
            },
        )

    async def call() -> str:
        async with NasikoClient(
            {"memo_assistant": "http://127.0.0.1:8080/agent"},
            transport=httpx.MockTransport(respond),
        ) as client:
            return await client.send("memo_assistant", "request")

    assert asyncio.run(call()) == "Direct reply"


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com/api/agents/id",
        "http://localhost.evil/api/agents/id",
        "http://user:password@localhost/api/agents/id",
        "http://localhost/api/agents/id?unused=value",
        "http://localhost:99999/api/agents/id",
    ],
)
def test_client_rejects_nonlocal_or_unsafe_endpoints(endpoint: str) -> None:
    with pytest.raises(ValueError):
        NasikoClient({"calendar_assistant": endpoint})


def test_client_rejects_unknown_sandbox_target() -> None:
    async def call() -> None:
        async with NasikoClient(
            {"calendar_assistant": "http://localhost:8080/api/agents/id"}
        ) as client:
            await client.send("memo_assistant", "request")

    with pytest.raises(TargetRequestError, match="unknown Nasiko sandbox target"):
        asyncio.run(call())


def test_client_surfaces_http_failures_without_echoing_response_body() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="PRIVATE SERVER DETAIL")

    async def call() -> None:
        async with NasikoClient(
            {"calendar_assistant": "http://localhost:8080/api/agents/id"},
            transport=httpx.MockTransport(respond),
        ) as client:
            await client.send("calendar_assistant", "request")

    with pytest.raises(TargetRequestError, match="HTTP 503") as error:
        asyncio.run(call())
    assert "PRIVATE SERVER DETAIL" not in str(error.value)


def test_client_rejects_mismatched_jsonrpc_response_id() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": "wrong-id", "result": {}},
        )

    async def call() -> None:
        async with NasikoClient(
            {"calendar_assistant": "http://localhost:8080/api/agents/id"},
            transport=httpx.MockTransport(respond),
        ) as client:
            await client.send("calendar_assistant", "request")

    with pytest.raises(TargetRequestError, match="mismatched JSON-RPC"):
        asyncio.run(call())


def test_client_maps_jsonrpc_errors_without_echoing_server_details() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": json.loads(request.content)["id"],
                "error": {"code": -32000, "message": "PRIVATE SERVER DETAIL"},
            },
        )

    async def call() -> None:
        async with NasikoClient(
            {"calendar_assistant": "http://localhost:8080/api/agents/id"},
            transport=httpx.MockTransport(respond),
        ) as client:
            await client.send("calendar_assistant", "request")

    with pytest.raises(TargetRequestError, match="JSON-RPC error -32000") as error:
        asyncio.run(call())
    assert "PRIVATE SERVER DETAIL" not in str(error.value)


def test_client_maps_httpx_transport_errors() -> None:
    def respond(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("internal timeout detail")

    async def call() -> None:
        async with NasikoClient(
            {"calendar_assistant": "http://localhost:8080/api/agents/id"},
            transport=httpx.MockTransport(respond),
        ) as client:
            await client.send("calendar_assistant", "request")

    with pytest.raises(TargetRequestError, match="timed out"):
        asyncio.run(call())


def test_client_rejects_empty_endpoint_map_and_invalid_timeout() -> None:
    with pytest.raises(ValueError, match="at least one"):
        NasikoClient({})
    with pytest.raises(ValueError, match="positive"):
        NasikoClient({"calendar_assistant": "http://localhost:8080"}, timeout_seconds=0)


@pytest.mark.parametrize("auth_token", ["", " token", "token "])
def test_client_rejects_empty_or_padded_auth_token(auth_token: str) -> None:
    with pytest.raises(ValueError, match="auth_token"):
        NasikoClient(
            {"calendar_assistant": "http://localhost:8080"},
            auth_token=auth_token,
        )
