"""Campaign pages show measured progress without inventing missing metrics."""
from html.parser import HTMLParser
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from pokeagent_bench.campaign_report import export_campaign_report, render_campaign_report, enrich_current_profile, _power_profiles
from pokeagent_bench.campaign_runtime import CampaignTracker
from test_campaign_runtime import state, mon, confirm


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input':
            self.inputs.append(attrs)
        if tag == 'a':
            self.links.append(attrs.get('href'))


def report():
    facts = state()
    tracker = CampaignTracker(facts)
    facts['story']['starter'] = True
    facts['party'] = [mon()]
    facts['party'][0]['nick'] = 'SQUIRTLE'
    confirm(tracker, facts)
    return tracker.report()


def test_page_has_all_fifty_read_only_milestones_and_correct_earned_count():
    data = report()
    page = render_campaign_report(data)
    parsed = Elements()
    parsed.feed(page)
    assert len(parsed.inputs) == 50
    assert all('disabled' in item for item in parsed.inputs)
    assert sum('checked' in item for item in parsed.inputs) == 1
    assert '5 / 1,000' in page
    assert '1 / 50' in page
    assert 'SQUIRTLE' in page
    assert '#overview' in parsed.links
    assert '#team' in parsed.links
    assert 'Not tracked' in page
    assert 'Purchases, sales' in page


def test_tokens_do_not_add_cached_input_twice_and_html_is_escaped():
    data = report()
    data['milestones'][0]['label'] = '<script>alert(1)</script>'
    page = render_campaign_report(data, manifest={'agent': {'model': '<b>model</b>'}},
        result={'state': 'running', 'wall_seconds': 123,
                'usage': {'available': True, 'input_tokens': 1000, 'output_tokens': 25, 'cached_input_tokens': 900}},
        run_name='<img src=x onerror=alert(1)>')
    assert '1,025' in page
    assert '1,925' not in page
    assert '<script>' not in page
    assert '&lt;script&gt;' in page
    assert '&lt;b&gt;model&lt;/b&gt;' in page
    assert '<img src=x' not in page
    assert 'In progress' in page
    assert '2m 03s' in page


def test_export_reads_actual_campaign_file_and_does_not_modify_results(tmp_path):
    run = tmp_path / 'sample-campaign'
    run.mkdir()
    data = report()
    original = json.dumps(data)
    (run / 'campaign.json').write_text(original)
    (run / 'result.json').write_text(json.dumps({'state': 'finished', 'wall_seconds': 30}))
    output = export_campaign_report(run)
    assert output == run / 'campaign.html'
    assert 'sample-campaign' in output.read_text()
    assert 'Partial campaign' in output.read_text()
    assert (run / 'campaign.json').read_text() == original


def test_baseline_facts_are_excluded_and_no_fake_battle_power_is_displayed():
    facts = state()
    facts['story']['starter'] = True
    facts['party'] = [mon()]
    data = CampaignTracker(facts).report()
    page = render_campaign_report(data)
    parsed = Elements()
    parsed.feed(page)
    assert not any('checked' in item for item in parsed.inputs)
    assert 'Present at the starting checkpoint, excluded from score' in page
    assert 'unscored full-health moveset heuristic' in page
    assert '0 / 1,000' in page


def game_data(tmp_path):
    from pokeagent_bench.core import digest
    bundle = 'a' * 64
    root = tmp_path / 'bundles' / bundle
    root.mkdir(parents=True)
    (tmp_path / 'current.json').write_text(json.dumps({'bundle': bundle}))
    tables = {'maps': {}, 'species': {'177': 'SQUIRTLE'}, 'moves': {}, 'items': {}}
    strategy = {'species': {'177': {'stats': [44, 48, 65, 43, 50], 'types': [21, 21]}},
                'moves': {'33': {'name': 'TACKLE', 'type': 0, 'power': 35, 'accuracy': 95, 'pp': 35, 'effect': 'NO_ADDITIONAL_EFFECT'},
                          '39': {'name': 'TAIL_WHIP', 'type': 0, 'power': 0, 'accuracy': 100, 'pp': 30, 'effect': 'DEFENSE_DOWN1_EFFECT'}},
                'matchups': [[21, 21, 0.5]], 'world': {}}
    files = {}
    for name, data in [('tables', tables), ('strategy', strategy)]:
        raw = json.dumps(data).encode()
        (root / (name + '.json')).write_bytes(raw)
        files[name + '.json'] = digest(raw)
    (root / 'manifest.json').write_text(json.dumps({'schema': 1, 'source_revision': 'a1a22aaf84d1675bcdbaeb194592379d586d838e', 'files': files}))
    return tmp_path


def test_real_core_power_uses_individual_data_without_altering_points(tmp_path):
    data = report()
    score = data['score']
    _power_profiles(data, game_data(tmp_path))
    profile = data['current_profile']
    assert profile['battle_power'] > 0
    assert profile['battle_power'] == profile['party'][0]['battle_power']
    assert data['score'] == score
    original = profile['battle_power']
    profile['party'][0].update(hp=0, pp=[0, 0, 0, 0], status=8)
    _power_profiles(data, tmp_path)
    assert profile['battle_power'] == original
    profile['party'][0].pop('dvs')
    _power_profiles(data, tmp_path)
    assert profile['battle_power'] is None
    assert profile['party'][0]['battle_power'] is None


def test_power_rejects_unverified_game_tables(tmp_path):
    root = game_data(tmp_path)
    strategy = next(root.glob('bundles/*/strategy.json'))
    strategy.write_text('{}')
    with pytest.raises(ValueError, match='checksum'):
        _power_profiles(report(), root)


def test_storage_reports_all_boxes_without_inventing_historical_counts(monkeypatch):
    boxes = [{'box': n + 1, 'available': True, 'pokemon': []} for n in range(12)]
    boxes[0]['pokemon'] = [{'species': 177}, {'species': 177}]
    boxes[11]['pokemon'] = [{'species': 84}]
    monkeypatch.setattr('pokecore.gen1_ui.read_storage', lambda memory: {'available': True, 'boxes': boxes})
    original = report()
    enriched = enrich_current_profile(SimpleNamespace(memory=object()), original)
    assert enriched['current_profile']['stored_pokemon_count'] == 3
    assert enriched['current_profile']['all_storage_species'] == [84, 177]
    assert enriched['current_profile']['distinct_stored_species'] == 2
    assert 'stored_pokemon_count' not in original['current_profile']
    assert 'stored_pokemon_count' not in enriched['profiles'][0]['profile']
    boxes[11]['available'] = False
    incomplete = enrich_current_profile(SimpleNamespace(memory=object()), original)
    assert incomplete['current_profile']['stored_pokemon_count'] is None
    assert incomplete['current_profile']['all_storage_species'] is None


@pytest.mark.skipif(not os.environ.get('POKEBENCH_ROM') or not os.environ.get('POKEBENCH_CAMPAIGN_STATE'),
                    reason='Optional local ROM and checkpoint are not distributed')
def test_native_storage_profile_is_read_only():
    from pokeagent_bench.game import RedEngine
    from pokeagent_bench.campaign_runtime import read_campaign_evidence
    engine = RedEngine(Path(os.environ['POKEBENCH_ROM']), Path(os.environ['POKEBENCH_CAMPAIGN_STATE']).read_bytes())
    try:
        initial = engine.save()
        data = CampaignTracker(read_campaign_evidence(engine)).report()
        data = enrich_current_profile(engine, data)
        assert engine.save() == initial
        from pokecore.gen1_ui import read_storage
        boxes = read_storage(engine.memory)['boxes']
        complete = len(boxes) == 12 and all(box['available'] for box in boxes)
        assert data['current_profile']['stored_pokemon_count'] == (0 if complete else None)
        assert data['current_profile']['all_storage_species'] == ([] if complete else None)
        assert data['score'] == 0
    finally:
        engine.close()
