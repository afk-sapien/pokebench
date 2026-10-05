from types import SimpleNamespace

import pytest

from pokeagent_bench import dialogue
from pokeagent_bench.core import Limits
from pokeagent_bench.gameplay_commands import execute
from test_gameplay import setup


def screen(rows):
    from pokesim_core.gen1 import decode_text
    encoding = {decode_text(bytes([tile])): tile for tile in range(128, 256)}
    encoding.update({' ': 127, ':': 156})
    return {'textbox': True, 'tiles': [encoding.get(char, 127) for row in rows for char in row.ljust(20)[:20]]}


def test_wait_detection_requires_unique_routine_and_live_stack():
    memory = bytearray(65536)
    engine = SimpleNamespace(memory=memory, _pb=SimpleNamespace(register_file=SimpleNamespace(SP=0xD001)))
    # Synthetic instructions with variable addresses, not a distributed ROM excerpt.
    routine = (b'\xf0\x01\xf5\xf0\x02\xf5\xaf\xe0\x01\x3e\x06\xe0\x02'
               b'\xe5\xfa\x03\x04\xa7\x28\x03\xcd\x05\x06\x21\x07\x08\xcd\x09\x0a\xe1\xcd\x0b\x0c'
               b'\x3e\x2d\xcd\x0d\x0e\xf0\x0f\xe6\x03\x28\xe1\xf1\xe0\x02\xf1\xe0\x01\xc9')
    memory[0x100:0x100 + len(routine)] = routine
    memory[0xD001:0xD003] = (0x100 + 33).to_bytes(2, 'little')
    before = bytes(memory)
    assert dialogue.continue_ready(engine)
    assert bytes(memory) == before
    engine._pb.register_file.SP += 2
    assert not dialogue.continue_ready(engine)
    engine._pb.register_file.SP = 0xD001
    memory[0x200:0x200 + len(routine)] = routine
    del engine._dialogue_wait_returns
    assert not dialogue.continue_ready(engine)
    assert not dialogue.continue_ready(SimpleNamespace())


def test_transcript_keeps_pages_but_collapses_typing(monkeypatch):
    monkeypatch.setattr(dialogue, 'ui_state', lambda _: {'kind': 'dialogue'})
    rows = [''] * 18
    monkeypatch.setattr(dialogue, 'read_screen', lambda _: screen(rows))
    transcript = dialogue.Transcript()
    for text in ['O', 'OAK', 'OAK: Choose!', 'OAK: Choose!', 'You may take one.']:
        rows[14] = text
        transcript.capture(None)
    assert transcript.pages == ['OAK: Choose!', 'You may take one.']
    transcript.pages = ['X' * 16384]
    rows[14] = 'Another page'
    transcript.capture(None)
    assert transcript.limited
    assert transcript.result('transcript limit', 0)['transcript_limit_reached']


def fake_ui(engine, monkeypatch, kind):
    monkeypatch.setattr(dialogue, 'ui_state', lambda _: {'kind': kind(engine.frame)})
    monkeypatch.setattr(dialogue, 'read_screen', lambda _: screen([''] * 14 + ['Dialogue text', '', '', '']))
    monkeypatch.setattr(dialogue, 'continue_ready', lambda _: True)


@pytest.mark.parametrize('kind', ['menu', 'naming', 'battle_menu', 'move_menu'])
def test_never_confirms_choice_or_naming(tmp_path, engine, monkeypatch, kind):
    session = setup(tmp_path, engine)
    fake_ui(engine, monkeypatch, lambda frame: kind)
    try:
        result = execute(session, 'choice', {'command': 'advance_dialogue', 'argument': '', 'count': 1})
        assert result['dialogue']['stop_reason'] == 'choice'
        assert result['raw_actions'] == session.frame == 0
        assert not engine.inputs
    finally:
        session.close()


def test_continue_until_choice_and_retry_does_not_repeat(tmp_path, engine, monkeypatch):
    session = setup(tmp_path, engine)
    fake_ui(engine, monkeypatch, lambda frame: 'dialogue' if frame < 2 else 'menu')
    command = {'command': 'advance_dialogue', 'argument': '', 'count': 1}
    try:
        result = execute(session, 'continue', command)
        assert result['dialogue']['pages'] == ['Dialogue text']
        assert result['dialogue']['stop_reason'] == 'choice'
        assert [row for row in engine.inputs if row[0] == 'press'] == [('press', 'a', 0)]
        assert session.frame == 32
        assert execute(session, 'continue', command)['retried']
        assert session.frame == 32
        inspected = execute(session, 'inspect', {'command': 'inspect', 'argument': 'memory', 'count': 1})
        assert inspected['raw_actions'] == 0 and session.frame == 32
    finally:
        session.close()


@pytest.mark.parametrize('limit,value,reason', [
    ('max_dialogue_frames', 32, 'dialogue frame limit'),
    ('max_frames', 15, 'run ended'),
    ('max_actions', 1, 'run ended'),
])
def test_dialogue_respects_local_and_global_caps(tmp_path, engine, monkeypatch, limit, value, reason):
    session = setup(tmp_path, engine)
    session.limits = Limits(**{limit: value})
    fake_ui(engine, monkeypatch, lambda frame: 'dialogue')
    try:
        result = execute(session, 'bounded', {'command': 'advance_dialogue', 'argument': '', 'count': 1})
        assert result['dialogue']['stop_reason'] == reason
        if limit == 'max_actions':
            assert session.actions == value
        else:
            assert session.frame == value
    finally:
        session.close()


def test_uncertain_wait_does_not_guess(tmp_path, engine, monkeypatch):
    session = setup(tmp_path, engine)
    fake_ui(engine, monkeypatch, lambda frame: 'dialogue')
    monkeypatch.setattr(dialogue, 'continue_ready', lambda _: False)
    try:
        result = execute(session, 'unknown', {'command': 'advance_dialogue', 'argument': '', 'count': 1})
        assert result['dialogue']['stop_reason'] == 'unrecognized or long animation'
        assert not [row for row in engine.inputs if row[0] == 'press']
    finally:
        session.close()


def test_brief_overworld_gap_does_not_split_conversation(tmp_path, engine, monkeypatch):
    session = setup(tmp_path, engine)
    fake_ui(engine, monkeypatch, lambda frame: 'dialogue' if frame < 2 or 40 <= frame < 80 else 'overworld')
    try:
        result = execute(session, 'gap', {'command': 'advance_dialogue', 'argument': '', 'count': 1})
        assert len([row for row in engine.inputs if row[0] == 'press']) == 2
        assert result['dialogue']['stop_reason'] == 'control returned'
        assert session.frame >= 200
    finally:
        session.close()


def test_global_completion_stops_collector_immediately(tmp_path, engine, monkeypatch):
    session = setup(tmp_path, engine)
    fake_ui(engine, monkeypatch, lambda frame: 'dialogue')
    engine.on_tick = lambda fake: fake.state.update(badges=1, gym_flags=[True] + [False] * 7)
    try:
        result = execute(session, 'complete', {'command': 'advance_dialogue', 'argument': '', 'count': 1})
        assert session.reason == 'completed' and session.frame == 2
        assert result['dialogue']['stop_reason'] == 'run ended'
    finally:
        session.close()


def test_ligatures_and_punctuation_are_kept(monkeypatch):
    monkeypatch.setattr(dialogue, 'ui_state', lambda _: {'kind': 'dialogue'})
    view = screen([''] * 18)
    view['tiles'][280:285] = [0x88, 0xB3, 0xBD, 0x9C, 0xE6]
    monkeypatch.setattr(dialogue, 'read_screen', lambda _: view)
    transcript = dialogue.Transcript()
    transcript.capture(None)
    assert transcript.pages == ["It's:?"]
    view['textbox'] = False
    view['tiles'][280] = 0x99
    transcript.capture(None)
    assert transcript.pages == ["It's:?"]


def test_transcript_survives_checkpoint(tmp_path, engine, monkeypatch):
    import json
    from pokeagent_bench.recovery import checkpoint, unpack
    session = setup(tmp_path, engine)
    fake_ui(engine, monkeypatch, lambda frame: 'dialogue' if frame < 2 else 'menu')
    try:
        result = execute(session, 'continue', {'command': 'advance_dialogue', 'argument': '', 'count': 1})
        checkpoint(session, {})
        saved = unpack(json.loads((session.output / 'recovery.json').read_text())['payload'])
        assert saved['session']['gameplay_result'] == result
        assert saved['session']['gameplay_operations']['continue'] == result
        from pokeagent_bench.visual_feedback import public_context
        assert public_context(session.observe())['max_dialogue_frames'] == session.limits.max_dialogue_frames
    finally:
        session.close()


def test_yes_no_options_exclude_adjacent_hud(tmp_path, engine):
    from pokeagent_bench.gameplay import ui_state
    session = setup(tmp_path, engine)
    mem = engine.memory
    mem[0xCC24:0xCC29] = bytes([8, 1, 0, 127, 1])
    for y, tiles in [(8, [0xED, 0x98, 0x84, 0x92, 127, 0x7C]), (10, [127, 0x8D, 0x8E, 127, 127, 0x7C])]:
        mem[0xC3A0 + y * 20 + 1:0xC3A0 + y * 20 + 7] = bytes(tiles)
        mem[0xC3A0 + y * 20 + 15] = 0xF9
    try:
        assert ui_state(mem)['visible_choices'] == ['YES', 'NO']
        assert ui_state(mem)['selected_text'] == 'YES'
        def move_cursor(fake):
            if fake.frame == 1:
                mem[0xCC26] = 1
                mem[0xC3A0 + 8 * 20 + 1] = 127
                mem[0xC3A0 + 10 * 20 + 1] = 0xED
        engine.on_tick = move_cursor
        execute(session, 'choose-no', {'command': 'choose', 'argument': 'NO', 'count': 1})
        assert [row[1] for row in engine.inputs if row[0] == 'press'] == ['down', 'a']
    finally:
        session.close()


def test_rejected_command_does_not_trigger_auto_continue(tmp_path, engine, monkeypatch):
    session = setup(tmp_path, engine)
    fake_ui(engine, monkeypatch, lambda frame: 'dialogue')
    try:
        result = execute(session, 'no-menu', {'command': 'choose', 'argument': 'YES', 'count': 1})
        assert result['dialogue']['stop_reason'] == 'command not executed'
        assert not engine.inputs
    finally:
        session.close()


def test_move_menu_options_keep_single_row_spacing(tmp_path, engine):
    from pokeagent_bench.gameplay import ui_state
    session = setup(tmp_path, engine)
    mem = engine.memory
    mem[0xD057] = 2
    mem[0xCC24:0xCC29] = bytes([13, 5, 1, 127, 3])
    view = screen([''] * 13 + ['      TACKLE', '     >TAIL WHIP', '      BUBBLE', '      -', ''])
    mem[0xC3A0:0xC3A0 + 360] = bytes(view['tiles'])
    mem[0xC3A0 + 14 * 20 + 5] = 0xED
    try:
        assert ui_state(mem)['kind'] == 'move_menu'
        assert ui_state(mem)['visible_choices'] == ['TACKLE', 'TAIL WHIP', 'BUBBLE', '-']
    finally:
        session.close()


def test_model_receives_transcript_once(monkeypatch):
    from pokeagent_bench.continuous_provider import ContinuousCodexProvider
    from pokeagent_bench.gameplay_provider import GameplayCodexProvider
    provider = object.__new__(GameplayCodexProvider)
    transcript = {'dialogue': {'pages': ['OAK: Choose!']}, 'end_frame': 42}
    recent = [{'frame': 42}, dict(transcript)]
    monkeypatch.setattr(ContinuousCodexProvider, 'decide', lambda self, observation, notes, recent, limits, timeout: recent)
    result = provider.decide({'game': {'last_command': transcript}}, '', recent, Limits(), 10)
    assert result == [{'frame': 42}]
    assert len(recent) == 2
