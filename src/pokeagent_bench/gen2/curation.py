"""Offline Gen II curation: play native actions and drive a pinned PokeSim policy.

Only the fixture builder, the determinism proof and the reference tests use this module.
The policy reads RAM through a read-only view and returns controller actions. Nothing here
writes game memory.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

# PokeSim at this tag pins the same Core 0.12.3 the benchmark uses. Its packages/pokecore is
# byte-identical to the released 0.12.3 wheel. PokeSim's newer HEAD needs a later Core.
POKESIM_TAG = 'pokecore-v0.12.3'
POKESIM_COMMIT = '37fff4cf3092b968d515e38163d32398596135a2'
GEN2_WAIT = 16
IDLE_FRAMES = 12


class ReadOnlyMemory:
    """Memory reads for a policy. Any write raises."""

    def __init__(self, memory):
        self._memory = memory

    def __getitem__(self, key):
        return self._memory[key]

    def __setitem__(self, key, value):
        raise PermissionError('Curation policies may not write game memory')

    def __getattr__(self, name):
        if name.startswith(('write', 'set', 'poke')):
            raise PermissionError('Curation policies may not write game memory')
        return getattr(self._memory, name)


def play(emulator, action):
    """One native action: press, hold, release, then wait the gap. A button always comes up."""
    button, hold, gap = action
    if button:
        emulator.press(button)
    try:
        if hold:
            emulator.tick(hold, True)
    finally:
        if button:
            emulator.release(button)
    if gap:
        emulator.tick(gap, True)
    return hold + gap


def source_digest(checkout):
    """One hash over the PokeSim package sources, recorded with every output."""
    package = Path(checkout) / 'pokesim'
    files = {path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(package.rglob('*.py'))}
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def manifest_digest(folder):
    return hashlib.sha256((Path(folder) / 'manifest.json').read_bytes()).hexdigest()


class PokeSimDriver:
    """PokeSim's Gen II story policy at the pinned tag, asked once per action as play_gen2 does."""

    def __init__(self, checkout, data_root, *, seed=1, starter='cyndaquil'):
        """data_root holds gen2/crystal game data. PokeSim's shared strategy tables come from its
        Gen I folder, found through GAME_DATA_DIR, or game-data next to data_root's parent."""
        checkout = Path(checkout).resolve()
        if str(checkout) not in sys.path:
            sys.path.insert(0, str(checkout))
        shared = Path(os.environ.get('GAME_DATA_DIR') or Path(data_root).resolve().parent.parent / 'game-data')
        os.environ['GAME_DATA_DIR'] = str(shared)
        from pokecore.gen2.ram import read_snapshot
        from pokesim.gen2.data import GameData
        from pokesim.gen2.policy import Goal, Policy
        from pokesim.runtime.policy import PolicyContext, stack_pointer
        self.read_snapshot, self.Goal, self.PolicyContext, self.stack_pointer = read_snapshot, Goal, PolicyContext, stack_pointer
        self.data = GameData.load(Path(data_root), 'crystal')
        self.policy = Policy(self.data, seed=seed, starter=starter)
        self.provenance = {'pokesim_tag': POKESIM_TAG, 'pokesim_commit': POKESIM_COMMIT,
                           'pokesim_source_sha256': source_digest(checkout), 'seed': seed, 'starter': starter,
                           'game_data_manifest_sha256': manifest_digest(Path(data_root) / 'gen2' / 'crystal'),
                           'strategy_bundle': json.loads((shared / 'current.json').read_text())['bundle']}

    def snapshot(self, emulator, frame):
        return self.read_snapshot(ReadOnlyMemory(emulator.memory), self.data, frame)

    def decide(self, emulator, frame, snapshot=None):
        """The next native action as (button, hold, gap)."""
        memory = ReadOnlyMemory(emulator.memory)
        snapshot = snapshot or self.read_snapshot(memory, self.data, frame)
        actions = list(self.policy.step(self.PolicyContext(snapshot, frame, memory, self.stack_pointer(emulator))))
        if not actions:
            return (None, 0, IDLE_FRAMES)
        action = actions[0]
        return (action.button, action.hold, GEN2_WAIT if action.gap is None else action.gap)
