"""Campaign progress must remain evidence based across retries and resume."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from pokeagent_bench.campaign_runtime import (
    V1, VERSION, CampaignTracker, ITEM_MILESTONES, STORY_FLAGS, VISITS, area_checks, milestone_definitions,
    read_campaign_evidence,
)


def mon(species=177, *, trainer=123, dvs=(15, 15, 15, 15, 15), hp=20):
    return {'species': species, 'trainer_id': trainer, 'dvs': dvs, 'hp': hp, 'max_hp': 20,
            'level': 5, 'experience': 125, 'stat_exp': (0, 0, 0, 0, 0),
            'moves': (33, 39, 0, 0), 'pp': (35, 40, 0, 0), 'status': 0,
            'attack': 12, 'defense': 14, 'speed': 10, 'special': 11}


def state():
    return {'valid': True, 'map_id': 37, 'story': {}, 'badges': 0,
            'gym_flags': [False] * 8, 'elite': {}, 'champion': False, 'hall_of_fame': 0,
            'party': [], 'items': [], 'money': 3000, 'owned': [], 'seen': [],
            'battle': 0, 'battle_type': 0, 'enemy_species': 0, 'captured_species': 0,
            'evolution_occurred': False, 'battle_result': 0, 'active_box': 0,
            'box_species': [], 'overworld': True, 'x': 3, 'y': 6,
            'evolution_data': {'families': {'177': 177, '179': 177, '28': 177, '84': 84, '85': 84},
                               'edges': [[177, 179], [179, 28], [84, 85]]}}


def confirm(tracker, facts, frame=1):
    first = tracker.observe(deepcopy(facts), frame, frame / 60)
    return first + tracker.observe(deepcopy(facts), frame + 1, (frame + 1) / 60)


@pytest.mark.parametrize('version, count', [(V1, 50), (VERSION, 75)])
def test_each_protocol_keeps_its_weights_and_native_bindings(version, count):
    rows = milestone_definitions(version)
    assert len(rows) == count
    assert sum(row['points'] for row in rows.values()) == 1000
    assert set(STORY_FLAGS) | set(ITEM_MILESTONES) | {'ss-anne-rival', 'snorlax-resolved'} == {
        key for key, row in rows.items() if row['group'] == 'story'}
    assert len(VISITS) == 10
    assert set(area_checks(version)) == {key for key, row in rows.items() if row['group'] == 'areas'}


def test_v2_keeps_every_v1_milestone_and_adds_the_areas():
    old, new = milestone_definitions(V1), milestone_definitions(VERSION)
    assert set(new) - set(old) == set(area_checks()) and len(area_checks()) == 25
    assert set(old) <= set(new) and not area_checks(V1)
    assert {key: row['points'] for key, row in old.items()}['badge:boulder'] == 50
    assert new['badge:boulder']['points'] == 40 and new['champion']['points'] == 80


def test_baseline_exclusion_and_same_frame_is_not_confirmation():
    facts = state()
    facts['story']['starter'] = True
    facts['party'] = [mon()]
    facts['items'] = [[74, 1]]
    tracker = CampaignTracker(facts)
    facts['story']['parcel-collected'] = True
    assert tracker.observe(facts, 1, 0) == []
    assert tracker.observe(facts, 1, 0) == []
    awards = tracker.observe(facts, 2, 0, decision=9, tokens=2000, actions=16)
    assert [row['id'] for row in awards] == ['parcel-collected']
    assert awards[0]['tokens'] == 2000
    assert 'starter' not in tracker.awarded
    assert 'lift-key' in tracker.initial_keys
    assert confirm(tracker, facts, 3) == []
    with pytest.raises(ValueError, match='backwards'):
        tracker.observe(facts, 2, 0)


def test_badges_need_both_facts_and_transients_do_not_score():
    facts = state()
    tracker = CampaignTracker(facts)
    facts['badges'] = 1
    assert confirm(tracker, facts) == []
    facts['gym_flags'][0] = True
    tracker.observe(facts, 3, 0)
    facts['valid'] = False
    assert tracker.observe(facts, 4, 0) == []
    facts['valid'] = True
    assert tracker.observe(facts, 5, 0) == []
    assert tracker.observe(facts, 6, 0)[0]['id'] == 'badge:boulder'
    facts['badges'] = 0
    confirm(tracker, facts, 7)
    assert tracker.score == 40


def test_visits_require_overworld_and_exclude_initial_map():
    facts = state()
    facts['map_id'] = 1
    tracker = CampaignTracker(facts)
    facts['map_id'] = 2
    facts['overworld'] = False
    assert confirm(tracker, facts) == []
    facts['overworld'] = True
    assert confirm(tracker, facts, 3)[0]['id'] == 'visit:pewter-city'
    facts['map_id'] = 1
    assert confirm(tracker, facts, 5) == []


def test_item_pickup_requires_correct_map_and_stable_gain():
    facts = state()
    tracker = CampaignTracker(facts)
    facts['items'] = [[74, 1]]
    assert confirm(tracker, facts) == []
    facts['items'] = []
    tracker.observe(facts, 3, 0)
    facts['map_id'] = 202
    facts['items'] = [[74, 1]]
    # Entering the room earns its area milestone. The key needs one more confirming frame.
    assert [row['id'] for row in confirm(tracker, facts, 4)] == ['area:hideout-b4f']
    assert tracker.observe(facts, 6, 0)[0]['id'] == 'lift-key'
    facts['items'] = []
    tracker.observe(facts, 7, 0)
    facts['items'] = [[74, 1]]
    confirm(tracker, facts, 8)
    assert tracker.score == 16


def capture(tracker, facts, species, frame, *, boxed=False):
    facts['battle'] = 1
    facts['enemy_species'] = species
    facts['captured_species'] = 0
    tracker.observe(deepcopy(facts), frame, 0)
    facts['captured_species'] = species
    tracker.observe(deepcopy(facts), frame + 1, 0)
    if boxed:
        facts['box_species'].append(species)
    else:
        facts['party'].append(mon(species, trainer=100 + frame))
    tracker.observe(deepcopy(facts), frame + 2, 0)
    tracker.observe(deepcopy(facts), frame + 3, 0)
    facts['battle'] = 0
    facts['captured_species'] = 0
    tracker.observe(deepcopy(facts), frame + 4, 0)


def test_capture_requires_latch_and_population_confirmation_including_pc():
    facts = state()
    facts['party'] = [mon()]
    tracker = CampaignTracker(facts)
    facts['owned'] = [7, 25]
    facts['party'].append(mon(84))
    confirm(tracker, facts)
    assert tracker.counters['captures'] == 0
    capture(tracker, facts, 84, 3, boxed=True)
    assert tracker.counters['captures'] == 1
    assert tracker.score == 5
    capture(tracker, facts, 84, 8, boxed=True)
    assert tracker.counters['captures'] == 2
    assert tracker.caught_species == {84}
    assert tracker.score == 5


def test_failed_capture_and_species_guess_never_score():
    facts = state()
    facts['party'] = [mon()]
    tracker = CampaignTracker(facts)
    facts.update(battle=1, enemy_species=84, captured_species=84)
    confirm(tracker, facts)
    facts.update(battle=0, captured_species=0)
    confirm(tracker, facts, 3)
    assert tracker.counters['captures'] == 0


def test_evolution_counts_family_once_and_ignores_swaps_and_cancels():
    facts = state()
    facts['party'] = [mon()]
    tracker = CampaignTracker(facts)
    facts['evolution_occurred'] = True
    confirm(tracker, facts)
    assert tracker.counters['evolutions'] == 0
    facts['party'][0]['species'] = 179
    confirm(tracker, facts, 3)
    tracker.observe(facts, 5, 0)
    assert tracker.evolved_families == {177}
    facts['party'][0]['species'] = 28
    confirm(tracker, facts, 6)
    tracker.observe(facts, 8, 0)
    assert tracker.counters['evolutions'] == 2
    assert tracker.score == 5
    facts['party'] = [mon(84, trainer=333)]
    confirm(tracker, facts, 9)
    facts['party'] = [mon(85, trainer=555)]
    confirm(tracker, facts, 11)
    assert tracker.counters['evolutions'] == 2


def test_resume_retains_pending_capture_and_awards_without_duplicate_credit():
    facts = state()
    facts['party'] = [mon()]
    tracker = CampaignTracker(facts)
    facts.update(battle=1, enemy_species=84)
    tracker.observe(facts, 1, 0)
    facts['captured_species'] = 84
    tracker.observe(facts, 2, 0)
    restored = CampaignTracker.from_dict(json.loads(json.dumps(tracker.to_dict())))
    facts['box_species'] = [84]
    confirm(restored, facts, 3)
    restored.observe(facts, 5, 0)
    assert restored.counters['captures'] == 1
    assert restored.score == 5
    again = CampaignTracker.from_dict(json.loads(json.dumps(restored.to_dict())))
    assert confirm(again, facts, 6) == []
    assert again.score == 5
    assert again.report()['counters']['purchases'] is None


def test_champion_requires_new_hall_of_fame_registration():
    facts = state()
    tracker = CampaignTracker(facts)
    facts.update(champion=True, map_id=118)
    assert confirm(tracker, facts) == []
    facts['hall_of_fame'] = 1
    assert confirm(tracker, facts, 3)[0]['id'] == 'champion'
    assert tracker.complete()
    assert tracker.score == 80


def test_area_milestones_need_the_map_the_spot_and_no_battle():
    facts = state()
    tracker = CampaignTracker(facts)
    facts.update(map_id=61, x=5, y=5)
    assert confirm(tracker, facts) == []
    facts.update(x=21, y=16, battle=1)
    assert confirm(tracker, facts, 3) == []
    facts['battle'] = 0
    assert [row['id'] for row in confirm(tracker, facts, 5)] == ['area:mt-moon-b2f']
    facts.update(map_id=15, x=30, y=18)
    assert confirm(tracker, facts, 7) == []
    facts['y'] = 17
    assert [row['id'] for row in confirm(tracker, facts, 9)] == ['area:mt-moon-exit']
    assert tracker.score == 16
    facts['items'] = [[61, 1]]
    assert [row['id'] for row in confirm(tracker, facts, 11)] == ['area:saffron-drink']


def test_areas_present_at_the_start_never_score():
    facts = state()
    facts.update(map_id=51)
    tracker = CampaignTracker(facts)
    assert 'area:viridian-forest' in tracker.initial_keys
    assert confirm(tracker, facts) == []


def test_v1_tracker_scores_v1_only_and_v2_needs_position():
    facts = state()
    del facts['x'], facts['y']
    with pytest.raises(ValueError, match='position'):
        CampaignTracker(facts)
    tracker = CampaignTracker(facts, version=V1)
    facts['map_id'] = 2
    assert [row['points'] for row in confirm(tracker, facts)] == [5]
    report = tracker.report()
    assert report['version'] == V1 and report['total_milestones'] == 50
    assert 'areas' not in report['groups']
    with pytest.raises(ValueError, match='Unsupported'):
        CampaignTracker(state(), version='campaign-progress-v0')


@pytest.mark.parametrize('version', [V1, VERSION])
def test_checkpoints_keep_their_protocol(version):
    tracker = CampaignTracker(state(), version=version)
    restored = CampaignTracker.from_dict(json.loads(json.dumps(tracker.to_dict())))
    assert restored.version == version
    assert restored.report()['total_milestones'] == len(milestone_definitions(version))
    # A tracker packed before versions existed has no version attribute. It scored v1.
    legacy = CampaignTracker(state(), version=V1)
    del legacy.__dict__['version']
    assert legacy.version == V1 and legacy.report()['total_milestones'] == 50


@pytest.mark.parametrize('version', [V1, VERSION])
def test_all_milestones_can_be_awarded_once(version):
    facts = state()
    tracker = CampaignTracker(facts, version=version)
    frame = 1
    for key, check in area_checks(version).items():
        facts['map_id'] = check.get('map', 0)
        facts['x'], facts['y'] = check.get('near') or check.get('area', [3, 6])[:2]
        facts['items'] = [[check['item'][0], 1]] if 'item' in check else []
        assert key in [row['id'] for row in confirm(tracker, facts, frame)]
        frame += 2
    facts.update(map_id=37, items=[])
    facts['story'] = dict.fromkeys(set(STORY_FLAGS) | {'ss-anne-rival', 'snorlax-resolved'}, True)
    confirm(tracker, facts, frame)
    frame += 2
    for key, (item, room) in ITEM_MILESTONES.items():
        facts['map_id'] = room
        facts['items'].append([item, 1])
        for _ in range(3):
            tracker.observe(deepcopy(facts), frame, 0)
            frame += 1
    for room in VISITS:
        facts['map_id'] = room
        confirm(tracker, facts, frame)
        frame += 2
    facts.update(badges=255, gym_flags=[True] * 8,
                 elite=dict.fromkeys(['Lorelei', 'Bruno', 'Agatha', 'Lance'], True),
                 champion=True, map_id=118, hall_of_fame=1)
    confirm(tracker, facts, frame)
    frame += 2
    for species in range(1, 21):
        capture(tracker, facts, species, frame, boxed=True)
        frame += 5
    facts['party'] = [mon(n, trainer=n) for n in range(1, 7)]
    facts['evolution_data'] = {'families': {'7': 1, '8': 2, '9': 3}, 'edges': [[1, 7], [2, 8], [3, 9]]}
    confirm(tracker, facts, frame)
    frame += 2
    facts['evolution_occurred'] = True
    for index in range(3):
        facts['party'][index]['species'] = index + 7
        for _ in range(3):
            tracker.observe(deepcopy(facts), frame, 0)
            frame += 1
    report = tracker.report()
    assert report['score'] == 1000
    assert report['completed_milestones'] == report['total_milestones'] == len(milestone_definitions(version))
    assert confirm(tracker, facts, frame) == []


@pytest.mark.skipif(not os.environ.get('POKEBENCH_ROM') or not os.environ.get('POKEBENCH_CAMPAIGN_STATE'),
                    reason='Optional local real ROM and checkpoint are not distributed')
def test_native_campaign_reader_is_read_only_and_resumable():
    from pokeagent_bench.game import RedEngine
    engine = RedEngine(Path(os.environ['POKEBENCH_ROM']), Path(os.environ['POKEBENCH_CAMPAIGN_STATE']).read_bytes())
    try:
        before = engine.save()
        facts = read_campaign_evidence(engine, position=True)
        assert engine.save() == before
        assert len(facts['evolution_data']['edges']) == 72
        tracker = CampaignTracker(facts)
        for frame in range(1, 4):
            engine.tick(1)
            tracker.observe(read_campaign_evidence(engine, position=True), frame, 0)
        restored = CampaignTracker.from_dict(json.loads(json.dumps(tracker.to_dict())))
        assert restored.report()['score'] == tracker.report()['score']
        assert restored.report()['total_milestones'] == 75
    finally:
        engine.close()


@pytest.mark.skipif(not os.environ.get('POKEBENCH_ROM') or not os.environ.get('POKEBENCH_CAPTURE_RUN'),
                    reason='Optional local capture replay is not distributed')
def test_native_successful_capture_replay_awards_once():
    from pokeagent_bench.game import RedEngine
    run = Path(os.environ['POKEBENCH_CAPTURE_RUN'])
    engine = RedEngine(Path(os.environ['POKEBENCH_ROM']), (run / 'initial.state').read_bytes())
    try:
        tracker = CampaignTracker(read_campaign_evidence(engine), version=V1)
        frame = 0
        for line in (run / 'actions.jsonl').read_text().splitlines():
            row = json.loads(line)
            action = row['action']
            if action['button']:
                engine.press(action['button'])
            for index in range(row['executed_frames']):
                if action['button'] and index == action['hold_frames']:
                    engine.release(action['button'])
                engine.tick()
                frame += 1
                tracker.observe(read_campaign_evidence(engine), frame, 0)
            if action['button']:
                engine.release(action['button'])
        assert tracker.counters['captures'] == 1
        assert 'caught-species:1' in tracker.awarded
        assert tracker.score == 5
    finally:
        engine.close()


@pytest.mark.skipif(not os.environ.get('POKEBENCH_ROM') or not os.environ.get('POKEBENCH_LONG_RUN'),
                    reason='Optional stored Long run is not distributed')
def test_v1_run_rescores_under_v2_without_changing_its_verified_score():
    from pokeagent_bench.session import replay
    run = Path(os.environ['POKEBENCH_LONG_RUN'])
    recorded = json.loads((run / 'result.json').read_text())
    assert json.loads((run / 'manifest.json').read_text())['scoring_protocol'] == V1
    verified = replay(Path(os.environ['POKEBENCH_ROM']), run, rescore=VERSION)
    second = verified.pop('rescore')
    assert verified['score'] == recorded['score']
    assert second['total_milestones'] == 75
    old = {row['id']: row['frame'] for row in recorded['campaign']['events'] if row['kind'] == 'milestone'}
    new = {row['id']: row['frame'] for row in second['events'] if row['kind'] == 'milestone'}
    assert all(new[key] == frame for key, frame in old.items())
