"""Offline Gen 1 fixture construction with recorded setup and frozen start facts.

This module is never imported by the gameplay runner. Fixture edits happen
before trials and are recorded in each scenario's provenance.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from pokesim_core.gen1 import (
    W_PARTY_COUNT, W_PARTY_SPECIES, W_PARTY_MONS, W_PARTY_NICKS,
    W_PARTY_OT, W_NUM_BAG_ITEMS, W_BAG_ITEMS, W_MONEY, W_EVENT_FLAGS, W_PLAYER_ID, W_PLAYER_NAME,
)
from .core import core_provenance, digest, encoded, emulator_manifest, write_json
from .game import RedEngine
from .gameplay import ui_state


def read(path):
    return json.loads(Path(path).read_text())


def load_source(rom, source, settle=0):
    """Import an archived state into a new fixture, never mutate its source."""
    source = Path(source)
    data = source.read_bytes()
    raw = gzip.decompress(data) if data[:2] == b'\x1f\x8b' else data
    engine = RedEngine(Path(rom), raw)
    if settle:
        engine.tick(settle)
    return engine, {
        'source': str(source), 'source_sha256': digest(data),
        'decompressed_sha256': digest(raw), 'released_settle_frames': settle,
        'source_backend': 'archived-pyboy', 'backend_import': emulator_manifest(),
    }


def species_record(strategy, name):
    for sid, spec in strategy['species'].items():
        if spec['name'].lower() == name.lower():
            return int(sid), spec
    raise ValueError(f'Unknown species: {name}')


def experience(growth, level):
    if growth == 'MEDIUM_FAST':
        return level ** 3
    if growth == 'MEDIUM_SLOW':
        return max(0, 6 * level ** 3 // 5 - 15 * level ** 2 + 100 * level - 140)
    if growth == 'FAST':
        return 4 * level ** 3 // 5
    if growth == 'SLOW':
        return 5 * level ** 3 // 4
    raise ValueError(f'Unsupported growth: {growth}')


def set_party(engine, strategy, party):
    """Initialize legal species structs with explicit moves and deterministic DVs."""
    if not 0 <= len(party) <= 6:
        raise ValueError('Party size must be between zero and six')
    m = engine.memory
    m[W_PARTY_COUNT] = len(party)
    for slot in range(6):
        m[W_PARTY_SPECIES + slot] = 255
        for offset in range(44):
            m[W_PARTY_MONS + slot * 44 + offset] = 0
        for base in (W_PARTY_NICKS, W_PARTY_OT):
            for offset in range(11):
                m[base + slot * 11 + offset] = 0x50
    m[W_PARTY_SPECIES + len(party)] = 255
    for slot, member in enumerate(party):
        sid, spec = species_record(strategy, member['species'])
        level = member['level']
        moves = member['moves']
        if not 1 <= len(moves) <= 4:
            raise ValueError('Each party member needs one to four moves')
        block = bytearray(44)
        block[0] = sid
        block[3] = level
        block[4] = member.get('status', 0)
        block[5:7] = bytes(spec['types'])
        block[7] = spec['catch_rate']
        block[8:12] = bytes(moves + [0] * (4 - len(moves)))
        block[12:14] = bytes(m[W_PLAYER_ID:W_PLAYER_ID + 2])
        block[14:17] = experience(spec['growth'], level).to_bytes(3, 'big')
        hp_dv = 0
        if 'max_hp' in member:
            candidates = [dv for dv in range(16)
                          if 2 * (spec['stats'][0] + dv) * level // 100 + level + 10 == member['max_hp']]
            if not candidates:
                raise ValueError(f'HP incompatible with species and level: {member}')
            hp_dv = candidates[0]
        dvs = [8 | ((hp_dv >> shift) & 1) for shift in (3, 2, 1, 0)]
        block[27:29] = bytes([(dvs[0] << 4) | dvs[1], (dvs[2] << 4) | dvs[3]])
        pp = [strategy['moves'][str(move)]['pp'] for move in moves]
        pp = member.get('pp', pp)
        block[29:33] = bytes(pp + [0] * (4 - len(pp)))
        block[33] = level
        for index, base in enumerate(spec['stats']):
            dv = hp_dv if index == 0 else dvs[index - 1]
            value = 2 * (base + dv) * level // 100 + (level + 10 if index == 0 else 5)
            if index == 0 and 'max_hp' in member:
                value = member['max_hp']
            block[34 + 2 * index:36 + 2 * index] = value.to_bytes(2, 'big')
        block[1:3] = member.get('hp', int.from_bytes(block[34:36], 'big')).to_bytes(2, 'big')
        for index, value in enumerate(block):
            m[W_PARTY_MONS + slot * 44 + index] = value
        m[W_PARTY_SPECIES + slot] = sid
        label = spec['name'].replace('_M', '♂').replace('_F', '♀')
        name = bytes({'♂': 0xEF, '♀': 0xF5}.get(c, ord(c) - ord('A') + 0x80) for c in label)[:10]
        for index, value in enumerate(name):
            m[W_PARTY_NICKS + slot * 11 + index] = value
        for index, value in enumerate(bytes(m[W_PLAYER_NAME:W_PLAYER_NAME + 11])):
            m[W_PARTY_OT + slot * 11 + index] = value


def set_bag(engine, bag, money=None):
    if len(bag) > 20 or len({item for item, _ in bag}) != len(bag):
        raise ValueError('Bag needs at most twenty distinct item types')
    m = engine.memory
    m[W_NUM_BAG_ITEMS] = len(bag)
    for index in range(41):
        m[W_BAG_ITEMS + index] = 0
    for index, (item, count) in enumerate(bag):
        if not 1 <= count <= 99:
            raise ValueError('Item count outside native bag range')
        m[W_BAG_ITEMS + index * 2] = item
        m[W_BAG_ITEMS + index * 2 + 1] = count
    m[W_BAG_ITEMS + len(bag) * 2] = 255
    if money is not None:
        amount = f'{money:06d}'
        if not 0 <= money <= 999999:
            raise ValueError('Money outside native range')
        for index in range(3):
            m[W_MONEY + index] = int(amount[index * 2:index * 2 + 2], 16)


def set_event(engine, strategy, name, value):
    number = strategy['events'][name]
    address = W_EVENT_FLAGS + number // 8
    bit = 1 << (number % 8)
    engine.memory[address] = (engine.memory[address] | bit) if value else (engine.memory[address] & ~bit)


def command(engine, button=None, hold=8, release=24):
    if button:
        engine.press(button)
    if hold:
        engine.tick(hold)
    if button:
        engine.release(button)
    if release:
        engine.tick(release)
    return {'button': button, 'hold_frames': hold, 'release_frames': release}


def snapshot(engine):
    return {'state': engine.structured(), 'progress': engine.evidence(), 'ui': ui_state(engine.memory)['kind']}


def save(engine, rom, entry, output, provenance, expected):
    """Write an immutable candidate with checked state roundtrip and start facts."""
    facts = snapshot(engine)
    actual = facts['state']
    for field, wanted in expected.items():
        if field == 'map_id':
            observed = actual['location']['map_id']
        elif field == 'position':
            observed = [actual['location']['x'], actual['location']['y']]
        elif field == 'ui':
            observed = facts['ui']
        else:
            observed = actual[field]
        if observed != wanted:
            raise ValueError(f'{entry["id"]}: {field} is {observed}, expected {wanted}')
    state = engine.save()
    engine.load(state)
    if snapshot(engine) != facts:
        raise ValueError('State roundtrip changed fixture start facts')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    screen = engine.screenshot()
    (output / 'initial.state').write_bytes(state)
    (output / 'preview.png').write_bytes(screen)
    objective = {'kind': 'catalog-task', 'task_id': entry['id'], 'description': entry['agent_goal']}
    if entry['id'] == 'campaign-full-game':
        objective = {'kind': 'milestone', 'target': 'champion', 'description': entry['agent_goal']}
    manifest = {
        'format': 1, 'game': 'red', 'name': entry['id'], 'task_id': entry['id'],
        'tested_skill': entry['tested_skill'], 'action_policy': entry['action_policy'],
        'rom_sha256': digest(Path(rom).read_bytes()), 'state_sha256': digest(state),
        'preview_sha256': digest(screen), 'setup_wait_frames': 0,
        'input_policy': 'release-all-before-first-tick-v1',
        'objective': objective, 'catalog_sha256': digest(encoded(entry)),
        'core': core_provenance(), **emulator_manifest(),
        'curation': 'offline-setup-start-checked-reference-pending',
        'provenance': provenance, 'expected_start': expected,
    }
    if provenance.get('navigation_setup'):
        manifest['navigation_condition'] = provenance['navigation_setup']['protocol']
    write_json(output / 'scenario.json', manifest)
    write_json(output / 'start-facts.json', facts)
    write_json(output / 'start-validation.json', {
        'passed': True, 'roundtrip': True, 'checks': expected,
        'state_sha256': digest(state), 'reference_completed': False,
    })
    return {'scenario': str(output), 'start_checked': True, 'reference_completed': False}


def walk_to(engine, x, y, limit=400):
    """Find an offline controller-only path within a single map."""
    from collections import deque
    original = engine.save()
    location = engine.structured()['location']
    map_id = location['map_id']
    queue = deque([(original, [])])
    seen = {(location['x'], location['y'])}
    for _ in range(limit):
        if not queue:
            break
        state, path = queue.popleft()
        engine.load(state)
        here = engine.structured()['location']
        if (here['x'], here['y']) == (x, y):
            return path
        for direction in ('up', 'right', 'down', 'left'):
            engine.load(state)
            action = command(engine, direction)
            there = engine.structured()['location']
            position = (there['x'], there['y'])
            if there['map_id'] != map_id or position in seen:
                continue
            if ui_state(engine.memory)['kind'] != 'overworld':
                continue
            seen.add(position)
            queue.append((engine.save(), path + [action]))
    engine.load(original)
    raise ValueError(f'No native controller path to {(map_id, x, y)}')


def set_active_box(engine, strategy, members):
    """Initialize only the active native storage box before a trial."""
    if len(members) > 20:
        raise ValueError('Box capacity exceeded')
    original = engine.save()
    records = []
    for member in members:
        set_party(engine, strategy, [member])
        m = engine.memory
        records.append((m[W_PARTY_SPECIES], bytes(m[W_PARTY_MONS:W_PARTY_MONS+33]),
                        bytes(m[W_PARTY_OT:W_PARTY_OT+11]), bytes(m[W_PARTY_NICKS:W_PARTY_NICKS+11])))
    engine.load(original)
    m = engine.memory
    base = 0xDA80
    for offset in range(1122):
        m[base+offset] = 0
    m[base] = len(records)
    m[base+1+len(records)] = 255
    for slot, (species, record, ot, nick) in enumerate(records):
        m[base+1+slot] = species
        for start, block in ((base+22+33*slot, record), (base+682+11*slot, ot), (base+902+11*slot, nick)):
            for index, value in enumerate(block):
                m[start+index] = value
