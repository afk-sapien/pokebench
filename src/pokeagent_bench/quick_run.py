"""`run --model X --suite NAME`: plan, estimate, run with resume and print a plain summary.

This only chooses defaults. The work is done by the catalog batch runner.
"""
import json
from pathlib import Path
import re

from .benchmark_tracks import LONG, NAMES, SHORT, for_category
from .catalog_batch import plan, report, run_batch
from .catalog_execution import inventory
from .core import write_json

# benchmark, default token budget, fixed task list (None means every ready task)
SUITES = {
    'smoke': (SHORT, 500_000, ('preparation-lead-selection', 'battle-heal-switch-attack-tradeoff', 'battle-wild-basics')),
    'short': (SHORT, 60_000_000, None),
    'long': (LONG, 30_000_000, None),
}
LONG_DECISIONS = 2000
SCALE = {
    'smoke': 'Two leaderboard models used about 40K tokens on these three tasks.',
    'short': 'Two leaderboard models used 27M and 49M tokens on this suite.',
    'long': f'The campaign stops at {LONG_DECISIONS:,} decisions or the token budget, whichever comes first.',
}
PREFIXES = (('claude', 'claude'), ('gpt', 'codex'))
PROVIDERS = ('codex', 'claude')


def resolve_model(provider, model):
    if not model:
        raise ValueError('Name a model with --model')
    if provider is None and model.partition(':')[0] in PROVIDERS:
        provider, _, model = model.partition(':')
    if provider is None:
        provider = next((name for prefix, name in PREFIXES if model.startswith(prefix)), None)
    if provider not in PROVIDERS or not model:
        raise ValueError('Suite runs need --provider codex or --provider claude')
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
    manifest = plan(fixtures, [f'{provider}:{model}'], tasks, benchmark=benchmark)
    manifest['suite'] = suite
    manifest['held_tasks'] = [] if fixed else sorted(row['id'] for row in rows if not row['runnable'])
    if suite == 'smoke':
        manifest['note'] = 'Setup check only. Not a benchmark result.'
    if suite == 'long':
        for cell in manifest['cells']:
            cell['decision_limit'] = LONG_DECISIONS
    return manifest


def millions(tokens):
    return f'{tokens / 1e6:.1f}M' if tokens >= 1e6 else f'{tokens / 1e3:.0f}K'


def estimate(manifest, budget, output, used=0, done=0, price=None):
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
    lines.append(f'Token budget {millions(budget)}, counting input plus output. No new run starts once it is spent.')
    lines.append(SCALE[suite])
    if price is not None:
        lines.append(f'At ${price:g} per million tokens the full budget costs about ${budget * price / 1e6:,.2f}. '
                     'Cached input and output prices differ, so this is rough.')
    if suite == 'smoke':
        lines.append('This only checks your setup. It is not a benchmark result.')
    lines.append(f'Results go to {output}. Run the same command again to resume.')
    return '\n'.join(lines)


def summary(result, output):
    row = result['models'][0]
    lines = ['', f'{row["name"]}, model {row["provider"]}:{row["model"]}',
             f'Finished {row["completed"]} of {row["planned"]} runs, {row["evaluation_errors"]} errors.']
    if row['benchmark'] == LONG:
        for run in row['campaign_runs']:
            campaign = run.get('campaign')
            if campaign:
                lines.append(f'Campaign: {campaign["points"]} of {campaign["maximum_points"]} points, '
                             f'{campaign["milestones"]} milestones, Champion {"yes" if campaign["champion"] else "no"}.')
    elif row['available_category_average'] is not None:
        lines.append(f'Score {100 * row["available_category_average"]:.1f} of 100, the average of these categories:')
        lines += [f'  {name:<12} {100 * value:5.1f}' for name, value in sorted(row['category_scores'].items())]
    lines.append(f'Tokens used {millions(result["tokens_used"])} of {millions(result["token_budget"])}.')
    if row['completed'] < row['planned']:
        lines.append('Not every run finished. Run the same command again to continue, or raise --budget.')
    elif result.get('suite') == 'smoke':
        lines.append('Setup works. This was a check, not a benchmark result.')
    lines.append(f'Details: {Path(output) / "report.json"}')
    return '\n'.join(lines)


def progress(row, position, total):
    value = '' if row['value'] is None else f' score {100 * row["value"]:.0f}'
    print(f'[{position}/{total}] {row["task_id"]} {row["state"]}{value}, {millions(row["tokens"])} tokens', flush=True)


def recover(output, rom):
    """Finish a run that was interrupted mid task, using its saved checkpoint."""
    from .cli import execute, parser
    for row in report(output)['cells']:
        folder = output / row['id']
        if not folder.is_dir() or row['state'] in ('finished', 'evaluation_error'):
            continue
        if not any(folder.iterdir()):
            folder.rmdir()
        elif (folder / 'recovery.json').is_file():
            print(f'Resuming {row["task_id"]} from its checkpoint.', flush=True)
            execute(parser().parse_args(['resume', '--rom', str(rom), '--run', str(folder)]))


def run_suite(args):
    provider, model = resolve_model(args.provider, args.model)
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
    print(estimate(manifest, budget, output, used, done, args.input_price), flush=True)
    if args.dry_run:
        return None
    if not (output / 'plan.json').is_file():
        output.mkdir(parents=True)
        write_json(output / 'plan.json', manifest)
    recover(output, rom)
    total = len(manifest['cells'])
    result = run_batch(fixtures, rom, game_data, output, budget=budget, resume=True, benchmark=benchmark,
                       on_cell=lambda row: progress(row, int(row['id'][-4:]), total))
    result['suite'] = args.suite
    print(summary(result, output), flush=True)
    return None
