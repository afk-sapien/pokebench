"""Inspect local Codex context. This command never requests model inference.

The debug command does not support exec's --ignore-user-config option. Its
rendered context is diagnostic, not an exact billable-token preview.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from pokeagent_bench.codex_provider import CodexProvider


def audit(model):
    provider = CodexProvider(model)
    with TemporaryDirectory(prefix='pokeagent-audit-') as temporary:
        directory = Path(temporary)
        instructions = directory / 'benchmark.md'
        instructions.write_text(provider.prompt)
        command = [provider.executable, 'debug', 'prompt-input',
                   '--disable', 'shell_tool', '--disable', 'multi_agent', '--disable', 'skill_search',
                   '--disable', 'apps', '--disable', 'plugins', '--disable', 'personality',
                   '-c', 'model=' + json.dumps(model), '-c', 'web_search="disabled"',
                   '-c', 'project_doc_max_bytes=0', '-c', 'sandbox_mode="read-only"',
                   '-c', 'approval_policy="never"', '-c', 'model_instructions_file=' + json.dumps(str(instructions)),
                   'Inspect the supplied observation and return the next controller batch.']
        process = subprocess.run(command, env=provider.env, cwd=directory, text=True,
                                 capture_output=True, check=True, timeout=30)
        items = json.loads(process.stdout)
        context_chars = sum(len(content.get('text', '')) for item in items for content in item.get('content', []))
    catalog = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'models_cache.json'
    default_chars = None
    if catalog.exists():
        for item in json.loads(catalog.read_text()).get('models', []):
            if item.get('slug') == model:
                default_chars = len(item.get('model_messages', {}).get('instructions_template', '')) or None
    return {'model': model, 'cli_version': provider.cli_version, 'model_calls': 0,
            'default_coding_template_characters': default_chars,
            'benchmark_instructions_characters': len(provider.prompt),
            'local_debug_context_characters': context_chars,
            'is_token_count': False,
            'limitations': 'Debug uses user configuration. Counts exclude game payload, images, tool schemas, and server additions.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.model), indent=2))
