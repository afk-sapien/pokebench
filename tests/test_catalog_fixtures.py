"""Offline fixture construction must preserve native ownership and legal stats."""
import importlib.util
from pathlib import Path

import pytest

from pokecore.gen1 import (
    W_PLAYER_ID, W_PLAYER_NAME, W_PARTY_MONS, W_PARTY_OT, W_PARTY_NICKS,
    read_party,
)
from pokeagent_bench.catalog_fixtures import set_party, set_bag, experience


class Engine:
    def __init__(self):
        self.memory = bytearray(65536)
        self.memory[W_PLAYER_ID:W_PLAYER_ID + 2] = bytes([42, 87])
        self.memory[W_PLAYER_NAME:W_PLAYER_NAME + 11] = bytes([0x80, 0x92, 0x87] + [0x50] * 8)


STRATEGY = {
    'species': {
        '84': {'name': 'PIKACHU', 'growth': 'MEDIUM_FAST', 'types': [23, 23],
               'catch_rate': 190, 'stats': [35, 55, 30, 90, 50]},
        '3': {'name': 'NIDORAN_M', 'growth': 'MEDIUM_SLOW', 'types': [3, 3],
              'catch_rate': 235, 'stats': [46, 57, 40, 50, 40]},
    },
    'moves': {'84': {'pp': 30}, '45': {'pp': 40}, '39': {'pp': 30},
              '86': {'pp': 20}, '33': {'pp': 35}, '43': {'pp': 30}},
}


def test_party_uses_actual_player_id_and_original_trainer():
    engine = Engine()
    set_party(engine, STRATEGY, [{'species': 'PIKACHU', 'level': 13,
                                 'moves': [84, 45, 39, 86], 'max_hp': 35, 'hp': 12}])
    m = engine.memory
    assert m[W_PARTY_MONS + 12:W_PARTY_MONS + 14] == m[W_PLAYER_ID:W_PLAYER_ID + 2]
    assert m[W_PARTY_OT:W_PARTY_OT + 11] == m[W_PLAYER_NAME:W_PLAYER_NAME + 11]
    mon = read_party(m)[0]
    assert mon['hp'] == 12 and mon['max_hp'] == 35
    first, second = m[W_PARTY_MONS + 27:W_PARTY_MONS + 29]
    hp_dv = ((first >> 4) & 1) * 8 + (first & 1) * 4 + ((second >> 4) & 1) * 2 + (second & 1)
    assert 2 * (35 + hp_dv) * 13 // 100 + 13 + 10 == mon['max_hp']


def test_impossible_fixed_max_hp_is_rejected():
    with pytest.raises(ValueError, match='HP incompatible'):
        set_party(Engine(), STRATEGY, [{'species': 'PIKACHU', 'level': 16,
                                       'moves': [84], 'max_hp': 35}])


def test_species_gender_uses_native_character_not_underscore():
    engine = Engine()
    set_party(engine, STRATEGY, [{'species': 'NIDORAN_M', 'level': 9,
                                 'moves': [33, 43], 'max_hp': 28, 'hp': 18, 'status': 8}])
    assert engine.memory[W_PARTY_NICKS + 7] == 0xEF
    assert read_party(engine.memory)[0]['nick'] == 'NIDORAN♂'


def test_bag_rejects_duplicate_item_slots():
    with pytest.raises(ValueError, match='distinct'):
        set_bag(Engine(), [(20, 1), (20, 2)])


def recipes():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'prepare_catalog_fixtures.py'
    spec = importlib.util.spec_from_file_location('prepare_catalog_fixtures_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RECIPES


def test_no_start_holds_an_elevator_floor_label():
    # Ids 0x54 to 0x60 are floor names (B2F to 11F), not items. Using one runs past the end of the game's
    # item use table: it consumed one and printed a Poke Ball message in a Short boulder puzzle attempt.
    floors = range(0x54, 0x61)
    assert not {task: bag for task, recipe in recipes().items()
                for bag in [recipe.get('bag') or []] if any(item in floors for item, _ in bag)}


@pytest.mark.parametrize('task', ['navigation-warp-puzzle', 'navigation-spinning-floors',
                                  'navigation-boulder-puzzle', 'navigation-multifloor-required-stops'])
def test_navigation_starts_hold_the_documented_max_repels(task):
    assert recipes()[task]['bag'] == [[0x39, 20]]


def test_silph_co_start_locks_every_card_key_door_and_hides_only_the_beaten_rival():
    recipe = recipes()['navigation-hard-silph-co']
    doors = [name for name in recipe['events'] if 'UNLOCKED_DOOR' in name]
    # 2F to 11F hold 20 Card Key doors in the native scripts. Every one starts locked.
    assert len(set(doors)) == 20 and not any(recipe['events'][name] for name in doors)
    assert recipe['events']['EVENT_BEAT_SILPH_CO_RIVAL'] is True
    assert recipe['events']['EVENT_BEAT_SILPH_CO_GIOVANNI'] is False
    # Toggle 0xA7 is the 7F rival, who leaves after the beaten battle. Nothing else is hidden.
    assert recipe['hidden'] == [0xA7]


@pytest.mark.parametrize('growth,wanted', [('MEDIUM_FAST', 1000), ('MEDIUM_SLOW', 560),
                                         ('FAST', 800), ('SLOW', 1250)])
def test_growth_curve_start_experience(growth, wanted):
    assert experience(growth, 10) == wanted
