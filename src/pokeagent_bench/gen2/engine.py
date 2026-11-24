"""Crystal ROM check, a frame-locked clock and start states that carry their clock lock.

Gen II reads a real-time clock. A raw Core state keeps only the clock's zero point, so a
state opened on its own would read the host clock and every run would differ. Here the clock
is locked to emulated frames from the first tick, and every saved start writes its lock to
initial.clock.json next to initial.state. Opening a start without that file, with a lock that
does not follow frames, or with a lock that would put the clock before the moment the state
was saved, is refused. The cartridge treats a clock that runs backwards as a reset.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pokecore.gen2 import clock
from pokecore.gen2.memory_map import symbols

ROM_NAME = 'Pokemon - Crystal Version (USA, Europe) (Rev 1)'
ROM_SHA1 = 'f2f52230b536214ef7c9924f483392993e226cfb'
ROM_SHA256 = 'fdcc3c8c43813cf8731fc037d2a6d191bac75439c34b24ba1c27526e6acdc8a2'
CLOCK_FORMAT = 'gen2-frame-clock-v1'
CLOCK_FILE = 'initial.clock.json'
STATE_FILE = 'initial.state'
EPOCH = clock.FIXED_CLOCK_EPOCH
SYMBOLS = symbols('crystal')
PARTY_STRUCT = 48
MON_HP = 34
TIMES_OF_DAY = ('morning', 'day', 'night', 'darkness')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check_rom(path):
    """Return the ROM bytes, or explain which ROM is needed. The same rule as Red: SHA-256 must match."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'ROM not found: {path}')
    data = path.read_bytes()
    if sha256(data) != ROM_SHA256:
        raise ValueError(f'Unsupported ROM. The Gen II prep tasks need {ROM_NAME}, SHA-1 {ROM_SHA1}. '
                         f'{path} has SHA-1 {hashlib.sha1(data).hexdigest()}.')
    return data


def boot(rom_bytes):
    """A fresh cartridge with silent hardware and a clock locked to emulated frames.

    The clock starts at EPOCH reading zero elapsed time and moves 4389/262144 s per frame,
    the Game Boy frame length, so two runs with the same inputs see the same time.
    """
    emulator = clock.boot(bytes(rom_bytes), sound=False)
    clock.lock_clock(emulator, at=EPOCH, follow_frames=True, rebase=True)
    return emulator


def read(memory, name, size=1, offset=0):
    """Bytes of a named Crystal symbol, from its own WRAM bank whatever bank is mapped."""
    bank, address = SYMBOLS[name]
    address += offset
    if 0x8000 <= address < 0xE000:
        return bytes(memory[bank, address:address + size])
    return bytes(memory[address:address + size])


def byte(memory, name, offset=0):
    return read(memory, name, 1, offset)[0]


def event_set(memory, index):
    return bool(byte(memory, 'wEventFlags', index // 8) >> (index % 8) & 1)


def clock_record(emulator):
    """The lock and the instant the clock reads now."""
    lock = emulator.clock_lock_state()
    if not lock or not lock.get('follow_frames'):
        raise ValueError('The clock must be locked to emulated frames before a start is saved')
    memory = emulator.memory
    return {'format': CLOCK_FORMAT, 'lock': lock, 'timezero': emulator.rtc_state()['timezero'],
            'clock': emulator.clock_now(), 'elapsed': clock.clock_elapsed(emulator),
            'time_of_day': byte(memory, 'wTimeOfDay'), 'hours': byte(memory, 'hHours'),
            'minutes': byte(memory, 'hMinutes')}


def save_start(emulator, folder):
    """Write initial.state and its clock lock. The folder must not exist yet."""
    folder = Path(folder)
    record = clock_record(emulator)
    state = emulator.save()
    record['state_sha256'] = sha256(state)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / STATE_FILE).write_bytes(state)
    (folder / CLOCK_FILE).write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return record


def read_clock(folder, state):
    """The checked clock record of a start, or an error that names why it is refused."""
    path = Path(folder) / CLOCK_FILE
    if not path.is_file():
        raise ValueError(f'{folder} has no {CLOCK_FILE}. A Gen II start without its clock lock is refused')
    record = json.loads(path.read_text())
    lock = record.get('lock')
    if record.get('format') != CLOCK_FORMAT or not isinstance(lock, dict):
        raise ValueError(f'{path} is not a {CLOCK_FORMAT} record')
    if set(lock) != {'base', 'offset', 'frames', 'follow_frames'} or lock['follow_frames'] is not True:
        raise ValueError(f'{path}: the clock lock must follow emulated frames')
    if record.get('state_sha256') != sha256(state):
        raise ValueError(f'{path} belongs to a different state')
    return record


def apply_clock(emulator, record):
    """Apply a saved lock to a loaded state and refuse it if the clock would read earlier than at save."""
    emulator.set_clock_lock_state(record['lock'])
    if emulator.rtc_state()['timezero'] != record['timezero']:
        raise ValueError('The state and its clock record disagree on the clock zero point')
    now = emulator.clock_now()
    if now < record['clock']:
        raise ValueError(f'The clock lock reads {now}, before the save time {record["clock"]}. Refused')
    return now


def load_start(rom_bytes, folder):
    """Open a saved start in a fresh emulator with its clock lock applied."""
    folder = Path(folder)
    state = (folder / STATE_FILE).read_bytes()
    record = read_clock(folder, state)
    emulator = clock.boot(bytes(rom_bytes), sound=False)
    try:
        emulator.load(state)
        apply_clock(emulator, record)
    except BaseException:
        emulator.stop(save=False)
        raise
    return emulator, record


def facts(emulator, events=()):
    """The RAM facts a Gen II milestone reads, with only the event flags it names."""
    memory = emulator.memory
    count = byte(memory, 'wPartyCount')
    party = []
    for slot in range(min(count, 6)):
        record = read(memory, 'wPartyMons', PARTY_STRUCT, slot * PARTY_STRUCT)
        party.append({'species': record[0], 'level': record[31],
                      'hp': int.from_bytes(record[MON_HP:MON_HP + 2], 'big'),
                      'max_hp': int.from_bytes(record[MON_HP + 2:MON_HP + 4], 'big')})
    items = []
    number = byte(memory, 'wNumItems')
    if number <= 20:
        raw = read(memory, 'wNumItems', 1 + 2 * number)[1:]
        items = [[raw[i], raw[i + 1]] for i in range(0, len(raw), 2)]
    keys = byte(memory, 'wNumKeyItems')
    key_items = list(read(memory, 'wNumKeyItems', 1 + keys)[1:]) if keys <= 25 else []
    group, number = byte(memory, 'wMapGroup'), byte(memory, 'wMapNumber')
    return {'valid': 1 <= group <= 26 and 1 <= count <= 6,
            'map': [group, number], 'x': byte(memory, 'wXCoord'), 'y': byte(memory, 'wYCoord'),
            'battle': byte(memory, 'wBattleMode'), 'script': byte(memory, 'wScriptRunning'),
            'badges': byte(memory, 'wJohtoBadges') | byte(memory, 'wKantoBadges') << 8,
            'items': items, 'key_items': key_items, 'party': party,
            'time_of_day': byte(memory, 'wTimeOfDay'),
            'events': {str(index): event_set(memory, index) for index in sorted(set(events))}}


def digests(emulator):
    """Hashes of the frame and of all work RAM, every WRAM bank and HRAM, read without side effects."""
    memory = emulator.memory
    work = bytes(memory[0, 0xC000:0xD000]) + b''.join(bytes(memory[bank, 0xD000:0xE000]) for bank in range(1, 8))
    return {'frame': sha256(bytes(emulator.screen.raw_buffer)), 'wram': sha256(work),
            'hram': sha256(bytes(memory[0xFF80:0xFFFF])), 'clock': emulator.clock_now()}
