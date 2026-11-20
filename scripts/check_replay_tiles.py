"""Check that new format 3 replays show the same screens and steps as the published format 2 pages.

For each published replays/<name>.html page this reads the page's own data, cuts its screens
out of the sprite sheets with Pillow and runs the page's own reader in Node. For the new
replays/<name>.gz it runs the decoder from the new replays/view.html in Node. It then compares
the RGBA pixels of every screen, every step field and every other header field, and checks
that the page at the old address is the stub that opens the viewer.
"""
import argparse
import base64
import hashlib
import io
import json
from multiprocessing import Pool
from pathlib import Path
import re
import shutil
import subprocess
import sys

from PIL import Image

from pokeagent_bench.public_site import replay_stub

DATA = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)
PNG = 'data:image/png' + chr(59) + 'base64,'
NODE = shutil.which('node')

# Runs the published page's own unpack() and turns each screen reference back into a frame number.
OLD_READER = r'''
const page = require('fs').readFileSync(process.argv[1], 'utf8')
const data = JSON.parse(page.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1])
const code = page.slice(page.indexOf('function unpack() {'), page.indexOf('const steps = unpack()'))
const f = data.frames
const number = ref => f.sheets.indexOf(ref.src) * f.per_sheet + ref.y / f.height * f.columns + ref.x / f.width
const steps = new Function('data', code + '\nreturn unpack()')(data)
console.log(JSON.stringify(steps.map(s => ({...s, before: number(s.before), after: number(s.after)}))))
'''

# Runs the new viewer's decoder on one replay file.
NEW_READER = r'''
const hash = bytes => require('crypto').createHash('sha256').update(bytes).digest('hex')
inflate(new Uint8Array(require('fs').readFileSync(process.argv[1]))).then(bytes => {
  const {data, frame} = parse(bytes)
  const frames = Array.from({length: data.frames.count}, (_, n) => hash(frame(n)))
  console.log(JSON.stringify({data, steps: unpack(data), frames}))
})
'''


def node(script, path):
    return json.loads(subprocess.run([NODE, '-e', script, str(path)], capture_output=True, check=True).stdout)


def old_screens(frames):
    """Return the sha256 of each screen's RGBA pixels and whether every sheet pixel is opaque."""
    hashes, opaque = [], True
    if len(frames['sheets']) != -(-frames['count'] // frames['per_sheet']):
        raise ValueError('Sheets do not match the screen count')
    for k, value in enumerate(frames['sheets']):
        if not value.startswith(PNG):
            raise ValueError('Sheet is not a PNG')
        with Image.open(io.BytesIO(base64.b64decode(value[len(PNG):], validate=True))) as image:
            sheet = image.convert('RGBA')
        opaque = opaque and sheet.getchannel('A').getextrema() == (255, 255)
        for slot in range(min(frames['per_sheet'], frames['count'] - k * frames['per_sheet'])):
            left = slot % frames['columns'] * frames['width']
            top = slot // frames['columns'] * frames['height']
            screen = sheet.crop((left, top, left + frames['width'], top + frames['height']))
            hashes.append(hashlib.sha256(screen.tobytes()).hexdigest())
    return hashes, opaque


def header(data):
    return {key: value for key, value in data.items() if key not in ('format', 'frames', 'steps')}


def check(job):
    name, old_folder, new_folder, decoder = job
    page, packed = old_folder / f'{name}.html', new_folder / f'{name}.gz'
    result = {'name': name, 'old_bytes': page.stat().st_size, 'problems': []}
    problems = result['problems']
    if not packed.exists():
        problems.append('No new replay file')
        return result
    stub = new_folder / f'{name}.html'
    result['new_bytes'] = packed.stat().st_size + (stub.stat().st_size if stub.exists() else 0)
    if not stub.exists() or stub.read_text() != replay_stub(name):
        problems.append('The page at the old address is not the viewer stub')
    old = json.loads(DATA.search(page.read_text())[1])
    if old.get('format') != 2:
        problems.append(f'Published page is format {old.get("format")}')
        return result
    old_hashes, opaque = old_screens(old['frames'])
    old_steps = node(OLD_READER, page)
    new = node(decoder, packed)
    new_hashes, new_steps = new['frames'], new['steps']
    frames = new['data']['frames']
    result.update(screens=len(old_hashes), steps=len(old_steps), tiles=frames['tiles'],
                  colours=len(frames['palette']), same_order=old_hashes == new_hashes)
    if not opaque:
        problems.append('A published sheet has transparent pixels')
    if (frames['width'], frames['height']) != (old['frames']['width'], old['frames']['height']):
        problems.append('Screen size differs')
    if sorted(old_hashes) != sorted(new_hashes):
        problems.append(f'Screens differ: {len(set(old_hashes) ^ set(new_hashes))} not in both')
    if header(old) != header(new['data']):
        keys = sorted(k for k in header(old).keys() | header(new['data']).keys()
                      if header(old).get(k) != header(new['data']).get(k))
        problems.append(f'Header fields differ: {keys}')
    if len(old_steps) != len(new_steps):
        problems.append(f'Step count differs: {len(old_steps)} published, {len(new_steps)} new')
    for i, (a, b) in enumerate(zip(old_steps, new_steps)):
        for side in ('before', 'after'):
            if old_hashes[a[side]] != new_hashes[b[side]]:
                problems.append(f'Step {i} {side} screen differs')
        rest = {k for k in a.keys() | b.keys() if k not in ('before', 'after') and a.get(k) != b.get(k)}
        if rest:
            problems.append(f'Step {i} fields differ: {sorted(rest)}')
        if len(problems) > 20:
            problems.append('Stopped after 20 problems')
            break
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--old', required=True, type=Path, help='Published replays folder with format 2 pages')
    parser.add_argument('--new', required=True, type=Path, help='New replays folder with view.html and .gz files')
    parser.add_argument('--out', required=True, type=Path, help='JSON report to write')
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('names', nargs='*', help='Only these replays (default: every published page)')
    args = parser.parse_args()
    if not NODE:
        sys.exit('Node is not installed')
    viewer = (args.new / 'view.html').read_text()
    decoder = viewer[viewer.index('// replay decoder begin'):viewer.index('// replay decoder end')] + NEW_READER
    pages = sorted(args.old.glob('*.html'), key=lambda p: -p.stat().st_size)
    names = args.names or [p.stem for p in pages]
    extra = sorted({p.stem for p in args.new.glob('*.gz')} - {p.stem for p in pages}) if not args.names else []
    with Pool(args.workers) as pool:
        results = list(pool.imap_unordered(check, [(n, args.old, args.new, decoder) for n in names]))
    results.sort(key=lambda r: r['name'])
    bad = [r for r in results if r['problems']]
    summary = {
        'replays': len(results), 'match': len(results) - len(bad), 'new_without_published_page': extra,
        'screens': sum(r.get('screens', 0) for r in results), 'steps': sum(r.get('steps', 0) for r in results),
        'same_screen_order': sum(bool(r.get('same_order')) for r in results),
        'published_bytes': sum(r['old_bytes'] for r in results),
        'new_bytes': sum(r.get('new_bytes', 0) for r in results) + len(viewer.encode()),
    }
    args.out.write_text(json.dumps({'summary': summary, 'replays': results}, indent=1) + '\n')
    print(json.dumps(summary))
    for r in bad:
        print(r['name'], r['problems'][:3])
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
