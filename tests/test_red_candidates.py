"""The harder Red candidates: they leave the released suite alone, and their caps, pins and stop rules hold.

The candidates live in their own catalog folder, which Short, Long and the fixture pack never read.
Their two stop rules, no_faint and fail_on, are opt-in fields of the milestone runtime that no
released task sets. The runtime change does change the harness source hash.

The tests that need the Red ROM or the built starts skip without them. Set POKEBENCH_ROM to the Red
ROM and POKEBENCH_CANDIDATE_FIXTURES to the folder scripts/prepare_candidate_fixtures.py wrote, after
scripts/reference_candidate_tasks.py has written each reference proof next to its start.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from pokeagent_bench import catalog_batch, catalog_execution, local_setup, recovery
from pokeagent_bench import evaluation_catalog as catalog
from pokeagent_bench import milestone_runtime as runtime
from pokeagent_bench.benchmark_tracks import LONG, SHORT, for_category
from pokeagent_bench.core import digest, encoded
from pokeagent_bench.evaluation_catalog import CATEGORIES, catalog_files, load_catalog
from pokeagent_bench.quick_run import SUITES
from pokeagent_bench.session import Session
from pokeagent_bench.submission import this_harness

ROOT = Path(__file__).resolve().parents[1]
RELEASED = json.loads((ROOT / 'tests/fixtures/candidate-released-specs.json').read_text())
ROM = os.environ.get('POKEBENCH_ROM')
FIXTURES = os.environ.get('POKEBENCH_CANDIDATE_FIXTURES')
needs_starts = pytest.mark.skipif(not ROM or not FIXTURES,
                                  reason='The Red ROM and the candidate starts are not distributed. Set POKEBENCH_ROM '
                                         'and POKEBENCH_CANDIDATE_FIXTURES')
CANDIDATES = frozenset({'navigation-vermilion-gym-switches', 'objectives-saffron-gate-drink',
                        'navigation-safari-zone-secret-house', 'battle-champion-no-items-no-faint',
                        'battle-elite-four-no-items-no-faint'})
TASK_IDS = sorted(CANDIDATES)


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


def clear():
    catalog.candidate_tasks.cache_clear()
    catalog.milestone_tasks.cache_clear()
    catalog.retired_tasks.cache_clear()
    runtime._events.cache_clear()


@pytest.fixture(autouse=True)
def packaged_caches():
    """Read the packaged catalogs, whatever an earlier test cached."""
    clear()
    yield
    clear()


def test_released_catalog_suites_and_fixture_pack_match_main():
    now = released_now()
    for key in ('catalog_files', 'categories', 'packed', 'suites'):
        assert now[key] == RELEASED[key], key
    assert now['tasks'].keys() == RELEASED['tasks'].keys()
    changed = sorted(name for name, row in now['tasks'].items() if row != RELEASED['tasks'][name])
    assert not changed, f'released specifications changed: {changed}'


def test_short_and_long_task_lists_match_main():
    for track in (SHORT, LONG):
        listed = sorted(task['id'] for group in load_catalog() if for_category(group['category']) == track
                        for task in group['evals'])
        recorded = sorted(name for name, row in RELEASED['tasks'].items() if row['track'] == track and row['active'])
        assert listed == recorded
        assert not CANDIDATES & set(listed)


def test_candidate_catalog_is_never_loaded_by_the_released_suites(tmp_path):
    released_folder = catalog_files()[0].parent
    assert {path.parent for path in catalog.candidate_files()} == {released_folder / 'candidates'}
    assert not set(catalog.candidate_files()) & set(catalog_files())
    released = {task['id'] for group in load_catalog(include_retired=True) for task in group['evals']}
    assert catalog.candidate_tasks() == CANDIDATES and not released & CANDIDATES
    assert not {row['id'] for row in catalog_execution.inventory(tmp_path)['tasks']} & CANDIDATES
    assert {row['id'] for row in catalog_execution.inventory(tmp_path, candidates=True)['tasks']} == CANDIDATES
    for benchmark in (SHORT, LONG):
        with pytest.raises(ValueError, match='Tasks are not in'):
            catalog_batch.plan(tmp_path, ['codex:model'], tasks=[TASK_IDS[0]], benchmark=benchmark)


def test_no_released_task_sets_a_stop_rule_and_the_released_elite_four_is_kept():
    for group in load_catalog(include_retired=True):
        for task in group['evals']:
            assert 'no_faint' not in task and 'fail_on' not in task, task['id']
    released = catalog.task_definition('battle-elite-four-no-items')
    assert digest(encoded(released)) == RELEASED['tasks']['battle-elite-four-no-items']['spec_sha256']
    assert catalog.task_definition('battle-elite-four-no-items-no-faint')['no_faint'] is True


def test_candidate_catalogs_are_data_outside_the_harness_hash():
    package = ROOT / 'src/pokeagent_bench'
    hashed = {path.name: digest(path.read_bytes()) for path in sorted(package.glob('*.py'))}
    assert this_harness()['source_sha256'] == digest(encoded(hashed))
    assert not list((package / 'catalogs/candidates').glob('*.py'))


def test_every_candidate_validates_with_caps_set_from_its_reference():
    groups = catalog.load_candidates()
    assert sorted(group['category'] for group in groups) == ['battle', 'navigation', 'objectives']
    for group in groups:
        for task in group['evals']:
            pins = task['fixture']
            assert task['difficulty'] == 'hard' and len(task['milestones']) >= 2
            assert task['decision_limit'] == catalog.candidate_cap(pins['decisions'])
            assert task['token_limit'] == catalog.CANDIDATE_TOKENS_PER_DECISION * task['decision_limit']
            assert task['agent_goal'] == task['objective']['description']
            assert task.get('no_faint', False) is (group['category'] == 'battle')
            assert task['id'] in catalog.milestone_tasks()


def test_candidate_text_has_no_em_dash_or_semicolon():
    for path in catalog.candidate_files():
        text = path.read_text()
        assert chr(0x2014) not in text and chr(0x3B) not in text, path.name


@pytest.mark.parametrize('decisions, cap', [
    (70, 350), (73, 370), (68, 340), (109, 550), (22, 110), (1, 5), (21, 110), (199, 1000), (2009, 10000),
    (2100, 11000),
])
def test_the_candidate_cap_is_five_times_the_reference_to_two_figures_rounded_half_up(decisions, cap):
    assert catalog.candidate_cap(decisions) == cap


@pytest.mark.parametrize('change, message', [
    (lambda task: task.update(decision_limit=task['decision_limit'] + 1), 'decision cap'),
    (lambda task: task.update(token_limit=task['token_limit'] - 1), 'token budget'),
    (lambda task: task['fixture'].pop('frames'), 'candidates pin'),
    (lambda task: task['fixture'].update(actions_sha256='0' * 63), 'SHA-256'),
    (lambda task: task['fixture'].update(decisions=0), 'positive integers'),
    (lambda task: task.update(difficulty='medium'), 'hard milestone tasks'),
])
def test_candidate_validation_refuses_drift(change, message):
    task = deepcopy(catalog.task_definition(TASK_IDS[0]))
    change(task)
    with pytest.raises(ValueError, match=message):
        catalog.validate_candidate(task)


@pytest.mark.parametrize('rules, message', [
    ({'no_faint': False}, 'no_faint is true'),
    ({'fail_on': []}, 'at least one check'),
    ({'fail_on': [{'check': {'map': 156}}]}, 'description and a check'),
    ({'fail_on': [{'description': ' ', 'check': {'map': 156}}]}, 'needs a description'),
    ({'fail_on': [{'description': 'Gate.', 'check': {}}]}, 'known RAM conditions'),
])
def test_stop_rules_refuse_bad_values(rules, message):
    with pytest.raises(ValueError, match=message):
        runtime.validate_rules({'id': 'battle-test', **rules})


@pytest.fixture
def candidate_root(tmp_path, monkeypatch):
    """The packaged catalogs and candidates, copied so a test can change one candidate file."""
    root = tmp_path / 'catalogs'
    (root / 'candidates').mkdir(parents=True)
    for path in catalog_files():
        (root / path.name).write_bytes(path.read_bytes())
    for path in catalog.candidate_files():
        (root / 'candidates' / path.name).write_bytes(path.read_bytes())
    monkeypatch.setattr(catalog, '_root', lambda: root)
    clear()
    yield root / 'candidates'
    clear()


def edit(path, change):
    group = json.loads(path.read_text())
    change(group)
    path.write_text(json.dumps(group))


def reuse_released_id(group):
    group['evals'][0]['id'] = group['evals'][0]['objective']['task_id'] = 'battle-elite-four-no-items'


@pytest.mark.parametrize('name, change, message', [
    ('battle.json', lambda group: group.pop('candidate'), 'says it is a candidate'),
    ('battle.json', reuse_released_id, 'reuse a released task id'),
    ('navigation.json', lambda group: group['evals'][1].update(fail_on=[{'check': {'map': 156}}]),
     'description and a check'),
])
def test_candidate_loader_refuses_bad_files(candidate_root, name, change, message):
    edit(candidate_root / name, change)
    with pytest.raises(ValueError, match=message):
        catalog.load_candidates()


def test_a_candidate_file_is_named_for_its_category(candidate_root):
    (candidate_root / 'battle.json').rename(candidate_root / 'league.json')
    with pytest.raises(ValueError, match='names its category'):
        catalog.load_candidates()


def test_fail_on_event_flags_are_read_with_the_milestone_flags(candidate_root):
    rule = {'description': 'Got HM03 some other way.', 'check': {'event': 2176}}
    edit(candidate_root / 'navigation.json', lambda group: group['evals'][1]['fail_on'].append(rule))
    assert runtime._events('navigation-safari-zone-secret-house') == (2176,)


OBJECTIVE = {'kind': 'catalog-task', 'task_id': 'battle-test-league', 'description': 'Win the League.'}
MILESTONES = [{'id': 'lorelei', 'description': 'Defeat Lorelei.', 'check': {'elite': 'Lorelei'}},
              {'id': 'bruno', 'description': 'Defeat Bruno.', 'check': {'elite': 'Bruno'}}]
GATE = {'description': 'Back in the Safari Zone gate.', 'check': {'map': 156}}


def rules_task(**rules):
    return {'id': OBJECTIVE['task_id'], 'milestones': deepcopy(MILESTONES), **rules}


def facts(beaten=(), **changes):
    state = {'valid': True, 'map_id': 113, 'battle': 0, 'x': 5, 'y': 5, 'events': {}, 'items': [], 'badges': 255,
             'story': {}, 'elite': {name: name in beaten for name in runtime.ELITE}, 'champion': False,
             'hall_of_fame': 0, 'party': [{'hp': 50}, {'hp': 40}]}
    state.update(changes)
    return state


ONE_DOWN = [{'hp': 0}, {'hp': 40}]


def test_no_faint_stops_on_the_first_faint_and_keeps_earned_milestones():
    evaluator = runtime.MilestoneEvaluator(facts(), OBJECTIVE, rules_task(no_faint=True))
    assert evaluator.observe(facts(['Lorelei']), 1, 0) == []
    assert evaluator.observe(facts(['Lorelei']), 2, 0)[0]['id'] == 'milestone:lorelei'
    assert evaluator.observe(facts(['Lorelei'], party=ONE_DOWN), 3, 0) == []
    assert evaluator.disqualified and evaluator.disqualification_reason == 'A party member fainted'
    both = facts(['Lorelei', 'Bruno'])
    assert evaluator.observe(both, 4, 0) == [] and evaluator.observe(both, 5, 0) == []
    assert evaluator.score == 1


def test_without_no_faint_only_a_blackout_stops_the_run():
    evaluator = runtime.MilestoneEvaluator(facts(), OBJECTIVE, rules_task())
    assert evaluator.observe(facts(party=ONE_DOWN), 1, 0) == [] and not evaluator.disqualified
    assert evaluator.observe(facts(party=[{'hp': 0}, {'hp': 0}]), 2, 0) == []
    assert evaluator.disqualification_reason == 'Blackout during the task'


def test_fail_on_stops_the_run_only_when_it_holds_on_two_different_frames():
    evaluator = runtime.MilestoneEvaluator(facts(), OBJECTIVE, rules_task(fail_on=[GATE]))
    gate = facts(map_id=156)
    assert evaluator.observe(gate, 1, 0) == [] and not evaluator.disqualified
    assert evaluator.observe(facts(), 2, 0) == [] and not evaluator.disqualified
    assert evaluator.observe(gate, 3, 0) == [] and evaluator.observe(gate, 3, 0) == []
    assert not evaluator.disqualified
    assert evaluator.observe(facts(map_id=156, battle=1), 4, 0) == [] and not evaluator.disqualified
    assert evaluator.observe(gate, 5, 0) == [] and evaluator.observe(gate, 6, 0) == []
    assert evaluator.disqualified and evaluator.disqualification_reason == GATE['description']


def test_a_start_that_already_breaks_a_stop_rule_is_refused():
    with pytest.raises(ValueError, match='fainted Pokemon'):
        runtime.MilestoneEvaluator(facts(party=ONE_DOWN), OBJECTIVE, rules_task(no_faint=True))
    with pytest.raises(ValueError, match='already holds at the start'):
        runtime.MilestoneEvaluator(facts(map_id=156), OBJECTIVE, rules_task(fail_on=[GATE]))
    runtime.MilestoneEvaluator(facts(party=ONE_DOWN), OBJECTIVE, rules_task())


def test_stop_rules_survive_a_checkpoint_and_an_older_checkpoint_keeps_the_defaults():
    evaluator = runtime.MilestoneEvaluator(facts(), OBJECTIVE, rules_task(no_faint=True, fail_on=[GATE]))
    evaluator.observe(facts(map_id=156), 1, 0)
    restored = recovery.unpack(json.loads(encoded(recovery.pack(evaluator))))
    assert vars(restored) == vars(evaluator)
    assert restored.observe(facts(map_id=156), 2, 0) == [] and restored.disqualified
    older = runtime.MilestoneEvaluator(facts(), OBJECTIVE, rules_task())
    for name in ('no_faint', 'fail_on', 'failing'):
        delattr(older, name)
    restored = recovery.unpack(json.loads(encoded(recovery.pack(older))))
    assert restored.observe(facts(map_id=156, party=ONE_DOWN), 1, 0) == [] and not restored.disqualified


def test_session_records_the_candidate_track_and_stops_on_a_faint(tmp_path, monkeypatch, engine):
    task = catalog.task_definition('battle-champion-no-items-no-faint')
    state = facts(['Lorelei', 'Bruno', 'Agatha', 'Lance'], map_id=120, party=[{'hp': 148}, {'hp': 136}, {'hp': 226}])
    monkeypatch.setattr(runtime, 'milestone_evidence', lambda engine, task_id: deepcopy(state))
    scenario = {'task_id': task['id'], 'objective': deepcopy(task['objective']),
                'action_policy': 'assisted-gameplay-v1', 'tested_skill': 'battle-strategy'}
    session = Session(engine, tmp_path / 'run', scenario, goal='challenge')
    try:
        assert session.score_max == 2
        assert session.manifest['benchmark_track'] == 'candidate'
        assert session.manifest['evaluation_spec_sha256'] == digest(encoded(task))
        state['party'] = [{'hp': 148}, {'hp': 0}, {'hp': 226}]
        session.wait('wait-1', 3)
        result = json.loads((tmp_path / 'run' / 'result.json').read_text())
        assert result['stop_reason'] == 'challenge_failed'
        assert (result['score'], result['score_max'], result['completed']) == (0, 2, False)
        assert result['failure_reason'] == 'A party member fainted'
    finally:
        session.close()


@needs_starts
@pytest.mark.parametrize('task_id', TASK_IDS)
def test_each_built_start_and_reference_proof_match_the_pins(task_id):
    from pokeagent_bench.game import RedEngine
    task = catalog.task_definition(task_id)
    pins = task['fixture']
    folder = catalog_execution.select_scenario(Path(FIXTURES), task_id)
    state = (folder / 'initial.state').read_bytes()
    scenario = json.loads((folder / 'scenario.json').read_text())
    proof = json.loads((folder / 'reference-validation.json').read_text())
    assert digest(state) == scenario['state_sha256'] == proof['state_sha256'] == pins['state_sha256']
    assert scenario['catalog_sha256'] == proof['evaluation_spec_sha256'] == digest(encoded(task))
    assert proof['completed'] and proof['replay']['verified']
    assert proof['replay']['score'] == len(task['milestones'])
    assert (proof['replay']['actions'], proof['replay']['frames']) == (pins['actions'], pins['frames'])
    engine = RedEngine(Path(ROM), state)
    try:
        start = runtime.milestone_evidence(engine, task_id)
        evaluator = runtime.MilestoneEvaluator(start, task['objective'])
        assert evaluator.observe(start, 1, 0) == [] and not evaluator.disqualified
    finally:
        engine.close()
