"""The Gen II prep work: it leaves the released suite alone, and its starts and references hold.

The tests that need the Crystal ROM or the built starts skip without them. Set
POKEBENCH_CRYSTAL_ROM to the Crystal ROM and POKEBENCH_GEN2_FIXTURES to the folder
scripts/prepare_gen2_fixtures.py wrote.
"""
import json
import os
from pathlib import Path
import random

import pytest

from pokeagent_bench import local_setup
from pokeagent_bench.benchmark_tracks import SHORT, for_category
from pokeagent_bench.core import digest, encoded
from pokeagent_bench.evaluation_catalog import CATEGORIES, catalog_files, load_catalog
from pokeagent_bench.gen2 import catalog, engine
from pokeagent_bench.gen2.evaluator import MilestoneEvaluator, holds, validate_check, watched_events
from pokeagent_bench.quick_run import SUITES
from pokeagent_bench.submission import this_harness

ROOT = Path(__file__).resolve().parents[1]
RELEASED = json.loads((ROOT / 'tests/fixtures/gen2-prep-released-specs.json').read_text())
ROM = os.environ.get('POKEBENCH_CRYSTAL_ROM')
FIXTURES = os.environ.get('POKEBENCH_GEN2_FIXTURES')
needs_rom = pytest.mark.skipif(not ROM, reason='The Crystal ROM is not distributed. Set POKEBENCH_CRYSTAL_ROM')
needs_starts = pytest.mark.skipif(not ROM or not FIXTURES,
                                  reason='Crystal starts are not distributed. Set POKEBENCH_CRYSTAL_ROM and '
                                         'POKEBENCH_GEN2_FIXTURES')
TASK_IDS = [task['id'] for task in catalog.load_tasks()]


def released_now():
    tasks = {}
    for group in load_catalog(include_retired=True):
        for task in group['evals']:
            tasks[task['id']] = {'active': task.get('active', True), 'category': group['category'],
                                 'spec_sha256': digest(encoded(task)), 'track': for_category(group['category'])}
    return {'catalog_files': sorted(path.name for path in catalog_files()), 'categories': list(CATEGORIES),
            'packed': sorted(local_setup.PACKED), 'tasks': tasks,
            'suites': {name: [benchmark, budget, list(fixed) if fixed else None]
                       for name, (benchmark, budget, fixed) in SUITES.items()}}


def test_released_catalog_suites_and_fixture_pack_match_main():
    now = released_now()
    for key in ('catalog_files', 'categories', 'packed', 'suites'):
        assert now[key] == RELEASED[key], key
    assert now['tasks'].keys() == RELEASED['tasks'].keys()
    changed = sorted(name for name, row in now['tasks'].items() if row != RELEASED['tasks'][name])
    assert not changed, f'released specifications changed: {changed}'


def test_short_task_list_matches_main():
    short = sorted(task['id'] for group in load_catalog() if for_category(group['category']) == SHORT
                   for task in group['evals'])
    recorded = sorted(name for name, row in RELEASED['tasks'].items() if row['track'] == SHORT and row['active'])
    assert short == recorded
    assert not any(name.startswith('gen2-') for name in short)


def test_gen2_catalog_is_never_loaded_by_the_released_suites():
    assert catalog.CATALOG.parent != catalog_files()[0].parent
    assert catalog.CATEGORY not in CATEGORIES
    released = {task['id'] for group in load_catalog(include_retired=True) for task in group['evals']}
    assert not released & set(TASK_IDS)


def test_gen2_sources_cannot_change_the_harness_hash():
    package = ROOT / 'src/pokeagent_bench'
    hashed = {path.name: digest(path.read_bytes()) for path in sorted(package.glob('*.py'))}
    assert this_harness()['source_sha256'] == digest(encoded(hashed))
    assert (package / 'gen2/__init__.py').is_file() and not any('gen2' in name for name in hashed)


def test_every_gen2_task_validates_and_pins_its_start_and_reference():
    tasks = catalog.load_tasks()
    assert 5 <= len(tasks) <= 8 and all(task['difficulty'] == 'hard' for task in tasks)
    for task in tasks:
        fixture = task['fixture']
        assert task['decision_limit'] == catalog.REFERENCE_MULTIPLE * fixture['decisions']
        assert task['token_limit'] == catalog.TOKENS_PER_DECISION * task['decision_limit']
        assert len(task['milestones']) >= 2


@pytest.mark.parametrize('change, message', [
    (lambda task: task.update(id='kabuto'), 'start with gen2-'),
    (lambda task: task.update(decision_limit=task['decision_limit'] + 1), 'decision cap'),
    (lambda task: task.update(token_limit=task['token_limit'] - 1), 'token budget'),
    (lambda task: task['fixture'].update(actions_sha256='0' * 63), 'SHA-256'),
    (lambda task: task['capture'].update(route='elsewhere'), 'capture route'),
    (lambda task: task['objective'].update(description='Something else'), 'agent goal'),
    (lambda task: task.update(milestones=[]), 'ordered milestones'),
])
def test_gen2_task_validation_refuses_drift(change, message):
    task = catalog.task_definition(TASK_IDS[0])
    change(task)
    with pytest.raises(ValueError, match=message):
        catalog.validate_task(task)


@pytest.mark.parametrize('check', [
    {}, {'map': [0, 1]}, {'near': [3, 3]}, {'map': [3, 24], 'area': [5, 5, 4, 6]}, {'event': 2048},
    {'events': [1]}, {'events': [5, 5]}, {'badge': 16}, {'item': 0}, {'species': 1},
])
def test_milestone_checks_refuse_what_engine_facts_cannot_read(check):
    with pytest.raises(ValueError):
        validate_check(check)


def test_reference_pins_count_actions_frames_and_button_runs():
    actions = [['up', 2, 14], ['up', 2, 14], [None, 0, 30], ['a', 2, 6], ['up', 2, 14]]
    pinned = catalog.pins(b'state', actions)
    assert pinned['actions'] == 5 and pinned['frames'] == 86 and pinned['decisions'] == 3
    assert pinned['actions_sha256'] == catalog.actions_digest([tuple(action) for action in actions])


def facts(**changes):
    base = {'valid': True, 'map': [3, 13], 'x': 8, 'y': 15, 'battle': 0, 'script': 0, 'badges': 7, 'items': [],
            'key_items': [], 'party': [{'species': 156, 'level': 30, 'hp': 88, 'max_hp': 88}], 'time_of_day': 1,
            'events': {'818': False, '123': False}}
    return base | changes


def task(milestones):
    return {'id': 'gen2-test', 'milestones': milestones,
            'objective': {'kind': 'catalog-task', 'task_id': 'gen2-test', 'description': 'Test.'}}


MILESTONES = [{'id': 'hole', 'description': 'Floor gives way.', 'check': {'event': 818}},
              {'id': 'basement', 'description': 'Basement.', 'check': {'map': [3, 14]}},
              {'id': 'beasts', 'description': 'Beasts.', 'check': {'events': [818, 123]}}]


def test_each_milestone_needs_two_different_frames_and_comes_in_order():
    evaluator = MilestoneEvaluator(facts(), task(MILESTONES))
    hole = facts(events={'818': True, '123': False})
    assert evaluator.observe(facts(map=[3, 14], events={'818': False, '123': True}), 1) == []
    assert evaluator.observe(hole, 2) == [] and evaluator.observe(hole, 2) == []
    assert [award['id'] for award in evaluator.observe(hole, 3)] == ['milestone:hole']
    below = facts(map=[3, 14], events={'818': True, '123': False})
    assert evaluator.observe(below, 4) == [] and evaluator.observe(facts(events={'818': True}), 5) == []
    assert evaluator.observe(below, 6) == [] and evaluator.observe(below, 7)[0]['id'] == 'milestone:basement'
    done = facts(map=[3, 14], events={'818': True, '123': True})
    assert evaluator.observe(done, 8) == [] and not evaluator.complete()
    assert evaluator.observe(done, 9)[0]['id'] == 'milestone:beasts' and evaluator.complete()
    assert evaluator.score == 3
    with pytest.raises(ValueError, match='backwards'):
        evaluator.observe(done, 8)


def test_a_map_milestone_fails_in_battle_and_a_blackout_ends_the_run():
    evaluator = MilestoneEvaluator(facts(), task(MILESTONES[1:2]))
    assert not holds({'map': [3, 14]}, facts(map=[3, 14], battle=2))
    assert evaluator.observe(facts(map=[3, 14], battle=1), 1) == []
    assert evaluator.observe(facts(map=[3, 14], battle=1), 2) == []
    fainted = facts(party=[{'species': 156, 'level': 30, 'hp': 0, 'max_hp': 88}])
    assert evaluator.observe(fainted, 3) == [] and evaluator.disqualified
    assert evaluator.observe(facts(map=[3, 14]), 4) == [] and evaluator.observe(facts(map=[3, 14]), 5) == []
    assert evaluator.score == 0


def test_a_start_that_already_meets_a_milestone_or_is_blacked_out_is_refused():
    with pytest.raises(ValueError, match='already met'):
        MilestoneEvaluator(facts(events={'818': True, '123': False}), task(MILESTONES))
    with pytest.raises(ValueError, match='blacked out'):
        MilestoneEvaluator(facts(party=[{'species': 156, 'level': 30, 'hp': 0, 'max_hp': 88}]), task(MILESTONES))
    assert watched_events(MILESTONES) == (123, 818)


def test_a_start_without_its_matching_clock_lock_is_refused(tmp_path):
    state = b'not a real state'
    with pytest.raises(ValueError, match='without its clock lock'):
        engine.read_clock(tmp_path, state)
    record = {'format': engine.CLOCK_FORMAT, 'state_sha256': engine.sha256(state),
              'lock': {'base': engine.EPOCH, 'offset': 0.0, 'frames': 10, 'follow_frames': False}}
    (tmp_path / engine.CLOCK_FILE).write_text(json.dumps(record))
    with pytest.raises(ValueError, match='follow emulated frames'):
        engine.read_clock(tmp_path, state)
    record['lock']['follow_frames'] = True
    (tmp_path / engine.CLOCK_FILE).write_text(json.dumps(record))
    assert engine.read_clock(tmp_path, state)['lock']['frames'] == 10
    with pytest.raises(ValueError, match='different state'):
        engine.read_clock(tmp_path, b'another state')


def test_only_the_crystal_rom_is_accepted(tmp_path):
    other = tmp_path / 'other.gbc'
    other.write_bytes(b'\0' * 1024)
    with pytest.raises(ValueError, match=engine.ROM_SHA1):
        engine.check_rom(other)
    with pytest.raises(ValueError, match='ROM not found'):
        engine.check_rom(tmp_path / 'missing.gbc')


def seeded(seed, count):
    rng = random.Random(seed)
    return [(rng.choice(('a', 'a', 'b', 'start', 'up', 'down', 'left', 'right')), rng.choice((2, 4, 8)),
             rng.choice((8, 16, 24))) for _ in range(count)]


@needs_rom
def test_a_saved_start_replays_exactly_on_the_frame_locked_clock(tmp_path):
    from pokeagent_bench.gen2.curation import play
    rom = engine.check_rom(ROM)
    actions = seeded(7, 400)
    emulator = engine.boot(rom)
    try:
        for action in actions[:200]:
            play(emulator, action)
        record = engine.save_start(emulator, tmp_path / 'start')
        expected = []
        for action in actions[200:]:
            play(emulator, action)
            expected.append(engine.digests(emulator))
    finally:
        emulator.stop(save=False)
    replay, loaded = engine.load_start(rom, tmp_path / 'start')
    try:
        assert loaded['clock'] == record['clock'] == replay.clock_now()
        seen = []
        for action in actions[200:]:
            play(replay, action)
            seen.append(engine.digests(replay))
    finally:
        replay.stop(save=False)
    assert seen == expected


@needs_starts
@pytest.mark.parametrize('task_id', TASK_IDS)
def test_scripted_reference_reaches_success_and_no_sooner(task_id):
    from pokeagent_bench.gen2.curation import play
    definition = catalog.task_definition(task_id)
    folder = Path(FIXTURES) / task_id
    state = (folder / engine.STATE_FILE).read_bytes()
    reference = json.loads((folder / 'reference.json').read_text())
    actions = reference['actions']
    assert catalog.pins(state, actions) == definition['fixture']
    assert reference['task_id'] == task_id and reference['state_sha256'] == definition['fixture']['state_sha256']
    events = watched_events(definition['milestones'])
    emulator, _ = engine.load_start(engine.check_rom(ROM), folder)
    try:
        evaluator = MilestoneEvaluator(engine.facts(emulator, events), definition)
        frame, awarded = 0, []
        for index, action in enumerate(actions, 1):
            assert not evaluator.complete(), f'{task_id} succeeded at action {index - 1} of {len(actions)}'
            frame += play(emulator, action)
            awarded += [award['id'] for award in evaluator.observe(engine.facts(emulator, events), frame)]
            assert not evaluator.disqualified, evaluator.disqualification_reason
    finally:
        emulator.stop(save=False)
    assert evaluator.complete()
    assert awarded == ['milestone:' + milestone['id'] for milestone in definition['milestones']]
