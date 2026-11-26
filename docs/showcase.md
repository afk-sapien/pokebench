# PokeBench showcase

The local main page presents two views of the same project:

- PokeBench Gen 1 Short: category-balanced short-task scores, coverage, tokens, searchable tasks and per-attempt replays.
- PokeBench Gen 1 Long: campaign points, badges, milestones, decision usage and full-run replays.

Short and Long scores are never averaged together. Partial models remain visible with provisional scores and completed-trial counts. Interface revisions are identified without discarding earlier results.

Build the page with the existing result folders:

```sh
uv run python scripts/export_showcase.py --data /path/to/private/data --web /path/to/local/reviews/all-results-preview
```

Add `--watch` to refresh the result snapshot every minute while trials are pending. The exporter does not run models or change traces. It preserves the previous main page as `analysis-v060.html`. The browser also refreshes the snapshot every minute and preserves task filters and expanded details.

The build reads the existing focused analysis, the additional Astra and Fable Short batches, and the v065 and v067 Long runs. It exports selected result fields to `showcase-data.json`, the full file behind the download link. The page itself loads `showcase-summary.json`, which holds every row, score, label and cost but no attempts. Each row carries its 95% interval, computed at build time, and a string marking in task order which tasks it has attempts on. The attempts sit in `showcase-cells/model/` and `showcase-cells/task/`, one file per row and one per task, and the page fetches a file only when a visitor picks that row or opens that task. Each Short row grows the summary by about 1.7 KB, against about 50 KB in the full file. Each attempt and Long run carries the benchmark version from its own manifest. The Short ranking shows each model's revision (original pass or current interface) and the range of versions its attempts recorded, with a note that rows on different harness versions are not strictly comparable. The UI uses relative links and loads replay pages only when requested. Missing replay files are not linked.

## Maintainer rows and suite versions

`src/pokeagent_bench/showcase_sources/maintainer-rows.json` lists rows the maintainers ran on a newer harness. Each names a verified report, its SHA-256, the run folder the report was packed from and any kept attempt that was run again. A row is shown only when the report, its hash and the run folder all agree with the stored Short suite. Otherwise it is left off the site and the build prints `<id>: left off the site. <reason>`. A maintainer row stays out of the cost comparison and moves no other row.

The paths in a row are relative to the data folder. A row whose runs live elsewhere names a `root`, and the build is given that root's folder by name:

```sh
uv run python scripts/export_showcase.py --data /path/to/private/data --web /path/to/local/reviews/all-results-preview \
  --root runs-20261123=/path/to/runs-20261123
```

Repeat `--root` for each root. The checked-in file holds only the root's name, and the page shows each such row's source as `<root>/<runs>`, never the folder. A row whose root is not given is left off with the reason `Its root <name> was not given.`

`short-versions.json` lists the Short suite versions newest first, each with its run and task count. Its entry for the stored suite must match `short-red-v0.63.json`. With rows on the stored suite, the Short board draws one table per version, headed by its name and counts, then one table for the earlier set, which counts the scored starts its rows ran. Each table ranks its own rows from 01. A version newer than every version a row ran, such as one not released yet, lists the rows of the newest version that has them as `Not yet run on this version`, with its note and no rank. With no row on the stored suite, the board is one table with no heading.

## Public site

This is a local showcase, not a public deployment command. For the public site, `scripts/export_public_showcase.py` rebuilds each replay with screenshots and controller actions only. It writes one shared viewer, `replays/view.html`, one data file per replay, `replays/<name>.gz`, and a small page at each old `replays/<name>.html` address that opens the viewer. The data files store each distinct 8 by 8 tile once, see docs/replay-format.md. The largest Long replay is about 0.55 MB, against 81 to 87 MB for a local Long replay file. Before deploying, run `scripts/check_replay_tiles.py` against the published replays to show the new files keep every screen and step. Keep the report's earlier-snapshot label until its results are refreshed. Do not publish the private artifact directory wholesale.

## Reporting labels

Labels never change a score. Each Short cell carries `labels`, a list of codes computed from its own files. `earlier_spec` means its spec hash differs from the current task, `earlier_start` means its fixture differs from the one fixture used by current-spec cells of the same task and variant, `earlier_policy` means preparation was scored with an older battle controller, `no_end_line` means its prompt lacks the run-ends sentence, and `harness_fault` marks the zeros the v0.61 failure study traced to the harness. Each model row counts the labels on its counted cells. `short.label_text` holds the text shown for each code. `short.attempts` holds the retry rule and a log of every replaced, resumed or continued copy that a batch keeps. Long runs carry `pair_blocks`, the moves the game refused at a tile pair collision out of all blocked moves. Facts the run files do not record live in `src/pokeagent_bench/reporting_labels.py`. See docs/history/fair-harness-v061.md.

Source assets are in `src/pokeagent_bench/showcase_assets`. No JavaScript framework or frontend build step is required.

The project name remains PokeBench. The two Gen 1 tracks have separate rankings. Future Gen 2 tracks can share this landing page without mixing generations.

New v067 runs use per-model budgets: 60M tokens across Fable Short, and 30M tokens plus 2,000 decisions each for Fable Long and Astra Long. The Short task limits match Astra v066. The gameplay runtime is unchanged from v065. Fable copies add an exact-model subscription access check after verifying the account picker. Previous aggregate spending remains accounting history.
