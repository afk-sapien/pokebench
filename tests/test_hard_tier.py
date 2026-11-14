"""PokeBench Hard is its own table, scored by ordered private milestones read from RAM."""
from copy import deepcopy
import json

import pytest

from pokeagent_bench import benchmark_tracks as tracks
from pokeagent_bench import catalog_batch as batch
from pokeagent_bench import evaluation_catalog as catalog
from pokeagent_bench import milestone_runtime as runtime
from pokeagent_bench import quick_run, recovery, submission
from pokeagent_bench.core import encoded, write_json
from pokeagent_bench.session import Session

TASK = 'navigation-hard-test-cave'
OBJECTIVE = {'kind': 'catalog-task', 'task_id': TASK, 'description': 'Cross the cave and leave by the far exit.'}
MILESTONES = [
    {'id': 'second-floor', 'description': 'Reach the second floor.', 'check': {'map': 194}},
    {'id': 'switch', 'description': 'Press the floor switch.', 'check': {'event': 2000}},
    {'id': 'exit', 'description': 'Leave by the far exit.', 'check': {'map': 34, 'area': [0, 0, 20, 20]}},
]


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
    catalog._hard_definitions.cache_clear()
    catalog.retired_tasks.cache_clear()
    runtime._events.cache_clear()


def write_hard(root, *entries):
    root.mkdir(exist_ok=True)
    write_json(root / 'navigation.json', {'category': 'navigation', 'title': 'Navigation', 'evals': list(entries)})


@pytest.fixture
def hard_root(tmp_path, monkeypatch):
    root = tmp_path / 'hard'
    write_hard(root, task())
    monkeypatch.setattr(catalog, '_hard_root', lambda: root)
    clear()
    yield root
    clear()


def facts(**changes):
    state = {'valid': True, 'map_id': 108, 'battle': 0, 'x': 5, 'y': 5, 'events': {'2000': False}, 'items': [],
             'badges': 255, 'story': {}, 'elite': {name: False for name in runtime.ELITE}, 'champion': False,
             'hall_of_fame': 0, 'party': [{'hp': 50}]}
    state.update(changes)
    return state


def test_hard_tasks_stay_out_of_short_and_long(hard_root):
    assert catalog.hard_tasks() == {TASK}
    assert TASK not in {entry['id'] for group in catalog.load_catalog(include_retired=True) for entry in group['evals']}
    assert [group['category'] for group in catalog.load_catalog(hard=True)] == ['navigation']
    assert catalog.task_definition(TASK)['milestones'] == MILESTONES
    assert tracks.for_task(TASK, 'navigation') == tracks.HARD
    assert tracks.for_task('navigation-forest-crossing', 'navigation') == tracks.SHORT
    assert tracks.for_task('campaign-full-game', 'campaign') == tracks.LONG
    short = catalog.summary(benchmark=tracks.SHORT)
    assert short['primary_task_count'] == 46 and short['eval_count'] == 47 and short['category_count'] == 5
    hard = catalog.summary(benchmark=tracks.HARD)
    assert hard['eval_count'] == 1 and hard['categories'][0]['evals'][0]['id'] == TASK


def test_without_hard_tasks_nothing_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, '_hard_root', lambda: tmp_path / 'missing')
    clear()
    try:
        assert catalog.hard_tasks() == frozenset()
        assert catalog.load_catalog(hard=True) == []
        assert catalog.summary(benchmark=tracks.HARD)['eval_count'] == 0
    finally:
        clear()


@pytest.mark.parametrize('changes,message', [
    ({'decision_limit': None}, 'decision cap'),
    ({'difficulty': 'easy'}, 'hard or stretch'),
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
def test_hard_loader_rejects_bad_tasks(hard_root, changes, message):
    entry = task(**changes)
    if entry['decision_limit'] is None:
        del entry['decision_limit']
    write_hard(hard_root, entry)
    clear()
    with pytest.raises(ValueError, match=message):
        catalog.load_catalog(hard=True)


def test_hard_ids_must_differ_from_short(hard_root):
    short = catalog.load_catalog('navigation')[0]['evals'][0]['id']
    write_hard(hard_root, task(id=short, objective={**OBJECTIVE, 'task_id': short}))
    clear()
    with pytest.raises(ValueError, match='must differ'):
        catalog.hard_tasks()


def test_milestones_count_only_in_order_and_on_two_frames(hard_root):
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


def test_blackout_ends_the_task_and_keeps_earned_milestones(hard_root):
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
def test_start_must_not_meet_a_milestone_or_be_blacked_out(hard_root, start):
    with pytest.raises(ValueError, match='already met|blacked out'):
        runtime.MilestoneEvaluator(start, OBJECTIVE)


def test_league_checks_read_wins_and_new_hall_of_fame_entries(hard_root):
    evaluator = runtime.MilestoneEvaluator(facts(hall_of_fame=2), OBJECTIVE)
    assert evaluator.holds({'elite': 'Bruno'}, facts(elite={**facts()['elite'], 'Bruno': True}))
    assert not evaluator.holds({'elite': 'Bruno'}, facts())
    assert not evaluator.holds({'hall_of_fame': True}, facts(hall_of_fame=2))
    assert evaluator.holds({'hall_of_fame': True}, facts(hall_of_fame=3))
    assert evaluator.holds({'badge': 6}, facts(badges=64)) and not evaluator.holds({'badge': 6}, facts(badges=63))
    assert evaluator.holds({'item': 73}, facts(items=[[73, 1]])) and not evaluator.holds({'item': 73}, facts())
    assert evaluator.holds({'map': 3, 'near': [4, 5]}, facts(map_id=3, x=4, y=6))
    assert not evaluator.holds({'map': 3, 'near': [4, 5]}, facts(map_id=3, x=5, y=6))


def test_milestone_evaluator_survives_a_checkpoint(hard_root):
    evaluator = runtime.MilestoneEvaluator(facts(), OBJECTIVE)
    evaluator.observe(facts(map_id=194), 1, 0)
    evaluator.observe(facts(map_id=194), 2, 0)
    evaluator.observe(facts(map_id=194, events={'2000': True}), 3, 0)
    restored = recovery.unpack(json.loads(encoded(recovery.pack(evaluator))))
    assert type(restored) is runtime.MilestoneEvaluator and vars(restored) == vars(evaluator)
    assert restored.observe(facts(map_id=194, events={'2000': True}), 4, 0)[0]['id'] == 'milestone:switch'


def test_hard_session_records_the_track_and_partial_credit(hard_root, tmp_path, monkeypatch, engine):
    state = facts()
    monkeypatch.setattr(runtime, 'milestone_evidence', lambda engine, task_id: deepcopy(state))
    scenario = {'task_id': TASK, 'objective': deepcopy(OBJECTIVE), 'action_policy': 'assisted-gameplay-v1',
                'tested_skill': 'navigation'}
    session = Session(engine, tmp_path / 'run', scenario, goal='challenge')
    try:
        assert session.score_max == 3
        assert session.manifest['benchmark_track'] == tracks.HARD
        assert session.manifest['scoring_protocol'] == runtime.PROTOCOL
        state['map_id'] = 194
        session.wait('wait-1', 3)
        assert session.evaluator.score == 1
        state['party'] = [{'hp': 0}]
        session.wait('wait-2', 3)
        result = json.loads((tmp_path / 'run' / 'result.json').read_text())
        assert result['stop_reason'] == 'challenge_failed'
        assert (result['score'], result['score_max'], result['completed']) == (1, 3, False)
        assert result['failure_reason'] == 'Blackout during the Hard task'
    finally:
        session.close()


@pytest.fixture
def rows(tmp_path, monkeypatch):
    listed = {}
    for name, category, hard in [('navigation-forest-crossing', 'navigation', False), (TASK, 'navigation', True)]:
        folder = tmp_path / name
        folder.mkdir()
        write_json(folder / 'scenario.json', {'state_sha256': 'state', 'catalog_sha256': 'spec'})
        listed.setdefault(hard, []).append({'id': name, 'category': category, 'mode': 'gameplay', 'runnable': True,
                                            'variants': [{'path': str(folder), 'variant': 'default'}]})
    monkeypatch.setattr(batch, 'inventory', lambda root, hard=False: {'tasks': listed[hard]})
    monkeypatch.setattr(quick_run, 'inventory', lambda root, hard=False: {'tasks': listed[hard]})
    return tmp_path


def test_hard_batches_plan_and_rank_in_their_own_table(hard_root, rows, tmp_path):
    assert [cell['task_id'] for cell in batch.plan(rows, ['codex:test'])['cells']] == ['navigation-forest-crossing']
    manifest = batch.plan(rows, ['codex:test'], benchmark=tracks.HARD)
    assert [cell['task_id'] for cell in manifest['cells']] == [TASK]
    assert manifest['cells'][0]['benchmark'] == tracks.HARD and manifest['cells'][0]['decision_limit'] == 100
    with pytest.raises(ValueError, match='not in PokeBench Hard'):
        batch.plan(rows, ['codex:test'], ['navigation-forest-crossing'], benchmark=tracks.HARD)
    output = tmp_path / 'batch'
    output.mkdir()
    write_json(output / 'plan.json', manifest)
    (output / 'cell-0001').mkdir()
    write_json(output / 'cell-0001' / 'result.json', {'state': 'finished', 'score': 2, 'score_max': 3,
                                                       'usage': {'input_tokens': 10, 'output_tokens': 5}})
    summary = batch.report(output)['models'][0]
    assert summary['benchmark'] == tracks.HARD and summary['name'] == 'PokeBench Hard'
    assert summary['category_scores'] == {'navigation': pytest.approx(2 / 3)}
    assert summary['available_category_average'] == pytest.approx(2 / 3)
    assert summary['unranked_categories'] == []


def test_hard_suite_plans_ready_tasks_and_refuses_an_empty_suite(hard_root, rows, monkeypatch):
    manifest = quick_run.new_plan('hard', rows, 'codex', 'test')
    assert [cell['task_id'] for cell in manifest['cells']] == [TASK]
    assert manifest['cells'][0]['reasoning_effort'] == 'low'
    monkeypatch.setattr(quick_run, 'inventory', lambda root, hard=False: {'tasks': []})
    with pytest.raises(ValueError, match='No PokeBench Hard tasks are ready yet'):
        quick_run.new_plan('hard', rows, 'codex', 'test')


def test_hard_verification_expects_the_milestone_protocol(hard_root):
    assert submission.scoring(TASK) == {'goal': 'challenge', 'track': 'gameplay',
                                        'scoring_protocol': 'catalog-milestones-v1', 'score_max': 3}
    assert submission.scoring('navigation-forest-crossing')['scoring_protocol'] == 'catalog-tasks-v1'


def test_unknown_benchmark_names_all_three():
    with pytest.raises(ValueError, match='pokebench, pokebench-hard or pokebench-long'):
        tracks.validate('pokebench-extra')
