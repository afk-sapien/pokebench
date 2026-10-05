# Architecture and roadmap

This repository owns its own Python package, environment, tests, Git history, and
run directories. It has no runtime import or editable install of PokeSim.
PokeSim Core supplies the shared Red/Blue decoder, ROM validation, and isolated
emulator. The benchmark pins a released wheel by SHA-256, then restricts the
engine to Red and selects agent-visible fields explicitly. The autonomous player,
recovery code, trading, custom rewards, and application database stay in PokeSim.

## Components

| Module | Responsibility |
| --- | --- |
| `pokesim_core` dependency | ROM validation, isolated emulator, shared game facts |
| `game.py` | Red-only engine policy and explicit agent observation allowlist |
| `session.py` | Frame stepping, budgets, idempotency, artifacts, scenario preparation, replay |
| `scoring.py` | Private evidence, two-frame confirmation, unique achievement awards |
| `challenges.py` | Curated checkpoint objectives and private success evidence |
| `codex_provider.py` | ChatGPT-authenticated Codex CLI decisions and usage |
| `paper_export.py` | Sanitized frozen results for paper-scaffold |
| `providers.py` | OpenAI Responses and Anthropic Messages adapters, random baseline |
| `runner.py` | Common prompt, notebook, recent actions, model usage, termination |
| `mcp_server.py` | Six agent tools over stdio |
| `report.py` | Comparable experiment groups and repeated-trial aggregates |
| `dashboard.py` | Local read-only screens, grouped model comparisons, and JSON export |

## Boundaries

The agent gets native-resolution PNG screenshots and an explicit structured
allowlist when that track is enabled. Raw emulator memory, RNG state, event flags,
unseen maps, evaluator records, save states, and model credentials are not tool
outputs. The current screenshot supplies dialogue and visible battle details.
The decoder does not attempt OCR or provide the opponent's hidden statistics.

The controlled runner alone holds provider keys. It only sends allowlisted
observations, notes, and recent action summaries. The MCP server uses no API key.

The local MCP process is a cooperative integration boundary, not an OS sandbox.
An external agent with independent filesystem access could inspect the server's
private files. An official submission service will need separate worker processes
or containers with agent and evaluator credentials and mounts separated.

## Current scope

v0.3 provides a runnable first-gym benchmark and experimental campaign evaluator.
It includes a real emulator, two model API adapters, external-agent MCP access,
hash-checked action replay, local viewing, and grouped reports. No paid model
campaign has been used to claim gameplay capability or calibrated budgets.

## Next milestones

1. Run matched first-gym pilots with exact model versions. Freeze a practical
   frame, call, wall, output-token, and notebook budget from those pilot results.
2. Collect private real-game fixtures for wins, losses, transient badge updates,
   Elite Four event resets, and Hall of Fame registration. Promote campaign scoring
   only after replay verification of those fixtures.
3. Add a trial-matrix scheduler with budgeted concurrency and a frozen set of
   starting states. Report confidence intervals rather than relying on one run.
4. Add checkpoint challenge suites, scored separately from fresh campaigns.
5. Add provider-specific reasoning settings as explicit experiment configuration.
   Do not silently choose a setting or claim identical internal compute.
6. Add an isolated submission service and authenticated remote MCP transport if
   external leaderboard submissions become a goal.
7. Add Blue through a separately verified adapter. Other generations require
   their own emulator and RAM adapter, not only a different ROM path.

## Shared core updates

Core releases are adopted explicitly by changing the wheel URL and SHA-256, then
regenerating `uv.lock`. Run the test suite and replay existing private ROM traces
before upgrading. Any change to observations, scoring, prompts, or budgets also
requires a benchmark version change. Run manifests record core version, direct
installation metadata, and source hashes so locally edited builds remain distinct.

## References

- [PokeSim Core](https://github.com/afk-sapien/pokesim-core)

- [PokeSim source](https://github.com/afk-sapien/PokeSim)
- [PyBoy API](https://docs.pyboy.dk/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision)
- [Anthropic vision](https://platform.claude.com/docs/en/build-with-claude/vision)
- [Anthropic tool definitions](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [PokéAgent Challenge speedrunning](https://pokeagentchallenge.com/speedrunning.html)
