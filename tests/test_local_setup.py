import io
import json
import tarfile

import httpx
import pytest
import zstandard

from pokeagent_bench import catalog_execution, local_setup
from pokeagent_bench.cli import main

# No real ROM is used here. A stub stands in for it and the expected hash is patched to match.
STUB_ROM = bytes(range(256)) * 512


@pytest.fixture
def rom(tmp_path, monkeypatch):
    path = tmp_path / 'stub.gb'
    path.write_bytes(STUB_ROM)
    monkeypatch.setattr(local_setup, 'ROM_SHA256', local_setup.sha256(STUB_ROM))
    return path


@pytest.fixture
def private_tree(tmp_path):
    """A tiny private fixture root with one task and one target scenario outside the root."""
    root = tmp_path / 'private' / 'catalog'
    outside = tmp_path / 'private' / 'older' / 'task' / 'target'
    for folder in (root / 'task' / 'default', outside):
        folder.mkdir(parents=True)
        (folder / 'initial.state').write_bytes(STUB_ROM[1000:9000] + b'save data')
        (folder / 'scenario.json').write_text(json.dumps({'folder': str(folder), 'origin': '/home/someone/work/run'}))
        (folder / 'notes.txt').write_text('private notes')
    (root / 'preparation-bindings.json').write_text(json.dumps({'targets': [{'scenario': str(outside)}]}))
    return root


def test_wrong_rom_is_rejected_with_the_needed_hash(tmp_path):
    wrong = tmp_path / 'other.gb'
    wrong.write_bytes(b'not the game')
    with pytest.raises(ValueError, match=local_setup.ROM_SHA1):
        local_setup.check_rom(wrong)
    with pytest.raises(ValueError, match='ROM not found'):
        local_setup.check_rom(tmp_path / 'missing.gb')


def test_pack_round_trip_restores_files_and_hides_private_paths(tmp_path, rom, private_tree):
    summary = local_setup.build_pack(rom, private_tree, tmp_path / 'pack')
    assert summary['files'] == 5 and summary['states'] == 2
    packed_json = json.loads((tmp_path / 'pack' / 'fixtures.json').read_text())
    assert packed_json == summary
    built = tmp_path / 'out' / 'fixtures'
    local_setup.unpack_fixtures(STUB_ROM, built, tmp_path / 'pack')
    state = private_tree / 'task' / 'default' / 'initial.state'
    assert (built / 'task' / 'default' / 'initial.state').read_bytes() == state.read_bytes()
    assert not list(built.rglob('notes.txt'))
    scenario = json.loads((built / 'task' / 'default' / 'scenario.json').read_text())
    assert scenario == {'folder': str(built / 'task' / 'default'), 'origin': 'private:/work/run'}
    target = json.loads((built / 'preparation-bindings.json').read_text())['targets'][0]['scenario']
    assert target == str(built / 'external' / 'older' / 'task' / 'target')
    assert (built / 'external' / 'older' / 'task' / 'target' / 'initial.state').is_file()
    everything = b''.join(path.read_bytes() for path in built.rglob('*.json'))
    assert str(private_tree.parent).encode() not in everything and b'/home/' not in everything


def test_pack_does_not_open_with_another_rom(tmp_path, rom, private_tree):
    local_setup.build_pack(rom, private_tree, tmp_path / 'pack')
    with pytest.raises(ValueError, match='different ROM'):
        local_setup.unpack_fixtures(STUB_ROM[::-1], tmp_path / 'out', tmp_path / 'pack')
    assert not (tmp_path / 'out').exists()


def test_damaged_pack_is_rejected(tmp_path, rom, private_tree):
    local_setup.build_pack(rom, private_tree, tmp_path / 'pack')
    packed = tmp_path / 'pack' / 'fixtures.pack'
    data = bytearray(packed.read_bytes())
    data[len(data) // 2] ^= 0xFF
    packed.write_bytes(bytes(data))
    with pytest.raises(ValueError, match='damaged'):
        local_setup.unpack_fixtures(STUB_ROM, tmp_path / 'out', tmp_path / 'pack')


def test_pack_entry_outside_the_output_folder_is_rejected(tmp_path, rom):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as tree:
        member = tarfile.TarInfo('../escape.json')
        member.size = 2
        tree.addfile(member, io.BytesIO(b'{}'))
    raw = buffer.getvalue()
    pack = tmp_path / 'pack'
    pack.mkdir()
    dictionary = zstandard.ZstdCompressionDict(STUB_ROM, dict_type=zstandard.DICT_TYPE_RAWCONTENT)
    (pack / 'fixtures.pack').write_bytes(zstandard.ZstdCompressor(dict_data=dictionary).compress(raw))
    (pack / 'fixtures.json').write_text(json.dumps({
        'format': 1, 'rom_sha256': local_setup.sha256(STUB_ROM), 'tree_sha256': local_setup.sha256(raw)}))
    with pytest.raises(ValueError, match='unexpected entry'):
        local_setup.unpack_fixtures(STUB_ROM, tmp_path / 'out', pack)
    assert not (tmp_path / 'escape.json').exists()


def test_checkout_without_a_pack_says_so(tmp_path):
    with pytest.raises(ValueError, match='no fixture pack'):
        local_setup.unpack_fixtures(STUB_ROM, tmp_path / 'out', tmp_path / 'absent')


def test_shipped_pack_is_bound_to_the_required_rom():
    summary = local_setup.PACK / 'fixtures.json'
    if not summary.is_file():
        pytest.skip('this checkout has no fixture pack')
    assert json.loads(summary.read_text())['rom_sha256'] == local_setup.ROM_SHA256
    assert (local_setup.PACK / 'fixtures.pack').stat().st_size < 1024 * 1024


def test_altered_reference_archive_is_rejected(tmp_path):
    archive = tmp_path / 'pokered.tar.gz'
    archive.write_bytes(b'not the pinned archive')
    with pytest.raises(ValueError, match='failed verification'):
        local_setup.build_game_data(tmp_path / 'game-data', archive)
    assert not (tmp_path / 'game-data').exists()


def test_generated_game_data_matches_the_leaderboard_hashes(tmp_path):
    """Needs the public pret/pokered archive, so it is skipped without a network."""
    try:
        raw = local_setup.download_reference()
    except httpx.HTTPError as error:
        pytest.skip(f'pret/pokered archive not reachable: {error}')
    archive = tmp_path / 'pokered.tar.gz'
    archive.write_bytes(raw)
    bundle = local_setup.build_game_data(tmp_path / 'game-data', archive)
    assert {name: local_setup.sha256((bundle / name).read_bytes())
            for name in local_setup.GAME_DATA_SHA256} == local_setup.GAME_DATA_SHA256
    current = json.loads((tmp_path / 'game-data' / 'current.json').read_text())
    assert current['bundle'] == bundle.name
    from pokeagent_bench.gameplay import load_catalog
    assert load_catalog(tmp_path / 'game-data')


def test_setup_command_builds_once_and_reports(tmp_path, rom, private_tree, monkeypatch, capsys):
    local_setup.build_pack(rom, private_tree, tmp_path / 'pack')
    monkeypatch.setattr(local_setup, 'PACK', tmp_path / 'pack')
    calls = []

    def fake_game_data(destination, archive=None):
        calls.append(archive)
        destination.mkdir(parents=True)
        (destination / 'current.json').write_text('{}')

    monkeypatch.setattr(local_setup, 'build_game_data', fake_game_data)
    monkeypatch.setattr(catalog_execution, 'inventory', lambda fixtures: {
        'runnable': 1, 'tasks': [{'id': 'ready', 'runnable': True}, {'id': 'held', 'runnable': False}]})
    output = tmp_path / 'data'
    monkeypatch.setattr('sys.argv', ['pokebench', 'setup', '--rom', str(rom), '--output', str(output)])
    assert main() == 0
    first = json.loads(capsys.readouterr().out)
    assert first['built'] == ['fixtures', 'game-data']
    assert first['tasks_ready'] == 1 and first['tasks_held'] == ['held']
    assert (output / 'fixtures' / 'task' / 'default' / 'initial.state').is_file()
    assert main() == 0
    assert json.loads(capsys.readouterr().out)['built'] == []
    assert calls == [None]
