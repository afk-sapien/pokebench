"""`run --model X --suite NAME`: plan, estimate, run with resume and print a plain summary.

This only chooses defaults. The work is done by the catalog batch runner.
"""
from http.client import HTTPException
import json
from pathlib import Path
import re
import urllib.request

from . import BENCHMARK_VERSION
from .benchmark_tracks import LONG, NAMES, SHORT, for_category
from .catalog_batch import plan, report, run_batch
from .catalog_execution import PROVIDERS, inventory
from .core import write_json
from .interrupts import pause_on_interrupt
from .recovery import NO_REPLY, STOPPED

# benchmark, reference token budget, fixed task list (None means every ready task).
# The reference budget only warns. Each task runs at its own caps, so run order never changes a task.
SUITES = {
    'smoke': (SHORT, 500_000, ('operations-battle-switch', 'battle-heal-switch-attack-tradeoff', 'battle-wild-basics')),
    'short': (SHORT, 60_000_000, None),
    'long': (LONG, 30_000_000, None),
}
LONG_DECISIONS = 2000
# Stop after this many tokens without a new v2 milestone. The longest stored stretch that still ended
# in a milestone is 8.2M (Terra through Mt. Moon), so 10M leaves a 1.8M margin.
LONG_MILESTONE_GUARD_TOKENS = 10_000_000
# The published Long runs used these. The single-run defaults of 20K actions and 6 h would cut a campaign short.
LONG_LIMITS = {'max_actions': 150_000, 'max_frames': 10_000_000, 'max_wall_seconds': 86_400,
               'max_loop_tokens': 2_000_000, 'max_milestone_tokens': LONG_MILESTONE_GUARD_TOKENS}
# The published Short runs used low effort and the published Long runs medium.
EFFORT = {'smoke': 'low', 'short': 'low', 'long': 'medium'}
LONG_STOPS = (f'The campaign stops at {LONG_DECISIONS:,} decisions or its token cap, whichever comes first. '
              'It also stops at 150K controller actions, 10M frames, 24 h, '
              'or 2M tokens spent without reaching a new tile or milestone, '
              'or 10M tokens spent without a new milestone.')
# Short stops a task after two thirds of its own token cap without a new milestone. A pass or fail task has no
# milestone before it passes, so there it stops at two thirds of the cap. No stored Short success used more than
# 0.60 of its cap, and no Long stretch through the same caves and buildings came closer than 0.65.
SHORT_GUARD = (2, 3)
SHORT_STOPS = ('Each task also stops after two thirds of its token cap without a new milestone. '
               'A pass or fail task has no milestone before it passes, so it stops at two thirds of its cap.')
PREFIXES = (('claude', 'claude'), ('gpt', 'codex'))
# The expected cost comes only from runs the public site publishes for the release being run.
SITE = 'https://afk-sapien.github.io/pokebench/'
SITE_DATA_BYTES = 16_000_000
NO_EXPECTED = 'so there is no expected cost to show. The worst case above is the only firm bound.'
MATCH_KEYS = ('task_id', 'variant', 'evaluation_spec_sha256', 'fixture_sha256', 'decision_limit', 'token_limit')


def resolve_model(provider, model, suite=None):
    if provider == 'random' and not model:
        model = 'random'
    if not model:
        raise ValueError('Name a model with --model. To check your setup for free, run --suite smoke --provider random')
    if provider is None and model.partition(':')[0] in PROVIDERS:
        provider, _, model = model.partition(':')
    if provider is None:
        provider = next((name for prefix, name in PREFIXES if model.startswith(prefix)), None)
    if provider not in PROVIDERS or not model:
        raise ValueError('Suite runs need --provider codex, claude or openai-compatible, '
                         'or --provider random with --suite smoke for a free setup check')
    if provider == 'random' and suite != 'smoke':
        raise ValueError('The random player runs the smoke suite only. It checks your setup and calls no model')
    return provider, model


def locate(data, rom):
    data = Path(data)
    fixtures, game_data = data / 'fixtures', data / 'game-data'
    if not fixtures.is_dir() or not (game_data / 'current.json').is_file():
        raise ValueError(f'No benchmark data in {data}. Run: pokebench setup --rom /path/to/red.gb')
    if rom is None:
        record = data / 'setup.json'
        rom = Path(json.loads(record.read_text())['rom']) if record.is_file() else None
    if rom is None or not Path(rom).is_file():
        raise ValueError('ROM not found. Pass --rom /path/to/red.gb')
    return fixtures, game_data, Path(rom)


def new_plan(suite, fixtures, provider, model):
    benchmark, _, fixed = SUITES[suite]
    rows = [row for row in inventory(fixtures)['tasks'] if for_category(row['category']) == benchmark]
    tasks = list(fixed) if fixed else [row['id'] for row in rows if row['runnable']]
    if not tasks:
        raise ValueError(f'No {NAMES[benchmark]} tasks are ready yet')
    manifest = plan(fixtures, [f'{provider}:{model}'], tasks, benchmark=benchmark)
    manifest['suite'] = suite
    manifest['held_tasks'] = [] if fixed else sorted(row['id'] for row in rows if not row['runnable'])
    for cell in manifest['cells']:
        cell['reasoning_effort'] = EFFORT[suite]
    if suite == 'smoke':
        manifest['note'] = 'Setup check only. Not a benchmark result.'
    if suite == 'long':
        for cell in manifest['cells']:
            cell['decision_limit'] = LONG_DECISIONS
            cell['run_limits'] = dict(LONG_LIMITS)
    if suite == 'short':
        share, whole = SHORT_GUARD
        for cell in manifest['cells']:
            cell['run_limits'] = {'max_milestone_tokens': cell['token_limit'] * share // whole}
    return manifest


def millions(tokens):
    return f'{tokens / 1e6:.1f}M' if tokens >= 1e6 else f'{tokens / 1e3:.0f}K'


def published(url=SITE + 'showcase-data.json', timeout=10):
    """The public site data and None, or None and the reason it could not be read."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as reply:
            data = reply.read(SITE_DATA_BYTES + 1)
        if len(data) > SITE_DATA_BYTES:
            raise ValueError('the site data is larger than expected')
        value = json.loads(data)
        if not isinstance(value, dict) or value.get('schema') != 'pokebench-showcase-v1':
            raise ValueError('the site data has an unknown format')
        return value, None
    except (OSError, ValueError, HTTPException) as error:
        return None, str(error) or type(error).__name__


def matching_runs(manifest, data, release):
    """Published runs on this release with the plan's tasks, start states and caps. Each model must cover the plan."""
    first = manifest['cells'][0]
    if manifest['benchmark'] == LONG:
        return {row['model']: [row] for row in data.get('long') or []
                if row.get('harness') == release and row.get('state') == 'finished' and type(row.get('tokens')) is int
                and (row.get('decision_limit'), row.get('token_limit')) == (first['decision_limit'], first['token_limit'])}
    wanted = {tuple(cell.get(key) for key in MATCH_KEYS) for cell in manifest['cells']}
    found = {}
    for cell in (data.get('short') or {}).get('cells') or []:
        key = tuple(cell.get(name) for name in MATCH_KEYS)
        if (cell.get('harness') == release and cell.get('state') == 'finished' and not cell.get('retired')
                and type(cell.get('tokens')) is int and key in wanted):
            found.setdefault(cell['model'], {})[key] = cell
    return {model: list(cells.values()) for model, cells in found.items() if len(cells) == len(wanted)}


def expected(manifest, data, problem, release=BENCHMARK_VERSION):
    """Lines that state what published runs of this release used. Every number is read from the site."""
    if data is None:
        return [f'Could not read the published runs from {SITE} ({problem}), {NO_EXPECTED}']
    try:
        runs = matching_runs(manifest, data, release)
    except (AttributeError, KeyError, TypeError):
        return [f'The published runs on {SITE} could not be read, {NO_EXPECTED}']
    suite = manifest['suite']
    if not runs:
        return [f'No published {suite} runs exist yet for this release, {release}, {NO_EXPECTED}']
    totals = sorted(sum(row['tokens'] for row in rows) for rows in runs.values())
    spread = millions(totals[0]) if len(totals) == 1 else f'{millions(totals[0])} to {millions(totals[-1])}'
    lines = [f'Published {suite} runs on {release}: {len(totals)} model{"s" if len(totals) > 1 else ""} '
             f'used {spread} tokens.']
    model = manifest['cells'][0]['model']
    if model in runs:
        costs = [row.get('cost') if isinstance(row.get('cost'), dict) else {} for row in runs[model]]
        tokens = millions(sum(row['tokens'] for row in runs[model]))
        if all(isinstance(cost.get(key), (int, float)) for cost in costs for key in ('low', 'high')) and not any(
                cost.get('partial') for cost in costs):
            low, high = (sum(cost[key] for cost in costs) for key in ('low', 'high'))
            lines.append(f'{model} used {tokens} tokens there, about ${low:,.2f} to ${high:,.2f} at the API prices '
                         'the site lists.')
        else:
            lines.append(f'{model} used {tokens} tokens there.')
    return lines


def estimate(manifest, budget, output, used=0, done=0, price=None, expected_lines=()):
    cells = manifest['cells']
    suite = manifest['suite']
    model = f'{cells[0]["provider"]}:{cells[0]["model"]}'
    tasks = len({cell['task_id'] for cell in cells})
    lines = [f'Suite {suite} ({NAMES[manifest["benchmark"]]}), model {model}',
             f'Runs: {len(cells)} over {tasks} task{"s" if tasks > 1 else ""}, one at a time.']
    if done:
        lines.append(f'Resuming: {done} of {len(cells)} runs already finished, {millions(used)} tokens used.')
    if manifest.get('held_tasks'):
        lines.append('Left out, fixture needs revalidation: ' + ', '.join(manifest['held_tasks']))
    worst = sum(cell['token_limit'] for cell in cells)
    lines.append(f'Each task runs at its own decision and token caps. Worst case {millions(worst)} tokens, '
                 'counting input plus output.')
    lines.append(f'Reference budget {millions(budget)}. Passing it prints a warning. It never stops or shortens a task.')
    if suite == 'long':
        lines.append(LONG_STOPS)
    if suite == 'short':
        lines.append(SHORT_STOPS)
    lines += expected_lines
    if price is not None:
        lines.append(f'At ${price:g} per million tokens the reference budget costs about ${budget * price / 1e6:,.2f} '
                     f'and the worst case about ${worst * price / 1e6:,.2f}. '
                     'Cached input and output prices differ, so this is rough.')
    if suite == 'smoke':
        lines.append('This only checks your setup. It is not a benchmark result.')
    lines.append(f'Results go to {output}. Run the same command again to resume.')
    return '\n'.join(lines)


def summary(result, output, next_step=True):
    row = result['models'][0]
    lines = ['', f'{row["name"]}, model {row["provider"]}:{row["model"]}',
             f'Finished {row["completed"]} of {row["planned"]} runs, {row["evaluation_errors"]} errors.']
    if row['benchmark'] == LONG:
        for run in row['campaign_runs']:
            campaign = run.get('campaign')
            if campaign:
                lines.append(f'Campaign: {campaign["points"]} of {campaign["maximum_points"]} points, '
                             f'{campaign["milestones"]} milestones, Champion {"yes" if campaign["champion"] else "no"}.')
    elif row['category_scores'] and row['available_category_average'] is not None:
        lines.append(f'Score {100 * row["available_category_average"]:.1f} of 100, the average of these categories:')
        lines += [f'  {name:<12} {100 * value:5.1f}' for name, value in sorted(row['category_scores'].items())]
    lines.append(f'Tokens used {millions(result["tokens_used"])}. Reference budget {millions(result["token_budget"])}.')
    if result['tokens_used'] > result['token_budget']:
        lines.append('Warning: this run passed the reference budget. Every task still ran at its own caps.')
    for cell in result['cells']:
        if cell['state'] == 'paused':
            folder = Path(output) / cell['id']
            pending = folder / 'pending.json'
            phase = json.loads(pending.read_text()).get('phase') if pending.is_file() else None
            if phase == STOPPED:
                lines.append(f'{cell["task_id"]} was stopped by Ctrl-C during a decision. It cannot resume and is not scored. '
                             f'Delete {folder} and run the same command again to rerun it.')
            elif phase == NO_REPLY:
                lines.append(f'{cell["task_id"]} paused after a provider error with no model reply. '
                             'Its checkpoint is kept and the same command resumes it.')
            else:
                lines.append(f'{cell["task_id"]} paused. Its checkpoint is kept and the same command resumes it.')
        if cell['state'] == 'evaluation_error':
            folder = Path(output) / cell['id']
            lines.append(f'{cell["task_id"]} failed and is not retried. The reason is in {folder / "error.json"}. '
                         f'Delete {folder} and run the same command again to retry it.')
    if any(cell['state'] == 'evaluation_error' for cell in result['cells']) and not row['accounting_complete']:
        lines.append('Some token usage of a failed task is unknown, so the token total may be low.')
    if any(cell['state'] not in ('finished', 'evaluation_error') for cell in result['cells']):
        lines.append('Not every run finished. Run the same command again to continue.')
    elif result.get('suite') == 'smoke' and row['completed'] == row['planned']:
        lines.append('Setup works. This was a check, not a benchmark result.')
    lines.append(f'Details: {Path(output) / "report.json"}')
    if next_step and all(cell['state'] == 'finished' for cell in result['cells']):
        lines.append(f'Next, pack the bundle: pokebench submit {output} --handle YOUR_GITHUB_NAME')
    return '\n'.join(lines)


def progress(row, position, total):
    value = '' if row['value'] is None else f' score {100 * row["value"]:.0f}'
    print(f'[{position}/{total}] {row["task_id"]} {row["state"]}{value}, {millions(row["tokens"])} tokens', flush=True)


def recover(output, rom, guard=None):
    """Finish a run that was interrupted mid task, using its saved checkpoint. Return False after a Ctrl-C pause."""
    from .cli import execute, parser
    for row in report(output)['cells']:
        folder = output / row['id']
        if not folder.is_dir() or row['state'] in ('finished', 'evaluation_error'):
            continue
        if guard and guard.requested:
            return False
        if not any(folder.iterdir()):
            folder.rmdir()
        elif (folder / 'recovery.json').is_file():
            print(f'Resuming {row["task_id"]} from its checkpoint.', flush=True)
            result = execute(parser().parse_args(['resume', '--rom', str(rom), '--run', str(folder)]))
            if isinstance(result, dict) and result.get('state') == 'paused':
                if guard and guard.requested:
                    return False
                raise ValueError(f'{row["task_id"]} paused again after a provider error with no model reply. '
                                 'No tokens were spent on it. Run the same command again later')
    return True


def run_suite(args, *, ask=None, next_step=True):
    """Plan, estimate and run a suite with resume. Return the run folder, its report, the ROM and the fixtures.

    ask, when given, is called after the estimate while some run is unfinished. A false answer starts nothing
    and returns None.
    """
    provider, model = resolve_model(args.provider, args.model, args.suite)
    benchmark, default_budget, _ = SUITES[args.suite]
    budget = args.budget or default_budget
    fixtures, game_data, rom = locate(args.data, args.rom)
    output = args.output or Path('runs') / f'{args.suite}-{re.sub(r"[^A-Za-z0-9.]+", "-", model)}'
    used = done = 0
    if (output / 'plan.json').is_file():
        manifest = json.loads((output / 'plan.json').read_text())
        if manifest.get('suite') != args.suite or {(c['provider'], c['model']) for c in manifest['cells']} != {(provider, model)}:
            raise ValueError(f'{output} holds a different run. Choose another --output')
        current = report(output)
        used = sum(row['tokens'] for row in current['cells'])
        done = sum(row['state'] == 'finished' for row in current['cells'])
    elif output.exists():
        raise ValueError(f'{output} already exists and is not a suite run. Choose another --output')
    else:
        manifest = new_plan(args.suite, fixtures, provider, model)
    lines = (['The random player calls no model and uses no tokens.'] if provider == 'random'
             else expected(manifest, *published()))
    print(estimate(manifest, budget, output, used, done, args.input_price, lines), flush=True)
    if provider == 'claude':
        from .claude_provider import pin_cli
        print(pin_cli(args.data), flush=True)
    if args.dry_run:
        return None
    if ask is not None and done < len(manifest['cells']) and not ask():
        print('Nothing was started.', flush=True)
        return None
    if not (output / 'plan.json').is_file():
        output.mkdir(parents=True)
        write_json(output / 'plan.json', manifest)
    total = len(manifest['cells'])
    # One guard covers the resumed task and the batch, so Ctrl-C pauses the task and starts nothing after it.
    with pause_on_interrupt() as guard:
        if recover(output, rom, guard):
            result = run_batch(fixtures, rom, game_data, output, budget=budget, resume=True, benchmark=benchmark,
                               on_cell=lambda row: progress(row, int(row['id'][-4:]), total))
        else:
            result = report(output)
            result.update(token_budget=budget, tokens_used=sum(row['tokens'] for row in result['cells']))
    result['suite'] = args.suite
    print(summary(result, output, next_step), flush=True)
    return output, result, rom, fixtures
