# Release checklist for a frozen harness

Community submissions are accepted only from a frozen release. A release is frozen when its entry is in [accepted_harness.json](../src/pokeagent_bench/accepted_harness.json). While that list is empty, `submit` and `verify` refuse every run.

Do these in order, on the commit that will be tagged.

1. Bump the package version in `pyproject.toml` and `src/pokeagent_bench/__init__.py`, and set `BENCHMARK_VERSION` if the harness name changes. Run `uv lock`.
2. If any task spec or start state changed, rebuild the fixture pack with `local_setup.build_pack(rom, fixtures, output)` and commit it. Run `uv run pokebench setup --rom /path/to/red.gb` on a clean checkout to confirm the pack opens.
3. Print this checkout's harness entry and paste it into the `accepted` list. Do this last among code changes, because any change to a `.py` file in the package changes the source hash. Editing the JSON file does not.

   ```sh
   uv run python -c "import json; from pokeagent_bench.submission import this_harness; print(json.dumps(this_harness(), indent=2))"
   ```

4. Run `uv run ruff check .` and `uv run pytest`. Then run a smoke suite, `submit` it and `verify` the bundle. A passing `verify` shows the entry matches the checkout.
5. Commit, tag the commit with the package version and push the tag. Name the tag in [SUBMITTING.md](../SUBMITTING.md) so submitters know what to check out.

## What an entry holds

Every entry needs all three values, and a run manifest must match all three.

- `benchmark`, the harness name, for example `red-v0.61-fair-harness`.
- `package_version`, the package version.
- `source_sha256`, a hash over every `.py` file at the top level of the package. A development build that keeps the same names but changes any of that code has a different hash and is refused.

The hash does not cover the fixture pack, the task catalogs or the lock file. Start states and task definitions are checked separately, because `verify` compares their hashes in a bundle with the verifier's own suite.

## Later changes

Development after the tag changes the source hash, so `main` stops matching the entry. That is intended. Submitters and verifiers check out the tag. To accept a newer release, add its entry. Remove an old entry only when runs from it should no longer be accepted.
