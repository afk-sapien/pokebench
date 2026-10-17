"""Focused trials and continuous campaigns never share execution or ranking."""
import json
from unittest.mock import Mock

import pytest

from pokeagent_bench import catalog_batch as batch
from pokeagent_bench.catalog_portal import export_catalog
from pokeagent_bench.cli import execute, parser
from pokeagent_bench.core import write_json


@pytest.fixture
def fixtures(tmp_path, monkeypatch):
    rows = []
    for task, category in [('navigation-forest-crossing', 'navigation'), ('campaign-full-game', 'campaign')]:
        folder = tmp_path / task
        folder.mkdir()
        write_json(folder / 'scenario.json', {'state_sha256': 'state', 'catalog_sha256': 'spec'})
        rows.append({'id': task, 'category': category, 'mode': 'gameplay', 'runnable': True,
                     'variants': [{'path': str(folder), 'variant': 'default'}]})
    monkeypatch.setattr(batch, 'inventory', lambda root: {'tasks': rows})
    return tmp_path


def test_default_batch_only_runs_focused_tasks(fixtures):
    result = batch.plan(fixtures, ['codex:test'])
    assert result['benchmark'] == 'pokebench'
    assert [row['task_id'] for row in result['cells']] == ['navigation-forest-crossing']
    assert result['cells'][0]['benchmark'] == 'pokebench'


def test_long_batch_only_runs_full_game(fixtures):
    result = batch.plan(fixtures, ['codex:test'], benchmark='pokebench-long')
    assert result['benchmark'] == 'pokebench-long'
    assert [row['task_id'] for row in result['cells']] == ['campaign-full-game']
    assert result['cells'][0]['token_limit'] == 30000000


@pytest.mark.parametrize('benchmark,task', [('pokebench','campaign-full-game'),
    ('pokebench-long','navigation-forest-crossing')])
def test_cross_benchmark_selection_requires_matching_track(fixtures, benchmark, task):
    with pytest.raises(ValueError, match='matching --benchmark'):
        batch.plan(fixtures, ['codex:test'], tasks=[task], benchmark=benchmark)


def test_resume_cannot_change_the_saved_benchmark(tmp_path, monkeypatch):
    write_json(tmp_path / 'plan.json', {'protocol': 'catalog-batch-v2', 'benchmark': 'pokebench-long',
        'cells': [{'category': 'campaign'}]})
    launch = Mock()
    monkeypatch.setattr(batch, 'run_task', launch)
    with pytest.raises(ValueError, match='different benchmark'):
        batch.run_batch(None,None,None,tmp_path,budget=100000,resume=True,benchmark='pokebench')
    launch.assert_not_called()


def test_cli_default_catalog_is_short_and_long_is_explicit():
    short = execute(parser().parse_args(['catalog']))
    long = execute(parser().parse_args(['catalog','--benchmark','pokebench-long']))
    assert short['benchmark'] == 'pokebench'
    assert short['primary_task_count'] == 48 and short['eval_count'] == 49
    assert short['category_count'] == 5
    assert long['eval_count'] == 1 and long['categories'][0]['category'] == 'campaign'
    assert execute(parser().parse_args(['catalog','--category','campaign']))['benchmark'] == 'pokebench-long'


def test_export_has_two_distinct_pages_and_keeps_old_campaign_links(tmp_path):
    assert export_catalog(tmp_path) == 50
    short = (tmp_path / 'catalog.html').read_text()
    long = (tmp_path / 'pokebench-long.html').read_text()
    assert 'id="campaign-full-game"' not in short
    assert 'id="campaign-full-game"' in long
    assert 'id="navigation-forest-crossing"' in short
    assert 'id="navigation-forest-crossing"' not in long
    assert '<h1>PokeBench Long</h1>' in long
    assert 'href="pokebench-long.json"' in long
    assert 'continuous campaign</span>' in long
    assert '5 categories' in short
    assert "location.replace('pokebench-long.html#' + hash)" in short
    assert json.loads((tmp_path / 'catalog.json').read_text())['benchmark'] == 'pokebench'
    assert json.loads((tmp_path / 'pokebench-long.json').read_text())['benchmark'] == 'pokebench-long'


def test_long_progress_is_not_an_ability_average(tmp_path):
    write_json(tmp_path / 'plan.json', {'protocol': 'catalog-batch-v2', 'benchmark': 'pokebench-long',
        'cells': [{'id': 'cell-1', 'task_id': 'campaign-full-game', 'category': 'campaign',
                   'provider': 'codex', 'model': 'test', 'mode': 'gameplay'}]})
    run = tmp_path / 'cell-1'
    run.mkdir()
    write_json(run / 'result.json', {'state': 'finished', 'score': 400, 'score_max': 1000,
        'completed': False, 'stop_reason': 'token_budget', 'achievements': [{'id': 'starter'}],
        'frames': 8000, 'wall_seconds': 200, 'usage': {'input_tokens': 9000, 'output_tokens': 1000}})
    report = batch.report(tmp_path)
    model = report['models'][0]
    assert model['benchmark'] == 'pokebench-long'
    assert model['category_scores'] == {}
    assert model['available_category_average'] is None
    assert model['campaign_mean_progress'] == .4
    assert model['champion_completions'] == 0
    assert model['campaign_runs'][0]['campaign']['points'] == 400
    assert model['tokens'] == 10000
