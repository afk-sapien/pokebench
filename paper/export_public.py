"""Stage an explicit, source-complete public paper package without private history."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

FILES = (
    "README.md", "LICENSE.scaffold", "STYLE.md", "CLAUDE.md", "AGENTS.md",
    "pyproject.toml", "uv.lock", "justfile", ".paper/scaffold.lock.json",
    "paper.typ", "config.typ", "si-body.typ", "references.bib",
    "american-chemical-society.csl", "stats.typ", "assets.typ", "code.typ",
    "wordcount.typ", "wordcount-sections.typ", "journal.toml", "word-limits.toml",
    "word-watchlist.toml", "prose-check.toml", "cover-letter.typ",
    "stats.json", "assets.json", "si/pilot.typ", "si/calibration.typ", "si/catalog.typ", "si/models.typ",
    "analysis/pyproject.toml", "analysis/justfile",
    "analysis/scripts/_assets.py", "analysis/scripts/_stats.py", "analysis/scripts/_provenance.py",
    "analysis/scripts/_toolchain/atomic_io.py", "analysis/scripts/_toolchain/hashcache.py",
    "analysis/scripts/_toolchain/manifest_validation.py", "analysis/scripts/_toolchain/paths.py",
    "analysis/scripts/_toolchain/evidence.py", "analysis/scripts/gen_stats.py",
    "analysis/scripts/gen_results_table.py", "analysis/scripts/export_release_snapshot.py",
    "analysis/tests/test_export_release_snapshot.py",
    "analysis/inputs/pokebench-v1-protocol.json",
    "analysis/inputs/pokebench-development.json",
    "analysis/inputs/tactical-reliability-v042.json",
    "analysis/inputs/decision-suite-v044-development.json",
    "export_public.py", "paper.pdf",
)

IGNORE = """# Local build environments and caches
.venv/
analysis/.venv/
__pycache__/
*.pyc
.build-state/
.hash-cache.json
.paper/docs/
stats-rendered.json
paper.docx
paper.resolved.typ
*.review.txt
submission/
viz/
# Private historical development artifacts are not part of this package.
archive/
analysis/data/
analysis/results/
# Only reviewed sanitized inputs belong in the public source package.
analysis/inputs/*
!analysis/inputs/pokebench-v1-protocol.json
!analysis/inputs/pokebench-development.json
!analysis/inputs/tactical-reliability-v042.json
!analysis/inputs/decision-suite-v044-development.json
"""


def stage(source, output):
    source = source.resolve()
    output = output.resolve()
    if output == source or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError("Public output must be separate from the working manuscript")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be absent or empty, no existing files will be overwritten")
    for name in FILES:
        path = source / name
        if not path.is_file() or not path.resolve().is_relative_to(source):
            raise ValueError("Missing or external source: " + name)
        if name.endswith(".json"):
            content = path.read_text()
            if any(value in content for value in ("/home/", "/Users/", "/tmp/", "data:image/", "Bearer ")):
                raise ValueError("Public JSON contains a private path or embedded payload: " + name)
            json.loads(content)
    output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in FILES:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / ".gitignore").write_text(IGNORE)
    hashes[".gitignore"] = hashlib.sha256(IGNORE.encode()).hexdigest()
    manifest = {
        "schema_version": 1,
        "kind": "PokeBench public paper package",
        "files": hashes,
        "excluded": ["archives", "private audit inputs", "game assets", "save states", "images", "account logs", "build caches"],
        "evidence_status": "development-only, controlled release results pending",
    }
    (output / "PUBLIC-FILES.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = stage(args.source, args.output)
    print("Staged " + str(len(result["files"])) + " reviewed files")


if __name__ == "__main__":
    main()
