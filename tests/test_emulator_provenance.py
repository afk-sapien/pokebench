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
