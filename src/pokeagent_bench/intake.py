"""Maintainer intake of one submission issue. It reads the issue with gh, downloads the attached bundle into a
new empty folder, verifies it and drafts a reply as a file. It never posts the reply, never adds the site row
and never publishes anything. The issue and the bundle are untrusted input."""
import json
from pathlib import Path
import re
import subprocess
import urllib.request
import zipfile

from .submission import ATTACHMENT_LIMIT, LABEL, harness_accepted, harness_refusal, this_harness, verify

REPO = 'afk-sapien/pokebench'
LINK = re.compile(r'https://github\.com/(?:user-attachments/files|[A-Za-z0-9-]+/[A-Za-z0-9._-]+/files)'
                  r'/\d+/([^\s()<>\[\]"\'`]+)')
BUNDLE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.pokebench\.zip')
FIELDS = {'model id': 'model', 'provider': 'provider', 'suite (short or long)': 'suite'}
FIELD = re.compile(r'^\s*-\s*(Model id|Provider|Suite \(short or long\))\s*:[ \t]*(.*)$', re.I | re.M)
CHUNK = 1 << 20


def read_issue(number, repo, run=subprocess.run):
    """Read the issue. gh issue view only reads."""
    try:
        done = run(['gh', 'issue', 'view', str(number), '--repo', repo,
                    '--json', 'number,title,body,author,state,url'], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise ValueError('intake reads the issue with the GitHub CLI. Install gh and run gh auth login') from None
    if done.returncode:
        raise ValueError(f'gh could not read issue {number} of {repo}: {done.stderr.strip()}')
    return json.loads(done.stdout)


def bundle_link(body):
    """The one .pokebench.zip attachment the issue links. Only GitHub attachment links count."""
    found = {match.group(0): match.group(1) for match in LINK.finditer(body or '')}
    bundles = {url: name for url, name in found.items() if BUNDLE.fullmatch(name)}
    if not bundles:
        raise ValueError('The issue has no .pokebench.zip file attached')
    if len(bundles) > 1:
        raise ValueError('The issue links more than one bundle. Attach one bundle per issue')
    url, name = next(iter(bundles.items()))
    return url, name


class HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('The attachment link redirected away from https')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, target, limit=ATTACHMENT_LIMIT, opener=None):
    """Stream the attachment to a new file and stop past the size limit. No GitHub token is sent."""
    opener = opener or urllib.request.build_opener(HttpsOnly)
    request = urllib.request.Request(url, headers={'User-Agent': 'pokebench-intake'})
    written = 0
    with opener.open(request, timeout=60) as response:
        size = response.headers.get('Content-Length')
        if size and size.isdigit() and int(size) > limit:
            raise ValueError(f'The attachment is larger than {limit / 1e6:.0f} MB')
        with open(target, 'xb') as handle:
            while chunk := response.read(CHUNK):
                written += len(chunk)
                if written > limit:
                    break
                handle.write(chunk)
    if written > limit:
        Path(target).unlink()
        raise ValueError(f'The attachment is larger than {limit / 1e6:.0f} MB. The download was stopped')
    return written


def check_type(path):
    """Refuse anything that is not a zip before verify reads it."""
    with open(path, 'rb') as handle:
        head = handle.read(4)
    if head != b'PK\x03\x04' or not zipfile.is_zipfile(path):
        raise ValueError('The attachment is not a zip file')


def new_folder(folder):
    folder = Path(folder)
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        raise ValueError(f'{folder} is not empty. Pick a new folder with --folder')
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def code(text, limit=200):
    """Untrusted text as an inline code span, so it cannot add links, mentions or formatting to the reply."""
    text = re.sub(r'[`\s]+', ' ', str(text)).strip()[:limit]
    return f'`{text}`' if text else '`(empty)`'


def result_lines(report):
    row = report.get('summary') or {}
    lines = [f'- Model: {code(report["model"], 100)} through {code(report["provider"], 40)}',
             f'- Suite: {report["suite"].capitalize()}',
             f'- Submitted by: {code(report["handle"]) if report.get("handle") else "no handle given"}']
    if row.get('available_category_average') is not None:
        lines.append(f'- Score: {100 * row["available_category_average"]:.1f} of 100')
    for run in row.get('campaign_runs', []):
        if run.get('campaign'):
            lines.append(f'- Campaign: {run["campaign"]["points"]} of {run["campaign"]["maximum_points"]} points')
    return lines


def draft_reply(report, refusal):
    """The reply text for the owner to read. It is never posted by this command."""
    if refusal is not None:
        return '\n'.join([
            'Thanks for the submission. The bundle could not be checked.', '',
            f'Reason: {code(refusal, 300)}', '',
            'Nothing was added to the site. SUBMITTING.md shows how to pack a bundle with `pokebench submit` '
            'and attach it. Please attach a new bundle here.', ''])
    harness = report['harness']
    release = f'{code(harness.get("benchmark"), 80)}, package {code(harness.get("package_version"), 40)}'
    if not report['verified']:
        problems = report['problems']
        return '\n'.join([
            f'Thanks for the submission. The bundle did not verify on {release}. '
            f'{len(problems)} problem(s) were found:', '',
            *[f'- {code(problem, 300)}' for problem in problems[:20]],
            *(['- and more'] if len(problems) > 20 else []), '',
            'Nothing was added to the site. Please check that you ran the release named in SUBMITTING.md '
            'from an unchanged install, run the suite again and attach the new bundle.', ''])
    if report['suite'] == 'smoke':
        return '\n'.join([
            f'Thanks for trying the submission path. Your smoke bundle replayed and verified on {release}, '
            'so your setup works.', '',
            'The smoke suite is a setup check and is never a leaderboard result. Run the Short or Long suite '
            'with your model and attach that bundle in a new issue.', ''])
    replayed = sum(cell.get('replay_verified') is True for cell in report.get('cells', []))
    return '\n'.join([
        f'Thanks for the submission. The bundle replayed and verified on {release}. '
        f'All {replayed} runs matched their logs from the benchmark start states.', '',
        *result_lines(report), '',
        f'The row will appear on the site labeled "{LABEL}" at the next site update. '
        'These parts are self reported and not checked: ' + ', '.join(report['self_reported']) + '.', ''])


def owner_notes(issue, report):
    """Things for the owner to look at before adding the row. Printed, never posted."""
    author = (issue.get('author') or {}).get('login') or 'unknown'
    notes = [f'Issue #{issue.get("number")} by {author}, state {issue.get("state")}: {issue.get("url")}']
    if report is None:
        return notes
    notes.append(f'Bundle SHA-256 {report["bundle_sha256"]}')
    if report.get('handle') and report['handle'].lower() != author.lower():
        notes.append(f'The bundle handle {report["handle"]!r} is not the issue author {author!r}.')
    for label, value in FIELD.findall(issue.get('body') or ''):
        key, value = FIELDS[label.lower()], value.strip()
        if value and value.lower() != str(report.get(key)).lower():
            notes.append(f'The issue says {label.lower()} {value[:80]!r} but the bundle says {report.get(key)!r}.')
    return notes


def intake(number, rom, fixtures, folder=None, *, repo=REPO, run=subprocess.run, fetch=download, check=verify):
    """Fetch, check and draft. Posts nothing and adds no row. Returns None so the CLI prints only the steps."""
    if not harness_accepted(this_harness()):
        raise ValueError(harness_refusal(this_harness(), 'Verification runs on an accepted release. This checkout is'))
    folder = new_folder(folder or f'intake-{number}')
    issue = read_issue(number, repo, run)
    report, refusal, bundle = None, None, None
    try:
        url, name = bundle_link(issue.get('body'))
        bundle = folder / name
        print(f'Downloading {name} into {folder}', flush=True)
        fetch(url, bundle)
        check_type(bundle)
        report = check(bundle, rom, fixtures, None)
    except ValueError as error:
        refusal = str(error)
        print(f'Refused: {refusal}', flush=True)
    reply = folder / 'reply.md'
    reply.write_text(draft_reply(report, refusal))
    lines = ['', *owner_notes(issue, report), '', 'Nothing was posted, added or published.',
             f'Read the draft reply: {reply}']
    if report and report['verified'] and report['suite'] in ('short', 'long'):
        verified = bundle.with_name(bundle.name.removesuffix('.zip') + '.verified.json')
        lines += ['If you agree, add the row to your local site data:',
                  f'  pokebench community-add {verified} --web WEB_FOLDER']
    lines += ['To post the reply yourself:', f'  gh issue comment {number} --repo {repo} --body-file {reply}']
    print('\n'.join(lines), flush=True)
    return None
