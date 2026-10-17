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

The build reads the existing focused analysis, the additional Astra and Fable Short batches, and the v065 and v067 Long runs. It exports selected result fields to `showcase-data.json`. The UI uses relative links and loads replay pages only when requested. Missing replay files are not linked.

This is a local showcase, not a public deployment command. For the public site, use the existing public replay export to produce screenshot and controller-action replays. The current local Long replay files are approximately 81 to 87 MB each. Package those separately from the small landing page. Keep the report's earlier-snapshot label until its results are refreshed. Do not publish the private artifact directory wholesale.

Source assets are in `src/pokeagent_bench/showcase_assets`. No JavaScript framework or frontend build step is required.

The project name remains PokeBench. The two Gen 1 tracks have separate rankings. Future Gen 2 tracks can share this landing page without mixing generations.

New v067 runs use per-model budgets: 60M tokens across Fable Short, and 30M tokens plus 2,000 decisions each for Fable Long and Astra Long. The Short task limits match Astra v066. The gameplay runtime is unchanged from v065. Fable copies add an exact-model subscription access check after verifying the account picker. Previous aggregate spending remains accounting history.
