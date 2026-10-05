"""Refresh sanitized release results and optionally publish a reviewed Pages checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from pokeagent_bench.public_site import export_public
from pokeagent_bench.release import read

EXPECTED = 'afk-sapien <327645577+afk-sapien@users.noreply.github.com>'
REMOTE = 'https://github.com/afk-sapien/pokebench.git'


def command(args, cwd):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def publish_checkout(path):
    if command(['git', 'remote', 'get-url', 'origin'], path) != REMOTE:
        raise ValueError('Unexpected publication repository')
    if command(['git', 'branch', '--show-current'], path) != 'gh-pages':
        raise ValueError('Publication requires the gh-pages branch')
    for role in ('GIT_AUTHOR_IDENT', 'GIT_COMMITTER_IDENT'):
        if not command(['git', 'var', role], path).startswith(EXPECTED + ' '):
            raise ValueError('Unexpected publication identity')
    if command(['gh', 'api', 'user', '--jq', '.login'], path) != 'afk-sapien':
        raise ValueError('GitHub account mismatch. Publication stopped.')
    subprocess.run(['git', 'add', '.'], cwd=path, check=True)
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=path).returncode
    if changed not in (0, 1):
        raise ValueError('Unable to inspect staged changes')
    if changed:
        subprocess.run(['git', 'commit', '-q', '-m', 'Update controlled evaluation progress'], cwd=path, check=True)
    attribution = command(['git', 'log', 'origin/gh-pages..HEAD', '--format=%an <%ae>%n%cn <%ce>'], path)
    if any(line != EXPECTED for line in attribution.splitlines()):
        raise ValueError('Unexpected attribution in unpublished commits')
    messages = command(['git', 'log', 'origin/gh-pages..HEAD', '--format=%B'], path).lower()
    if 'co-authored-by:' in messages or 'signed-off-by:' in messages:
        raise ValueError('Unexpected attribution trailer')
    subprocess.run(['git', 'push', 'origin', 'gh-pages'], cwd=path, check=True)


def refresh(args):
    summary = read(args.root / 'release-summary.json')
    with tempfile.TemporaryDirectory(prefix='pokebench-site-') as temporary:
        output = Path(temporary) / 'site'
        export_public(args.feed, args.config, output, args.report, args.root)
        for destination in (args.local_site, args.pages):
            if destination:
                destination.mkdir(parents=True, exist_ok=True)
                shutil.copytree(output, destination, dirs_exist_ok=True)
    if args.pages:
        publish_checkout(args.pages)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--feed', type=Path, default=Path('data/reviews/pokemon-benchmarks.json'))
    parser.add_argument('--config', type=Path, default=Path('data/portal-config.json'))
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--local-site', type=Path, required=True)
    parser.add_argument('--pages', type=Path)
    parser.add_argument('--watch-seconds', type=int, default=0)
    args = parser.parse_args()
    previous = None
    while True:
        summary = read(args.root / 'release-summary.json')
        # Publish when a trial finishes or the sweep changes phase, not every decision.
        signature = hashlib.sha256(json.dumps([summary['status'], summary['finished']], sort_keys=True).encode()).hexdigest()
        if signature != previous:
            summary = refresh(args)
            print(summary['status'], summary['finished'], summary['tokens'], flush=True)
            previous = signature
        if not args.watch_seconds or summary['status'] not in ('ready', 'running'):
            break
        time.sleep(max(15, args.watch_seconds))


if __name__ == '__main__':
    main()
