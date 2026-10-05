import asyncio
import json

from fastapi.testclient import TestClient

from pokeagent_bench.cli import load_labels
from pokeagent_bench.dashboard import create_app
from pokeagent_bench.mcp_server import create_server
from pokeagent_bench.report import read_runs, summarize


def test_mcp_returns_native_image_and_same_retry_result(session, engine):
    async def check():
        server = create_server(session)
        tools = await server.list_tools()
        assert {tool.name for tool in tools} == {"observe", "act", "wait", "status", "read_notes", "write_notes"}
        first = await server.call_tool("wait", {"operation_id": "one", "frames": 2})
        second = await server.call_tool("wait", {"operation_id": "one", "frames": 2})
        assert first == second
        # The SDK can return content plus structuredContent as a tuple.
        blocks = first[0] if isinstance(first, tuple) else first
        assert any(block.type == "image" for block in blocks)
        assert any(block.type == "text" for block in blocks)
    asyncio.run(check())
    assert engine.frame == 2


def test_dashboard_only_exposes_read_routes(session, tmp_path):
    session.wait("one", 1)
    client = TestClient(create_app(tmp_path))
    assert client.get("/").status_code == 200
    rows = client.get("/api/runs").json()
    assert rows[0]["id"] == "run"
    assert "evidence" not in rows[0]
    assert client.get("/api/runs/run/screen").headers["content-type"] == "image/png"
    assert client.post("/api/runs/run/act", json={"button": "a"}).status_code == 404
    assert client.get("/api/runs/run/initial.state").status_code == 404


def test_label_import_is_allowlisted(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"maps": {"1": "Town"}, "events": {"secret": 1},
                                "moves": {"3": {"name": "Move", "damage": 99}}}))
    labels = load_labels(path)
    assert "events" not in labels
    assert labels["moves"]["3"] == "Move"
    assert "damage" not in json.dumps(labels)


def test_report_excludes_infrastructure_errors_from_success_rate(session, tmp_path):
    session.finish("provider_error")
    rows = read_runs(tmp_path)
    summary = summarize(rows)
    assert summary[0]["errors_or_interruptions"] == 1
    assert summary[0]["success_rate"] is None


def test_report_separates_core_versions_origins_and_source_changes(session, tmp_path):
    from pokeagent_bench.core import write_json

    session.finish("action_budget")
    core = session.manifest["core"]
    assert core["version"]
    assert len(core["source_sha256"]) == 64
    groups = [read_runs(tmp_path)[0]["group"]]
    for key, value in (("version", "next-version"), ("direct_url", {"url": "https://example.invalid/core.whl"}),
                       ("source_sha256", "changed-source")):
        original = core[key]
        core[key] = value
        write_json(session.output / "manifest.json", session.manifest)
        groups.append(read_runs(tmp_path)[0]["group"])
        core[key] = original
    assert len(set(groups)) == 4
