# Short guard red-v0.63

This tag freezes the fixes made for the rerun on `v0.37.0`. It is released as package 0.37.1, git tag `v0.37.1`, under the harness name `red-v0.63-short-guard`. No model was called to build or check it. The task specs, the start states and the fixture pack are those of `v0.37.0`, and PokeSim Core 0.12.0 and PyBoy RS 0.1.5 stay pinned.

## What changes a run

1. Each Short task stops after two thirds of its own token cap without a new milestone, with the stop reason `milestone_token_budget`. Stored runs lose no points at that guard. The numbers are in [the guard notes](short-milestone-guard-v0371.md).
2. The local map draws overworld ledges in their hop direction, the Pokemon Mansion 3F floor gap as `o` and the 3F border as blocked. A move result reports an object that vanished from a square still in view. Details are in [the local map notes](truthful-local-map-v0371.md).
3. One Ctrl-C pauses after the decision in progress, and the same command resumes. It no longer scores a partial run.
4. A usage limit whose reset is at most 6 hours away waits until 2 minutes after the reset and asks the same decision again, at most twice per decision. The wait is left out of the wall limit.
5. Every Claude call sets `DISABLE_AUTOUPDATER=1`. `run --suite` puts `toolchains/claude-2.1.323/bin/claude` first on PATH for the whole command when the data folder or the folder above it holds that copy.

## Verify

`verify` now checks each cell against the run limits of its own trusted plan. A Long run at its published limits passed `run` but failed `verify` on `v0.37.0`, and it passes now. The Short guard is part of each Short task's run limits, so `verify` requires it on every Short run.

## Prompt dry-run

`navigation-victory-road`, `navigation-pewter-to-lavender` and `objectives-cinnabar-gym` were replayed from their reference commands through the runner with a scripted provider, and every model-visible input was saved. Every step of each route can be read from the prompt or found by playing, so no prompt text changed. Four renders told the model something false, and item 2 fixes them. After the fix the pewter replay finishes 219 of 219 decisions with score 6 and the cinnabar replay 214 of 214 with score 5.

## Accepted releases

The v0.37.1 entry is added to [accepted_harness.json](../../src/pokeagent_bench/accepted_harness.json) after the v0.37.0 entry. The v0.36.0 and v0.37.0 entries stay, so their runs keep their labels. Their Short run limits differ from this release, so a bundle from either is verified on its own release's checkout. Existing leaderboard rows keep the harness label they ran on.
