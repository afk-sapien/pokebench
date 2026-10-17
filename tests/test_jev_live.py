import json
import threading
import time

import pytest

from pokeagent_bench.jev_live import LiveSession, execute
from pokeagent_bench.providers import ProviderError
from test_jev_provider import answer


class LiveEngine:
    """FakeEngine plus the frame-count tick and close the live player uses."""

    rom_sha256 = "test-rom"

    def __init__(self, engine):
        self.inner = engine
        self.closed = False

    def press(self, button):
        self.inner.press(button)

    def release(self, button):
        self.inner.release(button)

    def tick(self, frames=1):
        for _ in range(frames):
            self.inner.tick()

    def screenshot(self):
        return self.inner.screenshot()

    def structured(self, labels=None):
        return self.inner.structured(labels)

    def save(self):
        return self.inner.save()

    def close(self):
        self.closed = True


def wait_for(predicate):
    deadline = time.monotonic() + 3
    while not predicate():
        assert time.monotonic() < deadline, "Worker did not reach expected state"
        time.sleep(0.01)


def player_for(tmp_path, engine, **kwargs):
    return LiveSession(LiveEngine(engine), tmp_path, **kwargs)


def stop(player):
    player.halt.set()
    player.thread.join(timeout=3)
    assert not player.thread.is_alive()


def presses(engine):
    return [row[1] for row in engine.inputs if row[0] == "press"]


def test_release_button_even_when_emulation_fails(engine):
    live = LiveEngine(engine)

    def broken(frames=1):
        raise RuntimeError("emulator failed")
    live.tick = broken
    with pytest.raises(RuntimeError):
        execute(live, "a")
    assert engine.inputs[-1][:2] == ("release", "a")


def test_one_call_budget_executes_response_and_saves(tmp_path, engine):
    player = player_for(tmp_path, engine, key="test-key", steps=1)
    player.evaluate = lambda *args: answer()
    player.thread.start()
    try:
        player.command({"command": "start"})
        wait_for(lambda: player.actions == 1)
        wait_for(lambda: not player.running)
        assert player.calls == 1 and player.tokens == 100 and player.frame == 24
        assert "test-key" not in json.dumps(player.status())
    finally:
        stop(player)
    assert "test-key" not in (tmp_path / "decisions.jsonl").read_text()
    assert (tmp_path / "current.state").exists()
    assert json.loads((tmp_path / "current.json").read_text())["rom_sha256"] == "test-rom"
    assert player.engine.closed


def test_manual_takeover_discards_inflight_response(tmp_path, engine):
    player = player_for(tmp_path, engine, key="test-key", steps=2)
    requested, release = threading.Event(), threading.Event()

    def evaluate(*args):
        requested.set()
        assert release.wait(3)
        return answer("a")
    player.evaluate = evaluate
    player.thread.start()
    try:
        player.command({"command": "start"})
        assert requested.wait(3)
        player.command({"command": "action", "action": "down"})
        wait_for(lambda: player.actions == 1)
        release.set()
        wait_for(lambda: player.tokens == 100)
    finally:
        release.set()
        stop(player)
    assert presses(engine) == ["down"]
    rows = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text().splitlines()]
    assert rows[-1]["source"] == "jev" and rows[-1]["applied"] is False


def test_manual_play_without_key(tmp_path, engine):
    player = player_for(tmp_path, engine)
    with pytest.raises(ValueError, match="TypeSafe API key"):
        player.command({"command": "start"})
    player.thread.start()
    try:
        player.command({"command": "action", "action": "right"})
        wait_for(lambda: player.actions == 1)
        assert player.calls == 0
    finally:
        stop(player)


def test_request_failure_pauses_without_button_input(tmp_path, engine):
    player = player_for(tmp_path, engine, key="test-key")

    def fail(*args):
        raise ProviderError("Jev returned HTTP 401")
    player.evaluate = fail
    player.thread.start()
    try:
        player.command({"command": "start"})
        wait_for(lambda: bool(player.error))
        assert not player.running and "HTTP 401" in player.error
        assert presses(engine) == []
    finally:
        stop(player)
