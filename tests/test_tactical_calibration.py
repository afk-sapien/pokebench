import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def policy_module(monkeypatch):
    scripts=Path(__file__).resolve().parents[1]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('calibrate_test',scripts/'calibrate_tactical.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def view(species='Poliwrath', pp=(20,20,15,10), hp=120, status=None):
    moves=[{'id':move,'pp':power_points,'slot':i+1,'power':95 if move==57 else 0,'type':'Water' if move==57 else 'Psychic'}
           for i,(move,power_points) in enumerate(zip((95,133,57,156),pp))]
    return {'party':[{'slot':1,'species':species,'nickname':species.upper(),'hp':hp,'max_hp':150,
                      'level':50,'types':['Water','Fighting'],'status':status or ['healthy'],'moves':moves}],
            'battle':{'active_party_slot':1,'visible_hud':['DEWGONG','54']},
            'screen':{'kind':'battle_menu','text':[],'visible_choices':['FIGHT','PKMN','ITEM','RUN']},'bag':[]}


def test_exhausted_recovery_and_sleep_never_selected(policy_module):
    policy=policy_module.Policy('tactical')
    policy.active_slot=1
    policy.boosts=3
    command=policy.choose(view(pp=(0,0,10,0),hp=10))
    assert command==policy_module.request('use_move',3)


def test_item_requires_actual_inventory(policy_module):
    policy=policy_module.Policy('tactical')
    observation=view(pp=(20,20,1,10))
    assert policy.choose(observation)['command']!='use_item'
    observation['bag']=[{'id':82,'quantity':1}]
    assert policy.choose(observation)==policy_module.request('use_item','Elixer:1')


def test_confirmed_boosts_only(policy_module):
    policy=policy_module.Policy('tactical')
    before=view()
    command=policy_module.request('use_move',2)
    policy.feedback(before,command,{'dialogue':{'pages':['POLIWRATH is fast asleep!']}})
    assert policy.boosts==0
    policy.feedback(before,command,{'dialogue':{'pages':["Enemy SLOWBRO's SPECIAL",'SPECIAL greatly rose!']}})
    assert policy.boosts==0
    policy.feedback(before,command,{'dialogue':{'pages':["POLIWRATH's SPECIAL",'SPECIAL greatly rose!']}})
    assert policy.boosts==1


def test_sleep_uses_visible_hud_without_hidden_enemy_state(policy_module):
    policy=policy_module.Policy('tactical')
    observation=view()
    observation['battle']['visible_hud']=['DEWGONG','SLP']
    assert policy.choose(observation)==policy_module.request('use_move',2)
    observation['battle']['visible_hud']=['DEWGONG','PAR']
    assert policy.choose(observation)==policy_module.request('use_move',2)


def test_attack_first_uses_available_damage_over_status(policy_module):
    policy=policy_module.Policy('attack-first')
    assert policy.choose(view())==policy_module.request('use_move',3)
