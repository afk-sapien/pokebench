# Claude Code subscription runs

PokeBench supports the official Claude Code CLI with an existing Claude subscription login. The adapter does not extract OAuth credentials or fall back to an API key. The `anthropic` provider remains a separate API adapter and does not provide this gameplay protocol.

## Running

```sh
pokeagent run \
  --provider claude --model claude-sonnet-5-5 \
  --codex-policy bounded --reasoning-effort medium \
  --track gameplay --goal challenge \
  --rom /private/pokered.gb --game-data /private/game-data \
  --scenario /private/validated-fixture --output /private/new-run \
  --max-total-tokens 500000 --max-action-frames 600
```

Pause and resume use the same `pokeagent pause` and `pokeagent resume` commands as controlled Codex runs. Claude Code must retain its local session files. Deleting Claude's session storage prevents resuming that conversation. PokeBench never submits evaluator state, repository files or fixture paths to Claude.

The adapter requires an exact model identifier. It refuses aliases and Fable models. Fable can consume separately purchased usage credits without a prompt in non-interactive mode, and inclusion in the model picker does not prove included subscription entitlement.

## Shared protocol and isolation

The adapter inherits the exact bounded gameplay prompt, action schema, readable state packets, screenshot presentation, notes and goal plan. Context rotates after eight decisions or the 12,000-token context threshold. There are no model-generated summaries. A new segment receives the same deterministic state snapshot and observed history used by the Codex provider.

Claude runs in an empty temporary directory with safe mode, restricted mode, no built-in tools, empty strict MCP configuration, disabled slash commands, disabled Chrome, disabled hooks and no user or project settings. The only exposed tool is Claude's schema-only `StructuredOutput`. Initialization and response events reject outside tools, an unexpected model, or automatic compaction. Provider environment overrides and API keys are removed from the child environment. The adapter keeps the official CLI login mechanism.

The model can emit at most 4,096 output tokens per request through the CLI environment setting. This is a Claude transport control, not a claim that the Codex transport enforces the same output cap. Effort names are provider-specific controls, not equivalent amounts of computation. Haiku does not advertise adjustable effort, so its results must identify that limitation.

## Accounting

Claude's `modelUsage` counters accumulate within a session, including across process resumption. PokeBench subtracts the previous counters once per decision. Total input tokens include uncached input, cache reads and cache creation. Cache tokens are charged against the benchmark token budget once. Cache read and creation counts are retained separately in decision logs.

The subscription price is not allocated to individual runs. CLI dollar estimates are API-equivalent estimates, not subscription charges. The runner uses conservative admission estimates and checks reported usage between decisions. A timeout or missing usage ends the trial with incomplete accounting. The version 4 response boundary handles malformed decisions as metered invalid model responses when complete usage is available. It is not counted as a model failure. Automatic provider retries may consume tokens before a failed CLI response, which the CLI may not fully report.

## Local model inventory

The official CLI initialize response on October 5, 2026 reported these exact IDs under the installed Max subscription. This is an availability inventory, not evidence that every model has completed a benchmark call.

| Display name | Exact model ID | Adjustable effort advertised |
| --- | --- | --- |
| Opus 5.5 | `claude-opus-5-5` | Yes |
| Sonnet 5.5 | `claude-sonnet-5-5` | Yes |
| Haiku 4.5 | `claude-haiku-4-5-20251001` | No |
| Sonnet 5 | `claude-sonnet-5` | Yes |
| Opus 5 | `claude-opus-5` | Yes |
| Opus 4.8 | `claude-opus-4-8` | Yes |
| Opus 4.7 | `claude-opus-4-7` | Yes |
| Opus 4.6 | `claude-opus-4-6` | Yes |
| Sonnet 4.6 | `claude-sonnet-4-6` | Yes |

Fable 5.1 and Fable 5 were also listed. They are excluded pending separate entitlement and spending authorization. The account's default and the `opus` alias both resolved to Opus 5.5 and are not separate models.

CLI 2.1.289 successfully completed two Sonnet 5.5 transport tests. Two turns in one process used 2,091 reported tokens. Two turns separated by a CLI process restart used 2,159 reported tokens. Both returned the word supplied on the first turn when asked on the second. Opus 5.5 returned a successful schema response using 973 reported tokens. Haiku 4.5 did so using 1,365 reported tokens. A one-decision Sonnet 5.5 game smoke used 6,367 tokens and selected `switch_pokemon:2` from the bad-matchup fixture. Its 528-frame controller trace replayed exactly. These are transport checks, not benchmark scores. Two earlier initialization checks stopped before a result while validating the schema tool allowlist, so their provider usage is unknown and excluded from these successful-test totals.

## Sources

- [Programmatic Claude Code execution](https://code.claude.com/docs/en/headless)
- [Model configuration and Fable usage credits](https://code.claude.com/docs/en/model-config)
- [Authentication](https://code.claude.com/docs/en/authentication)

The installed CLI `--help` and read-only initialize response were used to verify current flags and local model inventory. `--bare` is deliberately not used because it disables subscription OAuth authentication.


## Response interface version 4

The CLI response schema allows omitted `notes`, `goal_plan` and `look_back`.
Omission means JSON null, preserving existing memory. An initial goal is still
required by the shared gameplay validator. No plan or action is invented.
The canonical gameplay schema and action validation remain unchanged.

The CLI exposes only StructuredOutput. A request for an unavailable game tool,
such as `use_move`, is never executed or translated into an action. The adapter
waits for the CLI result and accepts a valid structured decision if the model
corrects itself. Shell, file, network and other outside tool requests still abort.

A malformed response with complete usage returns a zero-action invalid decision.
The next normal decision receives bounded formatting feedback. Its token budget
is checked before another call, and three consecutive invalid decisions end the
trial under the existing runner policy. Every CLI result, including failed schema
attempts, contributes its cumulative usage delta once. Unknown usage still fails
closed. Repeated invalid responses are model-format failures, not battle losses.

Six previously incomplete Claude pairs have explicit version 4 replacement
registrations. Each retains its original checkpoint, prompt, 4,096-token response
cap, 180-second decision deadline and trial budget. The replacement records bind
the adapter and original errors by checksum. Historical outcomes and failed-call
budget holds are retained. No completed gameplay outcome is retried.
