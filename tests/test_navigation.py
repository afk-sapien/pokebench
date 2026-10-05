from pokeagent_bench.core import Limits
from pokeagent_bench.gameplay import known_map, observe_gameplay
from pokeagent_bench.gameplay_commands import execute
from test_gameplay import setup


def test_partial_move_reports_progress_and_block(tmp_path, engine):
    session = setup(tmp_path, engine)
    session.limits = Limits(max_action_frames=600)
    def walk(fake):
        if fake.frame in (1, 25):
            fake.memory[0xD362] += 1
            fake.memory[0xC109] = 12
    engine.on_tick = walk
    try:
        result = execute(session, 'move', {'command': 'move', 'argument': 'right', 'count': 4})
        assert result['tiles_moved'] == 2
        assert result['requested_tiles'] == 4
        assert result['position_before']['x'] == 4
        assert result['position_after']['x'] == result['blocked_at']['x'] == 6
        assert result['outcome'] == 'Moved 2 tiles, then blocked or no further movement.'
        assert session.gameplay_memory['movements'][-1]['tiles_moved'] == 2
    finally:
        session.close()


def test_map_transition_returns_settled_observation_without_direction_choices(tmp_path, engine):
    session = setup(tmp_path, engine)
    session.limits = Limits(max_action_frames=600)
    observe_gameplay(session)
    def warp(fake):
        if fake.frame == 1:
            fake.memory[0xD35E] = 1
            fake.memory[0xD362] = 2
            fake.memory[0xD361] = 3
    engine.on_tick = warp
    try:
        result = execute(session, 'warp', {'command': 'move', 'argument': 'right', 'count': 1})
        assert result['map_changed']
        assert session.frame >= session.gameplay_memory['map_ready_after']
        assert result['dialogue']['stop_reason'] == 'control returned'
        assert [r[1] for r in engine.inputs if r[0] == 'press'] == ['right']
    finally:
        session.close()


def test_scripted_control_lock_only_waits(tmp_path, engine, monkeypatch):
    from pokeagent_bench import dialogue
    session = setup(tmp_path, engine)
    session.limits = Limits(max_action_frames=600)
    monkeypatch.setattr(dialogue, 'input_locked', lambda _: engine.frame < 300)
    try:
        result = execute(session, 'locked', {'command': 'advance_dialogue', 'argument': '', 'count': 1})
        assert session.frame >= 420
        assert result['dialogue']['stop_reason'] == 'control returned'
        assert not [r for r in engine.inputs if r[0] == 'press']
    finally:
        session.close()


def test_known_map_only_recalls_supplied_observations():
    memory = {'tiles': {'38': {'0,0': '.', '2,0': 'E'}, '99': {'0,0': 'SECRET'}}}
    view = known_map(memory, 38, 0, 1)
    assert view['rows'] == ['.?E', '@??']
    assert 'SECRET' not in str(view)
    blank = known_map(memory, 17, 1, 1)
    assert blank['rows'] == ['@']


def test_eight_tile_request_is_explicit_and_bounded(tmp_path, engine):
    session = setup(tmp_path, engine)
    session.limits = Limits(max_action_frames=120)
    def walk(fake):
        if fake.frame % 24 == 1:
            fake.memory[0xD362] += 1
            fake.memory[0xC109] = 12
    engine.on_tick = walk
    try:
        result = execute(session, 'eight', {'command': 'move', 'argument': 'right', 'count': 8})
        assert result['requested_tiles'] == 8
        assert result['tiles_moved'] == 5
        assert session.frame == 120
        assert len([r for r in engine.inputs if r[0] == 'press']) == 5
    finally:
        session.close()


def test_global_stop_still_reports_last_movement(tmp_path, engine):
    session = setup(tmp_path, engine)
    session.limits = Limits(max_frames=10, max_action_frames=600)
    def walk(fake):
        if fake.frame == 1:
            fake.memory[0xD362] += 1
    engine.on_tick = walk
    try:
        result = execute(session, 'stop', {'command': 'move', 'argument': 'right', 'count': 4})
        assert session.frame == 10
        assert result['tiles_moved'] == 1
        assert result['position_after']['x'] == result['position_before']['x'] + 1
        assert result['outcome'] == 'stopped at budget boundary'
    finally:
        session.close()


def test_pokedex_and_unknown_modal_do_not_expose_map(tmp_path, engine):
    from pokeagent_bench.gameplay import ui_state
    from test_dialogue import screen
    session = setup(tmp_path, engine)
    try:
        engine.memory[0xC102] = 255
        rows = [''] * 18
        rows[2], rows[6], rows[8], rows[13] = 'CHARMANDER', 'HT  2 00', 'WT  19.0lb', 'from the tip of'
        tiles = screen(rows)['tiles']
        engine.memory[0xC3A0:0xC3A0 + 360] = bytes(tiles)
        ui = ui_state(engine.memory)
        assert ui['kind'] == 'dialogue' and ui['panel'] == 'pokedex'
        assert any('CHARMANDER' in line for line in ui['text'])
        assert not observe_gameplay(session)['local_map']['available']
        assert observe_gameplay(session)['memory']['known_map'] is None
        engine.memory[0xC3A0:0xC3A0 + 360] = bytes([1] * 360)
        assert ui_state(engine.memory)['kind'] == 'modal'
        result = execute(session, 'modal', {'command': 'move', 'argument': 'right', 'count': 1})
        assert result['raw_actions'] == 0
        result = execute(session, 'settle-modal', {'command': 'advance_dialogue', 'argument': '', 'count': 1})
        assert result['dialogue']['stop_reason'] == 'choice'
        assert result['raw_actions'] == 0
    finally:
        session.close()


def test_pokedex_wait_requires_visible_card_unique_signature_and_live_stack(monkeypatch):
    from types import SimpleNamespace
    from pokeagent_bench import dialogue
    routine = b'\xcd\x01\x02\xf0\x03\xe6\x03\x28\xf7\xf1\xe0\x04' + b'\xcd\x05\x06' * 5
    bank = bytearray(0x4000)
    bank[0x100:0x100 + len(routine)] = routine
    class Memory:
        def __init__(self):
            self.data = bytearray(65536)
        def __getitem__(self, key):
            if isinstance(key, tuple):
                assert key[0] == 16
                return bank[key[1].start - 0x4000:key[1].stop - 0x4000]
            return self.data[key]
    memory = Memory()
    memory.data[0xD001:0xD003] = (0x4103).to_bytes(2, 'little')
    engine = SimpleNamespace(memory=memory, _pb=SimpleNamespace(register_file=SimpleNamespace(SP=0xD001)))
    monkeypatch.setattr(dialogue, 'ui_state', lambda _: {'panel': 'pokedex'})
    before = bytes(memory.data), bytes(bank)
    assert dialogue.continue_ready(engine)
    assert before == (bytes(memory.data), bytes(bank))
    engine._pb.register_file.SP += 2
    assert not dialogue.continue_ready(engine)
    engine._pb.register_file.SP -= 2
    monkeypatch.setattr(dialogue, 'ui_state', lambda _: {'panel': None})
    assert not dialogue.continue_ready(engine)
    monkeypatch.setattr(dialogue, 'ui_state', lambda _: {'panel': 'pokedex'})
    bank[0x200:0x200 + len(routine)] = routine
    del engine._pokedex_wait_returns
    assert not dialogue.continue_ready(engine)


def test_control_lock_detection_is_read_only_and_requires_unique_code():
    from types import SimpleNamespace
    from pokeagent_bench.dialogue import input_locked
    memory = bytearray(65536)
    routine = (b'\xfa\x30\xd7\xcb\x7f\xc8\xf0\x01\x47\xfa\x02\x03\xa0\xc0'
               b'\x21\x04\x05\x35\x7e\xfe\xff\xaf' + b'\xea\x06\x07' * 3 + b'\xea\x6b\xcd\xe0')
    memory[0x100:0x100 + len(routine)] = routine
    engine = SimpleNamespace(memory=memory)
    assert not input_locked(engine)
    memory[0xD730] = 128
    before = bytes(memory)
    assert input_locked(engine)
    assert bytes(memory) == before
    memory[0xD730] = 0
    memory[0xCD6B] = 240
    assert input_locked(engine)
    memory[0xCD6B] = 1
    assert not input_locked(engine)
    memory[0x200:0x200 + len(routine)] = routine
    del engine._input_lock_addresses
    memory[0xD730] = 128
    assert not input_locked(engine)
