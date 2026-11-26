"""The five harder Short tasks: their caps follow their pinned references, and their stop rules hold.

They are released Short tasks under red-v0.64-harder-short. Each pins the digest of its start and of
its reference inputs, and its caps are set from that reference. Their two stop rules, no_faint and
fail_on, are opt-in fields of the milestone runtime that no other task sets.

The tests that need the Red ROM skip without it. Set POKEBENCH_ROM to the Red ROM. They unpack the
shipped fixture pack, the same way setup does, and check each start and reference proof against the pins.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from pokeagent_bench import catalog_execution, local_setup, recovery
from pokeagent_bench import evaluation_catalog as catalog
from pokeagent_bench import milestone_runtime as runtime
from pokeagent_bench.benchmark_tracks import SHORT, for_category
from pokeagent_bench.core import digest, encoded
from pokeagent_bench.evaluation_catalog import catalog_files, load_catalog
from pokeagent_bench.session import Session
from pokeagent_bench.submission import this_harness

ROOT = Path(__file__).resolve().parents[1]
ROM = os.environ.get('POKEBENCH_ROM')
needs_rom = pytest.mark.skipif(not ROM, reason='The Red ROM is not distributed. Set POKEBENCH_ROM')
HARDER = frozenset({'navigation-vermilion-gym-switches', 'objectives-saffron-gate-drink',
                    'navigation-safari-zone-secret-house', 'battle-champion-no-items-no-faint',
                    'battle-elite-four-no-items-no-faint'})
TASK_IDS = sorted(HARDER)


def clear():
    catalog.milestone_tasks.cache_clear()
    catalog.retired_tasks.cache_clear()
    runtime._events.cache_clear()


@pytest.fixture(autouse=True)
def packaged_caches():
    """Read the packaged catalogs, whatever an earlier test cached."""
    clear()
    yield
    clear()


def released():
    return {task['id']: (group['category'], task) for group in load_catalog(include_retired=True)
            for task in group['evals']}


def test_only_the_five_harder_tasks_pin_a_reference_and_set_a_stop_rule():
    tasks = released()
    assert {name for name, (_, task) in tasks.items() if 'fixture' in task} == HARDER
    assert {name for name, (_, task) in tasks.items() if task.get('no_faint')} == {
        'battle-elite-four-no-items-no-faint', 'battle-champion-no-items-no-faint'}
    assert {name for name, (_, task) in tasks.items() if 'fail_on' in task} == {'navigation-safari-zone-secret-house'}
    assert 'no_faint' not in catalog.task_definition('battle-elite-four-no-items')


def test_the_harder_tasks_are_short_tasks_in_the_released_catalogs():
    short = {task['id'] for group in load_catalog() if for_category(group['category']) == SHORT
             for task in group['evals']}
    assert HARDER <= short
    assert not (ROOT / 'src/pokeagent_bench/catalogs/candidates').exists()


def test_the_catalogs_stay_data_outside_the_harness_hash():
    package = ROOT / 'src/pokeagent_bench'
    hashed = {path.name: digest(path.read_bytes()) for path in sorted(package.glob('*.py'))}
    assert this_harness()['source_sha256'] == digest(encoded(hashed))
    assert all(path.suffix == '.json' for path in catalog_files())


def test_every_harder_task_validates_with_caps_set_from_its_reference():
    tasks = released()
    for name in TASK_IDS:
        category, task = tasks[name]
        pins = task['fixture']
        assert catalog.validate_reference_pins(deepcopy(task)) == task
        assert task['difficulty'] == 'hard' and len(task['milestones']) >= 2
        assert task['decision_limit'] == catalog.reference_cap(pins['decisions'])
        assert task['token_limit'] == catalog.TOKENS_PER_DECISION * task['decision_limit']
        assert task['agent_goal'] == task['objective']['description']
        assert task.get('no_faint', False) is (category == 'battle')
        assert name in catalog.milestone_tasks()


def test_harder_task_text_has_no_em_dash_or_semicolon():
    tasks = released()
    for name in TASK_IDS:
        text = json.dumps(tasks[name][1], ensure_ascii=False)
        assert chr(0x2014) not in text and chr(0x3B) not in text, name


@pytest.mark.parametrize('decisions, cap', [
    (70, 350), (73, 370), (68, 340), (109, 550), (22, 110), (1, 5), (21, 110), (199, 1000), (2009, 10000),
    (2100, 11000),
])
def test_the_reference_cap_is_five_times_the_reference_to_two_figures_rounded_half_up(decisions, cap):
    assert catalog.reference_cap(decisions) == cap


@pytest.mark.parametrize('change, message', [
    (lambda task: task.update(decision_limit=task['decision_limit'] + 1), 'decision cap'),
    (lambda task: task.update(token_limit=task['token_limit'] - 1), 'token budget'),
    (lambda task: task['fixture'].pop('frames'), 'a pinned task pins'),
    (lambda task: task['fixture'].update(actions_sha256='0' * 63), 'SHA-256'),
    (lambda task: task['fixture'].update(decisions=0), 'positive integers'),
    (lambda task: task.pop('milestones'), 'only milestone tasks'),
])
def test_reference_pin_validation_refuses_drift(change, message):
    task = deepcopy(catalog.task_definition(TASK_IDS[0]))
    change(task)
    with pytest.raises(ValueError, match=message):
        catalog.validate_reference_pins(task)


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
def catalog_root(tmp_path, monkeypatch):
    """The packaged catalogs, copied so a test can change one task."""
    root = tmp_path / 'catalogs'
    root.mkdir()
    for path in catalog_files():
        (root / path.name).write_bytes(path.read_bytes())
    monkeypatch.setattr(catalog, '_root', lambda: root)
    clear()
    yield root
    clear()


def edit_safari(root, change):
    path = root / 'navigation.json'
    group = json.loads(path.read_text())
    change(next(task for task in group['evals'] if task['id'] == 'navigation-safari-zone-secret-house'))
    path.write_text(json.dumps(group))


def test_the_catalog_loader_refuses_a_bad_stop_rule(catalog_root):
    edit_safari(catalog_root, lambda task: task.update(fail_on=[{'check': {'map': 156}}]))
    with pytest.raises(ValueError, match='description and a check'):
        load_catalog()


def test_fail_on_event_flags_are_read_with_the_milestone_flags(catalog_root):
    rule = {'description': 'Got HM03 some other way.', 'check': {'event': 2176}}
    edit_safari(catalog_root, lambda task: task['fail_on'].append(rule))
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


def test_session_records_the_short_track_and_stops_on_a_faint(tmp_path, monkeypatch, engine):
    task = catalog.task_definition('battle-champion-no-items-no-faint')
    state = facts(['Lorelei', 'Bruno', 'Agatha', 'Lance'], map_id=120, party=[{'hp': 148}, {'hp': 136}, {'hp': 226}])
    monkeypatch.setattr(runtime, 'milestone_evidence', lambda engine, task_id: deepcopy(state))
    scenario = {'task_id': task['id'], 'objective': deepcopy(task['objective']),
                'action_policy': 'assisted-gameplay-v1', 'tested_skill': 'battle-strategy'}
    session = Session(engine, tmp_path / 'run', scenario, goal='challenge')
    try:
        assert session.score_max == 2
        assert session.manifest['benchmark_track'] == 'pokebench'
        assert session.manifest['evaluation_spec_sha256'] == digest(encoded(task))
        state['party'] = [{'hp': 148}, {'hp': 0}, {'hp': 226}]
        session.wait('wait-1', 3)
        result = json.loads((tmp_path / 'run' / 'result.json').read_text())
        assert result['stop_reason'] == 'challenge_failed'
        assert (result['score'], result['score_max'], result['completed']) == (0, 2, False)
        assert result['failure_reason'] == 'A party member fainted'
    finally:
        session.close()


@pytest.fixture(scope='module')
def shipped(tmp_path_factory):
    """The shipped fixture pack, unpacked with the user's ROM the way setup does."""
    fixtures = tmp_path_factory.mktemp('shipped') / 'fixtures'
    local_setup.unpack_fixtures(local_setup.check_rom(ROM), fixtures)
    return fixtures


@needs_rom
@pytest.mark.parametrize('task_id', TASK_IDS)
def test_each_shipped_start_and_reference_proof_match_the_pins(shipped, task_id):
    from pokeagent_bench.game import RedEngine
    task = catalog.task_definition(task_id)
    pins = task['fixture']
    folder = catalog_execution.select_scenario(shipped, task_id)
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
