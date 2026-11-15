# Long decision checkpoints and extension chunks

Long extensions are separate cumulative runs. The original 2,000-decision result and replay remain unchanged. The showcase defaults to the 2,000-decision allowance. A single selector exposes 4,000 or later allowances only when those extensions exist. Live extension scores are provisional. A model without an extension is omitted from that comparison rather than treated as a failure. Runs that stop early retain their actual decision count and stop reason.

## The chunk rule

A Long run plays in 2,000-decision chunks. Only a run that is still earning milestones gets another chunk.

1. **Only a decision-capped run is extended.** The parent must have stopped on `model_call_budget` at its decision cap. A run that the no-progress guard (`loop_token_budget`), the no-milestone guard (`milestone_token_budget`), the token cap or any other budget stopped is never extended.
2. **One chunk per extension.** Each extension adds exactly 2,000 decisions.
3. **Each chunk gets its own allowance.** The new token, active-time, frame and action caps are what the run has used plus the first chunk's caps. For the published Long settings that is 29.68M reported tokens (30M with the 320K unreported reserve), 24 h, 10M frames and 150K actions per chunk. The continuation record stores this as `chunk_allowance`.
4. **The guards carry across chunks.** The 2M no-progress count and the 10M no-milestone count continue from the parent, so a new chunk does not reset either.

Use `scripts/continue_long.py --parent RUN_ROOT --output NEW_ROOT` to create an extension. It does not call a model. Start the resulting run with its frozen runtime and original provider configuration. The utility refuses a parent that a guard or another budget stopped, and it refuses mismatched frames, usage, logs or unfinished requests.

Each parent boundary is saved under `decision-checkpoints/002000`, then `004000` in the next parent, and so on. The archive includes the full agent checkpoint, emulator save, cumulative scores, usage, notebook, and action logs with checksums. Retain the original run directory for screenshots, fixtures, and the frozen runtime. Call `archive_boundary` at each completed extension. The next extension also archives its parent automatically. Existing boundary files are never overwritten.

The continuation metadata records the origin, parent, parent result checksum, start count, chunk allowance and new caps. A 6,000-decision extension must use the completed 4,000-decision root as its parent. No gameplay hints or agent decisions are introduced by extension.

## Published extensions built before this rule

These extensions were built by per-run controllers, not by `create_continuation`. Their records stay as published.

- **Astra 4k, Opus 4k, Sol 4k and Terra 4k** fit the rule. Each had a decision-capped parent, kept the no-progress guard and had a 60M cumulative token ceiling. Each second chunk spent 22.5M to 24.8M tokens, under the per-chunk allowance, so the rule gives the same result.
- **Astra 6k and 8k** do not fit. They ran under the remaining included subscription with the no-progress guard off, no practical token ceiling and a 7-day active-time cap. Their third and fourth chunks spent 23.4M and 21.5M tokens, under the per-chunk allowance, and Astra 8k used 90.2M tokens across four chunks. Astra 8k ended on a provider error.
- **Sonnet 4k and Luna plus 4k** do not fit. Sonnet 4k extended `long-v065-sonnet`, which the no-progress guard stopped at decision 1,936. Luna plus 4k added 4,000 decisions to `long-v069-luna`, which the same guard stopped at decision 1,309, and it ended on its 60M token ceiling. Both turned the no-progress guard off. Under the chunk rule neither parent gets another chunk.
