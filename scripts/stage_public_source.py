"""Stage reviewed source without importing private experiment history."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

DIRECTORIES = ('src', 'tests', 'scripts', 'docs', 'examples', 'fixtures', '.github')
FILES = ('README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'AGENTS.md',
         'pyproject.toml', 'uv.lock', '.python-version', '.gitignore')
BLOCKED = {'.gb', '.gbc', '.gba', '.ram', '.sav', '.state', '.log', '.pyc'}


def stage(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('Use a separate destination')
    destination.mkdir(parents=True, exist_ok=True)
    if any(p.name != 'paper' for p in destination.iterdir()):
        raise ValueError('Only a reviewed paper export may already exist in destination')
    selected = [source / name for name in FILES]
    for folder in DIRECTORIES:
        selected.extend(p for p in (source / folder).rglob('*') if p.is_file()
                        and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts)
    records = []
    for path in sorted(selected):
        if path.is_symlink() or path.suffix in BLOCKED:
            raise ValueError('Unexpected source artifact: ' + str(path.relative_to(source)))
        name = path.relative_to(source)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        records.append({'path': str(name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (destination / 'SOURCE-FILES.json').write_text(json.dumps(records, indent=2) + '\n')
    print(len(records), 'source files staged')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage(args.source, args.output)
