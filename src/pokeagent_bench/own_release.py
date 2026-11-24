"""Send a run back to the release that started it.

A run resumes only on the exact source, Core and emulator it started on, because another build may change
what a task allows or how it scores. Each manifest records its release, so a newer build that refuses a
run can print the command that continues it on its own release.
"""
import json
import os
from pathlib import Path
import shlex
import sys

from .core import _build_name, core_provenance, emulator_provenance, validate_emulator_manifest

REPOSITORY = 'git+https://github.com/afk-sapien/pokebench'
STOPPED = ('finished', 'evaluation_error')


class OtherRelease(ValueError):
    """A run made by another build. tag names its release, or is None when that build is no release."""

    def __init__(self, message, tag=None):
        super().__init__(message)
        self.tag = tag


def install(tag):
    return f'{REPOSITORY}@{tag}'


def release():
    """This build's release, recorded in each new manifest. None when the source is no accepted release."""
    from .submission import ENTRY_KEYS, accepted_harness, this_harness
    here = this_harness()
    if any(all(entry[key] == here[key] for key in ENTRY_KEYS) for entry in accepted_harness()):
        tag = 'v' + here['package_version']
        return {'tag': tag, 'install': install(tag)}
    return None


def run_release(manifest):
    """The tag of the release that made a run. Runs from before the release field match an accepted entry."""
    recorded = manifest.get('release')
    if isinstance(recorded, dict) and isinstance(recorded.get('tag'), str) and recorded['tag']:
        return recorded['tag']
    from .submission import ENTRY_KEYS, accepted_harness
    for entry in accepted_harness():
        if all(manifest.get(key) == entry[key] for key in ENTRY_KEYS):
            return 'v' + entry['package_version']
    return None


def differences(manifest):
    """The parts of source, Core and emulator where a run's manifest and this build differ."""
    from .submission import this_harness
    found = []
    if manifest.get('source_sha256') != this_harness()['source_sha256']:
        found.append('source')
    core, here = manifest.get('core'), core_provenance()
    if core != here:
        version = core.get('version') if isinstance(core, dict) else None
        found.append(f'Core (run {version}, here {here["version"]})')
    try:
        validate_emulator_manifest(manifest)
    except ValueError:
        found.append(f'emulator exact runtime fingerprint (run {_build_name(manifest.get("emulator"))}, '
                     f'here {_build_name(emulator_provenance())})')
    return found


def command(tag, words=None):
    """The same command, run on the release tag."""
    words = sys.argv[1:] if words is None else list(words)
    return shlex.join(['uvx', '--from', install(tag), 'pokebench', *words])


def refusal(manifest, subject='This run', missing=None):
    """The refusal for a run this build cannot continue exactly, or None when it can.

    missing names a Claude Code build the run needs and this machine lacks.
    """
    found = differences(manifest)
    if not found:
        return None
    what = ' and '.join(found)
    tag = run_release(manifest)
    if tag is None:
        return OtherRelease(f'Resume requires the original manifest and exact runtime source. {subject} was made by '
                            f'a build that is not a release and differs from this one in its {what}. '
                            'Check out that build to resume it')
    text = (f'{subject} was made by {tag} and differs from this build in its {what}. '
            'A run resumes only on the build that started it.')
    if missing:
        text += f' {missing}. Then run the same command on {tag}:'
    else:
        text += f' Run the same command on {tag}:'
    return OtherRelease(f'{text}\n  {command(tag)}', tag)


def cli_missing(manifest, data):
    """Name the Claude Code build a run used when neither a pinned copy nor PATH has it. None otherwise."""
    agent = manifest.get('agent') if isinstance(manifest.get('agent'), dict) else {}
    recorded = agent.get('cli_version')
    if agent.get('provider') != 'claude-code' or not isinstance(recorded, str) or not recorded.split():
        return None
    version = recorded.split()[0]
    data = Path(data).resolve()
    for root in (data, data.parent):
        if os.access(root / 'toolchains' / f'claude-{version}' / 'bin' / 'claude', os.X_OK):
            return None
    from . import claude_provider
    if claude_provider.installed_version() == version:
        return None
    return (f'It needs Claude Code {version}, which is neither pinned here nor on PATH. Copy that build to '
            f'{data / "toolchains" / f"claude-{version}" / "bin" / "claude"}')


def check_run(output, data=None):
    """Refuse before any work when a task this command would resume cannot resume on this build.

    The refusal names the run's own release and the command for it. With data, it also names a Claude Code
    build a task needs and this machine lacks. A provider error stop made by a build that is no release is
    left to recover, which reports it and goes on, as before.
    """
    from .catalog_batch import report, resumable
    output = Path(output)
    for row in report(output)['cells']:
        folder = output / row['id']
        if not (folder / 'recovery.json').is_file() or not (folder / 'manifest.json').is_file():
            continue
        stopped = row['state'] in STOPPED
        if stopped and not resumable(folder):
            continue
        manifest = json.loads((folder / 'manifest.json').read_text())
        missing = None if data is None else cli_missing(manifest, data)
        other = refusal(manifest, row['task_id'], missing)
        if other is not None and (other.tag is not None or not stopped):
            raise other
        if other is None and missing:
            raise ValueError(f'{row["task_id"]} cannot resume here. {missing}, then run the same command again')
