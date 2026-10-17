import json
import pytest
from pokeagent_bench.focused_analysis import grouped_scores, repeat_summary, trace_audit, task_sensitivity
from pokeagent_bench.focused_portal import page


def cell(task, category, value, **kwargs):
    return {'model': 'test', 'task_id': task, 'category': category, 'value': value,
            'state': 'finished', 'repeat': 1, **kwargs}


def test_variants_and_categories_have_declared_weights():
    cells = [cell('battle-a', 'battle', 1) for _ in range(3)]
    cells += [cell('battle-b', 'battle', 0), cell('nav', 'navigation', 0)]
    categories, score = grouped_scores(cells)
    assert categories == {'battle': .5, 'navigation': 0}
    assert score == .25


def test_errors_and_pending_do_not_become_zero_scores():
    cells = [cell('a', 'battle', 1), cell('b', 'battle', None, state='pending'),
             cell('c', 'battle', 0, state='evaluation_error')]
    assert grouped_scores(cells) == ({'battle': 1}, 1)
    assert grouped_scores(cells[1:]) == ({}, None)


def test_repeat_summary_retains_failures_and_pending():
    original = [cell('a', 'battle', 0)]
    repeats = [cell('a', 'battle', 1, repeat=2), cell('a', 'battle', None, repeat=3, state='running')]
    summary = repeat_summary(original, repeats)[0]
    assert summary['mean'] == pytest.approx(.5)
    assert summary['completed'] == 2
    assert summary['planned'] == 3
    assert summary['changed']
    assert grouped_scores(original)[1] == 0


def test_trace_audit_counts_rejections_and_retains_no_raw_text(tmp_path):
    rows = [{'decision': {'actions': [], 'interface_error': 'secret rejected response'},
             'provider': {'context': {'game': {'location': {'map_name': 'Saffron Gym'}}}}},
            {'decision': {'actions': [{'command': 'move'}]}}]
    (tmp_path / 'decisions.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
    result = trace_audit(tmp_path)
    assert result['format_error_decisions'] == 1
    assert result['recorded_decisions'] == 2
    assert 'secret' not in json.dumps(result)
    assert result['last_map'] == 'Saffron Gym'


def test_embedded_results_cannot_close_script_element():
    rendered = page({'task': '</script><img src=x onerror=alert(1)>'})
    assert '<img src=x' not in rendered
    assert '\\u003c/script\\u003e' in rendered


def test_task_mix_sensitivity_does_not_break_ties_by_name():
    rows = [cell('a', 'battle', 1, model='one'), cell('b', 'battle', 0, model='one'),
            cell('a', 'battle', 0, model='two'), cell('b', 'battle', 1, model='two')]
    result = task_sensitivity(rows)
    assert result['omissions'] == 2
    assert {(r['best_rank'], r['worst_rank']) for r in result['rows']} == {(1, 2)}
    tied = [dict(row, value=1) for row in rows]
    assert {(r['best_rank'], r['worst_rank']) for r in task_sensitivity(tied)['rows']} == {(1, 1)}
