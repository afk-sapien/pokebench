"""Portable local campaign results with scored progress and observed run profiles."""
from copy import deepcopy
from html import escape
import json
from pathlib import Path

GROUP_NAMES = {
    'story': 'Story and quests', 'exploration': 'Exploration', 'badges': 'Gym badges',
    'elite': 'Elite Four', 'champion': 'Champion', 'collection': 'Collection and development',
}


def _power_profiles(campaign, game_data):
    """Use Core's descriptive heuristic with the checked private game tables."""
    from pokecore.gen1_battle_power import BattlePower
    from .core import digest
    from .gameplay import load_catalog

    catalog = load_catalog(game_data)
    root = Path(game_data)
    bundle = json.loads((root / 'current.json').read_text())['bundle']
    import re
    if not re.fullmatch(r'[0-9a-f]{64}', bundle):
        raise ValueError('Invalid game data bundle')
    root = root / 'bundles' / bundle
    manifest = json.loads((root / 'manifest.json').read_text())
    raw = (root / 'strategy.json').read_bytes()
    if manifest.get('source_revision') != catalog['revision'] or digest(raw) != manifest['files']['strategy.json']:
        raise ValueError('Game data checksum mismatch')
    strategy = json.loads(raw)
    power = BattlePower({int(key): value for key, value in strategy['species'].items()},
                        {int(key): value for key, value in strategy['moves'].items()},
                        {(row[0], row[1]): row[2] for row in strategy['matchups']})
    profiles = [campaign['current_profile']] + [row['profile'] for row in campaign.get('profiles', [])]
    for profile in profiles:
        values = []
        for mon in profile.get('party', []):
            mon['battle_power'] = power.battle_power(mon)
            values.append(mon['battle_power'])
        profile['battle_power'] = sum(values) if all(value is not None for value in values) else None
        profile['battle_power_status'] = ('Core full-health moveset heuristic, unscored' if profile['battle_power'] is not None
                                          else 'individual data or moves unavailable')
        profile['battle_power_source'] = {'bundle': bundle, 'source_revision': catalog['revision']}
    return catalog['labels']


def enrich_current_profile(engine, report, game_data=None):
    """Sample private storage at persistence without advancing or modifying the game."""
    from pokecore.gen1_ui import read_storage

    report = deepcopy(report)
    profile = report['current_profile']
    storage = read_storage(engine.memory)
    boxes = storage.get('boxes', [])
    complete = bool(storage.get('available') and len(boxes) == 12 and all(box.get('available') for box in boxes))
    mons = [mon for box in boxes for mon in box.get('pokemon', [])]
    profile['all_storage_species'] = sorted({mon['species'] for mon in mons}) if complete else None
    profile['stored_pokemon_count'] = len(mons) if complete else None
    profile['distinct_stored_species'] = len(profile['all_storage_species']) if complete else None
    profile['all_storage_status'] = 'available' if complete else 'some storage boxes unavailable'
    if game_data is not None:
        _power_profiles(report, game_data)
    return report


def _text(value):
    return escape(str(value))


def _number(value):
    return 'Not tracked' if value is None else f'{value:,}' if isinstance(value, (int, float)) else _text(value)


def _time(value):
    if value is None:
        return 'Not tracked'
    seconds = int(value)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours:d}h {minutes:02d}m' if hours else f'{minutes:d}m {seconds:02d}s'


def _label(labels, kind, value):
    found = labels.get(kind, {}).get(str(value), f'#{value}')
    return found.get('name', f'#{value}') if isinstance(found, dict) else str(found)


def _table(headings, rows):
    return ('<div class="table-scroll"><table><thead><tr>' + ''.join('<th>' + _text(h) + '</th>' for h in headings)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + cell + '</td>' for cell in row) + '</tr>' for row in rows)
            + '</tbody></table></div>')


def _party(profile, labels):
    rows = []
    for index, mon in enumerate(profile.get('party', []), 1):
        name = mon.get('nick') or _label(labels, 'species', mon['species'])
        moves = ', '.join(f'{_label(labels, "moves", move)} ({mon.get("pp", [0] * 4)[slot]} PP)'
                          for slot, move in enumerate(mon.get('moves', [])) if move)
        stats = ' / '.join(str(mon.get(key, '?')) for key in ('attack', 'defense', 'speed', 'special'))
        rows.append([str(index), '<strong>' + _text(name) + '</strong>', _number(mon.get('level')),
                     f'{mon.get("hp", "?")}/{mon.get("max_hp", "?")}', _text(mon.get('status', 0)),
                     _text(moves), _text(stats), _number(mon.get('battle_power'))])
    if not rows:
        return '<p class="muted">No Pokemon in the party at this checkpoint.</p>'
    return _table(['Slot', 'Pokemon', 'Level', 'HP', 'Status byte', 'Moves and PP', 'Atk / Def / Spe / Spc', 'Power heuristic'], rows)


def _profile(profile, labels):
    metrics = [('Total party level', profile.get('total_level')), ('Median level', profile.get('median_level')),
               ('Usable Pokemon', profile.get('nonfainted')), ('Distinct party species', profile.get('distinct_party_species')),
               ('Owned species', profile.get('owned_species')), ('Money', profile.get('money')),
               ('Party power heuristic', profile.get('battle_power')), ('Stored Pokemon', profile.get('stored_pokemon_count')),
               ('Distinct stored species', profile.get('distinct_stored_species'))]
    summary = '<div class="small-metrics">' + ''.join('<div><span>' + _text(label) + '</span><strong>' + _number(value)
                                                    + '</strong></div>' for label, value in metrics) + '</div>'
    bag = ', '.join(f'{_label(labels, "items", item)} ×{quantity}' for item, quantity in profile.get('bag', [])) or 'Empty'
    return summary + _party(profile, labels) + '<p><strong>Bag:</strong> ' + _text(bag) + '</p>'


def render_campaign_report(campaign, *, result=None, manifest=None, labels=None, run_name='Campaign run'):
    """Render recorded data only. Missing observations stay explicitly untracked."""
    result, manifest, labels = result or {}, manifest or {}, labels or {}
    model = manifest.get('agent', {}).get('model') or 'Unspecified model'
    status = 'Champion' if campaign.get('champion') else ('In progress' if result.get('state') == 'running' else 'Partial campaign')
    usage = result.get('usage') or {}
    total_tokens = (usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
                    if usage.get('available') and usage.get('input_tokens') is not None and usage.get('output_tokens') is not None else None)
    metrics = [('Progress score', f'{campaign["score"]:,} / {campaign["maximum_points"]:,}'),
               ('Milestones', f'{campaign["completed_milestones"]} / {campaign["total_milestones"]}'),
               ('Reported tokens', _number(total_tokens)), ('Elapsed', _time(result.get('wall_seconds')))]
    metric_html = ''.join('<article class="metric"><span>' + _text(label) + '</span><strong>' + value + '</strong></article>'
                          for label, value in metrics)
    group_cards = []
    milestone_sections = []
    for group, totals in campaign.get('groups', {}).items():
        name = GROUP_NAMES.get(group, group.replace('-', ' ').title())
        group_cards.append('<article class="group-card"><h3>' + _text(name) + '</h3><p><strong>'
                           + str(totals['points']) + '</strong> / ' + str(totals['maximum_points']) + ' points</p>'
                           + f'<progress value="{totals["points"]}" max="{totals["maximum_points"]}" aria-label="{_text(name)}"></progress>'
                           + f'<p class="muted">{totals["completed"]} of {totals["total"]} milestones</p></article>')
        entries = []
        for row in campaign.get('milestones', []):
            if row['group'] != group:
                continue
            reached = row['status'] == 'achieved'
            award = row.get('achievement') or {}
            detail = ('Frame ' + _number(award.get('frame')) + ' · Decision ' + _number(award.get('decision'))
                      + ' · ' + _number(award.get('tokens')) + ' tokens') if reached else (
                          'Present at the starting checkpoint, excluded from score' if row['status'] == 'present-at-start' else 'Not reached')
            entries.append('<li class="milestone" data-state="' + _text(row['status']) + '"><input type="checkbox" disabled '
                           + ('checked ' if reached else '') + 'aria-label="' + _text(row['label']) + '">'
                           + '<div><strong>' + _text(row['label']) + '</strong><small>' + detail + '</small></div>'
                           + '<span class="points">' + str(row['points']) + ' pts</span></li>')
        milestone_sections.append('<section class="milestone-group"><h3>' + _text(name) + '</h3><ul>' + ''.join(entries) + '</ul></section>')
    events = []
    for event in campaign.get('events', []):
        kind = event.get('kind', 'event')
        label = event.get('label') or (
            'Caught ' + _label(labels, 'species', event['species']) if kind == 'capture' else
            'Evolved ' + _label(labels, 'species', event['from_species']) + ' into ' + _label(labels, 'species', event['species']) if kind == 'evolution' else
            'Blackout' if kind == 'blackout' else event.get('id', kind))
        events.append([_number(event.get('frame')), _time(event.get('wall_seconds')), _text(label),
                       _number(event.get('decision')), _number(event.get('tokens')),
                       str(event.get('points', 0))])
    timeline = _table(['Frame', 'Time', 'Event', 'Decision', 'Tokens', 'Points'], events) if events else '<p class="muted">No campaign events recorded yet.</p>'
    snapshots = []
    names = {row['id']: row['label'] for row in campaign.get('milestones', [])}
    for record in campaign.get('profiles', []):
        label = names.get(record['id'], 'Starting party' if record['id'] == 'start' else record['id'])
        snapshots.append('<details><summary>' + _text(label) + ' <span class="muted">· Frame '
                         + _number(record.get('frame')) + '</span></summary>' + _profile(record['profile'], labels) + '</details>')
    counters = campaign.get('counters', {})
    observed = [('Successful captures', counters.get('captures')), ('Distinct wild species', counters.get('distinct_wild_species')),
                ('Evolutions', counters.get('evolutions')), ('Evolution families', counters.get('distinct_evolved_families')),
                ('Observed faints', counters.get('observed_faints')), ('Blackouts', counters.get('blackouts'))]
    counter_html = ''.join('<div><span>' + label + '</span><strong>' + _number(value) + '</strong></div>' for label, value in observed)
    footer = ('<p class="muted">Purchases, sales, item-use counts and generic battle outcome counts are not tracked yet. '
              'Core battle power is an unscored full-health moveset heuristic. It does not account for current HP, status or remaining PP. '
              'It is not a win probability. Missing values are not tracked or could not be calculated.</p>')
    return (PAGE.replace('__TITLE__', _text(run_name)).replace('__MODEL__', _text(model)).replace('__STATUS__', status)
            .replace('__VERSION__', _text(campaign.get('version', 'Unknown protocol')))
            .replace('__METRICS__', metric_html).replace('__GROUPS__', ''.join(group_cards))
            .replace('__MILESTONES__', ''.join(milestone_sections)).replace('__TIMELINE__', timeline)
            .replace('__CURRENT__', _profile(campaign.get('current_profile', {}), labels))
            .replace('__SNAPSHOTS__', ''.join(snapshots)).replace('__COUNTERS__', counter_html)
            .replace('__FOOTER__', footer))


def export_campaign_report(run, output=None, *, labels=None, game_data=None):
    run = Path(run)
    campaign = json.loads((run / 'campaign.json').read_text())
    if game_data is not None:
        checked_labels = _power_profiles(campaign, game_data)
        labels = labels or checked_labels
    result = json.loads((run / 'result.json').read_text()) if (run / 'result.json').exists() else {}
    manifest = json.loads((run / 'manifest.json').read_text()) if (run / 'manifest.json').exists() else {}
    output = Path(output) if output is not None else run / 'campaign.html'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_campaign_report(campaign, result=result, manifest=manifest, labels=labels, run_name=run.name))
    return output


PAGE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PokeBench campaign · __TITLE__</title><style>
:root{font-family:Inter,system-ui,sans-serif}
:root{color:#182e2c}
:root{background:#f4f5ef}
*{box-sizing:border-box}
body{margin:0}
main{max-width:1240px}
main{margin:auto}
main{padding:36px 28px 80px}
a{color:#136e60}
header{padding-bottom:24px}
h1{font-size:clamp(28px,4vw,44px)}
h1{margin:12px 0}
h2{font-size:26px}
h2{margin:38px 0 18px}
h3{margin:0 0 12px}
p{line-height:1.6}
.eyebrow{font-size:12px}
.eyebrow{letter-spacing:.14em}
.eyebrow{font-weight:700}
.muted{color:#61716e}
.status{display:inline-block}
.status{border:1px solid #a7d4c4}
.status{border-radius:30px}
.status{padding:7px 12px}
.status{background:#e2f1e8}
nav{display:flex}
nav{flex-wrap:wrap}
nav{gap:24px}
nav{padding:14px 0}
nav{border-bottom:1px solid #d3ddd5}
.metrics{display:grid}
.metrics{grid-template-columns:repeat(4,1fr)}
.metrics{gap:16px}
.metric{background:white}
.metric{padding:22px}
.metric{border:1px solid #d3ddd5}
.metric{border-radius:12px}
.metric span,.small-metrics span{display:block}
.metric span,.small-metrics span{color:#61716e}
.metric strong{display:block}
.metric strong{font-size:30px}
.metric strong{margin-top:8px}
.groups{display:grid}
.groups{grid-template-columns:repeat(3,1fr)}
.groups{gap:16px}
.group-card{border:1px solid #d3ddd5}
.group-card{padding:20px}
.group-card{border-radius:12px}
progress{width:100%}
progress{accent-color:#17715d}
.milestone-grid{display:grid}
.milestone-grid{grid-template-columns:1fr 1fr}
.milestone-grid{gap:20px}
.milestone-group{background:white}
.milestone-group{padding:22px}
.milestone-group{border-radius:12px}
.milestone-group{border:1px solid #d3ddd5}
ul{list-style:none}
ul{padding:0}
ul{margin:0}
.milestone{display:flex}
.milestone{align-items:start}
.milestone{gap:12px}
.milestone{padding:14px 0}
.milestone{border-top:1px solid #e4e9e3}
.milestone input{accent-color:#17715d}
.milestone input{margin-top:4px}
.milestone div{flex:1}
.milestone small{display:block}
.milestone small{color:#687871}
.milestone small{margin-top:5px}
.points{white-space:nowrap}
.points{color:#61716e}
.table-scroll{overflow:auto}
table{width:100%}
table{border-collapse:collapse}
table{background:white}
th,td{text-align:left}
th,td{padding:14px}
th,td{border-bottom:1px solid #e0e6dd}
th{font-size:12px}
th{color:#61716e}
th{white-space:nowrap}
.small-metrics{display:grid}
.small-metrics{grid-template-columns:repeat(3,1fr)}
.small-metrics{gap:18px}
.small-metrics{margin:20px 0}
.small-metrics strong{display:block}
.small-metrics strong{font-size:22px}
.small-metrics strong{margin-top:5px}
details{margin:12px 0}
details{padding:18px}
details{background:white}
details{border:1px solid #d3ddd5}
details{border-radius:10px}
summary{cursor:pointer}
summary{font-weight:600}
@media(max-width:800px){.metrics{grid-template-columns:1fr 1fr}}
@media(max-width:800px){.groups{grid-template-columns:1fr 1fr}}
@media(max-width:800px){.milestone-grid{grid-template-columns:1fr}}
@media(max-width:500px){main{padding:24px 16px}}
@media(max-width:500px){.groups{grid-template-columns:1fr}}
@media(max-width:500px){.small-metrics{grid-template-columns:1fr 1fr}}
@media(max-width:500px){.metric strong{font-size:23px}}
</style></head><body><main>
<header><div class="eyebrow">POKEBENCH / CAMPAIGN RESULTS</div><h1>__TITLE__</h1>
<p>__MODEL__ · <span class="status">__STATUS__</span></p>
<p class="muted">One continuous game. Fifty milestones within the same attempt.</p>
<nav aria-label="Campaign sections"><a href="#overview">Overview</a><a href="#milestones">Milestones</a>
<a href="#timeline">Timeline</a><a href="#team">Team and resources</a></nav></header>
<section id="overview" aria-label="Run overview"><div class="metrics">__METRICS__</div>
<h2>Where the points came from</h2><div class="groups">__GROUPS__</div></section>
<section id="milestones"><h2>Milestone checklist</h2><div class="milestone-grid">__MILESTONES__</div></section>
<section id="timeline"><h2>What happened</h2>__TIMELINE__</section>
<section id="team"><h2>Latest team and resources</h2>__CURRENT__
<h3>Observed activity</h3><div class="small-metrics">__COUNTERS__</div>
<details><summary>Team snapshots at earlier milestones</summary>__SNAPSHOTS__</details>__FOOTER__</section>
<footer><p class="muted">Scoring protocol: __VERSION__. Collection bonuses are capped. Champion completion does not require all 1,000 points.</p></footer>
</main></body></html>'''
