"""Community submissions: `submit` packs a finished suite run, `verify` checks one by replay.

A bundle is a zip of controller input logs and results. It holds no ROM, save
state, screenshot, prompt or model reply. `verify` trusts nothing in it: start
states, task definitions and limits come from the verifier's own setup, and the
score is recomputed by replaying the recorded inputs. No model is called.
"""
from dataclasses import asdict
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import socket
import tempfile
from urllib.parse import urlsplit
import zipfile

from . import BENCHMARK_VERSION, __version__
from .catalog_batch import report
from .catalog_execution import select_scenario
from .core import Limits, digest, encoded, write_json
from .quick_run import SUITES, millions, new_plan

FORMAT = 'pokebench-submission-v1'
REPORT_FORMAT = 'pokebench-verified-report-v1'
LABEL = 'Community, replay verified, model unverified'
SELF_REPORTED = ('model identity', 'token counts', 'attempts', 'no outside help')
ATTACHMENT_LIMIT = 25_000_000  # GitHub issue attachment limit
UNPACKED_LIMIT = 500_000_000
REPLAY_FILES = ('manifest.json', 'actions.jsonl', 'result.json')
PREPARATION_FILES = ('preparation-result.json', 'model-usage.json')
MEMBER = re.compile(r'plan\.json|submit\.json|cell-\d{4}/(?:' + '|'.join(
    re.escape(name) for name in REPLAY_FILES + PREPARATION_FILES) + ')')
CONTENTS = {
    'plan.json': 'the task list with its limits and start state hashes',
    'submit.json': 'this summary and a SHA-256 for every file',
    'manifest.json': 'harness and package versions, model id, provider, settings, limits, timestamps',
    'actions.jsonl': 'every controller input and the game facts read after it',
    'result.json': 'score, stop reason, token counts, timings',
    'preparation-result.json': 'preparation outcome and token counts',
    'model-usage.json': 'preparation token counts',
}
HANDLE = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?')
PRIVATE = re.compile(
    r'/home/|/Users/|/root/|/mnt/|/tmp/|/var/|file://|[A-Za-z]:\\+Users\\'
    r'|sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|AKIA[0-9A-Z]{16}'
    r'|AIza[\w-]{30,}|xox[abprs]-[\w-]{10,}|Bearer\s+[\w.~+/-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY')
SECRET_NAME = re.compile(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL', re.I)
CELL_KEYS = ('id', 'task_id', 'variant', 'repeat', 'mode', 'category', 'fixture_sha256',
             'evaluation_spec_sha256', 'token_limit', 'decision_limit')
DECISION = re.compile(r'decision-(\d+)-')


def accepted_harness():
    return json.loads((Path(__file__).parent / 'accepted_harness.json').read_text())['accepted']


def harness_accepted(manifest):
    return any(all(manifest.get(key) == value for key, value in entry.items()) for entry in accepted_harness())


def harness_names():
    return ' or '.join(f'{entry["benchmark"]} (package {entry["package_version"]})' for entry in accepted_harness())


def local_names():
    """Names on this machine that should not appear in a public bundle."""
    names = {Path.home().name, socket.gethostname()}
    try:
        names.add(getpass.getuser())
    except (KeyError, OSError):
        pass
    return sorted(name for name in names if len(name) >= 3)


def privacy_findings(files, names):
    """Return text that looks like a path, a local name or a credential. Nothing is printed in full."""
    secrets = [value for key, value in os.environ.items() if SECRET_NAME.search(key) and len(value) >= 12]
    named = re.compile(r'(?<![A-Za-z0-9])(?:' + '|'.join(re.escape(name) for name in names) + r')(?![A-Za-z0-9])',
                       re.I) if names else None
    findings = []
    for name, data in files.items():
        text = data.decode()
        for match in PRIVATE.finditer(text):
            findings.append(f'{name}: path or key shaped text "{match[0][:10]}..."')
        if any(secret in text for secret in secrets):
            findings.append(f'{name}: the value of a secret environment variable')
        for match in named.finditer(text) if named else ():
            findings.append(f'{name}: local user or host name "{match[0]}"')
        if len(findings) >= 20:
            break
    return findings


def public_manifest(manifest, endpoint_host):
    """Drop the endpoint address and the platform string. A host name can identify the submitter."""
    manifest = json.loads(json.dumps(manifest))
    manifest.pop('platform', None)
    configuration = manifest.get('agent', {}).get('configuration') or {}
    endpoint = configuration.pop('endpoint', None)
    if endpoint and endpoint_host:
        configuration['endpoint_host'] = urlsplit(endpoint).hostname
    return manifest


def collect(run, *, handle=None, attempts=1, endpoint_host=False):
    """Read a finished suite run and return the bundle files as bytes."""
    run = Path(run)
    if not (run / 'plan.json').is_file():
        raise ValueError(f'{run} is not a suite run folder. Pass the folder that run --suite wrote')
    plan = json.loads((run / 'plan.json').read_text())
    if plan.get('suite') not in SUITES:
        raise ValueError('Only runs made with run --suite can be submitted')
    if handle is not None and not HANDLE.fullmatch(handle):
        raise ValueError('The handle must be a GitHub user name')
    if type(attempts) is not int or attempts < 1:
        raise ValueError('Attempts must be a positive integer')
    models = {(cell['provider'], cell['model']) for cell in plan['cells']}
    if len(models) != 1:
        raise ValueError('A submission covers one model')
    rows = report(run)['cells']
    unfinished = [row['task_id'] for row in rows if row['state'] != 'finished']
    if unfinished:
        raise ValueError(f'{len(unfinished)} of {len(rows)} runs are not finished: ' + ', '.join(unfinished[:5])
                         + '. Run the same run command again to finish them')
    files = {'plan.json': encoded(plan)}
    hosts = set()
    harness = {'benchmark': BENCHMARK_VERSION, 'package_version': __version__}
    for cell in plan['cells']:
        folder = run / cell['id']
        if cell['mode'] == 'preparation':
            for name in PREPARATION_FILES:
                if (folder / name).is_file():
                    files[f'{cell["id"]}/{name}'] = (folder / name).read_bytes()
            continue
        manifest = json.loads((folder / 'manifest.json').read_text())
        if not harness_accepted(manifest):
            raise ValueError(f'{cell["task_id"]} ran on {manifest.get("benchmark")} (package '
                             f'{manifest.get("package_version")}). Submissions are accepted from {harness_names()} only')
        harness = {key: manifest[key] for key in ('benchmark', 'package_version')}
        manifest = public_manifest(manifest, endpoint_host)
        hosts.add(manifest['agent'].get('configuration', {}).get('endpoint_host'))
        files[f'{cell["id"]}/manifest.json'] = encoded(manifest)
        for name in REPLAY_FILES[1:]:
            files[f'{cell["id"]}/{name}'] = (folder / name).read_bytes()
    provider, model = next(iter(models))
    summary = {'format': FORMAT, 'suite': plan['suite'], 'benchmark': plan['benchmark'], 'provider': provider,
               'model': model, 'handle': handle, 'attempts_declared': attempts,
               'harness': harness, 'tokens_self_reported': sum(row['tokens'] for row in rows),
               'files': {name: digest(data) for name, data in files.items()}}
    hosts.discard(None)
    if hosts:
        summary['endpoint_host'] = sorted(hosts)[0]
    files['submit.json'] = encoded(summary)
    return files, summary


def describe(files, summary):
    lines = [f'Bundle for suite {summary["suite"]}, model {summary["provider"]}:{summary["model"]}',
             f'Harness {summary["harness"]["benchmark"]}, package {summary["harness"]["package_version"]}',
             'GitHub handle: ' + (summary['handle'] or 'not given. Add --handle NAME to be credited'),
             f'Attempts declared: {summary["attempts_declared"]}',
             'Endpoint host: ' + summary.get('endpoint_host', 'not included'),
             f'Tokens reported: {millions(summary["tokens_self_reported"])}',
             f'Contents, {len(files)} files, {sum(map(len, files.values())) / 1e6:.1f} MB before compression:']
    for kind, meaning in CONTENTS.items():
        count = sum(name.rsplit('/', 1)[-1] == kind for name in files)
        if count:
            lines.append(f'  {count:>3} x {kind:<24} {meaning}')
    lines.append('Not included: ROM, save states, screenshots, prompts, model replies, notes, the endpoint address '
                 'and the platform string.')
    return '\n'.join(lines)


def submit(run, output=None, *, handle=None, attempts=1, endpoint_host=False, check_names=True):
    files, summary = collect(run, handle=handle, attempts=attempts, endpoint_host=endpoint_host)
    print(describe(files, summary), flush=True)
    findings = privacy_findings(files, local_names() if check_names else [])
    if findings:
        raise ValueError('Privacy scan stopped the bundle. Nothing was written.\n  ' + '\n  '.join(findings)
                         + '\nIf your user or host name is also a word in the game, add --skip-name-check')
    print('Privacy scan: no absolute paths, key shaped text'
          + (', user names or host names found.' if check_names else ' found. Name check skipped.'), flush=True)
    name = re.sub(r'[^A-Za-z0-9.]+', '-', summary['model'])
    output = Path(output) if output else Path(f'{name}-{summary["suite"]}.pokebench.zip')
    if output.exists():
        raise ValueError(f'{output} already exists. Choose another --output')
    temporary = output.with_name(output.name + '.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for member in sorted(files):
            archive.writestr(zipfile.ZipInfo(member), files[member], zipfile.ZIP_DEFLATED, 9)
    size = temporary.stat().st_size
    if size > ATTACHMENT_LIMIT:
        temporary.unlink()
        raise ValueError(f'The bundle is {size / 1e6:.1f} MB. GitHub issues take at most '
                         f'{ATTACHMENT_LIMIT / 1e6:.0f} MB. Nothing was written')
    temporary.replace(output)
    print(f'Wrote {output}, {size / 1e6:.2f} MB. Attach it to a submission issue.', flush=True)
    if summary['suite'] == 'smoke':
        print('This is the smoke suite. It checks the submission path and is never a leaderboard result.', flush=True)
    return None


def open_bundle(path):
    """Read an untrusted bundle into memory. Only known file names are accepted and nothing is extracted."""
    path = Path(path)
    if path.stat().st_size > ATTACHMENT_LIMIT:
        raise ValueError(f'Bundle is larger than {ATTACHMENT_LIMIT / 1e6:.0f} MB')
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ValueError('Bundle is not a zip file') from None
    with archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        refused = [name for name in names if not MEMBER.fullmatch(name)]
        if refused:
            raise ValueError(f'Bundle holds an entry that is not allowed: {refused[0]!r}')
        if len(set(names)) != len(names):
            raise ValueError('Bundle holds the same file twice')
        if sum(entry.file_size for entry in entries) > UNPACKED_LIMIT:
            raise ValueError('Bundle unpacks to more than the size limit')
        try:
            return {entry.filename: archive.read(entry) for entry in entries}
        except (zipfile.BadZipFile, OSError, EOFError, ValueError):
            raise ValueError('Bundle is damaged') from None


def parse(files, name):
    try:
        value = json.loads(files[name])
    except KeyError:
        raise ValueError(f'Bundle is missing {name}') from None
    except ValueError:
        raise ValueError(f'{name} is not valid JSON') from None
    if not isinstance(value, dict):
        raise ValueError(f'{name} is not a JSON object')
    return value


def check_plan(files, fixtures):
    """Compare the claimed task list with the suite this checkout defines. Return the trusted plan."""
    summary, claimed = parse(files, 'submit.json'), parse(files, 'plan.json')
    if summary.get('format') != FORMAT:
        raise ValueError('Unknown bundle format')
    hashes = {name: digest(data) for name, data in files.items() if name != 'submit.json'}
    if summary.get('files') != hashes:
        raise ValueError('Bundle files do not match the hashes in submit.json')
    suite = claimed.get('suite')
    if suite not in SUITES or summary.get('suite') != suite:
        raise ValueError('Bundle does not name a known suite')
    cells = claimed.get('cells')
    if not isinstance(cells, list) or not cells or not all(isinstance(cell, dict) for cell in cells):
        raise ValueError('Bundle plan has no runs')
    models = {(str(cell.get('provider')), str(cell.get('model'))) for cell in cells}
    if len(models) != 1 or models != {(summary.get('provider'), summary.get('model'))}:
        raise ValueError('A submission covers one model')
    provider, model = next(iter(models))
    trusted = new_plan(suite, fixtures, provider, model)
    expected = {cell['id']: {key: cell.get(key) for key in CELL_KEYS} for cell in trusted['cells']}
    found = {str(cell.get('id')): {key: cell.get(key) for key in CELL_KEYS} for cell in cells}
    missing = sorted({row['task_id'] for key, row in expected.items() if key not in found})
    if missing:
        raise ValueError('Bundle is missing tasks of the suite: ' + ', '.join(missing))
    if len(found) != len(cells) or set(found) != set(expected):
        raise ValueError('Bundle holds runs that are not part of the suite')
    changed = sorted({row['task_id'] for key, row in expected.items() if found[key] != row})
    if changed:
        raise ValueError('Start state, task definition or limits differ from the suite: ' + ', '.join(changed))
    return summary, trusted


def decisions_used(actions):
    numbers = set()
    for line in actions.decode().splitlines():
        match = DECISION.match(str(json.loads(line).get('operation_id')))
        if match:
            numbers.add(int(match[1]))
    return len(numbers)


def scoring(task_id):
    """What a suite run of this task must record about how it is played and scored."""
    if task_id == 'campaign-full-game':
        return {'goal': 'campaign', 'track': 'gameplay', 'scoring_protocol': 'campaign-progress-v1', 'score_max': 1000}
    return {'goal': 'challenge', 'track': 'gameplay', 'scoring_protocol': 'catalog-tasks-v1', 'score_max': 1}


def check_cell(cell, files, fixtures, rom, work, replay):
    """Replay one gameplay run from the verifier's own start state. Return a result built from the replay."""
    manifest = parse(files, f'{cell["id"]}/manifest.json')
    result = parse(files, f'{cell["id"]}/result.json')
    actions = files.get(f'{cell["id"]}/actions.jsonl')
    if actions is None:
        raise ValueError('Bundle is missing the action log')
    if not harness_accepted(manifest):
        raise ValueError(f'Ran on {manifest.get("benchmark")} (package {manifest.get("package_version")}). '
                         f'Accepted: {harness_names()}')
    source = select_scenario(fixtures, cell['task_id'], cell['variant'])
    scenario = json.loads((source / 'scenario.json').read_text())
    if manifest.get('initial_sha256') != scenario['state_sha256']:
        raise ValueError('Start state is not the benchmark start for this task')
    if manifest.get('scenario') != scenario:
        raise ValueError('Scenario differs from the benchmark fixture')
    protocol = scoring(cell['task_id'])
    maximum = protocol.pop('score_max')
    if any(manifest.get(key) != value for key, value in protocol.items()):
        raise ValueError('Goal or scoring protocol differs from the benchmark')
    limits, standard = manifest.get('limits'), asdict(Limits())
    if not isinstance(limits, dict) or set(limits) != set(standard):
        raise ValueError('Limits are missing')
    if any(limits[key] != value for key, value in standard.items() if key not in ('max_total_tokens', 'max_model_calls')):
        raise ValueError('Run limits differ from the benchmark')
    agent = manifest.get('agent') if isinstance(manifest.get('agent'), dict) else {}
    if agent.get('model') != cell['model']:
        raise ValueError('Manifest names a different model')
    usage = result.get('usage') if isinstance(result.get('usage'), dict) else {}
    tokens = sum(usage.get(key) if type(usage.get(key)) is int else 0 for key in ('input_tokens', 'output_tokens'))
    calls = usage.get('calls') if type(usage.get('calls')) is int else 0
    if (limits['max_model_calls'] > cell['decision_limit'] or max(calls, decisions_used(actions)) > cell['decision_limit']):
        raise ValueError(f'Over budget: more than {cell["decision_limit"]} decisions')
    # One response in flight can pass the limit, and that run then stops for the token budget.
    if limits['max_total_tokens'] > cell['token_limit'] or (
            tokens > cell['token_limit'] and result.get('stop_reason') != 'token_budget'):
        raise ValueError(f'Over budget: more than {cell["token_limit"]} tokens')
    if result.get('state') != 'finished' or result.get('outcome_category') in ('infrastructure_failure', 'interface_failure'):
        raise ValueError('Run did not finish')
    if result.get('score_max') != maximum:
        raise ValueError('Maximum score differs from the benchmark')
    folder = work / cell['id']
    folder.mkdir()
    write_json(folder / 'manifest.json', {**manifest, 'scenario': scenario})
    (folder / 'actions.jsonl').write_bytes(actions)
    (folder / 'result.json').write_bytes(files[f'{cell["id"]}/result.json'])
    shutil.copyfile(source / 'initial.state', folder / 'initial.state')
    proof = replay(Path(rom), folder)
    awards = [award for line in actions.decode().splitlines() for award in json.loads(line)['achievements']]
    return {'state': 'finished', 'score': proof['score'], 'score_max': maximum, 'completed': bool(result.get('completed')),
            'achievements': awards, 'actions': proof['actions'], 'frames': proof['frames'],
            'stop_reason': str(result.get('stop_reason')), 'usage': {**usage, 'calls': calls},
            'wall_seconds': result.get('wall_seconds') if isinstance(result.get('wall_seconds'), (int, float)) else None}


def verify(bundle, rom, fixtures, output=None, *, replay=None):
    """Check a bundle and write a verified report. Raises ValueError when the bundle is refused outright."""
    if replay is None:
        from .session import replay
    if not harness_accepted({'benchmark': BENCHMARK_VERSION, 'package_version': __version__}):
        raise ValueError(f'This checkout is {BENCHMARK_VERSION} (package {__version__}). '
                         f'Verification needs {harness_names()}. Check out that release')
    bundle = Path(bundle)
    files = open_bundle(bundle)
    summary, plan = check_plan(files, fixtures)
    problems, unverified = [], []
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        write_json(work / 'plan.json', plan)
        (work / 'replay').mkdir()
        for position, cell in enumerate(plan['cells'], 1):
            (work / cell['id']).mkdir()
            if cell['mode'] == 'preparation':
                for name in PREPARATION_FILES:
                    if f'{cell["id"]}/{name}' in files:
                        write_json(work / cell['id'] / name, parse(files, f'{cell["id"]}/{name}'))
                unverified.append(cell['task_id'])
                print(f'[{position}/{len(plan["cells"])}] {cell["task_id"]} not replay verified', flush=True)
                continue
            state = 'replayed'
            try:
                write_json(work / cell['id'] / 'result.json',
                           check_cell(cell, files, fixtures, rom, work / 'replay', replay))
            except Exception as error:  # the bundle is untrusted, so any failure is a failed run
                problems.append(f'{cell["id"]} {cell["task_id"]}: {error}')
                state = 'FAILED'
            print(f'[{position}/{len(plan["cells"])}] {cell["task_id"]} {state}', flush=True)
        scored = report(work) if not problems else None
    result = {'format': REPORT_FORMAT, 'verified': not problems, 'problems': problems,
              'label': LABEL, 'suite': plan['suite'], 'benchmark': plan['benchmark'],
              'provider': summary['provider'], 'model': summary['model'],
              'handle': summary.get('handle') if isinstance(summary.get('handle'), str)
              and HANDLE.fullmatch(summary['handle']) else None,
              'attempts_declared': summary.get('attempts_declared') if type(summary.get('attempts_declared')) is int else None,
              'harness': {'benchmark': BENCHMARK_VERSION, 'package_version': __version__},
              'bundle_sha256': digest(bundle.read_bytes()), 'self_reported': list(SELF_REPORTED),
              'not_replay_verified': sorted(unverified)}
    if plan['suite'] == 'smoke':
        result['note'] = 'Setup check only. Not a leaderboard result.'
    if scored:
        result['summary'] = scored['models'][0]
        result['cells'] = [{**row, 'replay_verified': row['mode'] != 'preparation'} for row in scored['cells']]
    output = Path(output) if output else bundle.with_name(bundle.name.removesuffix('.zip') + '.verified.json')
    write_json(output, result)
    print(conclusion(result, output), flush=True)
    return result


def conclusion(result, output):
    if not result['verified']:
        return '\n'.join(['', f'NOT VERIFIED. {len(result["problems"])} problem(s):']
                         + ['  ' + problem for problem in result['problems']] + [f'Report: {output}'])
    row = result['summary']
    replayed = sum(cell['replay_verified'] for cell in result['cells'])
    lines = ['', f'VERIFIED. {replayed} runs replayed from the benchmark start states and matched their logs.',
             f'{row["name"]}, model {row["provider"]}:{row["model"]}, submitted by {result["handle"] or "unnamed"}']
    if row.get('available_category_average') is not None:
        lines.append(f'Score {100 * row["available_category_average"]:.1f} of 100')
    for run in row.get('campaign_runs', []):
        if run.get('campaign'):
            lines.append(f'Campaign: {run["campaign"]["points"]} of {run["campaign"]["maximum_points"]} points')
    if result['not_replay_verified']:
        lines.append('Not replay verified, score as reported: ' + ', '.join(result['not_replay_verified']))
    lines.append('Self reported and not checked: ' + ', '.join(result['self_reported']) + '.')
    if result.get('note'):
        lines.append(result['note'])
    lines.append(f'Report: {output}')
    return '\n'.join(lines)
