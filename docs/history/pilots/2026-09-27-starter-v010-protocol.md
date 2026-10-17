# Starter rerun protocol, v0.10

Declared before any live decisions. Run Luna, Terra, and Sol once each through
the subscription-backed Codex CLI, with low reasoning effort, compact visual
observations, the current-panel and previous-plan protocol, and the bounded
agent-authored journal. No pixel labels, motion assistance, gameplay hints, or
manual actions. Each model runs in an independent emulator.

Use the controller-verified starter-repro-v04 initial save and preview without
changing their bytes. Copy its scenario metadata with this clarified objective:
"Obtain your first starter Pokemon from Professor Oak. Begin at home and find
your own way. Finish the acquisition dialogue and decline a nickname."
The evaluator still requires a valid starter in the party and the game's starter
flag, stable across two frames. It stops immediately when that condition is met.
The no-nickname rule also appears in the shared prompt.

Each run is capped at 1,000,000 reported input plus output tokens, 400 model
calls, 1,000 actions, 600,000 game frames, and 7,200 active wall seconds. Each
decision permits two actions, each at most 600 frames. Notebook capacity is
8,192 bytes. Journal limits are defined in ../long-runs.md. The repeated-view
termination guard is disabled. All three receive identical settings.

Exact model IDs are gpt-5.6-luna, gpt-5.6-terra, and gpt-5.6-sol. Runtime source is
hashed and copied to a private frozen source directory before launch. The
private protocol file records that hash and every configured limit. No runtime
changes or assistance are introduced during these trials. Infrastructure errors
are reported separately from gameplay failures, without silently replacing runs.

Token enforcement occurs between decisions with a next-call reserve. The CLI
cannot impose a strict per-call token ceiling, so a final in-flight call could
exceed the nominal total. No API billing fallback or usage reset is authorized.

After all runs finish, verify controller traces with deterministic replay, export
an offline multi-run decision review, and report actual completion, budgets,
usage, decisions, actions, and journal use. Compare the earlier v0.6 pilots only
as descriptive context. Several harness changes occurred together, so these
trials cannot isolate a causal effect or establish a model ranking.
