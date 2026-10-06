# PokeBench public website

The public website has one leaderboard and one benchmark explorer. It is a
static export, independent of the local portal and its private experiment
archive. A benchmark has a stable detail page with exact model identifiers,
harness versions, collection dates, outcomes and replay links.

## Build a new snapshot

Run from the repository root after publishing the local comparison feed:

```sh
PYTHONPATH=src .venv/bin/python scripts/export_public_site.py \
  --feed data/reviews/pokemon-benchmarks.json \
  --config data/portal-config.json \
  --output data/public-site-2026-10-05
```

The destination must be new. Add `--report paper/pokebench-technical-report.pdf`
only after reviewing the paper and its PDF metadata for publication. The
exporter does not audit arbitrary PDF attachments.

The export is labeled development evidence. It does not claim that historical
runs constitute a frozen release evaluation. The current main analysis and the
latest pilot results for otherwise unrun tasks are included. The full local
archive remains untouched.

## Published data

- Numeric outcomes, token usage, estimated credits and timing.
- Exact model, provider, harness, effort, collection date and selected protocol settings.
- Source, prompt and starting-state checksums.
- Reencoded game screenshots without embedded image metadata.
- Fast decision-boundary replays containing executed gamepad actions.
- Results JSON and CSV, benchmark permalinks, methodology and a report link.
- A manifest of SHA-256 checksums and byte counts for every exported file.

The exporter constructs data using explicit field allowlists. It never copies
local replay HTML, raw notes, prompts, provider transcripts, account session
identifiers, credentials, ROMs, emulator states or generated game catalogs.
Known private path and credential markers fail closed. A replay must match its
scored model, source attempt and outcome, and its source must have recorded
replay verification. Public replay pages are regenerated from this restricted
payload. Their images are decoded and reencoded to remove PNG metadata.

Replay screenshots show decision boundaries, not every video frame. Controls
stay in place and offer 2, 8 or 20 decisions per second, arrow keys and a scrubber.
The default speed is 8 decisions per second.

## Validate and publish

```sh
uv run --locked --offline pytest -q tests/test_public_site.py tests/test_portal.py
uv run --locked --offline ruff check .
python3 -m http.server 8943 --bind 127.0.0.1 --directory data/public-site-2026-10-05
```

Before publication, review the generated manifest, representative pages and
replays, and the technical report. Verify that every local hyperlink resolves
inside the export and that files match their manifest checksums. The generated
`.nojekyll` file supports GitHub Pages. Upload only the export directory, never
`data/reviews`, the entire repository's `data` folder or any raw run directory.

Use the existing repository's GitHub Pages with the verified `afk-sapien`
identity. Deployment is separate from export. No credentials or authenticated
Git operations are performed by the exporter.

## Controlled release panel

Add `--release-root data/pokebench-v1` after that directory contains the frozen
`protocol.json` and its `release-summary.json`. The exporter verifies their
checksum binding and the complete registered model, task and variant matrix.
It publishes allowlisted derivatives as `release-protocol.json` and
`release-summary.json`. The original protocol checksum identifies the source,
while the export manifest hashes the sanitized public derivative.

The controlled evaluation is the main leaderboard. The earlier development
ranking and cost estimates are collapsed below it. There is still no suite selector. It displays
verified coverage, observed passes, pending work, infrastructure errors and the
shared execution ceiling. Budget-paused attempts remain pending, never losses.
The full registered per-attempt maximum is shown separately from the execution
ceiling. Registering a large matrix does not authorize spending its full maximum.

The frozen full-suite score remains unavailable until every eligible
task has every registered model and starting variant finished with a verified
replay. Scores are recomputed from attempts rather than trusted from a summary
score field. Experimental tasks remain excluded.

The reporting policy `shared-starts-equal-task-weight-v1` adds a provisional
partial-suite rank without changing the frozen protocol or its final score.
Include a task and start pair only when every registered model has a finished
attempt with a verified replay, boolean outcome and complete token accounting.
Average outcomes across those shared starts within each task, then average
included task scores equally. Do not weight tasks by their number of shared
starts. Equal scores share a rank with no token-based tiebreaker. If no starts
qualify, show every model with pending scores and no rank.

Missing, errored and unverified attempts exclude that start for every model.
Actual gameplay losses count. Selection depends on completion, never outcome,
but completion patterns can still bias early rankings. Show the exact tasks and
start numbers alongside the coverage and label the result provisional. This is
not evidence of overall ability across the unrun suite or a statistically
established difference. Export the subset and scores under `provisional` in
`release-summary.json` and provide `release-leaderboard.csv`.

The progress publisher loads presentation code from its source checkout while
the evaluation workers retain the immutable gameplay runtime. Restart the
publisher after a reporting change. Never edit the frozen runtime to change
the website.

Development task links and replays remain available until controlled replay
publication is added.
