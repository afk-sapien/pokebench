"""The shared decoder must not widen the benchmark's observation permissions."""
from pathlib import Path

from pokesim_core.emulator import GameBoy
from pokesim_core.gen1 import (
    W_BADGES,
    W_BAG_ITEMS,
    W_CUR_MAP,
    W_EVENT_FLAGS,
    W_IS_IN_BATTLE,
    W_MONEY,
    W_NUM_BAG_ITEMS,
    W_PARTY_COUNT,
    W_PARTY_MONS,
    W_PARTY_NICKS,
    W_X,
    W_Y,
)

from pokeagent_bench.game import RedEngine, structured


def test_shared_party_decoding_preserves_observation_allowlist():
    memory = bytearray(65536)
    memory[W_PARTY_COUNT] = 2
    base = W_PARTY_MONS
    memory[base] = 153
    memory[base + 1:base + 3] = (19).to_bytes(2, "big")
    memory[base + 4] = 8
    memory[base + 8:base + 12] = bytes([33, 0, 45, 0])
    memory[base + 29:base + 33] = bytes([0xC5, 0, 9, 0])
    memory[base + 33] = 5
    memory[base + 34:base + 36] = (22).to_bytes(2, "big")
    memory[base + 27:base + 29] = bytes([255, 255])
    memory[W_PARTY_NICKS:W_PARTY_NICKS + 5] = bytes([0x80, 0xEF, 0xF5, 0x60, 0x50])
    memory[W_NUM_BAG_ITEMS] = 2
    memory[W_BAG_ITEMS:W_BAG_ITEMS + 4] = bytes([4, 3, 255, 0])
    memory[W_CUR_MAP] = 2
    memory[W_X] = 3
    memory[W_Y] = 4
    memory[W_BADGES] = 1
    memory[W_IS_IN_BATTLE] = 2
    memory[W_MONEY:W_MONEY + 3] = bytes([0x12, 0x34, 0x56])
    memory[W_EVENT_FLAGS:W_EVENT_FLAGS + 320] = bytes([255]) * 320
    labels = {"species": {"153": "Bulbasaur"}, "moves": {"33": {"name": "Tackle", "hidden": "secret"}}}
    observation = structured(memory, labels)
    assert observation == {
        "location": {"map_id": 2, "map_name": "#2", "x": 3, "y": 4},
        "party": [{"species_id": 153, "species": "Bulbasaur", "nickname": "A♂♀?",
                   "hp": 19, "max_hp": 22, "level": 5, "status": 8,
                   "moves": [{"id": 33, "name": "Tackle", "pp": 5}, {"id": 45, "name": "#45", "pp": 9}]}],
        "inventory": [{"id": 4, "name": "#4", "quantity": 3}],
        "money": 123456, "badges": ["Boulder"], "battle": {"kind": "trainer"},
    }


def test_red_engine_keeps_red_only_policy(monkeypatch):
    calls = []

    def initialize(self, rom, state, **kwargs):
        calls.append((rom, state, kwargs))

    monkeypatch.setattr(GameBoy, "__init__", initialize)
    RedEngine(Path("red.gb"), b"state")
    assert calls == [(Path("red.gb"), b"state", {"allowed_games": ("red",)})]


def test_checkpoint_screen_is_stable_until_controller_advances(monkeypatch):
    ticks = []
    monkeypatch.setattr(GameBoy, "__init__", lambda *args, **kwargs: None)
    monkeypatch.setattr(GameBoy, "tick", lambda self, frames, **kwargs: ticks.append(frames))
    monkeypatch.setattr(GameBoy, "screenshot", lambda self: b"live")
    engine = RedEngine(Path("red.gb"), b"state")
    engine.initial_screen = b"checkpoint"
    assert engine.screenshot() == b"checkpoint"
    assert engine.screenshot() == b"checkpoint"
    assert ticks == []
    engine.tick()
    assert engine.screenshot() == b"live"
    assert ticks == [1]
