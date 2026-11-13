"""Turn a legal Pokemon Red ROM into the fixtures and game data a benchmark run needs.

The repository holds no ROM, no save state and no game table. Fixtures ship as one
pack that is compressed against the ROM itself, so it only opens with the right ROM.
Game tables are generated from the public pret/pokered disassembly at a pinned commit.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
import tempfile
from pathlib import Path

import zstandard

from . import game_data_strategy, game_data_tables

ROM_NAME = 'Pokemon Red (USA, Europe) (SGB Enhanced)'
ROM_SHA1 = 'ea9bcae617fdf159b045185467ae58b2e4a48b9a'
ROM_SHA256 = '5ca7ba01642a3b27b0cc0b5349b52792795b62d3ed977e98a09390659af96b7b'
REVISION = 'a1a22aaf84d1675bcdbaeb194592379d586d838e'
REFERENCE_URL = f'https://github.com/pret/pokered/archive/{REVISION}.tar.gz'
REFERENCE_SHA256 = 'be0520c19c43ef2396e6e91ae7bdb46fd7e7b5ea3a76a5f285e2231c0f32ce3c'
# Hashes of the tables every leaderboard run used.
GAME_DATA_SHA256 = {
    'strategy.json': '61d5d9aa5448e377d657f6febaa8be684cdc29f47c5aaf86ec49f047e729caa3',
    'tables.json': '5f59ac59459df2dee33c3e371f7eeea09cd79b43e45924d704f7844ab1c8d841',
}
PACK = Path(__file__).with_name('fixture_pack')
TOKEN = '@POKEBENCH_FIXTURES@'
WINDOW_LOG = 27
MAX_TREE = 64 * 1024 * 1024
# Only the files the runner reads go into the pack.
PACKED = {'initial.state', 'preview.png', 'scenario.json', 'start-facts.json', 'start-validation.json',
          'reference-validation.json', 'reference-commands.json', 'preparation-bindings.json',
          'preparation-reference-summary.json'}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check_rom(path):
    """Return the ROM bytes, or explain which ROM is needed."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'ROM not found: {path}')
    data = path.read_bytes()
    if sha256(data) != ROM_SHA256:
        raise ValueError(f'Unsupported ROM. This benchmark needs {ROM_NAME}, SHA-1 {ROM_SHA1}. '
                         f'{path} has SHA-1 {hashlib.sha1(data).hexdigest()}.')
    return data


def download_reference():
    import httpx
    response = httpx.get(REFERENCE_URL, follow_redirects=True, timeout=120)
    response.raise_for_status()
    return response.content


def build_game_data(destination, archive=None):
    """Generate the game tables from the pinned pret/pokered archive and check their hashes."""
    raw = Path(archive).read_bytes() if archive else download_reference()
    if sha256(raw) != REFERENCE_SHA256:
        raise ValueError(f'The pret/pokered archive failed verification. Expected SHA-256 {REFERENCE_SHA256}.')
    with tempfile.TemporaryDirectory() as temporary:
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as source_archive:
            source_archive.extractall(temporary, filter='data')
        source = Path(temporary) / f'pokered-{REVISION}'
        values = {'strategy.json': game_data_strategy.generate(source, REVISION),
                  'tables.json': game_data_tables.generate(source)}
    files = {name: (json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
             for name, value in values.items()}
    hashes = {name: sha256(data) for name, data in files.items()}
    if hashes != GAME_DATA_SHA256:
        raise ValueError('Generated game data differs from the data the leaderboard runs used')
    manifest = {'schema': 1, 'source': 'https://github.com/pret/pokered', 'source_revision': REVISION,
                'generator': 'pokebench', 'files': hashes}
    identity = sha256(json.dumps(manifest, sort_keys=True).encode())
    bundle = Path(destination) / 'bundles' / identity
    bundle.mkdir(parents=True)
    for name, data in files.items():
        (bundle / name).write_bytes(data)
    (bundle / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (Path(destination) / 'current.json').write_text(json.dumps({'bundle': identity}) + '\n')
    return bundle


def _dictionary(rom):
    return zstandard.ZstdCompressionDict(rom, dict_type=zstandard.DICT_TYPE_RAWCONTENT)


def _target_scenarios(root):
    """Scenario folders outside the fixture root that preparation tasks load while running."""
    bindings = root / 'preparation-bindings.json'
    found = set()

    def walk(value):
        if isinstance(value, dict):
            scenario = value.get('scenario')
            if isinstance(scenario, str) and (Path(scenario) / 'scenario.json').is_file():
                found.add(Path(scenario))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    if bindings.is_file():
        walk(json.loads(bindings.read_text()))
    return sorted(path for path in found if root not in path.parents)


def build_pack(rom, fixtures, output):
    """Maintainer step: pack a validated private fixture root for publication.

    Folder paths inside the fixture root become a token that setup fills in again.
    Every other absolute path is provenance only and is reduced to a private marker.
    """
    rom_bytes = check_rom(rom)
    root = Path(fixtures).resolve()
    external = {path: f'external/{"/".join(path.parts[-3:])}' for path in _target_scenarios(root)}
    sources = [(path, path.relative_to(root).as_posix()) for path in sorted(root.rglob('*'))
               if path.is_file() and path.name in PACKED]
    for folder, name in external.items():
        sources += [(path, f'{name}/{path.name}') for path in sorted(folder.iterdir())
                    if path.is_file() and path.name in PACKED]
    replacements = sorted(((str(folder), f'{TOKEN}/{name}') for folder, name in external.items()),
                          key=lambda pair: -len(pair[0])) + [(str(root), TOKEN)]
    buffer = io.BytesIO()
    states = 0
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as tree:
        for path, name in sorted(sources, key=lambda pair: pair[1]):
            data = path.read_bytes()
            if path.suffix == '.json':
                text = data.decode()
                for old, new in replacements:
                    text = text.replace(old, new)
                text = re.sub(r'(?:file://)?/(?:home|Users)/[^/"\\]+', 'private:', text)
                data = text.encode()
            states += path.suffix == '.state'
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            tree.addfile(member, io.BytesIO(data))
    raw = buffer.getvalue()
    parameters = zstandard.ZstdCompressionParameters.from_level(19, window_log=WINDOW_LOG, enable_ldm=True)
    packed = zstandard.ZstdCompressor(compression_params=parameters, dict_data=_dictionary(rom_bytes)).compress(raw)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'fixtures.pack').write_bytes(packed)
    summary = {'format': 1, 'rom_sha256': ROM_SHA256, 'tree_sha256': sha256(raw), 'tree_bytes': len(raw),
               'pack_bytes': len(packed), 'files': len(sources), 'states': states}
    (output / 'fixtures.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def unpack_fixtures(rom_bytes, destination, pack=None):
    """Rebuild the fixture folder from the pack and the user's own ROM."""
    pack = Path(pack or PACK)
    if not (pack / 'fixtures.pack').is_file():
        raise ValueError('This checkout has no fixture pack, so benchmark fixtures cannot be built')
    summary = json.loads((pack / 'fixtures.json').read_text())
    if summary.get('format') != 1 or summary.get('rom_sha256') != sha256(rom_bytes):
        raise ValueError('The fixture pack was built for a different ROM')
    try:
        raw = zstandard.ZstdDecompressor(dict_data=_dictionary(rom_bytes), max_window_size=2 ** WINDOW_LOG).decompress(
            (pack / 'fixtures.pack').read_bytes(), max_output_size=MAX_TREE)
    except zstandard.ZstdError as error:
        raise ValueError(f'The fixture pack is damaged: {error}') from error
    if sha256(raw) != summary['tree_sha256']:
        raise ValueError('The fixture pack is damaged: checksum mismatch')
    destination = Path(destination).resolve()
    destination.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as tree:
        for member in tree:
            target = (destination / member.name).resolve()
            if not member.isfile() or destination not in target.parents:
                raise ValueError('The fixture pack holds an unexpected entry')
            data = tree.extractfile(member).read()
            if target.suffix == '.json':
                data = data.replace(TOKEN.encode(), destination.as_posix().encode())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return summary


def setup(rom, output, reference_archive=None):
    """Check the ROM, then build whatever is missing under the output folder."""
    from .catalog_execution import inventory
    rom_bytes = check_rom(rom)
    output = Path(output)
    fixtures, game_data = output / 'fixtures', output / 'game-data'
    built = []
    if not fixtures.exists():
        unpack_fixtures(rom_bytes, fixtures)
        built.append('fixtures')
    if not (game_data / 'current.json').is_file():
        build_game_data(game_data, reference_archive)
        built.append('game-data')
    report = inventory(fixtures)
    if not report['runnable']:
        raise ValueError(f'No task is ready to run. Delete {fixtures} and run setup again.')
    # A task is held back when its definition changed after its fixture was last validated.
    held = sorted(row['id'] for row in report['tasks'] if not row['runnable'])
    return {'rom': ROM_NAME, 'fixtures': str(fixtures), 'game_data': str(game_data), 'built': built,
            'tasks_ready': report['runnable'], 'tasks_held': held}
