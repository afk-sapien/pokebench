# PokeBench technical report

This is a paper-style technical report built with public
[Paper Scaffold](https://github.com/pgarrett-scripps/paper-scaffold), version 5.3.2,
pinned to commit `c9cb1046d710b3fab851e9984b23254b82a031bc`.
The upstream MIT notice remains in `LICENSE.scaffold`.

The main report describes the current gameplay contract and audited development
evidence. It does not claim the pending frozen release evaluation has completed.
The previous manuscript sources, result declarations, and generators are retained
under `archive/pre-release-development`. Existing audit inputs remain unchanged.

## Rebuild

From this directory:

```bash
uv sync --locked
uv run paper sync --check
just assets
just paper
just verify
```

`paper.pdf` is the compiled report. Results in prose use scaffold statistic IDs.
Tables are generated, not hand edited.

To intentionally freeze a new audited development snapshot:

```bash
uv run python analysis/scripts/export_release_snapshot.py \
  --combined ../data/reviews/pokemon-benchmarks-combined.json \
  --pilot-audit ../data/decision-v1-pilot/final-audit.json \
  --output analysis/inputs/pokebench-development.json
just assets
just paper
just verify
```

The export has an explicit field allowlist. It contains no ROMs, states, images,
prompts, responses, private paths, or credentials. Hashes provide provenance,
not independent attestation. Exporting and building do not trigger model runs.

Before public release, populate the frozen release section from its registered
attempts and retain infrastructure errors, missing usage, and retry history.
Do not substitute historical development rankings for release results.

## Public source package

`export_public.py` stages an exact file allowlist. It excludes the historical
archive, older audit inputs, caches, account artifacts, game assets, and all
screenshots. It preserves the pinned scaffold files, license, active sanitized
inputs, generators, source manuscript, and compiled PDF. The output must be new
or empty. It never publishes or modifies the working manuscript.

```bash
uv run python export_public.py --output /tmp/pokebench-public-source/paper
```

`PUBLIC-FILES.json` records every copied file hash. Rebuild the paper before
staging it. The complete historical archive is retained only in the working
repository and is intentionally absent from this public source package.


The prospective beta protocol is frozen in
`analysis/inputs/pokebench-v1-protocol.json`. Its canonical checksum is
`99c4e3a7dfbc0598d2be7c2f75201a08efeb7c63ba7b617da30bc4c7ad2a6d05`.
The registered matrix has 16 models, 28 tasks, three starting variants, and
1,344 planned attempts. The approved aggregate cap is 50 million reported
tokens. The sum of per-attempt thresholds is 1.26 billion tokens. The matrix
therefore represents staged collection, with incomplete coverage reported
explicitly. Controlled release results are pending.
