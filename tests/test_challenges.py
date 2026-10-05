from copy import deepcopy
import json

import pytest

from conftest import FakeEngine, blank_evidence
from pokeagent_bench.challenges import ChallengeEvaluator, validate_objective
from pokeagent_bench.core import digest
from pokeagent_bench.session import Session, checkpoint, replay


CASCADE = {"kind": "milestone", "target": "badge:cascade", "description": "Earn the Cascade Badge"}


def test_previous_badges_do_not_score_and_target_needs_two_frames(tmp_path):
    engine = FakeEngine()
    engine.state["badges"] = 1
    engine.state["gym_flags"][0] = True
    session = Session(engine, tmp_path / "run", {"objective": CASCADE}, goal="challenge")
    assert session.status()["score"] == 0
    assert session.status()["score_max"] == 1
    assert session.observe()["status"]["objective"] == CASCADE["description"]
    assert "event_id" not in json.dumps(session.observe())
    engine.state["badges"] = 3
    engine.state["gym_flags"][1] = True
    assert session.wait("first", 1)["status"]["score"] == 0
    status = session.wait("second", 1)["status"]
    assert status["completed"]
    assert status["score"] == 1
    saved = session.output / "milestones/000000000002.state"
    assert saved.exists()
    metadata = json.loads(saved.with_suffix(".json").read_text())
    assert metadata["state_sha256"] == digest(saved.read_bytes())
    session.close()


def test_trainer_flag_and_battle_exit_are_both_required():
    initial = blank_evidence()
    initial["challenge"] = {"event": False, "battle": 2}
    objective = {"kind": "trainer", "event_id": 100, "description": "Defeat this trainer"}
    evaluator = ChallengeEvaluator(initial, objective)
    state = deepcopy(initial)
    state["challenge"]["battle"] = 0
    assert evaluator.observe(state, 1, 0) == []
    assert evaluator.observe(state, 2, 0) == []
    state["challenge"]["event"] = True
    assert evaluator.observe(state, 3, 0) == []
    assert evaluator.observe(state, 4, 0)[0]["points"] == 1
    with pytest.raises(ValueError, match="already"):
        ChallengeEvaluator(state, objective)


def test_location_requires_exact_position_and_a_fresh_start():
    objective = {"kind": "location", "map_id": 1, "x": 2, "y": 3, "description": "Reach the exit"}
    initial = blank_evidence()
    initial["challenge"] = {"location": [1, 2, 2]}
    evaluator = ChallengeEvaluator(initial, objective)
    state = deepcopy(initial)
    state["challenge"]["location"][2] = 3
    evaluator.observe(state, 1, 0)
    assert evaluator.observe(state, 2, 0)
    with pytest.raises(ValueError, match="already"):
        ChallengeEvaluator(state, objective)


@pytest.mark.parametrize("objective", [dict(CASCADE, target="badge:invented"),
                         {"kind": "trainer", "event_id": -1, "description": "Win"},
                         {"kind": "location", "map_id": True, "x": 0, "y": 0, "description": "Go"},
                         dict(CASCADE, memory_write=123)])
def test_invalid_objectives_are_rejected(objective):
    with pytest.raises(ValueError):
        validate_objective(objective)


def test_challenge_replay_reconstructs_evaluator(tmp_path, monkeypatch):
    rom = tmp_path / "fake.gb"
    rom.write_bytes(b"rom")

    def make_engine(*args):
        engine = FakeEngine()
        def tick(engine):
            engine.state["badges"] = 2
            engine.state["gym_flags"][1] = True
        engine.on_tick = tick
        return engine

    session = Session(make_engine(), tmp_path / "run", {"rom_sha256": digest(b"rom"), "objective": CASCADE},
                      goal="challenge")
    session.wait("one", 5)
    session.close()
    monkeypatch.setattr("pokeagent_bench.session.RedEngine", make_engine)
    result = replay(rom, session.output)
    assert result["verified"] and result["score"] == 1 and result["frames"] == 2


def test_checkpoint_import_records_setup_wait_and_paired_screen(tmp_path, monkeypatch):
    engine = FakeEngine()
    engine.rom_sha256 = "rom-checksum"
    monkeypatch.setattr("pokeagent_bench.session.RedEngine", lambda *args: engine)
    state = tmp_path / "input.state"
    state.write_bytes(b"private-state")
    output = tmp_path / "checkpoint"
    manifest = checkpoint(tmp_path / "red.gb", state, output, name="cascade-segment", objective=CASCADE)
    assert manifest["source_state_sha256"] == digest(b"private-state")
    assert manifest["setup_wait_frames"] == 1
    assert engine.frame == 1
    assert manifest["preview_sha256"] == digest(engine.screenshot())
    assert manifest["objective"] == CASCADE
    assert manifest["curation"] == "unverified"
    assert manifest["state_sha256"] == digest((output / "initial.state").read_bytes())
    assert engine.closed


def test_loading_checkpoint_preserves_preview_without_a_hidden_tick(tmp_path, monkeypatch):
    from pokeagent_bench.session import load_engine
    engine = FakeEngine()
    rom = tmp_path / 'red.gb'
    rom.write_bytes(b'rom')
    engine.rom_sha256 = digest(rom.read_bytes())
    monkeypatch.setattr('pokeagent_bench.session.RedEngine', lambda *args: engine)
    state = tmp_path / 'input.state'
    state.write_bytes(b'state')
    scenario = tmp_path / 'scenario'
    checkpoint(rom, state, scenario, name='test', objective=CASCADE)
    frame = engine.frame
    restored, manifest = load_engine(rom, scenario)
    assert restored.frame == frame
    assert restored.initial_screen == (scenario / 'preview.png').read_bytes()
    assert digest(restored.initial_screen) == manifest['preview_sha256']
    (scenario / 'preview.png').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='preview checksum'):
        load_engine(rom, scenario)
