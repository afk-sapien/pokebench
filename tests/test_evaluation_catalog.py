from copy import deepcopy

import pytest

from pokeagent_bench.evaluation_catalog import (
    CATEGORIES, catalog_files, load_catalog, retired_tasks, summary, validate_category,
)


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
    assert len(entries) == len({e['id'] for e in entries}) == 45
    report = summary()
    assert report['runnable_new_evals'] == report['model_calls'] == 0
    assert report['eval_count'] == 45
    operations = load_catalog('operations')[0]['evals']
    assert all(e['action_policy'] == 'manual-menu-v1' for e in operations)
    assert all(e['mode'] == 'gameplay' for e in entries)
    with pytest.raises(ValueError, match='Unknown'):
        load_catalog('preparation')


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
    args = parser().parse_args(['catalog', '--category', 'operations'])
    assert args.command == 'catalog'
    assert args.category == 'operations'
    with pytest.raises(ValueError, match='Unknown'):
        load_catalog('unknown')


def test_campaign_is_one_attempt_with_unique_milestones():
    campaigns = load_catalog('campaign')[0]['evals']
    assert len(campaigns) == 1
    campaign = campaigns[0]
    assert campaign['run_unit'] == 'one-continuous-attempt'
    milestones = [m['id'] for m in campaign['milestones']]
    assert len(milestones) == len(set(milestones)) == 75
    assert campaign['objective']['target'] == 'champion'
    assert sum(key.startswith('badge:') for key in milestones) == 8
    assert sum(key.startswith('area:') for key in milestones) == 25
    groups = load_catalog()
    ids = {e['id'] for group in groups for e in group['evals']}
    assert 'objectives-resume-context-reset' not in ids
    assert 'battle-league-constrained' in ids


def test_portal_uses_actual_counts_and_campaign_milestones():
    from pokeagent_bench.catalog_portal import render_catalog
    page = render_catalog()
    assert '44 task drafts' in page and '<strong>43</strong><span>tasks in 4 categories' in page
    assert 'Milestones within this one attempt' not in page
    long_page = render_catalog(summary(benchmark='pokebench-long'))
    assert 'Milestones within this one attempt' in long_page
    assert 'Defeat Lance' in long_page
    assert '__COUNT__' not in page


def test_campaign_score_is_bounded_and_diagnostic_metrics_do_not_award_points():
    campaign = load_catalog('campaign')[0]['evals'][0]
    plan = campaign['scoring_plan']
    assert plan['status'] == 'runtime-scoring'
    assert plan['version'] == 'campaign-progress-v2'
    assert sum(m['points'] for m in campaign['milestones']) == plan['maximum_points'] == 1000
    assert {group['id'] for group in plan['groups']} == {m['group'] for m in campaign['milestones']}
    for group in plan['groups']:
        milestones = [m for m in campaign['milestones'] if m['group'] == group['id']]
        assert len(milestones) == group['count']
        assert sum(m['points'] for m in milestones) == group['points']
    assert all(m['points'] == 0 for m in campaign['run_metrics'])
    assert sum(m['points'] for m in campaign['milestones'] if m['group'] in ('badges', 'elite', 'champion')) == 540
    assert sum(m['points'] for m in campaign['milestones'] if m['group'] == 'areas') == 200


def test_published_long_runs_keep_the_pinned_v1_definition():
    from pokeagent_bench.campaign_runtime import V1, VERSION, campaign_definition
    from pokeagent_bench.core import digest, encoded
    from pokeagent_bench.evaluation_catalog import validate_run_spec
    # The digest every published Long run recorded in its manifest.
    published = '1b479e4ab14965293cb37c3094778d3cdb4972b7a7b0c7a62bfcbb119bfb69c3'
    assert digest(encoded(campaign_definition(V1))) == published
    assert digest(encoded(campaign_definition(VERSION))) == digest(encoded(load_catalog('campaign')[0]['evals'][0]))
    manifest = {'evaluation_spec_sha256': published, 'scenario': {'task_id': 'campaign-full-game'},
                'scoring_protocol': V1}
    validate_run_spec(manifest)
    with pytest.raises(ValueError, match='changed'):
        validate_run_spec({**manifest, 'scoring_protocol': VERSION})
    with pytest.raises(ValueError, match='Unsupported'):
        validate_run_spec({**manifest, 'scoring_protocol': 'campaign-progress-v0'})
    assert all(path.name != 'history' for path in catalog_files())


def test_cleanup_keeps_quests_distinct_and_inventory_variant_manual():
    groups = {group['category']: group for group in load_catalog()}
    assert len(groups['navigation']['evals']) == 10
    assert len(groups['battle']['evals']) == 14
    assert len(groups['objectives']['evals']) == 9
    quests = {task['id']: task for task in groups['objectives']['evals']}
    assert 'objectives-infeasible-plan-alternate' in quests
    assert 'objectives-find-capture-species' not in quests
    # Its Hideout and Tower halves are already the quest-trainer and prerequisite-chain tasks.
    assert 'objectives-poke-flute' not in quests
    assert 'objectives-recover-earlier-mistake' not in quests
    assert load_catalog('quests') == load_catalog('objectives')
    operations = {task['id']: task for task in groups['operations']['evals']}
    variant = operations['objectives-recover-earlier-mistake']
    assert variant['variant_of'] == 'operations-menu-checklist'
    assert variant['action_policy'] == 'manual-menu-v1'
    assert variant['difficulty'] == 'easy'
    assert summary()['primary_task_count'] == 44
    assert summary()['variant_count'] == 1
    retired = {task['id'] for group in load_catalog(include_retired=True)
               for task in group['evals'] if not task.get('active', True)}
    assert retired == retired_tasks() == {'navigation-town-landmark', 'navigation-multifloor-required-stops',
                                          'objectives-find-capture-species', 'objectives-capture-pikachu-fixed',
                                          'objectives-poke-flute'}


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
