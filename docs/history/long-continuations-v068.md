# Long decision checkpoints (v068)

Long extensions are separate cumulative runs. The original 2,000-decision result and replay remain unchanged. The showcase defaults to the 2,000-decision allowance. A single selector exposes 4,000 or later allowances only when those extensions exist. Live extension scores are provisional. A model without an extension is omitted from that comparison rather than treated as a failure. Runs that stop early retain their actual decision count and stop reason.

Use `scripts/continue_long.py --parent RUN_ROOT --output NEW_ROOT --additional-decisions 2000` to create an extension. It does not call a model. Start the resulting run with its frozen runtime and original provider configuration. The utility only extends a clean decision-limited run. It refuses mismatched frames, usage, logs, or unfinished requests.

Each parent boundary is saved under `decision-checkpoints/002000`, then `004000` in the next parent, and so on. The archive includes the full agent checkpoint, emulator save, cumulative scores, usage, notebook, and action logs with checksums. Retain the original run directory for screenshots, fixtures, and the frozen runtime. Call `archive_boundary` at each completed extension. The next extension also archives its parent automatically. Existing boundary files are never overwritten.

Only the decision allowance changes. Token, active-time, game-frame and no-progress limits remain cumulative and unchanged. A 4,000-decision allowance does not guarantee the run reaches 4,000 decisions if another budget ends it sooner. Service recovery charges and missing-usage reserves remain included. The initial Astra extension retains the original 30M token ceiling, including its 320K reserve. Future token-limit changes require explicit authorization and must be recorded separately.

The continuation metadata records the origin, parent, parent result checksum, start count, and new allowance. A 6,000-decision extension must use the completed 4,000-decision root as its parent. No gameplay hints or agent decisions are introduced by extension.
