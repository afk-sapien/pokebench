"""Scenario migration makes copies and records the new runtime without game input."""
import importlib.util
import json
from pathlib import Path

import pytest

from pokeagent_bench.core import digest


@pytest.fixture
def importer():
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'import_scenario.py'
    spec = importlib.util.spec_from_file_location('scenario_import', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_files(tmp_path):
    rom = tmp_path / 'rom.gb'
    rom.write_bytes(b'rom')
    source = tmp_path / 'original'
    source.mkdir()
    (source / 'initial.state').write_bytes(b'original save')
    (source / 'preview.png').write_bytes(b'preview')
    (source / 'scenario.json').write_text(json.dumps({
        'format': 1, 'game': 'red', 'name': 'item-recovery', 'pyboy_version': '2.7.0',
        'rom_sha256': digest(b'rom'), 'state_sha256': digest(b'original save'),
        'preview_sha256': digest(b'preview')}))
    return rom, source


def test_import_preserves_source_bytes_and_does_not_advance(importer, tmp_path, monkeypatch):
    rom, source = source_files(tmp_path)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    class Engine:
        def __init__(self, rom, state):
            assert state in (b'original save', b'round trip')
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def structured(self):
            return {'party': [{'hp': 10}]}
        def save(self):
            return b'round trip'
        def tick(self, *args):
            pytest.fail('Import must not advance gameplay')
    monkeypatch.setattr(importer, 'RedEngine', Engine)
    monkeypatch.setattr(importer, 'emulator_manifest', lambda: {'emulator': {'backend': 'pyboy-rs'}})
    output = tmp_path / 'copy'
    manifest = importer.import_scenario(rom, source, output)
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    assert (output / 'initial.state').read_bytes() == before['initial.state']
    assert (output / 'preview.png').read_bytes() == before['preview.png']
    assert manifest['emulator']['backend'] == 'pyboy-rs'
    assert 'pyboy_version' not in manifest
    assert manifest['runtime_import']['source_emulator']['version'] == '2.7.0'
    assert manifest['runtime_import']['frames_advanced'] == 0
    with pytest.raises(ValueError, match='already exists'):
        importer.import_scenario(rom, source, output)


def test_import_refuses_bad_hash_before_opening_emulator(importer, tmp_path, monkeypatch):
    rom, source = source_files(tmp_path)
    (source / 'initial.state').write_bytes(b'tampered')
    monkeypatch.setattr(importer, 'RedEngine', lambda *args: pytest.fail('Must reject before loading'))
    with pytest.raises(ValueError, match='checksum mismatch'):
        importer.import_scenario(rom, source, tmp_path / 'copy')
    assert not (tmp_path / 'copy').exists()
