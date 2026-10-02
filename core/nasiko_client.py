import re
from collections.abc import Mapping
from typing import Self
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from core.attacker import TargetRequestError

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
TARGET_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


def _validate_endpoint(target: str, endpoint: str) -> str:
    if not TARGET_NAME_PATTERN.fullmatch(target):
        raise ValueError(f"invalid Nasiko sandbox target name: {target!r}")
    if not endpoint or endpoint != endpoint.strip():
        raise ValueError(f"endpoint for {target!r} must be an absolute local URL")
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"invalid endpoint URL for {target!r}") from exc
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in LOCAL_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError(
            f"endpoint for {target!r} must use HTTP(S) on localhost or a loopback IP"
        )
    return endpoint


def _extract_text(result: object) -> str:
    if not isinstance(result, dict):
        raise TargetRequestError("Nasiko A2A response has no result object")

    task = result.get("task")
    if isinstance(task, dict):
        artifacts = task.get("artifacts")
        if isinstance(artifacts, list):
            artifact_text: list[str] = []
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                parts = artifact.get("parts")
                if isinstance(parts, list):
                    text = "".join(
                        part["text"]
                        for part in parts
                        if isinstance(part, dict)
                        and isinstance(part.get("text"), str)
                    )
                    if text:
                        artifact_text.append(text)
            if artifact_text:
                return "\n".join(artifact_text)

        status = task.get("status")
        message = status.get("message") if isinstance(status, dict) else None
        if isinstance(message, dict):
            parts = message.get("parts")
            if isinstance(parts, list):
                text = "".join(
                    part["text"]
                    for part in parts
                    if isinstance(part, dict)
                    and isinstance(part.get("text"), str)
                )
                if text:
                    return text

    message = result.get("message")
    if isinstance(message, dict):
        parts = message.get("parts")
        if isinstance(parts, list):
            text = "".join(
                part["text"]
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
            if text:
                return text

    raise TargetRequestError("Nasiko A2A response contains no text output")


class NasikoClient:
    """A2A 1.0 client for explicitly supplied local Nasiko proxy endpoints."""

    def __init__(
        self,
        endpoints: Mapping[str, str],
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not endpoints:
            raise ValueError("at least one local Nasiko endpoint is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._endpoints = {
            target: _validate_endpoint(target, endpoint)
            for target, endpoint in endpoints.items()
        }
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

    async def send(self, target: str, payload: str) -> str:
        try:
            endpoint = self._endpoints[target]
        except KeyError as exc:
            raise TargetRequestError(f"unknown Nasiko sandbox target: {target}") from exc

        request_id = str(uuid4())
        body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "SendMessage",
            "params": {
                "message": {
                    "messageId": str(uuid4()),
                    "contextId": str(uuid4()),
                    "role": "ROLE_USER",
                    "parts": [{"text": payload}],
                }
            },
        }
        try:
            response = await self._client.post(
                endpoint,
                json=body,
                headers={"A2A-Version": "1.0"},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TargetRequestError("Nasiko A2A request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise TargetRequestError(
                f"Nasiko A2A request returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise TargetRequestError("Nasiko A2A request failed") from exc

        try:
            response_body = response.json()
        except ValueError as exc:
            raise TargetRequestError("Nasiko returned invalid JSON") from exc
        if not isinstance(response_body, dict):
            raise TargetRequestError("Nasiko returned an invalid JSON-RPC response")
        if (
            response_body.get("jsonrpc") != "2.0"
            or response_body.get("id") != request_id
        ):
            raise TargetRequestError("Nasiko returned a mismatched JSON-RPC response")

        error = response_body.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            raise TargetRequestError(f"Nasiko A2A request returned JSON-RPC error {code}")
        return _extract_text(response_body.get("result"))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        await self.aclose()
