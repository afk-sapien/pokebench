> Current protocol: [screen feedback and structured memory](visual-feedback-v05.md).
> The control pilot below documents the older v1 harness.

# ChatGPT subscription runs

The `codex` provider uses the installed Codex CLI and its existing ChatGPT login.
It does not scrape ChatGPT web or reuse subscription tokens as API credentials.
The local implementation was inspected against Codex CLI 0.147.0. A mock-process
test validates the command and parser. Earlier live results are recorded in the
pilot reports, with each harness version kept separate.

```bash
codex login status
uv run pokeagent run --provider codex --model YOUR_AVAILABLE_CODEX_MODEL \
  --reasoning-effort low --rom /path/to/red.gb --scenario scenarios/after-brock \
  --goal challenge --track visual --max-actions-per-decision 2 \
  --max-total-tokens 25000 --max-model-calls 100 \
  --max-wall-seconds 600 --max-frames 10000 --output runs/codex-pilot
```

The command consumes subscription usage when executed. Exact model availability
comes from the account and installed Codex version. ChatGPT's web model picker
is not a guaranteed list of models callable through Codex.

Each decision uses an ephemeral Codex invocation in a temporary working folder
containing only its screenshot and response schema. User config is ignored.
Shell tools, web search, and subagents are disabled, and repository instructions
are not loaded. The adapter rejects outputs containing outside tool activity.
This is a cooperative harness, not an OS boundary against a hostile agent.
Its version, CLI version, reasoning effort, and prompt hash are recorded and
kept separate from direct API and external MCP comparison groups.

## Budget semantics

`--max-total-tokens` stops the runner once cumulative reported input plus output
tokens reach the threshold. Cached input is already part of input usage and is
not added twice. The runner checks usage after every response and before allowing
another action. Missing usage stops evaluation instead of treating it as free.
One in-flight decision can exceed the threshold. The CLI does not expose a verified
hard per-decision output cap here, so `--max-output-tokens` only applies to API
providers. Wall-time and model-call limits remain active for Codex runs.

Timeouts and transport failures may consume tokens without returning usage.
Such runs mark accounting incomplete. Reported tokens do not map exactly to
subscription quota consumption. No reset credits are redeemed, and no paid API
fallback is attempted. MCP clients have unavailable token accounting because
usage is outside the server's control.

Official references:

- [Authentication](https://learn.chatgpt.com/docs/auth)
- [Non-interactive execution and JSON usage events](https://learn.chatgpt.com/docs/non-interactive-mode)

### Verified control pilot

The first live pilot uses `gpt-5.6-sol` and `gpt-5.6-luna`, discovered through
`codex app-server` with the current ChatGPT login. Both use low reasoning effort
and the structured track. Each run has a 30,000 reported-token threshold, three
model calls, three controller actions, 360 emulator frames, and 120 wall seconds.
There are four runs total, one per model and task, without retries.

The tasks are moving one tile and closing a menu before moving one tile. The
private source checkpoint and ROM are required. `scripts/prepare_control_pilot.py`
records setup inputs and checks a successful controller reference with replay.
Raw checkpoints, references, model responses, and run artifacts stay local.
Results and exact provenance are frozen in the manuscript export.

A restored PyBoy state does not restore its screen buffer. New checkpoint imports
therefore perform one declared setup wait frame, then save the resulting state
and paired PNG. The loader verifies the image checksum and serves that image
until the first controller action advances the emulator. Observing a loaded run
does not advance it. Reimport old checkpoints to obtain a paired starting image.
