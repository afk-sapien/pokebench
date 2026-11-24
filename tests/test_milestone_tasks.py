"""Milestone tasks are Short tasks scored by ordered private milestones read from RAM."""
from copy import deepcopy
import json

import pytest

from pokeagent_bench import benchmark_tracks as tracks
from pokeagent_bench import catalog_batch as batch
from pokeagent_bench import evaluation_catalog as catalog
from pokeagent_bench import milestone_runtime as runtime
from pokeagent_bench import loop_budget, quick_run, recovery, submission
from pokeagent_bench.core import encoded, write_json
from pokeagent_bench.session import Session

TASK = 'navigation-test-cave'
OBJECTIVE = {'kind': 'catalog-task', 'task_id': TASK, 'description': 'Cross the cave and leave by the far exit.'}
MILESTONES = [
    {'id': 'second-floor', 'description': 'Reach the second floor.', 'check': {'map': 194}},
    {'id': 'switch', 'description': 'Press the floor switch.', 'check': {'event': 2000}},
    {'id': 'exit', 'description': 'Leave by the far exit.', 'check': {'map': 34, 'area': [0, 0, 20, 20]}},
]
PACKAGED = {path.name: json.loads(path.read_text()) for path in catalog.catalog_files()}


def task(**changes):
    entry = {'id': TASK, 'title': 'Cross a test cave', 'difficulty': 'hard', 'tested_skill': 'navigation',
             'mode': 'gameplay', 'action_policy': 'assisted-gameplay-v1', 'objective': deepcopy(OBJECTIVE),
             'start': 'Cave entrance.', 'success': ['Leave by the far exit.'], 'failure': ['The party blacks out.'],
             'variants': ['One start.'], 'token_limit': 1_500_000, 'decision_limit': 100, 'existing_task': None,
             'requirements': ['A scripted reference passes.'], 'status': 'specified', 'calibration': 'pending',
             'agent_goal': OBJECTIVE['description'], 'scenario_details': ['Party: one Pokemon.'],
             'open_questions': [], 'milestones': deepcopy(MILESTONES)}
    entry.update(changes)
    return entry


def clear():
    catalog.candidate_tasks.cache_clear()
    catalog.milestone_tasks.cache_clear()
    catalog.retired_tasks.cache_clear()
    runtime._events.cache_clear()


def write_catalog(root, entry):
    """The packaged catalogs with one extra navigation task."""
    root.mkdir(exist_ok=True)
    for name, group in PACKAGED.items():
        if name == 'navigation.json':
            group = {**group, 'evals': group['evals'] + [entry]}
        write_json(root / name, group)


@pytest.fixture
def catalog_root(tmp_path, monkeypatch):
    root = tmp_path / 'catalogs'
    write_catalog(root, task())
    monkeypatch.setattr(catalog, '_root', lambda: root)
    clear()
    yield root
    clear()


def facts(**changes):
    state = {'valid': True, 'map_id': 108, 'battle': 0, 'x': 5, 'y': 5, 'events': {'2000': False}, 'items': [],
             'badges': 255, 'story': {}, 'elite': {name: False for name in runtime.ELITE}, 'champion': False,
             'hall_of_fame': 0, 'party': [{'hp': 50}]}
    state.update(changes)
    return state


def test_milestone_tasks_are_short_tasks_in_their_category(catalog_root):
    assert TASK in catalog.milestone_tasks()
    # The campaign keeps its own milestone list and its own evaluator.
    assert 'campaign-full-game' not in catalog.milestone_tasks()
    assert catalog.task_definition(TASK)['milestones'] == MILESTONES
    short = catalog.summary(benchmark=tracks.SHORT)
    navigation = next(group for group in short['categories'] if group['category'] == 'navigation')
    assert TASK in {entry['id'] for entry in navigation['evals']}
    long = catalog.summary(benchmark=tracks.LONG)
    assert TASK not in {entry['id'] for group in long['categories'] for entry in group['evals']}


@pytest.mark.parametrize('changes,message', [
    ({'decision_limit': None}, 'decision cap'),
    ({'objective': {'kind': 'reach-map', 'map_id': 34, 'description': 'Leave the cave.'}}, 'own catalog evaluator'),
    ({'objective': {**OBJECTIVE, 'task_id': 'navigation-other'}}, 'Unknown task'),
    ({'milestones': []}, 'ordered milestones'),
    ({'milestones': [MILESTONES[0], MILESTONES[0]]}, 'distinct'),
    ({'milestones': [{'id': 'warp', 'description': 'Warp.', 'check': {'warp': 3}}]}, 'known RAM conditions'),
    ({'milestones': [{'id': 'spot', 'description': 'Stand.', 'check': {'near': [3, 4]}}]}, 'needs its map'),
    ({'milestones': [{'id': 'spot', 'description': 'Stand.', 'check': {'map': 3, 'area': [9, 0, 1, 1]}}]}, 'x0, y0, x1, y1'),
    ({'milestones': [{'id': 'quest', 'description': 'Story.', 'check': {'story': 'not-a-flag'}}]}, 'story flag'),
    ({'milestones': [{'id': 'win', 'description': 'Win.', 'check': {'champion': False}}]}, 'must be true'),
])
def test_loader_rejects_bad_milestone_tasks(catalog_root, changes, message):
    entry = task(**changes)
    if entry['decision_limit'] is None:
        del entry['decision_limit']
    write_catalog(catalog_root, entry)
    clear()
    with pytest.raises(ValueError, match=message):
        catalog.load_catalog('navigation')


def test_milestones_count_only_in_order_and_on_two_frames(catalog_root):
    evaluator = runtime.MilestoneEvaluator(facts(), OBJECTIVE)
    assert evaluator.score_max == 3 and evaluator.score == 0
    # The exit does not count before the earlier milestones.
    assert evaluator.observe(facts(map_id=34, x=3, y=3), 1, 0) == []
    assert evaluator.observe(facts(map_id=34, x=3, y=3), 2, 0) == []
    assert evaluator.observe(facts(map_id=194), 3, 0) == []
    # A battle on the right map does not confirm the floor.
    assert evaluator.observe(facts(map_id=194, battle=1), 4, 0) == []
    assert evaluator.observe(facts(map_id=194), 5, 0) == []
    assert evaluator.observe(facts(map_id=194), 5, 0) == []
    awards = evaluator.observe(facts(map_id=194), 6, 1.5)
    assert [award['id'] for award in awards] == ['milestone:second-floor'] and awards[0]['points'] == 1
    switched = {'2000': True}
    evaluator.observe(facts(map_id=194, events=switched), 7, 0)
    assert evaluator.observe(facts(map_id=194, events=switched), 8, 0)[0]['id'] == 'milestone:switch'
    # The exit area must hold, not just the map.
    evaluator.observe(facts(map_id=34, x=30, y=3, events=switched), 9, 0)
    assert evaluator.observe(facts(map_id=34, x=30, y=3, events=switched), 10, 0) == []
    evaluator.observe(facts(map_id=34, x=3, y=3, events=switched), 11, 0)
    assert evaluator.observe(facts(map_id=34, x=3, y=3, events=switched), 12, 0)[0]['id'] == 'milestone:exit'
    assert evaluator.complete() and evaluator.score == 3
    with pytest.raises(ValueError, match='backwards'):
        evaluator.observe(facts(), 11, 0)


def test_blackout_ends_the_task_and_keeps_earned_milestones(catalog_root):
    evaluator = runtime.MilestoneEvaluator(facts(), OBJECTIVE)
    evaluator.observe(facts(map_id=194), 1, 0)
    evaluator.observe(facts(map_id=194), 2, 0)
    assert evaluator.score == 1
    evaluator.observe(facts(map_id=194, party=[{'hp': 0}]), 3, 0)
    assert evaluator.disqualified and 'Blackout' in evaluator.disqualification_reason
    evaluator.observe(facts(map_id=194, events={'2000': True}), 4, 0)
    evaluator.observe(facts(map_id=194, events={'2000': True}), 5, 0)
    assert evaluator.score == 1 and not evaluator.complete()


@pytest.mark.parametrize('start', [facts(map_id=194), facts(party=[{'hp': 0}]), facts(battle=255)])
def test_start_must_not_meet_a_milestone_or_be_blacked_out(catalog_root, start):
    with pytest.raises(ValueError, match='already met|blacked out'):
        runtime.MilestoneEvaluator(start, OBJECTIVE)


def test_league_checks_read_wins_and_new_hall_of_fame_entries(catalog_root):
    evaluator = runtime.MilestoneEvaluator(facts(hall_of_fame=2), OBJECTIVE)
    assert evaluator.holds({'elite': 'Bruno'}, facts(elite={**facts()['elite'], 'Bruno': True}))
    assert not evaluator.holds({'elite': 'Bruno'}, facts())
    assert not evaluator.holds({'hall_of_fame': True}, facts(hall_of_fame=2))
    assert evaluator.holds({'hall_of_fame': True}, facts(hall_of_fame=3))
    assert evaluator.holds({'badge': 6}, facts(badges=64)) and not evaluator.holds({'badge': 6}, facts(badges=63))
    assert evaluator.holds({'item': 73}, facts(items=[[73, 1]])) and not evaluator.holds({'item': 73}, facts())
    assert evaluator.holds({'map': 3, 'near': [4, 5]}, facts(map_id=3, x=4, y=6))
    assert not evaluator.holds({'map': 3, 'near': [4, 5]}, facts(map_id=3, x=5, y=6))


def test_milestone_evaluator_survives_a_checkpoint(catalog_root):
    evaluator = runtime.MilestoneEvaluator(facts(), OBJECTIVE)
    evaluator.observe(facts(map_id=194), 1, 0)
    evaluator.observe(facts(map_id=194), 2, 0)
    evaluator.observe(facts(map_id=194, events={'2000': True}), 3, 0)
    restored = recovery.unpack(json.loads(encoded(recovery.pack(evaluator))))
    assert type(restored) is runtime.MilestoneEvaluator and vars(restored) == vars(evaluator)
    assert restored.observe(facts(map_id=194, events={'2000': True}), 4, 0)[0]['id'] == 'milestone:switch'


def test_session_records_the_short_track_and_partial_credit(catalog_root, tmp_path, monkeypatch, engine):
    state = facts()
    monkeypatch.setattr(runtime, 'milestone_evidence', lambda engine, task_id: deepcopy(state))
    scenario = {'task_id': TASK, 'objective': deepcopy(OBJECTIVE), 'action_policy': 'assisted-gameplay-v1',
                'tested_skill': 'navigation'}
    session = Session(engine, tmp_path / 'run', scenario, goal='challenge')
    try:
        assert session.score_max == 3
        assert session.manifest['benchmark_track'] == tracks.SHORT
        assert session.manifest['scoring_protocol'] == runtime.PROTOCOL
        state['map_id'] = 194
        session.wait('wait-1', 3)
        assert session.evaluator.score == 1
        state['party'] = [{'hp': 0}]
        session.wait('wait-2', 3)
        result = json.loads((tmp_path / 'run' / 'result.json').read_text())
        assert result['stop_reason'] == 'challenge_failed'
        assert (result['score'], result['score_max'], result['completed']) == (1, 3, False)
        assert result['failure_reason'] == 'Blackout during the task'
    finally:
        session.close()


@pytest.fixture
def rows(tmp_path, monkeypatch):
    listed = []
    for name in ('navigation-forest-crossing', TASK):
        folder = tmp_path / name
        folder.mkdir()
        write_json(folder / 'scenario.json', {'state_sha256': 'state', 'catalog_sha256': 'spec'})
        listed.append({'id': name, 'category': 'navigation', 'mode': 'gameplay', 'runnable': True,
                       'variants': [{'path': str(folder), 'variant': 'default'}]})
    monkeypatch.setattr(batch, 'inventory', lambda root: {'tasks': listed})
    monkeypatch.setattr(quick_run, 'inventory', lambda root: {'tasks': listed})
    return tmp_path


def test_milestone_tasks_plan_and_score_as_a_fraction_in_short(catalog_root, rows, tmp_path):
    planned = [cell['task_id'] for cell in batch.plan(rows, ['codex:test'])['cells']]
    assert planned == ['navigation-forest-crossing', TASK]
    manifest = batch.plan(rows, ['codex:test'], [TASK])
    assert manifest['cells'][0]['benchmark'] == tracks.SHORT and manifest['cells'][0]['decision_limit'] == 100
    with pytest.raises(ValueError, match='not in PokeBench Long'):
        batch.plan(rows, ['codex:test'], [TASK], benchmark=tracks.LONG)
    output = tmp_path / 'batch'
    output.mkdir()
    write_json(output / 'plan.json', manifest)
    (output / 'cell-0001').mkdir()
    write_json(output / 'cell-0001' / 'result.json', {'state': 'finished', 'score': 2, 'score_max': 3,
                                                       'usage': {'input_tokens': 10, 'output_tokens': 5}})
    summary = batch.report(output)['models'][0]
    assert summary['benchmark'] == tracks.SHORT and summary['name'] == 'PokeBench'
    assert summary['category_scores'] == {'navigation': pytest.approx(2 / 3)}
    assert summary['available_category_average'] == pytest.approx(2 / 3)
    assert 'unranked_categories' not in summary


def test_short_suite_includes_ready_milestone_tasks(catalog_root, rows, monkeypatch):
    manifest = quick_run.new_plan('short', rows, 'codex', 'test')
    assert TASK in [cell['task_id'] for cell in manifest['cells']]
    assert {cell['reasoning_effort'] for cell in manifest['cells']} == {'low'}
    # Every Short task stops after two thirds of its own token cap without a new milestone.
    guard = {cell['task_id']: cell['run_limits'] for cell in manifest['cells']}
    assert guard[TASK] == {'max_milestone_tokens': 1_000_000}
    assert all(limits['max_milestone_tokens'] == cell['token_limit'] * 2 // 3
               for cell, limits in zip(manifest['cells'], guard.values()))


def test_live_milestones_carry_the_stamps_the_guard_counts_from(catalog_root, tmp_path, monkeypatch, engine):
    state = facts()
    monkeypatch.setattr(runtime, 'milestone_evidence', lambda engine, task_id: deepcopy(state))
    scenario = {'task_id': TASK, 'objective': deepcopy(OBJECTIVE), 'action_policy': 'assisted-gameplay-v1',
                'tested_skill': 'navigation'}
    session = Session(engine, tmp_path / 'run', scenario, goal='challenge')
    try:
        session.current_decision = 4
        session.usage.update(input_tokens=900, output_tokens=100)
        state['map_id'] = 194
        session.wait('wait-1', 3)
        award = session.evaluator.awarded['milestone:second-floor']
        assert (award['decision'], award['tokens']) == (4, 1000)
        gap = loop_budget.milestone_gap(session.evaluator.awarded, 1600, 6)
        assert (gap['tokens_without_milestone'], gap['last_milestone_decision']) == (600, 4)
    finally:
        session.close()
    monkeypatch.setattr(quick_run, 'inventory', lambda root: {'tasks': []})
    with pytest.raises(ValueError, match='No PokeBench tasks are ready yet'):
        quick_run.new_plan('short', rows, 'codex', 'test')


def test_verification_expects_the_milestone_protocol(catalog_root):
    assert submission.scoring(TASK) == {'goal': 'challenge', 'track': 'gameplay',
                                        'scoring_protocol': 'catalog-milestones-v1', 'score_max': 3}
    assert submission.scoring('navigation-forest-crossing')['scoring_protocol'] == 'catalog-tasks-v1'


def test_unknown_benchmark_names_both():
    with pytest.raises(ValueError, match='pokebench or pokebench-long'):
        tracks.validate('pokebench-extra')
