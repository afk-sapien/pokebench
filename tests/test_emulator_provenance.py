"""Backend changes cannot silently reinterpret old experiments."""
from copy import deepcopy

import pytest

from pokeagent_bench import core


LEGACY = {"backend": "pyboy", "version": "2.7.0", "state_format": "pyboy-format-15"}
RUST = {"backend": "pyboy-rs", "version": "0.1.1", "state_format": "pyboy-format-15",
        "native_sha256": "native-build", "binding_sha256": "binding-build"}


@pytest.mark.parametrize("runtime", [LEGACY, RUST])
def test_new_manifest_records_actual_runtime(monkeypatch, runtime):
    monkeypatch.setattr(core, "emulator_provenance", lambda: deepcopy(runtime))
    manifest = core.emulator_manifest()
    assert manifest["emulator"] == runtime
    assert ("pyboy_version" in manifest) == (runtime["backend"] == "pyboy")
    core.validate_emulator_manifest(manifest)


def test_legacy_manifest_only_accepted_by_legacy_backend(monkeypatch):
    monkeypatch.setattr(core, "emulator_provenance", lambda: LEGACY)
    core.validate_emulator_manifest({"pyboy_version": "2.7.0"})
    monkeypatch.setattr(core, "emulator_provenance", lambda: RUST)
    with pytest.raises(ValueError, match="original PyBoy backend"):
        core.validate_emulator_manifest({"pyboy_version": "2.7.0"})


@pytest.mark.parametrize("field", list(RUST))
def test_changed_native_runtime_is_rejected(monkeypatch, field):
    monkeypatch.setattr(core, "emulator_provenance", lambda: RUST)
    changed = dict(RUST, **{field: "changed"})
    with pytest.raises(ValueError, match="exact runtime fingerprint"):
        core.validate_emulator_manifest({"emulator": changed})


def test_conflicting_backend_metadata_is_rejected(monkeypatch):
    monkeypatch.setattr(core, "emulator_provenance", lambda: RUST)
    with pytest.raises(ValueError, match="Conflicting"):
        core.validate_emulator_manifest({"emulator": RUST, "pyboy_version": "2.7.0"})


def test_scenario_refuses_backend_change_before_opening_engine(tmp_path, monkeypatch):
    import json
    from pokeagent_bench import session
    scenario = tmp_path / "scenario"
    scenario.mkdir()
    (scenario / "initial.state").write_bytes(b"state")
    (scenario / "scenario.json").write_text(json.dumps({
        "format": 1, "game": "red", "pyboy_version": "2.7.0"}))
    monkeypatch.setattr(core, "emulator_provenance", lambda: RUST)
    monkeypatch.setattr(session, "RedEngine", lambda *_: pytest.fail("Engine must not open"))
    with pytest.raises(ValueError, match="original PyBoy backend"):
        session.load_engine(tmp_path / "rom.gb", scenario)


class _CheckpointEngine:
    """Fixture wrapping the ordinary fake with a queue-aware Core checkpoint."""

    @staticmethod
    def create():
        from conftest import FakeEngine

        class Engine(FakeEngine):
            def __init__(self):
                super().__init__()
                self.pending = []
                self.matches = []

            def press(self, button):
                super().press(button)
                self.pending.append((button, True))

            def release(self, button):
                super().release(button)
                self.pending.append((button, False))

            def tick(self):
                self.pending.clear()
                super().tick()

            def checkpoint(self):
                return {"state": self.save(), "pending_inputs": list(self.pending), "frames": self.frame}

            def restore_checkpoint(self, saved, *, match):
                self.matches.append(match)
                self.frame = saved["frames"]
                self.pending = list(saved["pending_inputs"])

        return Engine()


def test_core_checkpoint_restores_all_queued_inputs_without_duplicate_release(tmp_path):
    from pokeagent_bench.recovery import checkpoint, resume, unpack
    from pokeagent_bench.session import Session
    import json

    rom = tmp_path / "red.gb"
    rom.write_bytes(b"rom")
    engine = _CheckpointEngine.create()
    session = Session(engine, tmp_path / "run", {"rom_sha256": core.digest(rom.read_bytes())})
    session.act("one", "right", 2, 0)
    engine.press("left")
    expected = list(engine.pending)
    assert expected == [("right", False), ("left", True)]
    checkpoint(session, {"decision_index": 1})
    saved = unpack(json.loads((session.output / "recovery.json").read_text())["payload"])
    assert saved["pending_button_release"] is None
    assert saved["engine_checkpoint"]["pending_inputs"] == expected
    engine.close()
    session.run_lease.close()
    constructed_states = []

    def factory(rom, state):
        constructed_states.append(state)
        return _CheckpointEngine.create()

    restored = resume(rom, session.output, engine_factory=factory)
    try:
        assert constructed_states == [None]
        assert restored.engine.pending == expected
        assert restored.engine.matches == ["exact"]
        assert restored.engine.inputs == []
        assert restored.engine.frame == restored.frame == 2
    finally:
        restored.close()


NEWER = dict(RUST, version="0.1.9", native_sha256="newer-native", binding_sha256="newer-binding")
UNLISTED = dict(RUST, version="0.2.0", native_sha256="unlisted-native", binding_sha256="unlisted-binding")


def _use_runtime(monkeypatch, runtime):
    monkeypatch.setattr(core, "emulator_provenance", lambda: deepcopy(runtime))
    monkeypatch.setattr(core, "VERIFIED_EMULATOR_PAIRS",
                        ({"recorded": RUST, "runtime": NEWER, "evidence": "test sweep"},))


def test_listed_pair_is_accepted_only_in_verified_mode(monkeypatch):
    _use_runtime(monkeypatch, NEWER)
    core.validate_emulator_manifest({"emulator": RUST}, verified_pairs=True)
    with pytest.raises(ValueError, match="exact runtime fingerprint"):
        core.validate_emulator_manifest({"emulator": RUST})
    _use_runtime(monkeypatch, RUST)
    with pytest.raises(ValueError, match="not verified: recorded pyboy-rs 0.1.9, runtime pyboy-rs 0.1.1"):
        core.validate_emulator_manifest({"emulator": NEWER}, verified_pairs=True)


@pytest.mark.parametrize("field", ["version", "native_sha256", "binding_sha256", "state_format"])
def test_unlisted_build_is_refused_with_how_to_verify(monkeypatch, field):
    _use_runtime(monkeypatch, dict(NEWER, **{field: "changed"}))
    with pytest.raises(ValueError, match="not verified") as refused:
        core.validate_emulator_manifest({"emulator": RUST}, verified_pairs=True)
    assert "scripts/verify_emulator_pair.py" in str(refused.value)
    assert "VERIFIED_EMULATOR_PAIRS" in str(refused.value)


def test_legacy_manifest_still_refused_in_verified_mode(monkeypatch):
    _use_runtime(monkeypatch, NEWER)
    with pytest.raises(ValueError, match="original PyBoy backend"):
        core.validate_emulator_manifest({"pyboy_version": "2.7.0"}, verified_pairs=True)
    with pytest.raises(ValueError, match="Conflicting"):
        core.validate_emulator_manifest({"emulator": RUST, "pyboy_version": "2.7.0"}, verified_pairs=True)


def _scenario(tmp_path):
    import json
    rom = tmp_path / "rom.gb"
    rom.write_bytes(b"rom")
    scenario = tmp_path / "scenario"
    scenario.mkdir()
    (scenario / "initial.state").write_bytes(b"state")
    (scenario / "scenario.json").write_text(json.dumps({
        "format": 1, "game": "red", "emulator": RUST,
        "state_sha256": core.digest(b"state"), "rom_sha256": core.digest(b"rom")}))
    return rom, scenario


class _EngineOpened(Exception):
    pass


def _refuse_engine(*_):
    raise _EngineOpened


@pytest.mark.parametrize("runtime, outcome", [(NEWER, _EngineOpened), (UNLISTED, ValueError)])
def test_load_engine_accepts_only_listed_pairs(tmp_path, monkeypatch, runtime, outcome):
    from pokeagent_bench import session
    rom, scenario = _scenario(tmp_path)
    _use_runtime(monkeypatch, runtime)
    monkeypatch.setattr(session, "RedEngine", _refuse_engine)
    with pytest.raises(outcome):
        session.load_engine(rom, scenario)


def test_rom_mismatch_names_expected_and_actual_checksums(tmp_path, monkeypatch):
    from pokeagent_bench import session
    rom, scenario = _scenario(tmp_path)
    rom.write_bytes(b"other rom")
    _use_runtime(monkeypatch, NEWER)
    monkeypatch.setattr(session, "RedEngine", _refuse_engine)
    with pytest.raises(ValueError, match="Scenario ROM checksum mismatch") as refused:
        session.load_engine(rom, scenario)
    assert f"expected SHA-256 {core.digest(b'rom')}, got {core.digest(b'other rom')}" in str(refused.value)


@pytest.mark.parametrize("runtime, message", [(NEWER, "Run state checksum mismatch"), (UNLISTED, "not verified")])
def test_replay_accepts_only_listed_pairs(tmp_path, monkeypatch, runtime, message):
    import json
    from pokeagent_bench import evaluation_catalog, session
    run = tmp_path / "run"
    run.mkdir()
    (run / "initial.state").write_bytes(b"state")
    (run / "manifest.json").write_text(json.dumps({"emulator": RUST, "initial_sha256": "0" * 64}))
    monkeypatch.setattr(evaluation_catalog, "validate_run_spec", lambda manifest: None)
    _use_runtime(monkeypatch, runtime)
    monkeypatch.setattr(session, "RedEngine", _refuse_engine)
    with pytest.raises(ValueError, match=message):
        session.replay(tmp_path / "rom.gb", run)


def test_resume_keeps_exact_build_rule_for_listed_pair(tmp_path, monkeypatch):
    from pokeagent_bench.recovery import checkpoint, resume
    from pokeagent_bench.session import Session
    rom = tmp_path / "red.gb"
    rom.write_bytes(b"rom")
    _use_runtime(monkeypatch, RUST)
    session = Session(_CheckpointEngine.create(), tmp_path / "run", {"rom_sha256": core.digest(rom.read_bytes())})
    checkpoint(session, {"decision_index": 0})
    session.engine.close()
    session.run_lease.close()
    _use_runtime(monkeypatch, NEWER)
    with pytest.raises(ValueError, match="exact runtime fingerprint"):
        resume(rom, session.output, engine_factory=lambda *_: pytest.fail("Engine must not open"))


def test_seeded_pairs_share_format_and_cite_a_sweep():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert core.VERIFIED_EMULATOR_PAIRS
    keys = {"backend", "version", "state_format", "native_sha256", "binding_sha256"}
    for pair in core.VERIFIED_EMULATOR_PAIRS:
        recorded, runtime = pair["recorded"], pair["runtime"]
        assert set(recorded) == set(runtime) == keys
        assert recorded != runtime
        assert (recorded["backend"], recorded["state_format"]) == (runtime["backend"], runtime["state_format"])
        assert (root / pair["evidence"]).is_file()
    assert [(p["recorded"]["version"], p["runtime"]["version"]) for p in core.VERIFIED_EMULATOR_PAIRS] == [
        ("0.1.1", "0.1.5")]


def test_core_checkpoint_never_falls_back_to_lossy_raw_restore(tmp_path):
    from conftest import FakeEngine
    from pokeagent_bench.recovery import checkpoint, resume
    from pokeagent_bench.session import Session

    rom = tmp_path / "red.gb"
    rom.write_bytes(b"rom")
    session = Session(_CheckpointEngine.create(), tmp_path / "run", {"rom_sha256": core.digest(rom.read_bytes())})
    checkpoint(session, {"decision_index": 0})
    session.engine.close()
    session.run_lease.close()
    with pytest.raises(ValueError, match="checkpoint capability"):
        resume(rom, session.output, engine_factory=lambda *_: FakeEngine())
