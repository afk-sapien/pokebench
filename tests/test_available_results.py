from pokeagent_bench.available_results import available_snapshot, available_section, benchmark_section, evaluation_status


def inputs():
    models = [{'model': 'openai', 'provider': 'codex'}, {'model': 'claude', 'provider': 'claude'}]
    tasks = [{'id': t, 'name': t, 'difficulty': 'medium', 'score_eligible': t != 'experiment'}
             for t in ['first', 'second', 'experiment']]
    protocol = {'models': models, 'tasks': tasks}
    release = {'attempts': [], 'status': 'running', 'finished': 1, 'running': 2}
    development = {'models': models[:1], 'tasks': tasks, 'attempts': []}
    return protocol, release, development


def attempt(model, task, won, **extra):
    return {'id': model+'-'+task, 'model': model, 'task': task, 'completed': won,
            'status': 'finished', 'replay_verified': True, 'accounting_complete': True,
            'tokens': 100, **extra}


def test_all_benchmarks_and_models_survive_sparse_coverage():
    p, r, d = inputs()
    d['attempts'] = [attempt('openai', 'first', True), attempt('openai', 'second', False)]
    r['attempts'] = [attempt('claude', 'first', True)]
    result = available_snapshot(p, r, d)
    assert len(result['tasks']) == 3
    assert len(result['cells']) == 6
    rows = {m['model']: m for m in result['models']}
    assert rows['openai']['tested'] == 2 and rows['openai']['score'] == 50
    assert rows['claude']['tested'] == 1 and rows['claude']['score'] == 100
    assert rows['claude']['eligible'] == 2
    missing = next(c for c in result['cells'] if c['model'] == 'claude' and c['task'] == 'second')
    assert missing['score'] is None and missing['source'] is None
    assert all('rank' not in row for row in result['models'])
    page = available_section(result, r)+benchmark_section(result)
    assert '3 benchmarks' in page and 'Coverage differs' in page
    assert 'Not tested' in page and 'Experimental' in page


def test_release_replaces_history_even_when_it_loses():
    p, r, d = inputs()
    d['attempts'] = [attempt('openai', 'first', True)]
    r['attempts'] = [attempt('openai', 'first', False), attempt('openai', 'first', True, id='second-start')]
    result = available_snapshot(p, r, d)
    cell = next(c for c in result['cells'] if c['model'] == 'openai' and c['task'] == 'first')
    assert cell['source'] == 'release'
    assert cell['finished'] == 2 and cell['wins'] == 1 and cell['score'] == 50
    assert next(m for m in result['models'] if m['model'] == 'openai')['development_tasks'] == 0


def test_invalid_release_results_do_not_replace_verified_history():
    p, r, d = inputs()
    d['attempts'] = [attempt('openai', 'first', False)]
    r['attempts'] = [attempt('openai', 'first', True, status='error'),
                     attempt('openai', 'first', True, replay_verified=False),
                     attempt('openai', 'first', True, accounting_complete=False),
                     attempt('openai', 'first', None, status='pending')]
    result = available_snapshot(p, r, d)
    cell = next(c for c in result['cells'] if c['model'] == 'openai' and c['task'] == 'first')
    assert cell['source'] == 'development' and cell['score'] == 0
    assert cell['release_errors'] == 1 and cell['release_pending'] == 1


def test_equal_task_weights_experiments_and_no_data():
    p, r, d = inputs()
    r['attempts'] = [attempt('openai', 'first', True, id='a'),
                     attempt('openai', 'first', True, id='b'),
                     attempt('openai', 'second', False),
                     attempt('openai', 'experiment', True)]
    result = available_snapshot(p, r, d)
    row = next(m for m in result['models'] if m['model'] == 'openai')
    assert row['score'] == 50 and row['finished'] == 3
    assert next(m for m in result['models'] if m['model'] == 'claude')['score'] is None
    assert any(c['score'] == 100 for c in result['cells'] if c['task'] == 'experiment')


def test_attempt_export_does_not_leak_extra_fields():
    p, r, d = inputs()
    r['attempts'] = [attempt('claude', 'first', True, private='/home/person', notes='hidden')]
    result = available_snapshot(p, r, d)
    assert '/home/' not in str(result) and 'hidden' not in str(result)


def test_pilot_evidence_fills_gaps_without_overriding_curated_history():
    p, r, d = inputs()
    d['attempts'] = [attempt('openai', 'first', False)]
    pilot = {'attempts': [attempt('openai', 'first', True), attempt('openai', 'experiment', True)]}
    result = available_snapshot(p, r, d, [pilot])
    cells = {c['task']: c for c in result['cells'] if c['model'] == 'openai'}
    assert cells['first']['score'] == 0
    assert cells['experiment']['score'] == 100
    assert next(m for m in result['models'] if m['model'] == 'openai')['score'] == 0


def test_saved_results_are_evaluated_despite_unused_release_repeat_slots():
    p, r, d = inputs()
    d['attempts'] = [attempt('openai', 'first', True)]
    r['attempts'] = [attempt('openai', 'first', None, id=f'planned-{i}', status='pending') for i in range(3)]
    r['attempts'] += [attempt('claude', 'first', False)]
    r['attempts'] += [attempt('claude', 'first', None, id=f'unused-{i}', status='pending') for i in range(2)]
    result = available_snapshot(p, r, d)
    cells = [c for c in result['cells'] if c['task'] == 'first']
    assert all(evaluation_status(c) == 'Evaluated · 1 completed trial' for c in cells)
    assert next(c for c in cells if c['model'] == 'claude')['score'] == 0
    page = benchmark_section(result)
    assert '0 / 3 finished' not in page
    assert '1 / 3 finished' not in page
    assert '3 pending' not in page
    assert '<th>Status</th>' in page
    assert 'Earlier development' in page


def test_status_distinguishes_running_errors_and_missing_results():
    p, r, d = inputs()
    r['attempts'] = [attempt('claude', 'first', None, status='running'),
                     attempt('claude', 'second', None, status='error')]
    result = available_snapshot(p, r, d)
    cells = {c['task']: c for c in result['cells'] if c['model'] == 'claude'}
    assert evaluation_status(cells['first']) == 'Running'
    assert evaluation_status(cells['second']) == 'Evaluation error · no valid result · 1 recorded error'
    assert evaluation_status(cells['experiment']) == 'Not evaluated'
    d['attempts'] = [attempt('claude', 'second', False)]
    result = available_snapshot(p, r, d)
    cell = next(c for c in result['cells'] if c['model'] == 'claude' and c['task'] == 'second')
    assert evaluation_status(cell) == 'Evaluated · 1 completed trial · 1 recorded error'
    assert cell['score'] == 0
