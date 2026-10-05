"""Allowlisted, static PokeBench publication from audited local result snapshots.

Never copy a local review page or provider transcript into this export. Public
replays contain reencoded screenshots and controller actions, not model notes.
"""
import base64
import csv
import hashlib
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import tempfile

from PIL import Image

from .portal import HTML


PRIVATE = re.compile(r'(/home/|/Users/|file://|localhost|127\.0\.0\.1|[A-Za-z]:\\|sk-[A-Za-z0-9]{12}|session[_ -]?id|api[_ -]?key|authorization\s*:)', re.I)
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/+ -]{0,199}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')
ATTEMPT_FIELDS = ('repeat', 'variant', 'completed', 'tokens', 'decisions', 'wall_seconds',
                  'replay_verified', 'input_tokens', 'cached_input_tokens', 'output_tokens',
                  'estimated_credits', 'cost_complete')


def public_text(value, maximum=2000):
    if not isinstance(value, str) or len(value) > maximum or PRIVATE.search(value):
        raise ValueError('Unsafe or oversized public text')
    return value


def identifier(value):
    value = public_text(value, 200)
    if not IDENTIFIER.fullmatch(value):
        raise ValueError('Invalid public identifier')
    return value


def number(value):
    if value is None or type(value) in (bool, int, float):
        if isinstance(value, float) and not (-1e100 < value < 1e100):
            raise ValueError('Non-finite public number')
        return value
    raise ValueError('Expected a public numeric value')


def sha(value):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ValueError('Invalid public checksum')
    return value


def png(value):
    prefix = 'data:image/png' + chr(59) + 'base64,'
    if not isinstance(value, str) or not value.startswith(prefix) or len(value) > 8_000_000:
        raise ValueError('Invalid screenshot')
    raw = base64.b64decode(value[len(prefix):], validate=True)
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != 'PNG' or image.width > 2048 or image.height > 2048:
            raise ValueError('Invalid screenshot dimensions')
        clean = Image.new('RGB', image.size)
        clean.paste(image.convert('RGB'))
        output = io.BytesIO()
        clean.save(output, format='PNG')
    return prefix + base64.b64encode(output.getvalue()).decode()


def json_text(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')


def write_json(path, value):
    path.write_text(json_text(value) + '\n')


def read(path):
    return json.loads(path.read_text())


def safe_metadata(manifest):
    agent = manifest.get('agent', {})
    result = {}
    for key in ('provider', 'model', 'harness', 'reasoning_effort', 'cli_version'):
        if agent.get(key) is not None:
            result[key] = identifier(agent[key])
    for key in ('created_at', 'benchmark', 'package_version', 'track', 'observation_policy'):
        if manifest.get(key) is not None:
            result[key] = public_text(manifest[key], 200)
    for key in ('source_sha256', 'initial_sha256'):
        if manifest.get(key):
            result[key] = sha(manifest[key])
    if agent.get('prompt_sha256'):
        result['prompt_sha256'] = sha(agent['prompt_sha256'])
    config = agent.get('configuration', {})
    result['context'] = {key: number(config[key]) for key in ('context_turns', 'compact_at', 'continuity') if key in config}
    result['core_version'] = identifier(manifest.get('core', {}).get('version', 'unrecorded'))
    return result


def replay_payload(path, attempt):
    """Extract only verified screen boundaries and executed gamepad actions."""
    source = path.read_text()
    match = re.search(r'<script[^>]*id="data"[^>]*>(.*?)</script>', source, re.S)
    if not match:
        raise ValueError('Missing replay data')
    runs = json.loads(match[1]).get('runs', [])
    if len(runs) != 1:
        raise ValueError('Public replay must contain one recorded attempt')
    run = runs[0]
    expected_id = attempt.get('source_run_id', attempt['id'])
    if (run.get('id') != expected_id or run.get('model') != attempt['model']
            or run.get('completed') != attempt['completed']):
        raise ValueError('Replay does not match its scored attempt')
    images = {}
    steps = []
    for step in run['steps']:
        out = {key: number(step[key]) for key in ('decision', 'before_frame', 'after_frame', 'tokens', 'cumulative_tokens')}
        for key in ('before', 'after'):
            original = step[key]
            if original not in images:
                images[original] = png(run['images'][original])
            out[key] = hashlib.sha256(images[original].encode()).hexdigest()
        out['actions'] = []
        for action in step.get('actions', []):
            button = action.get('button')
            if button not in (None, 'a', 'b', 'up', 'down', 'left', 'right', 'start', 'select'):
                raise ValueError('Unknown controller input')
            out['actions'].append({'button': button, 'hold_frames': number(action['hold_frames']),
                                   'release_frames': number(action['release_frames'])})
        steps.append(out)
    if not steps:
        raise ValueError('Replay has no decision boundaries')
    return {'model': identifier(attempt['model']), 'completed': bool(attempt['completed']),
            'benchmark': identifier(attempt.get('benchmark', 'unrecorded')), 'steps': steps,
            'images': {hashlib.sha256(value.encode()).hexdigest(): value for value in images.values()}}


def clean_task(task):
    result = {key: public_text(task[key]) for key in ('id', 'name', 'category', 'difficulty', 'description')}
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,99}', result['id']):
        raise ValueError('Invalid benchmark slug')
    result.update({key: number(task[key]) for key in ('tokens', 'variants', 'included_in_score') if key in task})
    result['state_hash'] = sha(task['state_hash'])
    result['variant_state_hashes'] = [sha(value) for value in task.get('variant_state_hashes', [])]
    result['preview'] = png(task['preview'])
    if task.get('validation'):
        result['validation'] = {key: public_text(task['validation'][key]) for key in ('status', 'message')}
    if task.get('source'):
        source = task['source']
        config = source.get('configuration', {})
        result['source'] = {'label': public_text(source['label']), 'benchmark_versions': [identifier(v) for v in source.get('benchmark_versions', [])],
                            'configuration': {'core': {'version': identifier(config.get('core', {}).get('version', 'unrecorded'))}}}
        if config.get('source_sha256'):
            result['source']['configuration']['source_sha256'] = sha(config['source_sha256'])
    return result


def document(title, content):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+' | PokeBench</title><style>body {max-width:900px} body {margin:40px auto} body {padding:0 24px} body {font:17px/1.6 system-ui} a {color:#186645} td,th {padding:10px} table {border-collapse:collapse} td {border-bottom:1px solid #ddd} code {overflow-wrap:anywhere}</style><a href="index.html">PokeBench</a>'+content+'</html>'


def release_snapshot(root):
    """Validate the registered matrix, then allowlist prospective evidence."""
    root = Path(root)
    protocol = read(root/'protocol.json')
    summary = read(root/'release-summary.json')
    canonical = json.dumps({k: v for k, v in protocol.items() if k != 'sha256'}, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if hashlib.sha256(canonical).hexdigest() != protocol.get('sha256') or summary.get('protocol_sha256') != protocol['sha256']:
        raise ValueError('Release summary does not match its frozen protocol')
    p = {key: public_text(protocol[key]) for key in ('id', 'frozen_at', 'track', 'scoring', 'uncertainty', 'budget_policy', 'retry_policy', 'history_policy')}
    p.update({key: number(protocol[key]) for key in ('variants', 'total_token_budget', 'maximum_planned_tokens', 'planned_attempts', 'context_turns', 'compact_at', 'paid_summaries')})
    p.update({key: sha(protocol[key]) for key in ('source_sha256', 'fixture_registration_sha256', 'rom_sha256', 'catalog_sha256')})
    p['source_protocol_sha256'] = sha(protocol['sha256'])
    p['checksum_note'] = 'Source checksum identifies the private original protocol. This allowlisted public derivative has its own checksum in manifest.json.'
    p['core_version'] = identifier(protocol.get('core', {}).get('version', 'unrecorded'))
    p['models'] = [{key: identifier(model[key]) for key in ('model', 'provider', 'effort')} for model in protocol['models']]
    p['tasks'] = []
    for task in protocol['tasks']:
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,99}', task['id']):
            raise ValueError('Invalid release task slug')
        p['tasks'].append({**{key: public_text(task[key]) for key in ('id', 'name', 'difficulty', 'validation_status')},
                           'tokens': number(task['tokens']), 'score_eligible': number(task['score_eligible']),
                           'starting_state_sha256': [sha(v) for v in task['starting_state_sha256']]})
    variants = p['variants']
    if type(variants) is not int or variants < 1:
        raise ValueError('Invalid release variant count')
    for key in ('total_token_budget', 'maximum_planned_tokens', 'planned_attempts'):
        if type(p[key]) is not int or p[key] <= 0:
            raise ValueError('Invalid registered release budget or count')
    if any(type(t['score_eligible']) is not bool or len(t['starting_state_sha256']) != variants for t in p['tasks']):
        raise ValueError('Invalid registered task coverage')
    model_ids = [m['model'] for m in p['models']]
    task_ids = [t['id'] for t in p['tasks']]
    if len(set(model_ids)) != len(model_ids) or len(set(task_ids)) != len(task_ids) or not model_ids or not task_ids:
        raise ValueError('Release matrix must have unique models and tasks')
    expected = {(model, task, variant) for model in model_ids for task in task_ids for variant in range(1, variants+1)}
    attempts = []
    observed = set()
    states = ('pending', 'running', 'finished', 'error', 'paused')
    for item in summary['attempts']:
        if type(item.get('variant')) is not int:
            raise ValueError('Invalid attempt variant')
        key = (item['model'], item['task'], item['variant'])
        if key not in expected or key in observed or item['status'] not in states:
            raise ValueError('Release attempt matrix differs from registration')
        observed.add(key)
        a = {field: identifier(item[field]) for field in ('id', 'model', 'task', 'provider', 'effort', 'status')}
        a.update({field: number(item.get(field)) for field in ('variant', 'token_limit', 'tokens', 'completed', 'decisions', 'wall_seconds', 'accounting_complete', 'replay_verified')})
        registered_model = next(m for m in p['models'] if m['model'] == a['model'])
        registered_task = next(t for t in p['tasks'] if t['id'] == a['task'])
        if any(a[field] != registered_model[field] for field in ('provider', 'effort')) or a['token_limit'] != registered_task['tokens']:
            raise ValueError('Attempt settings differ from registration')
        if type(a['tokens']) is not int or a['tokens'] < 0:
            raise ValueError('Invalid recorded release tokens')
        if item.get('stop_reason'):
            a['stop_reason'] = identifier(item['stop_reason'])
        attempts.append(a)
    if observed != expected or len(expected) != p['planned_attempts'] or summary['planned'] != len(expected):
        raise ValueError('Release coverage does not match registered matrix')
    eligible_ids = [t['id'] for t in p['tasks'] if t['score_eligible']]
    matched = [task for task in eligible_ids if all(a['status'] == 'finished' and a['replay_verified'] is True
               and type(a['completed']) is bool for a in attempts if a['task'] == task)]
    ready = bool(eligible_ids) and len(matched) == len(eligible_ids)
    models = []
    for model in p['models']:
        rows = [a for a in attempts if a['model'] == model['model']]
        finished = [a for a in rows if a['status'] == 'finished' and a['replay_verified'] is True]
        score_rows = [a for a in finished if a['task'] in eligible_ids]
        models.append({**model, 'finished': len(finished), 'planned': len(rows),
                       'wins': sum(a['completed'] is True for a in finished),
                       'tokens': sum(a['tokens'] or 0 for a in rows),
                       'score': 100*sum(a['completed'] is True for a in score_rows)/len(score_rows) if ready else None})
    result = {'id': p['id'], 'status': public_text(summary['status'], 100),
              'protocol_sha256': p['source_protocol_sha256'], 'planned': len(attempts),
              'finished': sum(a['status'] == 'finished' and a['replay_verified'] is True for a in attempts),
              'pending': sum(a['status'] == 'pending' for a in attempts),
              'running': sum(a['status'] == 'running' for a in attempts),
              'errors': sum(a['status'] == 'error' for a in attempts),
              'tokens': sum(a['tokens'] or 0 for a in attempts), 'total_token_budget': p['total_token_budget'],
              'matched_task_ids': matched, 'eligible_task_ids': eligible_ids,
              'headline_score_ready': ready, 'models': models, 'attempts': attempts}
    return p, result


def release_section(protocol, summary):
    e = html.escape
    def count(value):
        return f'{value:,}'
    status = summary['status']
    status_label = ('Paused at the shared token ceiling' if 'budget' in status
                    else 'Paused for infrastructure review' if 'infrastructure' in status
                    else 'Registered, collection pending' if status == 'ready' else status.capitalize())
    text = '<section id="controlled-evaluation"><h2>Controlled release evaluation</h2><p><strong>'+e(status_label)+'</strong></p>'
    text += '<p>'+count(summary['finished'])+' / '+count(summary['planned'])+' verified attempts complete · '+count(summary['pending'])+' pending · '+count(summary['running'])+' running · '+count(summary['errors'])+' errors.</p>'
    text += '<p>'+count(summary['tokens'])+' recorded tokens / '+count(summary['total_token_budget'])+' shared execution ceiling. The full registered matrix has '+str(len(protocol['models']))+' models × '+str(len(protocol['tasks']))+' benchmarks × '+str(protocol['variants'])+' starts.</p>'
    text += '<p class="muted small">The registered per-attempt ceilings total '+count(protocol['maximum_planned_tokens'])+' tokens. Registration is not a commitment to spend that amount. Only a staged subset fits the shared ceiling. Pending or budget-paused attempts are not failures. One in-flight response can exceed a boundary, as specified in the protocol.</p>'
    text += '<p class="small">Matched coverage: '+str(len(summary['matched_task_ids']))+' / '+str(len(summary['eligible_task_ids']))+' score-eligible benchmarks. '+('The complete registered comparison is ready.' if summary['headline_score_ready'] else 'No controlled headline score or rank is published until every eligible benchmark has all registered models and starts completed with verified replays.')+'</p>'
    text += '<div class="cost-scroll"><table class="cost-table"><thead><tr><th>Exact model</th><th>Provider</th><th>Verified coverage</th><th>Observed passes</th><th>Controlled score</th></tr></thead><tbody>'
    for model in summary['models']:
        score = f"{model['score']:.1f}%" if model['score'] is not None else 'Pending'
        text += '<tr><td>'+e(model['model'])+'</td><td>'+e(model['provider'])+'</td><td>'+str(model['finished'])+' / '+str(model['planned'])+'</td><td>'+str(model['wins'])+' / '+str(model['finished'])+'</td><td>'+score+'</td></tr>'
    text += '</tbody></table></div><p class="small muted">Observed passes describe finished attempts only. Models may currently have different task coverage. These counts are not a ranking.</p><p class="small"><a href="release-protocol.json">Frozen protocol</a> · <a href="release-summary.json">Controlled results JSON</a></p></section>'
    return text


def export_public(feed_path, config_path, output, report=None, release_root=None):
    """Publish only a complete audited snapshot, never a partial export."""
    destination = Path(output)
    if destination.exists():
        raise ValueError('Choose a new public export directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.pokebench-export-', dir=destination.parent) as temp:
        stage = Path(temp)/'site'
        result = _export_public(feed_path, config_path, stage, report, release_root)
        if destination.exists():
            raise ValueError('Public export destination appeared during generation')
        stage.rename(destination)
    return result


def _export_public(feed_path, config_path, output, report=None, release_root=None):
    """Create a new publication directory. Existing exports are immutable."""
    feed_path, config_path, output = map(Path, (feed_path, config_path, output))
    if output.exists():
        raise ValueError('Choose a new public export directory')
    feed = read(feed_path)
    combined = next(cohort for cohort in feed['cohorts'] if cohort.get('analysis'))
    task_ids = {task['id'] for task in combined['tasks']}
    absent = task_ids - {attempt['task'] for attempt in combined['attempts']}
    chosen = [combined]
    for cohort in feed['cohorts']:
        if cohort is combined or cohort.get('analysis'):
            continue
        selected = absent & {a['task'] for a in cohort['attempts'] if a['status'] == 'finished'}
        if selected:
            chosen.append({**cohort, 'tasks': [t for t in cohort['tasks'] if t['id'] in selected],
                           'attempts': [a for a in cohort['attempts'] if a['task'] in selected]})
            absent -= selected
    config = {entry['id']: entry for entry in read(config_path)}
    output.mkdir(parents=True)
    (output/'replays').mkdir()
    (output/'benchmarks').mkdir()
    public = {'updated_at': public_text(feed['updated_at'], 100), 'release_status': 'development', 'cohorts': []}
    replay_count = 0
    all_rows = []
    for cohort in chosen:
        c = {'id': identifier(cohort['id']), 'label': public_text(cohort['label']),
             'tasks': [clean_task(t) for t in cohort['tasks']], 'attempts': [],
             'models': [{'model': identifier(m['model'])} for m in cohort['models']],
             'configuration': {'selection_policy': 'Development results collected under multiple harness versions. Not a frozen release comparison.',
                               'curation_policy': 'Five trivial checkpoints are archived. Experimental tasks remain outside the score.'},
             'downloads': {'json': 'results.json', 'csv': 'results.csv'}}
        if cohort.get('analysis'):
            c['analysis'] = identifier(cohort['analysis'])
        for attempt in cohort['attempts']:
            a = {key: number(attempt[key]) for key in ATTEMPT_FIELDS if key in attempt}
            for key in ('id', 'task', 'model', 'status', 'benchmark', 'stop_reason', 'cost_rate_card'):
                if attempt.get(key) is not None:
                    a[key] = identifier(attempt[key])
            a['cost_note'] = public_text(attempt.get('cost_note', 'Unavailable'))
            source_id = attempt.get('source_cohort', cohort['id'])
            run_id = attempt.get('source_run_id', attempt['id'])
            if Path(run_id).name != run_id:
                raise ValueError('Invalid source run name')
            entry = config[source_id]
            batch = Path(entry['batch'])
            if not batch.is_absolute():
                batch = config_path.resolve().parent.parent/batch
            manifest_path = batch/run_id/'manifest.json'
            a['metadata'] = safe_metadata(read(manifest_path)) if manifest_path.is_file() else {}
            if a['metadata'].get('model', a['model']) != a['model']:
                raise ValueError('Attempt model does not match its source manifest')
            if manifest_path.is_file():
                a['metadata']['manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            a['source_cohort'] = identifier(source_id)
            a['source_run_id'] = identifier(run_id)
            a['replay'] = None
            if attempt.get('replay') and attempt.get('replay_verified') and attempt['status'] == 'finished':
                filename = attempt['replay']
                if Path(filename).name != filename:
                    raise ValueError('Replay path must be a local basename')
                path = feed_path.parent/filename
                if path.is_symlink():
                    raise ValueError('Replay symlinks are not publishable')
                payload = replay_payload(path, attempt)
                stem = hashlib.sha256((source_id+'/'+run_id).encode()).hexdigest()[:20]
                a['replay'] = 'replays/'+stem+'.html'
                (output/a['replay']).write_text(REPLAY.replace('__DATA__', json_text(payload)))
                replay_count += 1
            c['attempts'].append(a)
            all_rows.append(a)
        public['cohorts'].append(c)
    write_json(output/'results.json', public)
    with (output/'results.csv').open('w') as stream:
        fields = ['task', 'model', 'status', 'completed', 'repeat', 'variant', 'tokens', 'decisions', 'wall_seconds', 'benchmark', 'replay_verified', 'replay']
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)
    page = HTML.replace('__FEED__', '"results.json"')
    page = page.replace('Real game checkpoints. The same tools, saves and budgets for every model. Compare overall ability, then explore the individual tests.',
                        'Development preview. Real game checkpoints, recorded outcomes and verified replays. Historical tool versions differ. A frozen release evaluation is being prepared.')
    page = page.replace('<a href="#methodology">Methodology</a>', '<a href="methodology.html">Methodology</a><a href="technical-report.html">Report</a>')
    page = page.replace('<div class="model-id">Codex · bounded context</div>', '<div class="model-id">${esc([...new Set(m.rows.map(a=>a.metadata?.provider || "unrecorded"))].join(" / "))} · bounded context</div>')
    page = page.replace('${a.stop_reason ? `<p', '${a.metadata ? `<p class="small muted">${esc(a.model)} · ${esc(a.metadata.harness || "Harness unrecorded")} · ${esc(a.metadata.created_at || "Date unrecorded")}</p>` : ""}${a.stop_reason ? `<p')
    page = page.replace('<h3>Model attempts</h3>', '<p><a href="benchmarks/${esc(t.id)}.html">Benchmark permalink and exact provenance</a></p><h3>Model attempts</h3>')
    page = page.replace('Earlier runs and pilot results are available inside each benchmark.', 'Pilot results are available inside each benchmark. Full historical archives remain local.')
    page = page.replace('Results refresh in place. Search and open details stay where you left them.', 'Immutable development snapshot. <a href="manifest.json">Download provenance manifest</a>.')
    page = page.replace('setInterval(refresh,15000)', '')
    release_info = None
    if release_root:
        release_protocol, release_info = release_snapshot(release_root)
        write_json(output/'release-protocol.json', release_protocol)
        write_json(output/'release-summary.json', release_info)
        page = page.replace('<h1>How well can AI agents play Pokemon?</h1>', '<h1>PokeBench</h1>'+release_section(release_protocol, release_info)+'<h2>Development leaderboard</h2>')
        page = page.replace("$('board-title').textContent = state.category+' leaderboard'", "$('board-title').textContent = state.category+' development leaderboard'")
    (output/'index.html').write_text(page)
    for task in public['cohorts'][0]['tasks']:
        rows = [a for a in all_rows if a['task'] == task['id']]
        body = '<h1>'+html.escape(task['name'])+'</h1><p>'+html.escape(task['description'])+'</p><p>Development evidence. Difficulty and experimental status are provisional.</p><p>Budget: '+str(task['tokens'])+' tokens per attempt. Starting save SHA-256: <code>'+task['state_hash']+'</code>.</p>'
        if task.get('validation'):
            body += '<p>'+html.escape(task['validation']['status']+': '+task['validation']['message'])+'</p>'
        body += '<table><thead><tr><th>Exact model</th><th>Result</th><th>Tokens</th><th>Replay</th></tr></thead><tbody>'
        for a in rows:
            result = ('Passed' if a['completed'] else 'Failed') if a['status'] == 'finished' else a['status']
            link = '<a href="../'+a['replay']+'">Watch replay</a>' if a['replay'] else 'Unavailable'
            body += '<tr><td>'+html.escape(a['model'])+'</td><td>'+html.escape(result)+'</td><td>'+str(a.get('tokens', 0))+'</td><td>'+link+'</td></tr>'
        body += '</tbody></table><h2>Attempt provenance</h2><pre>'+html.escape(json.dumps([{'model': a['model'], **a['metadata']} for a in rows], indent=2))+'</pre>'
        task_page = document(task['name'], body).replace('href="index.html"', 'href="../index.html"')
        (output/'benchmarks'/(task['id']+'.html')).write_text(task_page)
    (output/'methodology.html').write_text(document('Methodology', METHODOLOGY))
    if report:
        report = Path(report)
        if report.is_symlink() or report.read_bytes()[:5] != b'%PDF-':
            raise ValueError('Report must be a reviewed PDF')
        (output/'technical-report.pdf').write_bytes(report.read_bytes())
        report_body = '<h1>Technical report</h1><p>Development report. Historical results are not a frozen release comparison.</p><a href="technical-report.pdf">Read the PDF</a>'
    else:
        report_body = '<h1>Technical report</h1><p>The release report is being prepared. Current evidence is documented in the methodology and downloadable results.</p><a href="methodology.html">Read the methodology</a>'
    (output/'technical-report.html').write_text(document('Technical report', report_body))
    (output/'.nojekyll').write_text('')
    files = []
    for path in sorted(output.rglob('*')):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if path.suffix != '.pdf' and PRIVATE.search(raw.decode()):
            raise ValueError('Private data found in public export')
        files.append({'path': str(path.relative_to(output)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    manifest = {'format': 1, 'project': 'PokeBench', 'status': 'development',
                'exported_at': datetime.now(timezone.utc).isoformat(), 'results_updated_at': public['updated_at'],
                'tasks': len(task_ids), 'attempts': len(all_rows), 'replays': replay_count,
                'source_feed_sha256': hashlib.sha256(feed_path.read_bytes()).hexdigest(),
                'publication_policy': 'Allowlisted numeric results and identifiers. Screenshots reencoded without metadata. Replays contain controller actions only. No raw notes, prompts, provider logs, filesystem paths, ROMs, emulator states or game catalogs.',
                'files': files}
    if release_info:
        manifest['controlled_release'] = {key: release_info[key] for key in ('id', 'status', 'protocol_sha256', 'planned', 'finished', 'tokens', 'total_token_budget', 'headline_score_ready')}
    write_json(output/'manifest.json', manifest)
    return manifest


METHODOLOGY = '''<h1>How PokeBench works</h1>
<p><strong>Development preview, not a frozen release leaderboard.</strong> Historical runs used multiple harness versions. Results characterize a model together with its recorded agent framework. They do not isolate raw model ability.</p>
<h2>Tasks and agent interface</h2><p>Tasks begin from recorded Pokemon Red checkpoints. The assisted gameplay track exposes player information and menu shortcuts. The model chooses the strategy and actions. Exact model, harness, prompt checksum, source checksum, starting state checksum and collection time are retained in each attempt's public metadata.</p>
<h2>Scoring</h2><p>Each scored task has equal weight. Repeated starts are averaged within a task. The exploratory leaderboard uses only tasks with matching completed coverage and verified replays for every compared model. Experimental tasks are visible but excluded. Infrastructure errors are not scored as gameplay losses. Original failed gameplay attempts count.</p>
<h2>Uncertainty and luck</h2><p>One successful attempt does not establish reliability. Fixed variants give every model the same starts, but action timing can change later randomness. Calibration and repeated independent trials are needed to distinguish tactical skill from luck. Do not interpret small differences here as statistically established rankings.</p>
<h2>Budgets and cost</h2><p>Token ceilings include accumulated model usage under the recorded runner. Cost figures are estimated Codex credits, not invoices, API dollar prices or subscription quota. Missing usage is shown as unavailable and excluded from matched cost comparisons.</p>
<h2>Replay and data publication</h2><p>Public replays show recorded screenshots at decision boundaries and executed controller actions. They intentionally exclude private provider transcripts and model notes. They are accelerated slideshows, not continuous video. Replay verification refers to the recorded source attempt. The export manifest separately hashes every published file.</p>
<h2>Reproduction</h2><p>Use the repository's task manifests and pinned environment with your own legally obtained ROM. This website does not distribute ROMs, emulator states or generated game catalogs. The release evaluation must use one frozen protocol and shared starting variants.</p>
<p><a href="results.json">Download results JSON</a> · <a href="results.csv">Download attempts CSV</a> · <a href="manifest.json">Download publication manifest</a></p>'''


REPLAY = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PokeBench replay</title>
<style>body {margin:0} body {background:#111b17} body {color:#edf3ef} body {font:16px/1.5 system-ui} main {max-width:1000px} main {margin:auto} main {padding:20px} a {color:#91d8b4} .screens {display:flex} .screens {gap:20px} .screens img {width:100%} .screens img {image-rendering:pixelated} .screens figure {flex:1} .screens figure {margin:0} .controls {position:sticky} .controls {top:0} .controls {background:#111b17} .controls {padding:16px 0} button,select {padding:12px} button,select {font:inherit} #seek {width:100%} pre {white-space:pre-wrap} #actions {height:130px} #actions {overflow:auto}</style>
<main><a href="../index.html">PokeBench</a><h1 id="title"></h1><p>Recorded controller replay. No private notes or provider transcripts. Before and after each decision.</p><div class="controls"><button id="prev">Previous</button> <button id="play">Play</button> <button id="next">Next</button> <label>Speed <select id="speed"><option value="500">2 decisions / sec</option><option value="125" selected>8 decisions / sec</option><option value="50">20 decisions / sec</option></select></label><input id="seek" type="range" min="0" value="0" aria-label="Decision"><div id="position"></div></div><div class="screens"><figure><figcaption>Before</figcaption><img id="before" alt="Before action"></figure><figure><figcaption>After</figcaption><img id="after" alt="After action"></figure></div><pre id="actions"></pre></main>
<script id="data" type="application/json">__DATA__</script><script>
const data = JSON.parse(document.getElementById('data').textContent)
const $ = id => document.getElementById(id)
let index = 0
let timer = null
$('title').textContent = data.model+' · '+(data.completed ? 'Passed' : 'Failed')
$('seek').max = data.steps.length-1
function render() {
 const step = data.steps[index]
 $('before').src = data.images[step.before]
 $('after').src = data.images[step.after]
 $('position').textContent = 'Decision '+step.decision+' · '+(index+1)+' / '+data.steps.length+' · '+step.cumulative_tokens.toLocaleString()+' cumulative tokens'
 $('actions').textContent = step.actions.map(a=>(a.button || 'wait')+' · hold '+a.hold_frames+' frames · release '+a.release_frames+' frames').join('\\n') || 'No controller input'
 $('seek').value = index
 $('prev').disabled = index===0
 $('next').disabled = index===data.steps.length-1
}
function stop() {clearInterval(timer)
 timer=null
 $('play').textContent='Play'
}
function play() {stop()
 if(index===data.steps.length-1) index=0
 $('play').textContent='Pause'
 timer=setInterval(()=>{if(index<data.steps.length-1) {index+=1
 render()
 } else stop()},Number($('speed').value))
}
$('prev').onclick=()=>{index=Math.max(0,index-1)
 render()}
$('next').onclick=()=>{index=Math.min(data.steps.length-1,index+1)
 render()}
$('play').onclick=()=>timer ? stop() : play()
$('speed').onchange=()=>{if(timer) play()}
$('seek').oninput=()=>{index=Number($('seek').value)
 render()}
document.onkeydown=e=>{if(e.key==='ArrowRight') $('next').click()
 if(e.key==='ArrowLeft') $('prev').click()}
render()
</script></html>'''
