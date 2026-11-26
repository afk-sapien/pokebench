"""The Short suite versions: each benchmark version and the exact runs its Short suite holds.

A Short score belongs to one suite version. Runs made on another version stay valid for that
version and are ranked separately. short_suites.json records every version, oldest first.
"""
from functools import cache
from importlib.resources import files
import json
import re

from . import BENCHMARK_VERSION
from .core import counted

KEYS = ('task_id', 'variant', 'evaluation_spec_sha256', 'fixture_sha256')
DIGESTS = ('evaluation_spec_sha256', 'fixture_sha256')
ENTRY = {'benchmark', 'run_count', 'task_count', 'runs'}


def identity(cell):
    """What makes two Short runs the same run: the task, its start and its scoring specification."""
    return tuple(str(cell.get(key)) for key in KEYS)


def validate(record):
    if not isinstance(record, dict) or record.get('format') != 1 or not isinstance(record.get('suites'), list):
        raise ValueError('Unknown Short suite record')
    names = set()
    for entry in record['suites']:
        if not isinstance(entry, dict) or set(entry) != ENTRY or not isinstance(entry['runs'], list):
            raise ValueError('A Short suite version names its benchmark, run count, task count and runs')
        name = entry['benchmark']
        if name in names:
            raise ValueError(f'{name} is recorded twice')
        names.add(name)
        for run in entry['runs']:
            if not isinstance(run, dict) or set(run) != set(KEYS) or not all(
                    isinstance(run[key], str) and re.fullmatch(r'[0-9a-f]{64}', run[key]) for key in DIGESTS):
                raise ValueError(f'{name}: each run names its task, variant and two SHA-256 digests')
        runs = {identity(run) for run in entry['runs']}
        if len(runs) != len(entry['runs']):
            raise ValueError(f'{name}: a run is listed twice')
        if entry['run_count'] != len(runs) or entry['task_count'] != len({run['task_id'] for run in entry['runs']}):
            raise ValueError(f'{name}: the run and task counts do not match its runs')
    return record


@cache
def versions():
    """Every recorded Short suite version, oldest first."""
    record = json.loads(files('pokeagent_bench').joinpath('short_suites.json').read_text())
    return tuple(validate(record)['suites'])


def current():
    """The Short suite of this release's benchmark version."""
    for entry in versions():
        if entry['benchmark'] == BENCHMARK_VERSION:
            return entry
    raise ValueError(f'No Short suite is recorded for {BENCHMARK_VERSION}')


def identify(cells):
    """The suite version whose runs are exactly these cells, or None."""
    found = sorted(identity(cell) for cell in cells)
    return next((entry for entry in versions() if sorted(identity(run) for run in entry['runs']) == found), None)


def label(entry):
    return f'{entry["benchmark"]}, {counted(entry["run_count"], "run")} over {counted(entry["task_count"], "task")}'


def line(cells):
    """One plain line naming the Short suite version of these runs."""
    entry = identify(cells)
    if entry is None:
        return 'Suite version: none. These runs match no recorded Short suite version, so they are not a ranked result.'
    return f'Suite version {label(entry)}.'
