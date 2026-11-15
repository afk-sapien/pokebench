from pathlib import Path
import re

from pokeagent_bench import __version__

ROOT = Path(__file__).resolve().parents[1]
DOCS = ['README.md', 'SUBMITTING.md', 'src/pokeagent_bench/showcase_assets/index.html']
PIN = re.compile(r'git\+https://github\.com/afk-sapien/pokebench@v(\d+)\.(\d+)\.(\d+) pokebench')


def test_every_uvx_line_names_one_tag_no_older_than_the_package():
    tags = {name: set(PIN.findall((ROOT / name).read_text())) for name in DOCS}
    assert all(tags.values()), f'a file has no pinned uvx line: {tags}'
    found = set().union(*tags.values())
    assert len(found) == 1, f'the docs name different tags: {tags}'
    package = tuple(int(part) for part in __version__.split('.'))
    assert tuple(int(part) for part in found.pop()) >= package


def test_each_doc_says_which_release_to_run_and_that_the_rom_is_yours():
    for name in ['README.md', 'SUBMITTING.md']:
        text = (ROOT / name).read_text()
        tag = 'v' + '.'.join(PIN.search(text).groups())
        assert f'release `{tag}`' in text
        assert 'your own Pokemon Red ROM' in text
        assert '--suite smoke --provider random' in text and 'never a leaderboard result' in text
    page = (ROOT / 'src/pokeagent_bench/showcase_assets/index.html').read_text()
    assert 'Bring your own Pokémon Red ROM' in page and 'never a leaderboard result' in page
