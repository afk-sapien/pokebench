import json

from pokeagent_bench.paper_export import export_results


def test_paper_export_is_frozen_and_excludes_private_artifacts(session, tmp_path):
    output = tmp_path / "paper/export.json"
    export_results(tmp_path, output)
    assert json.loads(output.read_text())["runs"] == []
    session.wait("one", 2)
    session.finish("action_budget")
    export_results(tmp_path, output)
    first = output.read_bytes()
    export_results(tmp_path, output)
    assert first == output.read_bytes()
    report = json.loads(first)
    assert len(report["runs"]) == 1
    assert len(report["source_sha256"]["run"]["actions.jsonl"]) == 64
    assert not {"evidence", "scenario", "notes", "achievements", "screenshot", "agent"} & report["runs"][0].keys()
    assert report["summary"][0]["trials"] == 1
