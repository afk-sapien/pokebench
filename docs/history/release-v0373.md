# Fixture path in Long bundles v0.37.3

This tag is package 0.37.3, git tag `v0.37.3`, under the same harness name `red-v0.63-short-guard`. The task specs, the start states, the fixture pack, the prompts, the run limits and the way a run is played and scored are those of `v0.37.2`. PokeSim Core 0.12.0, PyBoy RS 0.1.5 and Claude Code 2.1.323 stay pinned.

## What was wrong

Every Long run on `v0.37.0` to `v0.37.2` finished but could not be packed.

1. The maintainer step that rebound the catalog records where each rebuilt fixture came from, in `catalog_rebind.source`. For `campaign-full-game` and `objectives-find-capture-species` that folder sits next to the fixture root and its name starts with the root's name.
2. The fixture pack swaps the root for a token by plain text replacement, so that source became the token followed by `-source/...`.
3. `setup` filled the token wherever it appeared. That wrote the user's own folder, plus `-source`, into both scenarios.
4. A run copies its scenario into its manifest. The privacy scan in `submit` then found the absolute path and stopped the Long bundle. Short holds neither task, so its bundles were not affected.
5. `verify` compared the whole scenario with the verifier's own fixture, so a Long bundle from another machine would also have failed there.

## What changes

1. `setup` fills the token only where it stands for the whole fixture folder. The glued `-source` text is left as it is, so no local path is written. The fixture pack is unchanged.
2. `submit` leaves `catalog_rebind.source` out of each manifest. It only records where a fixture was rebuilt.
3. `verify` compares the scenario without that one field. Every other field, `catalog_rebind.previous_catalog_sha256` and `catalog_rebind.state_unchanged` among them, must still match the benchmark fixture.
4. The privacy scan is unchanged. A home path anywhere else in a manifest still stops the bundle.

## Runs from v0.37.1 and v0.37.2

Their entries stay in [accepted_harness.json](../../src/pokeagent_bench/accepted_harness.json). A finished Long run from either packs on `v0.37.3` with no rerun. Run its `enter` command again with `@v0.37.3`. A setup made before `v0.37.3` can keep its fixture folder. The path in it never reaches the bundle.
