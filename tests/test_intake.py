import io
import json
import subprocess
import zipfile

import pytest

from pokeagent_bench import intake as intake_module
from pokeagent_bench.intake import (HttpsOnly, bundle_link, check_type, code, download, draft_reply, intake,
                                    new_folder, owner_notes)
from pokeagent_bench.submission import LABEL, SELF_REPORTED

URL = 'https://github.com/user-attachments/files/17000001/local-model-short.pokebench.zip'
BODY = (f'Attach the file.\n\n[local-model-short.pokebench.zip]({URL})\n\n- Model id: local-model\n'
        '- Provider: openai-compatible\n- Suite (short or long): short\n- Attempts made with this model and suite: 1\n')
HARNESS = {'benchmark': 'red-v0.61-fair-harness', 'package_version': '0.37.0', 'source_sha256': 'f' * 64}


def report(**changes):
    value = {'format': 'pokebench-verified-report-v1', 'verified': True, 'problems': [], 'label': LABEL,
             'suite': 'short', 'benchmark': 'pokebench', 'provider': 'openai-compatible', 'model': 'local-model',
             'handle': 'octocat', 'attempts_declared': 1, 'harness': HARNESS, 'bundle_sha256': 'a' * 64,
             'self_reported': list(SELF_REPORTED), 'summary': {'available_category_average': 0.425},
             'cells': [{'id': 'cell-0001', 'replay_verified': True}, {'id': 'cell-0002', 'replay_verified': True}]}
    value.update(changes)
    return value


def gh(body=BODY, author='octocat'):
    calls = []

    def run(command, **options):
        calls.append(command)
        issue = {'number': 12, 'title': 'Run submission: local-model, short', 'body': body,
                 'author': {'login': author}, 'state': 'OPEN', 'url': 'https://github.com/afk-sapien/pokebench/issues/12'}
        return subprocess.CompletedProcess(command, 0, json.dumps(issue), '')
    return run, calls


def zip_fetch(url, target):
    with zipfile.ZipFile(target, 'w') as archive:
        archive.writestr('submit.json', '{}')


@pytest.fixture
def accepted(monkeypatch):
    monkeypatch.setattr(intake_module, 'harness_accepted', lambda found: True)


def test_intake_downloads_verifies_and_drafts_a_reply_without_posting(tmp_path, accepted, capsys):
    run, calls = gh()
    seen = []

    def check(bundle, rom, fixtures, output):
        seen.append(bundle)
        return report()
    folder = tmp_path / 'intake-12'
    assert intake(12, tmp_path / 'red.gb', tmp_path / 'fixtures', folder, run=run, fetch=zip_fetch, check=check) is None
    assert calls == [['gh', 'issue', 'view', '12', '--repo', 'afk-sapien/pokebench',
                      '--json', 'number,title,body,author,state,url']]
    assert seen == [folder / 'local-model-short.pokebench.zip']
    reply = (folder / 'reply.md').read_text()
    assert 'replayed and verified' in reply and LABEL in reply and 'Score: 42.5 of 100' in reply
    assert 'All 2 runs matched' in reply
    out = capsys.readouterr().out
    assert 'Nothing was posted, added or published.' in out
    assert f'pokebench community-add {folder}/local-model-short.pokebench.verified.json --web WEB_FOLDER' in out
    assert f'gh issue comment 12 --repo afk-sapien/pokebench --body-file {folder}/reply.md' in out


def test_intake_refuses_a_folder_that_is_not_empty_before_reading_the_issue(tmp_path, accepted):
    run, calls = gh()
    folder = tmp_path / 'used'
    folder.mkdir()
    (folder / 'old.txt').write_text('x')
    with pytest.raises(ValueError, match='not empty'):
        intake(12, tmp_path / 'red.gb', tmp_path, folder, run=run, fetch=zip_fetch, check=None)
    assert calls == []


def test_intake_needs_an_accepted_release(tmp_path, monkeypatch):
    monkeypatch.setattr(intake_module, 'harness_accepted', lambda found: False)
    run, calls = gh()
    with pytest.raises(ValueError, match='accepted release'):
        intake(12, tmp_path / 'red.gb', tmp_path, tmp_path / 'new', run=run, fetch=zip_fetch, check=None)
    assert calls == [] and not (tmp_path / 'new').exists()


def test_a_file_that_is_not_a_zip_is_refused_before_verify_reads_it(tmp_path, accepted):
    run, _ = gh()

    def fetch(url, target):
        target.write_bytes(b'#!/bin/sh\necho not a bundle\n')

    def check(*args):
        raise AssertionError('verify must not read a file that is not a zip')
    intake(12, tmp_path / 'red.gb', tmp_path, tmp_path / 'in', run=run, fetch=fetch, check=check)
    reply = (tmp_path / 'in' / 'reply.md').read_text()
    assert 'could not be checked' in reply and 'not a zip file' in reply


def test_a_bundle_verify_refuses_gets_a_refusal_reply_and_no_add_step(tmp_path, accepted, capsys):
    run, _ = gh()

    def check(*args):
        raise ValueError('Bundle holds an entry that is not allowed: \'../evil\'')
    intake(12, tmp_path / 'red.gb', tmp_path, tmp_path / 'in', run=run, fetch=zip_fetch, check=check)
    assert 'not allowed' in (tmp_path / 'in' / 'reply.md').read_text()
    assert 'community-add' not in capsys.readouterr().out


def test_bundle_link_needs_exactly_one_pokebench_zip_attached_on_github():
    assert bundle_link(BODY) == (URL, 'local-model-short.pokebench.zip')
    legacy = 'https://github.com/afk-sapien/pokebench/files/123/m-long.pokebench.zip'
    assert bundle_link(f'see {legacy}') == (legacy, 'm-long.pokebench.zip')
    for body in ['', None, 'no file here', 'https://example.com/user-attachments/files/1/x.pokebench.zip',
                 'https://github.com/user-attachments/files/1/x.zip',
                 'https://github.com/user-attachments/files/1/x.pokebench.zip.exe',
                 'https://github.com/user-attachments/assets/1/x.pokebench.zip']:
        with pytest.raises(ValueError, match='no .pokebench.zip'):
            bundle_link(body)
    with pytest.raises(ValueError, match='more than one bundle'):
        bundle_link(f'{URL}\nhttps://github.com/user-attachments/files/2/other.pokebench.zip')
    assert bundle_link(f'{URL} and again {URL}') == (URL, 'local-model-short.pokebench.zip')


class Response(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {'Content-Length': str(length)} if length is not None else {}


class Opener:
    def __init__(self, response):
        self.response, self.requests = response, []

    def open(self, request, timeout):
        self.requests.append(request)
        return self.response


def test_download_streams_into_a_new_file_without_a_token(tmp_path):
    opener = Opener(Response(b'PK\x03\x04' + b'x' * 10))
    assert download(URL, tmp_path / 'b.zip', limit=100, opener=opener) == 14
    assert (tmp_path / 'b.zip').read_bytes().startswith(b'PK')
    assert 'Authorization' not in opener.requests[0].headers
    with pytest.raises(FileExistsError):
        download(URL, tmp_path / 'b.zip', limit=100, opener=Opener(Response(b'again')))


def test_download_stops_past_the_size_cap_and_keeps_nothing(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='larger than'):
        download(URL, tmp_path / 'a.zip', limit=10, opener=Opener(Response(b'x' * 5, length=11)))
    assert not (tmp_path / 'a.zip').exists()
    monkeypatch.setattr(intake_module, 'CHUNK', 4)
    with pytest.raises(ValueError, match='download was stopped'):
        download(URL, tmp_path / 'b.zip', limit=10, opener=Opener(Response(b'x' * 30)))
    assert not (tmp_path / 'b.zip').exists()


def test_redirects_must_stay_on_https():
    handler = HttpsOnly()
    with pytest.raises(ValueError, match='away from https'):
        handler.redirect_request(None, None, 302, 'Found', {}, 'http://example.com/x.zip')


def test_check_type_and_new_folder(tmp_path):
    (tmp_path / 'fake.zip').write_bytes(b'PK\x03\x04 but not really a zip')
    with pytest.raises(ValueError, match='not a zip'):
        check_type(tmp_path / 'fake.zip')
    zip_fetch(None, tmp_path / 'real.zip')
    check_type(tmp_path / 'real.zip')
    assert new_folder(tmp_path / 'a' / 'b').is_dir()
    assert new_folder(tmp_path / 'a' / 'b') == tmp_path / 'a' / 'b'
    with pytest.raises(ValueError, match='not empty'):
        new_folder(tmp_path / 'real.zip')


def test_replies_for_smoke_failed_and_long_runs():
    smoke = draft_reply(report(suite='smoke', summary={}), None)
    assert 'never a leaderboard result' in smoke and LABEL not in smoke
    failed = draft_reply(report(verified=False, problems=['cell-0001 nav: final state differs'], cells=None), None)
    assert 'did not verify' in failed and '`cell-0001 nav: final state differs`' in failed
    assert '1 problem was found:' in failed
    twice = draft_reply(report(verified=False, problems=['one', 'two'], cells=None), None)
    assert '2 problems were found:' in twice
    long = draft_reply(report(suite='long', summary={'campaign_runs': [{'campaign': {'points': 9, 'maximum_points': 1000}}]},
                              cells=[{'id': 'cell-0001', 'replay_verified': True}]), None)
    assert 'Campaign: 9 of 1000 points' in long and 'Suite: Long' in long
    # One run reads as one run, never "All 1 runs".
    assert 'The run matched its log from the benchmark start state.' in long and 'All 1' not in long


def test_untrusted_text_stays_inside_code_spans():
    assert code('a`b`\n@owner [x](http://e)') == '`a b @owner [x](http://e)`'
    assert code('') == '`(empty)`'
    reply = draft_reply(report(model='evil`\n\n@owner please merge', handle=None), None)
    assert '`evil @owner please merge`' in reply and 'no handle given' in reply
    assert '\n@owner' not in reply


def test_owner_notes_flag_mismatches_between_issue_and_bundle():
    issue = {'number': 12, 'state': 'OPEN', 'url': 'u', 'author': {'login': 'someone'},
             'body': BODY.replace('local-model', 'big-model')}
    notes = owner_notes(issue, report())
    assert any('handle' in note and 'someone' in note for note in notes)
    assert any("model id 'big-model'" in note for note in notes)
    assert not any('provider' in note for note in notes)
    assert owner_notes(issue, None) == ['Issue #12 by someone, state OPEN: u']
