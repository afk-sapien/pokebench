"""Build the compact local showcase from existing benchmark evidence."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from .focused_analysis import grouped_scores
from .showcase_costs import PRICING, comparison, run_cost, sum_cost

LABELS = {'claude-fable-5-1': 'Fable 5.1', 'gpt-6-astra': 'Astra', 'gpt-5.6-sol': 'Sol', 'gpt-5.6-terra': 'Terra',
          'gpt-5.6-luna': 'Luna', 'claude-opus-5-5': 'Opus',
          'claude-sonnet-5-5': 'Sonnet', 'claude-haiku-5-5': 'Haiku'}
CELL_FIELDS = ('id', 'task_id', 'category', 'score_group', 'model', 'variant', 'mode',
               'state', 'value', 'tokens', 'decisions', 'stop_reason', 'decision_limit',
               'token_limit', 'evaluation_spec_sha256', 'fixture_sha256')


def load(path):
    return json.loads(Path(path).read_text())


def existing_link(web, relative):
    if not relative:
        return None
    path = (web / relative).resolve()
    if not path.is_relative_to(web.resolve()):
        return None
    return relative if path.is_file() else None


def short_snapshot(source, web, extra=None, base=None):
    cells = []
    for row in source['cells']:
        clean = {k: row.get(k) for k in CELL_FIELDS}
        clean['replay'] = existing_link(web, row.get('replay'))
        clean['revision'] = 'Original pass'
        if base is not None:
            clean['cost'] = run_cost(base / 'focused-pass-v056' / row['id'], row['model'], row.get('tokens'))
        cells.append(clean)
    extras = extra if isinstance(extra, list) else [extra] if extra else []
    for batch in extras:
        for row in batch['cells']:
            clean = {k: row.get(k) for k in CELL_FIELDS}
            revision = row.get('attempt_revision', 'v066-astra')
            clean['replay'] = existing_link(web, f"{batch.get('web_prefix', 'main-v066-astra')}/replays/focused-{revision}-{row['id']}.html")
            clean['revision'] = 'Current interface'
            if base is not None:
                clean['cost'] = run_cost(base / batch['web_prefix'] / row['id'], row['model'], row.get('tokens'))
            cells.append(clean)
    by_model = defaultdict(list)
    for cell in cells:
        by_model[cell['model']].append(cell)
    models = []
    for name, rows in by_model.items():
        categories, score = grouped_scores(rows)
        finished = sum(r['state'] == 'finished' for r in rows)
        models.append({'id': name, 'label': LABELS.get(name, name), 'score': score,
                       'categories': categories, 'finished': finished, 'planned': len(rows),
                       'complete': finished == len(rows), 'tokens': sum(r.get('tokens') or 0 for r in rows),
                       'cost': sum_cost(rows),
                       'errors': sum(r['state'] == 'evaluation_error' for r in rows)})
    models.sort(key=lambda m: (not m['complete'], -(m['score'] if m['score'] is not None else -1)))
    tasks = [{k: t.get(k) for k in ('id', 'title', 'category', 'goal', 'start', 'action_policy', 'mode')}
             for t in source['tasks']]
    return {'models': models, 'tasks': tasks, 'cells': cells, 'categories': source['categories'],
            'finished': sum(c['state'] == 'finished' for c in cells), 'planned': len(cells),
            'efficiency': comparison(cells, models)}


def long_row(root, web, name, decision_limit=2000):
    result = load(root / 'run/result.json') if (root / 'run/result.json').exists() else {'state': 'queued'}
    pilot = load(root / 'pilot.json') if (root / 'pilot.json').exists() else {}
    usage = result.get('usage', {})
    achievements = result.get('achievements', [])
    manifest = load(root / 'run/manifest.json') if (root / 'run/manifest.json').exists() else {}
    cost = run_cost(root / 'run', manifest.get('agent', {}).get('model'))
    replay = existing_link(web, f'{root.name}-replay.html')
    return {'id': name, 'label': 'Fable 5.1' if name == 'fable' else name.title(),
            'run_id': root.name, 'decision_limit': decision_limit,
            'token_limit': pilot.get('token_limit', 30000000), 'cost': cost,
            'report': existing_link(web, f'{root.name}.html'), 'score': result.get('score', 0),
            'maximum': 1000, 'badges': sum(a['id'].startswith('badge:') for a in achievements),
            'state': result['state'], 'stop_reason': result.get('stop_reason'),
            'decisions': usage.get('calls', 0),
            'tokens': usage.get('input_tokens', 0) + usage.get('output_tokens', 0),
            'milestones': [{k: a.get(k) for k in ('label', 'decision', 'points', 'id')} for a in achievements],
            'image': existing_link(web, f'{root.name}.png'), 'replay': replay,
            'replay_mb': round((web / replay).stat().st_size / 1e6) if replay else None}


def long_snapshot(base, web):
    rows = []
    runs = [(name, f'long-v065-{name}') for name in ('opus', 'sol', 'sonnet', 'terra')]
    runs += [(name, f'long-v067-{name}') for name in ('astra', 'fable') if (base / f'long-v067-{name}/pilot.json').exists()]
    if (base / 'long-v069-luna/pilot.json').exists():
        runs.append(('luna', 'long-v069-luna'))
    if (base / 'long-v073-haiku/pilot.json').exists():
        runs.append(('haiku', 'long-v073-haiku'))
    extensions = defaultdict(list)
    for path in sorted(base.glob('long-*/continuation.json')):
        record = load(path)
        if record.get('protocol') == 'long-decision-boundaries-v1':
            extensions[record['origin_run_id']].append((path.parent, record['decision_limit']))
    for name, run_id in runs:
        row = long_row(base / run_id, web, name)
        row['extensions'] = [long_row(root, web, name, limit)
                             for root, limit in sorted(extensions[run_id], key=lambda item: item[1])]
        rows.append(row)
    return sorted(rows, key=lambda r: -r['score'])


def export(base, web, *, install=False):
    base, web = Path(base), Path(web)
    source = load(web / 'focused-analysis.json')
    extra = []
    for folder in ('main-v066-astra', 'main-v067-fable'):
        path = base / folder / 'progress.json'
        if path.exists():
            batch = load(path)
            batch['web_prefix'] = folder
            extra.append(batch)
    data = {'schema': 'pokebench-showcase-v1', 'updated_at': datetime.now(timezone.utc).isoformat(),
            'short': short_snapshot(source, web, extra, base), 'long': long_snapshot(base, web),
            'pricing': PRICING,
            'report': existing_link(web, 'technical-report.pdf')}
    text = json.dumps(data, ensure_ascii=True, allow_nan=False) + '\n'
    temporary = web / 'showcase-data.json.tmp'
    temporary.write_text(text)
    temporary.replace(web / 'showcase-data.json')
    if install:
        assets = Path(__file__).with_name('showcase_assets')
        for name in ('showcase.css', 'showcase.js'):
            shutil.copy2(assets / name, web / name)
        if (web / 'index.html').exists() and not (web / 'analysis-v060.html').exists():
            shutil.copy2(web / 'index.html', web / 'analysis-v060.html')
        shutil.copy2(assets / 'index.html', web / 'index.html')
    return data


def public_replay(web, relative, model, output):
    """Write a public replay with screenshots and controller actions only."""
    import re
    from .public_site import REPLAY, json_text, replay_payload
    path = web / relative
    match = re.search(r'<script[^>]*id="data"[^>]*>(.*?)</script>', path.read_text(), re.S)
    runs = json.loads(match[1]).get('runs', []) if match else []
    if len(runs) != 1 or runs[0].get('model') != model:
        raise ValueError(f'Replay does not match its result: {relative}')
    payload = replay_payload(path, {'id': runs[0]['id'], 'model': model, 'completed': runs[0].get('completed')})
    target = 'replays/' + relative.removesuffix('.html').replace('/', '--') + '.html'
    (output / target).write_text(REPLAY.replace('__DATA__', json_text(payload)))
    return target


def public_image(web, relative, output):
    from PIL import Image
    target = 'images/' + Path(relative).name
    with Image.open(web / relative) as image:
        clean = Image.new('RGB', image.size)
        clean.paste(image.convert('RGB'))
        clean.save(output / target, format='PNG')
    return target


def export_public(web, output, *, report=None):
    """Build a static public copy of the showcase in a new directory.

    Local replays carry model plans and observations, so each is rebuilt from
    verified screenshots and executed controller actions only. Local run
    reports and the detailed analysis page are not published.
    """
    web, output = Path(web), Path(output)
    data = load(web / 'showcase-data.json')
    output.mkdir()
    (output / 'replays').mkdir()
    (output / 'images').mkdir()
    for cell in data['short']['cells']:
        cell['replay'] = public_replay(web, cell['replay'], cell['model'], output) if cell.get('replay') else None
    by_label = {label: model for model, label in LABELS.items()}
    for row in data['long']:
        for run in [row, *row.get('extensions', [])]:
            run['report'] = None
            run['replay'] = public_replay(web, run['replay'], by_label[run['label']], output) if run.get('replay') else None
            run['replay_mb'] = round((output / run['replay']).stat().st_size / 1e6, 1) if run['replay'] else None
            run['image'] = public_image(web, run['image'], output) if run.get('image') else None
    data['report'] = None
    if report:
        shutil.copy2(report, output / 'technical-report.pdf')
        data['report'] = 'technical-report.pdf'
    (output / 'showcase-data.json').write_text(json.dumps(data, ensure_ascii=True, allow_nan=False) + '\n')
    assets = Path(__file__).with_name('showcase_assets')
    for name in ('showcase.css', 'showcase.js'):
        shutil.copy2(assets / name, output / name)
    page = (assets / 'index.html').read_text().replace('<a href="analysis-v060.html">Detailed analysis ↗</a>', '')
    hero = next((r for r in data['long'] if r['run_id'] == 'long-v065-opus'), None)
    if hero and hero['replay'] and hero['image']:
        page = page.replace('href="long-v065-opus-replay.html"', f'href="{hero["replay"]}"').replace('src="long-v065-opus.png"', f'src="{hero["image"]}"')
    (output / 'index.html').write_text(page)
    (output / '.nojekyll').write_text('')
    return data
