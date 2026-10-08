import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core import loop
from core.nasiko_client import NasikoClient


class SafeResponseClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def send(self, target: str, payload: str) -> str:
        self.calls.append((target, payload))
        return "No private information disclosed."


class FailingClient:
    async def send(self, target: str, payload: str) -> str:
        raise RuntimeError("SECRET-CANARY-PRIVATE-EXCEPTION")


@pytest.fixture
def isolated_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(loop, "RUNS_DIR", runs_dir)
    return runs_dir


def test_post_runs_starts_async_run_and_status_and_report_are_available(
    isolated_runs: Path,
) -> None:
    sandbox_client = SafeResponseClient()
    app = create_app(client=sandbox_client)

    with TestClient(app) as client:
        response = client.post("/runs", json={"target": "calendar_assistant", "rounds": 0})
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status_response = client.get(f"/runs/{run_id}")
            assert status_response.status_code == 200
            if status_response.json()["status"] != "running":
                break
            time.sleep(0.01)

        assert status_response.json()["status"] == "done"
        assert status_response.json()["progress"]["run_id"] == run_id

        report_response = client.get(f"/runs/{run_id}/report")
        assert report_response.status_code == 200
        assert report_response.json()["run_id"] == run_id
        assert report_response.json()["status"] == "ok"

    assert sandbox_client.calls
    assert all(target == "calendar_assistant" for target, _ in sandbox_client.calls)
    assert (isolated_runs / run_id / "summary.json").is_file()


@pytest.mark.parametrize(
    ("payload", "expected_detail"),
    [
        ({"target": "missing_target", "rounds": 0}, "unknown sandbox target"),
        ({"target": "../calendar_assistant", "rounds": 0}, "lowercase identifier"),
        ({"target": "calendar_assistant", "rounds": 11}, "less than or equal to 10"),
        ({"target": "calendar_assistant", "rounds": True}, "valid integer"),
        ({"target": "calendar_assistant", "rounds": 0, "extra": True}, "extra"),
    ],
)
def test_post_runs_rejects_invalid_requests(
    isolated_runs: Path,
    payload: dict[str, object],
    expected_detail: str,
) -> None:
    with TestClient(create_app()) as client:
        response = client.post("/runs", json=payload)

    assert response.status_code == 422
    assert expected_detail in response.text
    assert not isolated_runs.exists()


def test_run_status_and_report_return_not_found_for_unknown_or_unsafe_ids(
    isolated_runs: Path,
) -> None:
    with TestClient(create_app()) as client:
        for endpoint in (
            "/runs/missing",
            "/runs/..%2Fsummary",
            "/runs/missing/report",
        ):
            response = client.get(endpoint)
            assert response.status_code == 404


def test_status_can_read_a_saved_run_after_process_restart(
    isolated_runs: Path,
) -> None:
    run_id = "saved-run"
    saved_dir = isolated_runs / run_id
    saved_dir.mkdir(parents=True)
    (saved_dir / "summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "target": "calendar_assistant",
                "status": "ok",
                "rounds": [],
                "stop_reason": "maximum rounds completed",
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_run_failure_is_reported_without_exposing_exception_contents(
    isolated_runs: Path,
) -> None:
    with TestClient(create_app(client=FailingClient())) as client:
        started = client.post(
            "/runs",
            json={"target": "calendar_assistant", "rounds": 0},
        )
        run_id = started.json()["run_id"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            response = client.get(f"/runs/{run_id}")
            if response.json()["status"] != "running":
                break
            time.sleep(0.01)

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert "RuntimeError" in response.json()["error"]
    assert "SECRET-CANARY" not in response.text
    report = json.loads(
        (isolated_runs / run_id / "summary.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "error"
    assert "SECRET-CANARY" not in json.dumps(report)


def test_a2a_agent_starts_the_same_async_loop_and_returns_run_id(
    isolated_runs: Path,
) -> None:
    async def run() -> None:
        sandbox_client = SafeResponseClient()
        app = create_app(client=sandbox_client)
        endpoint = "http://localhost:8000/"
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://localhost:8000",
        ) as http_client:
            async with NasikoClient(
                {"calendar_assistant": endpoint},
                transport=transport,
            ) as a2a_client:
                response_text = await a2a_client.send(
                    "calendar_assistant",
                    json.dumps({"target": "calendar_assistant", "rounds": 0}),
                )
            assert "Started red-team run " in response_text
            run_id = response_text.split("Started red-team run ", 1)[1].split()[0]

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                response = await http_client.get(f"/runs/{run_id}")
                assert response.status_code == 200
                if response.json()["status"] != "running":
                    break
                await asyncio.sleep(0.01)

            assert response.json()["status"] == "done"
            report = await http_client.get(f"/runs/{run_id}/report")
            assert report.json()["run_id"] == run_id
            assert sandbox_client.calls

    asyncio.run(run())


def test_a2a_agent_rejects_non_json_input(isolated_runs: Path) -> None:
    async def run() -> str:
        transport = httpx.ASGITransport(app=create_app())
        async with NasikoClient(
            {"calendar_assistant": "http://localhost:8000/"},
            transport=transport,
        ) as client:
            return await client.send("calendar_assistant", "run a calendar test")

    response = asyncio.run(run())

    assert "valid JSON" in response
    assert not isolated_runs.exists()
