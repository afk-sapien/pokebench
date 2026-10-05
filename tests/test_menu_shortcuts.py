from copy import deepcopy
import json

import pytest

from pokeagent_bench.core import Limits
from pokeagent_bench.gameplay import menu_options
from pokeagent_bench.gameplay_commands import execute, validate
from pokeagent_bench.gameplay_provider import GameplayCodexProvider
from pokeagent_bench.menu_shortcuts import parse_item, execute_shortcut
from test_gameplay import setup, memory


@pytest.mark.parametrize('value,expected', [('Full Restore:1',(16,0)), ('FULL_RESTORE:6',(16,5)),
                                           ('Elixir:2',(82,1)), ('Max Revive:3',(54,2))])
def test_explicit_item_and_one_based_target(value, expected):
    assert parse_item(value) == expected
    assert validate({'command':'use_item','argument':value,'count':1}, Limits())


@pytest.mark.parametrize('value', ['Full Restore', 'Full Restore:0', 'Revive:7', 'Revive:1:2',
                                   'TM01:1', 'Poke Ball:1', 'Ether:1', 'Potion:best', 'Revive:True'])
def test_reject_ambiguous_or_unsupported_item_targets(value):
    with pytest.raises(ValueError):
        parse_item(value)


def test_shortcut_contract_requires_one_selected_target():
    for command in [{'command':'switch_pokemon','argument':'0','count':1},
                    {'command':'switch_pokemon','argument':'best','count':1},
                    {'command':'use_item','argument':'Potion:1','count':2}]:
        with pytest.raises(ValueError):
            validate(command, Limits())
    provider = object.__new__(GameplayCodexProvider)
    provider.response_contract = 'simple'
    commands = provider.decision_schema(Limits())['properties']['actions']['items']['properties']['command']['enum']
    assert {'use_move','use_item','switch_pokemon'} <= set(commands)
    assert 'without a separate FIGHT' in provider.prompt


def mon(nick='SAME', hp=50):
    return {'species':177, 'trainer_id':12, 'dvs':[1,2,3,4,5], 'nick':nick, 'hp':hp}


def test_party_choices_identify_slots_even_with_duplicate_names_or_hp(monkeypatch):
    mem = memory()
    mem[0xCC24] = 1
    mem[0xCC28] = 1
    rows = [' ' * 20 for _ in range(18)]
    rows[0] = rows[2] = '   SAME       12'
    rows[1] = rows[3] = '             50  50'
    screen = {'cursor':(0,1), 'rows':rows, 'tiles':[0]*360}
    monkeypatch.setattr('pokeagent_bench.gameplay.read_party', lambda m:[mon(),mon()])
    assert menu_options(mem,screen,'menu') == [{'text':'1: SAME','cursor':[0,1]}, {'text':'2: SAME','cursor':[0,3]}]
    screen['rows'][2] = '   ANOTHER'
    assert not any(o['text'].startswith('2: SAME') for o in menu_options(mem,screen,'menu'))


def test_missing_item_never_opens_menus_and_same_id_is_idempotent(tmp_path, engine, monkeypatch):
    session = setup(tmp_path,engine)
    monkeypatch.setattr('pokeagent_bench.menu_shortcuts.read_party',lambda m:[mon()])
    monkeypatch.setattr('pokeagent_bench.menu_shortcuts.read_bag',lambda m:[])
    command = {'command':'use_item','argument':'Full Restore:1','count':1}
    try:
        before = bytes(engine.memory)
        result = execute(session,'once',command)
        assert result['outcome'].startswith('Requested item is not in the bag')
        assert session.frame == 0 and bytes(engine.memory) == before
        assert execute(session,'once',command)['retried']
        assert not engine.inputs
        with pytest.raises(ValueError):
            execute(session,'once',dict(command,argument='Revive:1'))
    finally:
        session.close()


def test_unknown_choice_stops_without_confirming(tmp_path, engine, monkeypatch):
    session = setup(tmp_path,engine)
    monkeypatch.setattr('pokeagent_bench.menu_shortcuts.read_party',lambda m:[mon()])
    monkeypatch.setattr('pokeagent_bench.menu_shortcuts.read_bag',lambda m:[(16,1)])
    monkeypatch.setattr('pokeagent_bench.menu_shortcuts.ui_state',lambda m:{'kind':'menu','cursor_tile':[1,2]})
    monkeypatch.setattr('pokeagent_bench.menu_shortcuts.panel',lambda *args:'unknown')
    result = {}
    try:
        execute_shortcut(session,{'command':'use_item','argument':'Full Restore:1'},
                         lambda *args:pytest.fail('Must not send input'),
                         lambda *args:pytest.fail('Must not choose'),result)
        assert 'Unsupported starting menu' in result['outcome']
    finally:
        session.close()


def test_unresponsive_menu_stops_and_never_confirms_a_target(tmp_path, engine, monkeypatch):
    session = setup(tmp_path,engine)
    monkeypatch.setattr('pokeagent_bench.menu_shortcuts.read_party',lambda m:[mon()])
    monkeypatch.setattr('pokeagent_bench.menu_shortcuts.read_bag',lambda m:[(16,1)])
    result = {}
    buttons = []
    def send(button, hold, release):
        buttons.append(button)
        session.frame += hold + release
        return True
    try:
        execute_shortcut(session,{'command':'use_item','argument':'Full Restore:1'},send,
                         lambda *args:pytest.fail('No visible menu'),result)
        assert 'Menu did not respond' in result['outcome']
        assert 'a' not in buttons
        assert session.frame < 2400
    finally:
        session.close()


def test_shortcut_result_survives_bounded_observation_allowlist():
    from pokeagent_bench.bounded_context import build, render
    from test_bounded_context import public
    observation = public()
    result = {'request':{'command':'use_item','argument':'Revive:2','count':1},
              'outcome':'Used the requested item.',
              'shortcut':{'kind':'use_item','party_slot':2,'item_id':53,'completed':True,'item_consumed':True},
              'private_flag':'NEVER_EXPOSE'}
    observation['game']['last_command'] = deepcopy(result)
    packet, _ = build(observation,'',[],None,1,1)
    assert packet['last_result']['shortcut'] == result['shortcut']
    assert 'NEVER_EXPOSE' not in json.dumps(packet)
    assert 'Item consumed: yes' in render(packet)
