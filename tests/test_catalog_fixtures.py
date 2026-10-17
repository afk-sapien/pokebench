"""Offline fixture construction must preserve native ownership and legal stats."""
import pytest

from pokesim_core.gen1 import (
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


@pytest.mark.parametrize('growth,wanted', [('MEDIUM_FAST', 1000), ('MEDIUM_SLOW', 560),
                                         ('FAST', 800), ('SLOW', 1250)])
def test_growth_curve_start_experience(growth, wanted):
    assert experience(growth, 10) == wanted
