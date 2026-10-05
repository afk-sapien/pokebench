import json

import pytest

from conftest import FakeEngine
from pokeagent_bench.core import digest, write_json
from pokeagent_bench.session import Session, replay


@pytest.fixture
def recorded(tmp_path, monkeypatch):
    rom = tmp_path / "fake.gb"
    rom.write_bytes(b"fake-rom")
    run = tmp_path / "run"
    session = Session(FakeEngine(), run, {"rom_sha256": digest(rom.read_bytes())})
    session.act("one", "a", 3, 2)
    session.wait("two", 4)
    session.finish("action_budget")
    session.close()
    monkeypatch.setattr("pokeagent_bench.session.RedEngine", lambda *_: FakeEngine())
    return rom, run


def test_replay_checks_exact_actions_and_frames(recorded):
    result = replay(*recorded)
    assert result["verified"]
    assert result["actions"] == 2
    assert result["frames"] == 9


def test_modified_action_record_is_rejected(recorded):
    rom, run = recorded
    path = run / "actions.jsonl"
    records = path.read_text().splitlines()
    row = json.loads(records[0])
    row["action"]["button"] = "b"
    records[0] = json.dumps(row)
    path.write_text("\n".join(records) + "\n")
    with pytest.raises(ValueError, match="Broken action"):
        replay(rom, run)


def test_unearned_completion_is_rejected(recorded):
    rom, run = recorded
    path = run / "result.json"
    result = json.loads(path.read_text())
    result["completed"] = True
    write_json(path, result)
    with pytest.raises(ValueError, match="completion"):
        replay(rom, run)


def test_different_rom_is_rejected(recorded):
    rom, run = recorded
    rom.write_bytes(b"other-rom")
    with pytest.raises(ValueError, match="ROM checksum"):
        replay(rom, run)


def test_modified_starting_state_is_rejected(recorded):
    rom, run = recorded
    (run / "initial.state").write_bytes(b"changed-state")
    with pytest.raises(ValueError, match="state checksum"):
        replay(rom, run)


def test_legacy_run_without_core_provenance_still_replays(recorded):
    rom, run = recorded
    manifest = json.loads((run / "manifest.json").read_text())
    manifest.pop("core")
    manifest["benchmark"] = "red-v0.1-experimental"
    manifest["package_version"] = "0.1.0"
    write_json(run / "manifest.json", manifest)
    assert replay(rom, run)["verified"]
