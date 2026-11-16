# Output cap reply v0.37.2

This tag is package 0.37.2, git tag `v0.37.2`, under the same harness name `red-v0.63-short-guard`. The task specs, the start states, the fixture pack, the prompts and the run limits are those of `v0.37.1`. PokeSim Core 0.12.0, PyBoy RS 0.1.5 and Claude Code 2.1.323 stay pinned.

## What changes a run

A Claude reply that runs past `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (8192) is now handled like any reply that holds no valid decision.

1. The pinned CLI first asks the model to continue on its own. When that still ends past the cap, it sends a synthetic error message, then a result with the usage of the whole reply.
2. `v0.37.1` stopped at the synthetic message with a provider error. The cell ended as an infrastructure failure with incomplete accounting, and `run --suite` stopped. This happened once, in `navigation-victory-road` of a Haiku Short pilot, after 580 decisions.
3. `v0.37.2` waits for the result and counts its tokens. No action runs, the decision is spent and the next request carries the correction `The reply reached the 8192 output token limit before it returned a decision`. The decision record names `provider_code: max_output_tokens`.
4. Three invalid replies in a row end the task with `invalid_model_response`, as before. Otherwise the task goes on under its usual caps.

The response adapter is now `claude-interface-v9`. Every other provider error is handled as in `v0.37.1`.

## Runs from v0.37.1

A `v0.37.1` run that never got a synthetic output cap message took the same path it takes on `v0.37.2`. Its entry stays in [accepted_harness.json](../../src/pokeagent_bench/accepted_harness.json), so a bundle may hold cells from both releases, and each cell keeps its own package version. Such a bundle is verified on the `v0.37.2` checkout.
