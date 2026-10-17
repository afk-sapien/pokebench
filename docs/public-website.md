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

The main leaderboard shows all available results. The matched-start comparison
and earlier development analysis are secondary expandable sections. There is still no suite selector. It displays
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

## All available results

The reporting policy `available-results-equal-task-weight-v1` keeps every
registered benchmark and model visible. Per model and task, select all verified
current release outcomes with complete accounting if any exist. Otherwise use
verified results from the curated development comparison. Do not pool the two
sources within a model and task or select by success. Retain all selected
attempt identifiers and show source and release coverage in each task row.

Average selected outcomes within each tested eligible task, then average those
task rates equally per model. Missing tasks are not losses. Experimental tasks
remain visible but do not affect the score. Sort by observed score, with broader
coverage first on equal scores and no comparative rank numbers. Coverage and
framework versions differ, so this descriptive ordering is not a controlled
head-to-head rank. The strict shared-start comparison remains secondary.

Export `available-results.json` with the task grid and selected evidence, plus
`available-leaderboard.csv`. The full-suite protocol and frozen scoring do not
change. New presentation code is loaded only by the publisher.

### Documented timeout replacement

After all registered variants for an uncovered Claude model and task end in held infrastructure errors, one explicitly documented replacement may repeat an original provider timeout. The original cells and artifacts remain unchanged. The replacement receives a new ID, the same starting variant, model, effort, observations and per-trial limits. The global ledger retains the original full token holds and funds the new allowance separately.

The replacement authorization binds the original error and result checksums. Both the scheduler and presentation validator reject changed conditions, duplicate replacements for the same repair, missing error holds, unfinished original attempts and any attempt to repeat a completed gameplay outcome. Response-format and outside-tool errors are not eligible for this timeout recovery path. The frozen gameplay runtime stays unchanged. The scheduler loads a separately checksummed validation adapter.

Available-results views include a verified replacement and expose its original attempt ID in result provenance. The original registered matrix stays intact. Exhausted errors are never presented as completed evaluations.

### Claude response headroom, adapter v2

A Forest timeout investigation found two assistant messages ending at `max_tokens`, each with 4,096 output tokens and essentially all output consumed by reasoning. The subscription CLI continued generating until the shared 180-second decision deadline. This was a response headroom failure, not evidence of a gameplay loss.

The next Claude adapter version raises the per-response output allowance from 4,096 to 8,192 and includes that allowance in the pre-decision token estimate. Per-trial and global token ceilings, reasoning effort, gameplay rules, prompts and observations remain unchanged. This change is recorded as `claude-code-bounded-gameplay-v2`. Existing frozen trials continue to use v1 and are not rewritten. A new versioned evaluation or diagnostic registration is required before running v2. More output headroom addresses the observed truncation mechanism but does not guarantee a valid response or fix unrelated schema and unsupported-tool errors.

Provider-only diagnostics are excluded from gameplay scores. Their original input hash, adapter version, response cap, wall deadline, CLI turn limit, result and usage are stored privately. Each diagnostic receives a checksummed reservation bound to the original release protocol. The scheduler charges those full reservations against the same global allowance, including after a diagnostic finishes, so a failed or partly accounted call cannot silently refund tokens. No diagnostic executes controller actions or rewrites an existing trial.

The verified Forest headroom diagnostic permits one separately identified `headroom-v2` replacement after the earlier timeout replacement remains a held error. This exception is limited to Sonnet 4.6 on Viridian Forest and binds the successful diagnostic checksum. The worker records the response adapter in its manifest and provenance. It preserves the original 1M task ceiling, starting variant, prompt, observations and medium reasoning effort. No completed gameplay result is eligible.

The v3 Forest recovery is bound to the next successful provider diagnostic. It permits 32,000 response tokens and a 600-second decision limit, capped by the trial's remaining wall time. The original 1M trial token setting, starting save, medium effort, observations and gameplay remain unchanged. The extra response allowance is included in the pre-decision token estimate. The previous 4K and 8K failures remain intact with their full holds. V3 is limited to one named Forest trial and is exposed as `claude-response-headroom-v3` in provenance.
