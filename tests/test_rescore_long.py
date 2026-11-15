import importlib.util
import json
from pathlib import Path

import pytest

from pokeagent_bench.core import write_json

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/rescore_long.py'
spec = importlib.util.spec_from_file_location('rescore_long_test', SCRIPT)
rescore_long = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rescore_long)


def stored_run(tmp_path, total):
    """Calls 1, 2 and 4 have decision rows. Call 3 hit the output limit and has none."""
    run = tmp_path / 'run'
    run.mkdir()
    rows = [{'index': index, 'usage': {'input_tokens': 100 * index, 'output_tokens': 10}} for index in (1, 2, 4)]
    (run / 'decisions.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    actions = [{'operation_id': f'decision-{index}-press'} for index in (1, 2, 2, 4)]
    (run / 'actions.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in actions))
    write_json(run / 'result.json', {'usage': {'input_tokens': total - 30, 'output_tokens': 30}})
    return run


def test_a_failed_call_counts_its_recovered_usage_at_that_call(tmp_path):
    run = stored_run(tmp_path, 110 + 210 + 50 + 410)
    write_json(run / 'output-limit-accounting.json', {'failed_decision': 3, 'recovered_input_tokens': 40,
                                                      'recovered_output_tokens': 10})
    decisions, tokens = rescore_long.decision_stamps(run)
    assert decisions == [1, 2, 2, 4]
    assert tokens == {1: 110, 2: 320, 3: 370, 4: 780}


def test_stamps_must_add_up_to_the_recorded_usage(tmp_path):
    # Without the accounting file the 50 tokens of call 3 are missing, so every later stamp would be short.
    run = stored_run(tmp_path, 110 + 210 + 50 + 410)
    with pytest.raises(ValueError, match='add up'):
        rescore_long.decision_stamps(run)
