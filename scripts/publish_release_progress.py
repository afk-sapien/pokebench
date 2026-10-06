"""Refresh sanitized release results and optionally publish a reviewed Pages checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

# Publishing uses current presentation code, independently of the frozen gameplay runtime.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from pokeagent_bench.public_site import export_public, public_text
from pokeagent_bench.core import digest, encoded
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


def execution_note(root, output):
    paths = sorted(root.glob('execution-amendment-*.json'))
    if not paths:
        return
    amendments = []
    allowed = {'format', 'protocol_sha256', 'created_at', 'scheduler_sha256', 'previous_batch_sha256',
               'workers', 'per_provider_limit', 'effective_after_finished', 'resumed_cells',
               'policy', 'timing', 'failure_policy', 'sha256', 'quarantined_cells'}
    for path in paths:
        value = read(path)
        if set(value) - allowed or digest(encoded({k:v for k,v in value.items() if k != 'sha256'})) != value['sha256']:
            raise ValueError('Unexpected execution amendment')
        public_text(json.dumps(value), maximum=10000)
        if value['protocol_sha256'] != read(root / 'protocol.json')['sha256']:
            raise ValueError('Execution amendment refers to another protocol')
        amendments.append(value)
    latest = amendments[-1]
    if type(latest['workers']) is not int or not 1 <= latest['workers'] <= 4:
        raise ValueError('Invalid worker count')
    holds = sum(c['budget_hold_tokens'] for a in amendments for c in a.get('quarantined_cells', []))
    note = ('<p><strong>Parallel execution:</strong> Up to ' + str(latest['workers']) +
            ' trials at once, with at most ' + str(latest['per_provider_limit']) +
            ' per provider. One shared 50M token allowance. Timing is not directly comparable across the scheduling change. ' +
            ('Reviewed error holds retain ' + format(holds, ',') + ' tokens against that allowance. Missing usage remains unreported. ' if holds else '') +
            '<a href="execution-amendments.json">Execution amendments</a>.</p>')
    target = output / 'index.html'
    target.write_text(target.read_text().replace('<h3>Collection progress</h3>', '<h3>Collection progress</h3>' + note))
    (output / 'execution-amendments.json').write_text(json.dumps(amendments, indent=2) + '\n')
    manifest = read(output / 'manifest.json')
    manifest['files'] = [{'path': str(p.relative_to(output)), 'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
                         for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'manifest.json']
    (output / 'manifest.json').write_text(json.dumps(manifest) + '\n')


def refresh(args):
    summary = read(args.root / 'release-summary.json')
    with tempfile.TemporaryDirectory(prefix='pokebench-site-') as temporary:
        output = Path(temporary) / 'site'
        export_public(args.feed, args.config, output, args.report, args.root)
        execution_note(args.root, output)
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
