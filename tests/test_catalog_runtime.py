"""Concrete catalog objectives reject shortcuts that bypass the tested outcome."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from pokeagent_bench.catalog_runtime import CatalogEvaluator, TASK_IDS, catalog_evidence
from pokeagent_bench.campaign_runtime import STORY_FLAGS


def mon(species, hp=29, maximum=None, dvs=1):
    return {'species': species, 'hp': hp, 'max_hp': maximum or hp, 'level': 10,
            'trainer_id': 1234, 'dvs': [0, dvs, 8, 8, 8], 'status': 0,
            'moves': [33, 45, 39, 98], 'pp': [35, 40, 30, 30],
            'experience': 1000, 'stat_exp': [0, 0, 0, 0, 0]}


def state():
    story = dict.fromkeys(set(STORY_FLAGS) | {'ss-anne-rival', 'snorlax-resolved'}, False)
    story['starter'] = True
    return {'valid': True, 'map_id': 1, 'x': 10, 'y': 10, 'last_map': 0,
            'story': story, 'badges': 0, 'gym_flags': [False] * 8,
            'elite': dict.fromkeys(['Lorelei', 'Bruno', 'Agatha', 'Lance'], False),
            'champion': False, 'hall_of_fame': 0,
            'party': [mon(153), mon(84, 12, 35, 2), mon(36, 23, dvs=3)],
            'items': [[20, 1], [11, 1], [4, 3]], 'money': 3000, 'owned': [1, 25, 16], 'seen': [1, 25, 16],
            'battle': 0, 'battle_type': 0, 'enemy_species': 0, 'enemy_hp': 10,
            'captured_species': 0, 'evolution_occurred': False, 'battle_result': 0,
            'active_box': 0, 'box_species': [], 'box': [], 'pc_items': [],
            'overworld': True, 'settled': True, 'active_slot': 0, 'active_species': 153,
            'saffron_open': False, 'bike_voucher_received': False,
            'bicycle_received': False, 'hideout_open': False, 'moon_stone_removed': False, 'run_attempts': 0,
            'ui': {'kind': 'overworld', 'selected_text': None, 'visible_choices': []},
            'party_menu': False, 'menu_index': 0,
            'evolution_data': {'families': {'148': 148, '38': 148}, 'edges': [[148, 38]]}}


def grader(task, facts=None):
    return CatalogEvaluator(facts or state(), {'kind': 'catalog-task', 'task_id': task, 'description': 'Task'})


def observe(ev, facts, frame=1):
    awards = ev.observe(deepcopy(facts), frame, 0)
    return awards + ev.observe(deepcopy(facts), frame + 1, 0)


def test_registry_matches_every_focused_catalog_entry():
    root = Path(__file__).parents[1] / 'src/pokeagent_bench/catalogs'
    ids = {row['id'] for category in ('navigation', 'battle', 'objectives', 'operations')
           for row in json.loads((root / (category + '.json')).read_text())['evals']}
    assert TASK_IDS == ids
    assert len(ids) == 41


@pytest.mark.parametrize('task,destination', [
    ('navigation-town-landmark', 41), ('navigation-forest-crossing', 2), ('navigation-branching-cave', 3)])
def test_navigation_requires_settled_arrival_and_no_blackout(task, destination):
    facts = state()
    ev = grader(task, facts)
    facts.update(map_id=destination, overworld=False)
    assert observe(ev, facts) == []
    facts['overworld'] = True
    assert observe(ev, facts, 3)
    failed = grader(task)
    facts['battle'] = 255
    failed.observe(facts, 1, 0)
    facts['battle'] = 0
    assert observe(failed, facts, 2) == []
    assert failed.disqualified


def test_navigation_puzzles_need_specific_destinations_and_order():
    facts = state()
    ev = grader('navigation-warp-puzzle', facts)
    facts.update(map_id=178, x=9, y=8)
    assert observe(ev, facts) == []
    facts['y'] = 9
    assert observe(ev, facts, 3)
    facts = state()
    facts['map_id'] = 108
    ev = grader('navigation-boulder-puzzle', facts)
    facts['map_id'] = 194
    assert not observe(ev, facts)
    assert ev.observe(facts, 3, 0)
    facts = state()
    ev = grader('navigation-multifloor-required-stops', facts)
    facts['map_id'] = 126
    assert observe(ev, facts) == []
    facts['map_id'] = 123
    ev.observe(facts, 3, 0)
    facts['map_id'] = 125
    ev.observe(facts, 4, 0)
    facts['map_id'] = 126
    assert observe(ev, facts, 5)


def test_blocked_route_opening_guard_disqualifies_even_if_destination_reached():
    facts = state()
    ev = grader('navigation-blocked-route-alternative', facts)
    facts.update(saffron_open=True, map_id=5)
    assert not observe(ev, facts)
    assert ev.disqualified


@pytest.mark.parametrize('task,item,target,changes', [
    ('operations-heal-potion-target', 20, 1, {'hp': 32}),
    ('operations-cure-poison', 11, 2, {'status': 0}),
    ('operations-restore-move-pp', 80, 0, {'pp': [35, 30, 8, 15]}),
    ('operations-teach-tm-replace-move', 234, 1, {'moves': [33, 117, 39, 98], 'pp': [35, 10, 30, 30]}),
])
def test_exact_item_operation_and_non_target_preservation(task, item, target, changes):
    facts = state()
    facts['items'] = [[item, 1], [4, 3]]
    if task == 'operations-cure-poison':
        facts['party'][2].update(species=3, hp=18, max_hp=28, status=8)
    if task == 'operations-restore-move-pp':
        facts['party'][0]['pp'] = [35, 30, 8, 5]
    ev = grader(task, facts)
    facts['items'] = [[4, 3]]
    facts['party'][target].update(changes)
    wrong = deepcopy(facts)
    wrong['party'][(target + 1) % 3]['hp'] -= 1
    assert not observe(ev, wrong)
    assert observe(ev, facts, 3)
    assert ev.score == 1
    assert not observe(ev, facts, 5)


def test_reorder_does_not_accept_a_simple_swap_or_stat_change():
    facts = state()
    ev = grader('operations-party-reorder', facts)
    original = deepcopy(facts['party'])
    facts['party'] = [original[2], original[1], original[0]]
    assert not observe(ev, facts)
    facts['party'] = [original[2], original[0], original[1]]
    assert observe(ev, facts, 3)


def test_purchase_requires_exact_quantity_cash_and_exit():
    facts = state()
    facts['items'], facts['money'] = [[20, 1], [11, 1]], 2000
    ev = grader('operations-buy-pokeballs', facts)
    facts['items'].append([4, 10])
    facts.update(money=0, map_id=42)
    assert not observe(ev, facts)
    facts['map_id'] = 1
    assert observe(ev, facts, 3)


def test_switch_requires_native_command_ledger_and_actual_battler():
    facts = state()
    facts.update(battle=2, active_species=176)
    facts['party'][0]['species'] = 176
    facts['party'][1], facts['party'][2] = facts['party'][2], facts['party'][1]
    ev = grader('operations-battle-switch', facts)
    facts['ui'] = {'kind': 'battle_menu', 'selected_text': 'PKMN', 'visible_choices': ['FIGHT', 'PKMN', 'ITEM', 'RUN']}
    ev.observe_input('a', facts)
    facts.update(party_menu=True, menu_index=2)
    facts['ui'] = {'kind': 'menu', 'selected_text': '3: PIKACHU', 'visible_choices': ['1: CHARMANDER', '2: PIDGEY', '3: PIKACHU']}
    ev.observe_input('a', facts)
    facts['active_slot'] = 2
    assert not observe(ev, facts)
    facts['active_species'] = 84
    assert observe(ev, facts, 3)
    failed = grader('operations-battle-switch', ev.baseline)
    failed.observe_input('a', {'ui': {'kind': 'battle_menu', 'selected_text': 'FIGHT'}})
    assert failed.disqualified


def test_pc_roundtrip_needs_deposit_withdraw_then_reorder_evidence():
    facts = state()
    facts['box'] = [mon(165, 18, dvs=4)]
    ev = grader('operations-deposit-withdraw', facts)
    original = deepcopy(facts['party'])
    assert not observe(ev, facts)
    target = facts['party'].pop(1)
    facts['box'].append(target)
    observe(ev, facts, 3)
    facts['party'].append(facts['box'].pop())
    observe(ev, facts, 5)
    facts['party'] = original
    observe(ev, facts, 7)
    assert ev.observe(facts, 9, 0)
    assert list(ev.stages) == ['deposit', 'withdraw', 'switch-back']


def test_pc_item_checklist_checks_actual_order_and_preserves_other_items():
    facts = state()
    facts['party'][1]['hp'] = 10
    facts['items'] = [[11, 1], [4, 3]]
    facts['pc_items'] = [[20, 1], [11, 1]]
    ev = grader('operations-menu-checklist', facts)
    facts['items'].append([20, 1])
    facts['pc_items'] = [[11, 1]]
    observe(ev, facts)
    facts['items'].pop()
    facts['party'][1]['hp'] = 30
    observe(ev, facts, 3)
    facts['party'] = [facts['party'][2], facts['party'][0], facts['party'][1]]
    observe(ev, facts, 5)
    assert ev.observe(facts, 7, 0)
    failed = grader('operations-menu-checklist', ev.baseline)
    assert not observe(failed, facts)
    assert failed.disqualified


def test_parcel_and_quest_cannot_skip_prerequisites():
    facts = state()
    ev = grader('objectives-parcel-roundtrip', facts)
    facts['story']['parcel'] = True
    assert not observe(ev, facts)
    facts['story']['parcel-collected'] = True
    observe(ev, facts, 3)
    assert ev.observe(facts, 5, 0)
    facts = state()
    ev = grader('objectives-quest-trainer', facts)
    facts['story']['hideout-giovanni'] = True
    facts['items'].append([72, 1])
    assert not observe(ev, facts)
    assert ev.disqualified


def test_voucher_must_be_new_for_bicycle_quest():
    facts = state()
    ev = grader('objectives-infeasible-plan-alternate', facts)
    facts.update(bicycle_received=True)
    facts['items'].append([6, 1])
    assert not observe(ev, facts)
    facts['bike_voucher_received'] = True
    observe(ev, facts, 3)
    assert ev.observe(facts, 5, 0)


def test_capture_does_not_credit_gifts_and_rejects_purchased_balls():
    facts = state()
    facts['party'] = [facts['party'][0]]
    ev = grader('objectives-find-capture-species', facts)
    facts['party'].append(mon(84, 35, dvs=7))
    assert not observe(ev, facts)
    facts['map_id'] = 42
    facts['items'].append([3, 1])
    assert not observe(ev, facts, 3)
    assert ev.disqualified


def test_true_capture_with_identity_and_training_before_misty():
    facts = state()
    ev = grader('objectives-capture-prepare-battle', facts)
    facts.update(battle=1, enemy_species=148, map_id=35, captured_species=0, overworld=False)
    ev.observe(deepcopy(facts), 1, 0)
    facts['captured_species'] = 148
    ev.observe(deepcopy(facts), 2, 0)
    facts['party'].append(mon(148, 20, dvs=7))
    observe(ev, facts, 3)
    facts.update(battle=0, captured_species=0, overworld=True)
    observe(ev, facts, 5)
    assert ev.capture_record
    assert ev.score == 0
    facts['party'][-1]['level'] += 1
    observe(ev, facts, 7)
    facts['badges'] = 2
    facts['gym_flags'][1] = True
    assert observe(ev, facts, 9)


def test_battle_win_requires_native_victory_and_rejects_blackout_recovery():
    facts = state()
    facts.update(battle=2, overworld=False)
    ev = grader('battle-prepared-gym', facts)
    facts.update(battle=0, overworld=True, badges=1)
    assert not observe(ev, facts)
    facts['gym_flags'][0] = True
    assert observe(ev, facts, 3)
    failed = grader('battle-prepared-gym', ev.baseline)
    facts['battle'] = 255
    failed.observe(facts, 1, 0)
    facts['battle'] = 0
    assert not observe(failed, facts, 2)


def test_wild_battle_requires_experience_from_initial_encounter():
    facts = state()
    facts.update(battle=1, overworld=False, enemy_species=165)
    ev = grader('battle-wild-basics', facts)
    facts['party'][0]['experience'] += 20
    ev.observe(facts, 1, 0)
    facts.update(battle=0, overworld=True)
    assert observe(ev, facts, 2)
    failed = grader('battle-wild-basics', ev.baseline)
    facts['party'][0]['experience'] -= 20
    assert not observe(failed, facts)


def test_duplicate_frame_cannot_confirm_and_resume_preserves_stages(tmp_path):
    from pokeagent_bench.recovery import pack, unpack
    facts = state()
    ev = grader('navigation-town-landmark', facts)
    facts['map_id'] = 41
    assert not ev.observe(facts, 1, 0)
    assert not ev.observe(facts, 1, 0)
    restored = unpack(json.loads(json.dumps(pack(ev))))
    assert restored.observe(facts, 2, 0)
    assert restored.score == 1


@pytest.mark.skipif(not os.environ.get('POKEBENCH_ROM') or not os.environ.get('POKEBENCH_CATALOG_FIXTURES'),
                    reason='Local fixtures and ROM are not distributed')
def test_native_available_fixtures_load_without_mutating_game():
    from pokeagent_bench.game import RedEngine
    root = Path(os.environ['POKEBENCH_CATALOG_FIXTURES'])
    count = 0
    for path in root.glob('*/initial.state'):
        task = path.parent.name
        if task not in TASK_IDS:
            continue
        engine = RedEngine(Path(os.environ['POKEBENCH_ROM']), path.read_bytes())
        try:
            saved = engine.save()
            facts = catalog_evidence(engine, task)
            assert engine.save() == saved
            ev = grader(task, facts)
            assert not ev.observe(facts, 1, 0)
            assert not ev.disqualified
            count += 1
        finally:
            engine.close()
    assert count == len(TASK_IDS)


@pytest.mark.parametrize('task', ['operations-heal-potion-target', 'operations-cure-poison', 'operations-restore-move-pp'])
@pytest.mark.skipif(not os.environ.get('POKEBENCH_ROM') or not os.environ.get('POKEBENCH_CATALOG_FIXTURES'),
                    reason='Local native menu references are not distributed')
def test_native_reference_inputs_pass_catalog_grader(task):
    from pokeagent_bench.game import RedEngine
    root = Path(os.environ['POKEBENCH_CATALOG_FIXTURES']) / task
    engine = RedEngine(Path(os.environ['POKEBENCH_ROM']), (root / 'initial.state').read_bytes())
    try:
        ev = grader(task, catalog_evidence(engine, task))
        frame = 0
        for action in json.loads((root / 'reference/commands.json').read_text()):
            button = action['button']
            ev.observe_input(button, catalog_evidence(engine, task))
            if button:
                engine.press(button)
            for index in range(action['hold_frames'] + action['release_frames']):
                if button and index == action['hold_frames']:
                    engine.release(button)
                engine.tick()
                frame += 1
                ev.observe(catalog_evidence(engine, task), frame, 0)
            if button:
                engine.release(button)
        assert ev.score == 1
        assert not ev.disqualified
    finally:
        engine.close()

@pytest.mark.parametrize('task,target', [
    ('battle-unfavorable-lead', 'Lorelei'), ('battle-ineffective-attack-adaptation', 'Lorelei'),
    ('battle-heal-switch-attack-tradeoff', 'Bruno'), ('battle-underleveled-status-setup', 'Lorelei'),
    ('battle-losing-midbattle-recovery', 'Agatha'),
])
def test_each_trainer_checkpoint_uses_its_own_victory_flag(task, target):
    facts = state()
    facts.update(battle=2, overworld=False)
    ev = grader(task, facts)
    facts.update(battle=0, overworld=True)
    facts['elite']['Lance'] = True
    assert not observe(ev, facts)
    facts['elite'][target] = True
    assert observe(ev, facts, 3)


@pytest.mark.parametrize('task', ['battle-league-balanced', 'battle-league-constrained'])
def test_league_requires_all_four_victories_and_hall_registration(task):
    facts = state()
    ev = grader(task, facts)
    facts.update(champion=True, map_id=118, hall_of_fame=1)
    assert not observe(ev, facts)
    facts['elite'] = dict.fromkeys(['Lorelei', 'Bruno', 'Agatha', 'Lance'], True)
    assert observe(ev, facts, 3)


@pytest.mark.parametrize('task', ['battle-preserve-specialist', 'battle-uncertain-opponent-lineup'])
def test_champion_battle_checkpoint_does_not_require_later_hall_dialogue(task):
    facts = state()
    facts.update(battle=2, overworld=False)
    ev = grader(task, facts)
    facts.update(battle=0, champion=True)
    assert observe(ev, facts)


def test_pp_gauntlet_requires_both_consecutive_targets():
    facts = state()
    facts.update(battle=2, overworld=False)
    ev = grader('battle-restricted-pp', facts)
    facts.update(battle=0, overworld=True)
    facts['elite']['Lorelei'] = True
    assert not observe(ev, facts)
    facts['elite']['Bruno'] = True
    assert observe(ev, facts, 3)


def test_bill_fuji_and_starter_require_native_rewards_and_default_name():
    facts = state()
    ev = grader('objectives-npc-instruction', facts)
    facts['story']['bill-ticket'] = True
    assert not observe(ev, facts)
    facts['items'].append([63, 1])
    assert observe(ev, facts, 3)
    facts = state()
    ev = grader('objectives-prerequisite-chain', facts)
    facts['story']['fuji-flute'] = True
    facts['items'].append([73, 1])
    assert not observe(ev, facts)
    facts['story']['ghost-marowak'] = True
    assert observe(ev, facts, 3)
    facts = state()
    facts['party'] = []
    facts['story']['starter'] = False
    ev = grader('objectives-starter-selection', facts)
    facts['story']['starter'] = True
    facts['party'] = [mon(177)]
    facts['party'][0]['nick'] = 'CUSTOM'
    assert not observe(ev, facts)
    facts['party'][0]['nick'] = 'SQUIRTLE'
    assert observe(ev, facts, 3)


def test_moon_stone_needs_pickup_in_correct_room_and_full_bag_quest_needs_exchange():
    facts = state()
    ev = grader('navigation-spinning-floors', facts)
    facts['items'].append([10, 1])
    assert not observe(ev, facts)
    facts['map_id'] = 200
    assert not observe(ev, facts, 3)
    facts['moon_stone_removed'] = True
    observe(ev, facts, 5)
    assert ev.observe(facts, 7, 0)
    facts = state()
    facts['items'].append([45, 1])
    ev = grader('objectives-recover-earlier-mistake', facts)
    facts['items'].append([6, 1])
    facts['bicycle_received'] = True
    assert not observe(ev, facts)
    facts['items'] = [row for row in facts['items'] if row[0] != 45]
    assert observe(ev, facts, 3)


def test_snorlax_requires_initial_encounter_capture_not_a_later_gift():
    facts = state()
    facts.update(battle=1, enemy_species=132, overworld=False)
    ev = grader('objectives-constrained-valuable-capture', facts)
    facts.update(battle=0, overworld=True)
    assert not observe(ev, facts)
    assert ev.disqualified


def test_sequential_hideout_quest_and_item_pc_heal_pass():
    facts = state()
    ev = grader('objectives-quest-trainer', facts)
    facts['hideout_open'] = True
    observe(ev, facts)
    facts['map_id'] = 202
    facts['items'].append([74, 1])
    observe(ev, facts, 3)
    facts['story']['hideout-giovanni'] = True
    observe(ev, facts, 5)
    facts['items'].append([72, 1])
    observe(ev, facts, 7)
    assert ev.observe(facts, 9, 0)
    facts = state()
    facts['party'][1]['hp'] = 10
    facts['items'] = [[11, 1], [4, 3]]
    facts['pc_items'] = [[20, 1], [11, 1]]
    ev = grader('operations-withdraw-item-and-use', facts)
    facts['items'].append([20, 1])
    facts['pc_items'] = [[11, 1]]
    observe(ev, facts)
    facts['items'].pop()
    facts['party'][1]['hp'] = 30
    observe(ev, facts, 3)
    assert ev.observe(facts, 5, 0)


def test_capture_allows_free_ball_pickups_without_relaxing_capture_requirement():
    facts = state()
    facts['party'] = [facts['party'][0]]
    ev = grader('objectives-find-capture-species', facts)
    facts['map_id'] = 51
    facts['items'] = [[4, 4]]
    assert not observe(ev, facts)
    assert not ev.disqualified
    facts['party'].append(mon(84, dvs=7))
    assert not observe(ev, facts, 3)
    assert ev.capture_record is None


@pytest.mark.parametrize('map_id', [42, 56, 67, 91, 123, 150, 152, 172, 173, 174, 180])
def test_ball_purchase_rejection_does_not_depend_on_money_update_timing(map_id):
    facts = state()
    facts['party'] = [facts['party'][0]]
    ev = grader('objectives-find-capture-species', facts)
    facts.update(map_id=map_id)
    facts['items'] = [[4, 4]]
    observe(ev, facts)
    assert ev.disqualified
