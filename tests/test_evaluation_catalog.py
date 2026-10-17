from copy import deepcopy

import pytest

from pokeagent_bench.evaluation_catalog import CATEGORIES, load_catalog, summary, validate_category


def category():
    return {'category': 'navigation', 'title': 'Navigation', 'evals': [
        {'id': f'navigation-example-{i}', 'title': f'Example {i}', 'difficulty': 'medium',
         'tested_skill': 'navigation', 'mode': 'gameplay', 'action_policy': 'assisted-gameplay-v1',
         'objective': {'kind': 'location', 'map_id': 0, 'x': 1, 'y': 1, 'description': 'Reach the target'},
         'agent_goal': 'Reach the town target', 'scenario_details': ['Town target at (1,1)'],
         'open_questions': ['Prepare the save'], 'start': 'Curated town checkpoint', 'success': ['Reach the target'], 'failure': ['Budget exhausted'],
         'variants': ['Starting positions'], 'token_limit': 100000, 'existing_task': None,
         'requirements': ['Curate a starting save'], 'status': 'specified', 'calibration': 'pending'}
        for i in range(10)]}


def test_validated_copy_is_detached():
    value = category()
    checked = validate_category(value)
    checked['evals'][0]['success'].append('changed')
    assert value == category()


@pytest.mark.parametrize('change', [
    {'status': 'ready'}, {'calibration': 'passed'}, {'action_policy': 'manual-menu-v1'},
    {'mode': 'preparation'}, {'token_limit': True}, {'requirements': []},
    {'agent_goal': ''}, {'scenario_details': []}, {'open_questions': 'unknown'},
    {'objective': {'kind': 'invented-grader', 'description': 'No implementation'}},
    {'existing_task': '../../secret'},
])
def test_rejects_false_readiness_unsupported_scoring_and_wrong_controls(change):
    value = category()
    value['evals'][0].update(change)
    with pytest.raises(ValueError):
        validate_category(value)


def test_rejects_duplicate_and_missing_evals():
    value = category()
    value['evals'][-1] = deepcopy(value['evals'][0])
    with pytest.raises(ValueError, match='Duplicate'):
        validate_category(value)
    value['evals'] = []
    with pytest.raises(ValueError, match='at least one eval'):
        validate_category(value)


def test_packaged_catalog_has_distinct_evals_and_honest_status():
    groups = load_catalog()
    assert tuple(group['category'] for group in groups) == CATEGORIES
    entries = [evaluation for group in groups for evaluation in group['evals']]
    assert len(entries) == len({e['id'] for e in entries}) == 50
    report = summary()
    assert report['runnable_new_evals'] == report['model_calls'] == 0
    assert report['eval_count'] == 50
    operations = load_catalog('operations')[0]['evals']
    assert all(e['action_policy'] == 'manual-menu-v1' for e in operations)
    preparation = load_catalog('preparation')[0]['evals']
    assert all(e['mode'] == 'preparation' and e['objective'] is None for e in preparation)


def test_fixture_inventory_does_not_promote_readiness(tmp_path):
    groups = load_catalog()
    source = next(e['existing_task'] for group in groups for e in group['evals'] if e['existing_task'])
    saved = tmp_path / source / 'variant-01'
    saved.mkdir(parents=True)
    (saved / 'scenario.json').write_text('{}')
    report = summary(fixtures=tmp_path)
    entries = [e for group in report['categories'] for e in group['evals']]
    assert all(e['source_variants_found'] == 1 for e in entries if e['existing_task'] == source)
    assert report['runnable_new_evals'] == 0


def test_cli_catalog_command_is_inspection_only():
    from pokeagent_bench.cli import parser
    args = parser().parse_args(['catalog', '--category', 'preparation'])
    assert args.command == 'catalog'
    assert args.category == 'preparation'
    with pytest.raises(ValueError, match='Unknown'):
        load_catalog('unknown')


def test_campaign_is_one_attempt_with_unique_milestones():
    campaigns = load_catalog('campaign')[0]['evals']
    assert len(campaigns) == 1
    campaign = campaigns[0]
    assert campaign['run_unit'] == 'one-continuous-attempt'
    milestones = [m['id'] for m in campaign['milestones']]
    assert len(milestones) == len(set(milestones)) == 50
    assert campaign['objective']['target'] == 'champion'
    assert sum(key.startswith('badge:') for key in milestones) == 8
    groups = load_catalog()
    ids = {e['id'] for group in groups for e in group['evals']}
    assert 'objectives-resume-context-reset' not in ids
    assert 'battle-league-constrained' in ids


def test_portal_uses_actual_counts_and_campaign_milestones():
    from pokeagent_bench.catalog_portal import render_catalog
    page = render_catalog()
    assert '49 task drafts' in page
    assert 'Milestones within this one attempt' not in page
    long_page = render_catalog(summary(benchmark='pokebench-long'))
    assert 'Milestones within this one attempt' in long_page
    assert 'Defeat Lance' in long_page
    assert '__COUNT__' not in page


def test_campaign_score_is_bounded_and_diagnostic_metrics_do_not_award_points():
    campaign = load_catalog('campaign')[0]['evals'][0]
    plan = campaign['scoring_plan']
    assert plan['status'] == 'proposed-not-runtime-scoring'
    assert sum(m['points'] for m in campaign['milestones']) == plan['maximum_points'] == 1000
    for group in plan['groups']:
        milestones = [m for m in campaign['milestones'] if m['group'] == group['id']]
        assert len(milestones) == group['count']
        assert sum(m['points'] for m in milestones) == group['points']
    assert all(m['points'] == 0 for m in campaign['run_metrics'])
    assert sum(m['points'] for m in campaign['milestones'] if m['group'] in ('badges', 'elite', 'champion')) == 800


def test_cleanup_keeps_quests_distinct_and_inventory_variant_manual():
    groups = {group['category']: group for group in load_catalog()}
    assert len(groups['navigation']['evals']) == 6
    assert len(groups['objectives']['evals']) == 10
    quests = {task['id']: task for task in groups['objectives']['evals']}
    assert 'objectives-infeasible-plan-alternate' in quests
    assert 'objectives-recover-earlier-mistake' not in quests
    assert load_catalog('quests') == load_catalog('objectives')
    operations = {task['id']: task for task in groups['operations']['evals']}
    variant = operations['objectives-recover-earlier-mistake']
    assert variant['variant_of'] == 'operations-menu-checklist'
    assert variant['action_policy'] == 'manual-menu-v1'
    assert variant['difficulty'] == 'easy'
    assert summary()['primary_task_count'] == 49
    assert summary()['variant_count'] == 1
    retired = {task['id'] for group in load_catalog(include_retired=True)
               for task in group['evals'] if not task.get('active', True)}
    assert retired == {'navigation-town-landmark', 'navigation-multifloor-required-stops'}


def test_portal_explains_bicycle_cases_and_does_not_inflate_difficulty():
    from pokeagent_bench.catalog_portal import render_catalog
    page = render_catalog()
    assert '<h2>Quests</h2>' in page
    assert 'What this tests' in page
    assert 'Expected solution (reviewer explanation)' in page
    assert '10 tasks + 1 variant' in page
    assert 'id="navigation-town-landmark"' not in page
    assert 'id="navigation-multifloor-required-stops"' not in page
    assert 'Estimate: Easy' in page


def test_menu_end_conditions_are_in_the_agent_instruction():
    tasks = load_catalog('operations')[0]['evals']
    requires_menu_exit = {
        'operations-heal-potion-target', 'operations-cure-poison',
        'operations-restore-move-pp', 'operations-party-reorder',
        'operations-deposit-withdraw', 'operations-teach-tm-replace-move',
        'operations-withdraw-item-and-use', 'operations-menu-checklist',
    }
    for task in tasks:
        if task['id'] in requires_menu_exit:
            assert 'returning to the overworld or pause menu' in task['agent_goal']
            assert any('final screen' in condition.lower() for condition in task['success'])
