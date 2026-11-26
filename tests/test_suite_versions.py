"""The Short suite versions: the record matches the catalog, and scores name the version they belong to."""
from copy import deepcopy
import os

import pytest

from pokeagent_bench import BENCHMARK_VERSION, local_setup, quick_run, submission, suite_versions
from pokeagent_bench.benchmark_tracks import SHORT, for_category
from pokeagent_bench.core import digest, encoded
from pokeagent_bench.evaluation_catalog import load_catalog, task_definition

ROM = os.environ.get('POKEBENCH_ROM')
OLD = 'red-v0.63-short-guard'
HARDER = {'navigation-vermilion-gym-switches', 'objectives-saffron-gate-drink', 'navigation-safari-zone-secret-house',
          'battle-champion-no-items-no-faint', 'battle-elite-four-no-items-no-faint'}


def entry(name):
    return next(version for version in suite_versions.versions() if version['benchmark'] == name)


def keys(version):
    return {suite_versions.identity(run) for run in version['runs']}


def test_the_record_holds_the_published_set_and_the_current_version():
    names = [version['benchmark'] for version in suite_versions.versions()]
    assert names[-1] == BENCHMARK_VERSION == suite_versions.current()['benchmark']
    old = entry(OLD)
    assert (old['run_count'], old['task_count']) == (46, 44)
    assert suite_versions.label(old) == 'red-v0.63-short-guard, 46 runs over 44 tasks'


def test_the_current_catalog_matches_the_current_entry():
    current = suite_versions.current()
    short = {task['id'] for group in load_catalog() if for_category(group['category']) == SHORT
             for task in group['evals']}
    assert {run['task_id'] for run in current['runs']} == short
    for run in current['runs']:
        assert run['evaluation_spec_sha256'] == digest(encoded(task_definition(run['task_id']))), run['task_id']
        pins = task_definition(run['task_id']).get('fixture')
        if pins:
            assert run['fixture_sha256'] == pins['state_sha256']


def test_the_current_version_adds_the_five_harder_tasks_and_keeps_every_older_run():
    old, current = entry(OLD), suite_versions.current()
    assert keys(old) < keys(current)
    added = keys(current) - keys(old)
    assert {key[0] for key in added} == HARDER and len(added) == 5
    assert (current['run_count'], current['task_count']) == (51, 49)


def cells(version):
    return [{'id': f'cell-{index:04d}', **run, 'model': 'test'} for index, run in enumerate(version['runs'], 1)]


def test_runs_name_their_version_only_when_they_match_it_exactly():
    old, current = entry(OLD), suite_versions.current()
    assert suite_versions.identify(cells(current)[::-1]) == current
    assert suite_versions.identify(cells(old)) == old
    assert suite_versions.line(cells(current)) == f'Suite version {BENCHMARK_VERSION}, 51 runs over 49 tasks.'
    changed = cells(current)
    changed[0]['fixture_sha256'] = '0' * 64
    for wrong in (cells(current)[1:], changed, cells(current) + cells(current)[:1]):
        assert suite_versions.identify(wrong) is None
        assert suite_versions.line(wrong).startswith('Suite version: none.')


@pytest.mark.parametrize('change, message', [
    (lambda record: record['suites'][0].update(run_count=45), 'counts do not match'),
    (lambda record: record['suites'][0]['runs'].append(record['suites'][0]['runs'][0]), 'listed twice'),
    (lambda record: record['suites'].append(record['suites'][0]), 'recorded twice'),
    (lambda record: record['suites'][0]['runs'][0].update(fixture_sha256='abc'), 'SHA-256'),
    (lambda record: record['suites'][0].pop('task_count'), 'names its benchmark'),
])
def test_a_bad_record_is_refused(change, message):
    record = {'format': 1, 'suites': deepcopy(list(suite_versions.versions()))}
    change(record)
    with pytest.raises(ValueError, match=message):
        suite_versions.validate(record)


def test_the_bundle_and_verified_report_carry_the_version_and_its_run_count():
    version = submission.suite_version(cells(entry(OLD)))
    assert version == {'benchmark': OLD, 'run_count': 46, 'task_count': 44}
    assert submission.version_line(version) == 'Suite version red-v0.63-short-guard, 46 runs over 44 tasks.'
    assert submission.suite_version(cells(entry(OLD))[1:]) is None
    assert submission.version_line(None).startswith('Suite version: none.')


@pytest.mark.skipif(not ROM, reason='The Red ROM is not distributed. Set POKEBENCH_ROM')
def test_a_fresh_setup_plans_exactly_the_current_short_suite(tmp_path):
    local_setup.unpack_fixtures(local_setup.check_rom(ROM), tmp_path / 'fixtures')
    plan = quick_run.new_plan('short', tmp_path / 'fixtures', 'claude', 'test')
    assert plan['held_tasks'] == []
    assert suite_versions.identify(plan['cells']) == suite_versions.current()
