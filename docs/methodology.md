# Benchmark methodology v0.2

Status: experimental. Results measure a model inside a specified agent harness,
not an intrinsic model capability independent of its tools and memory.

## Starting conditions

Use the same scenario directory for every compared run. The manifest identifies
the ROM and state by SHA-256 and pins PyBoy 2.7.0. The initial state contains the
cartridge RNG and machine state. Python's random-controller seed only controls
that baseline's choices. It does not reseed Pokemon.

The opening scenario is a fresh boot captured after 1,800 frames. Startup frame
cost is fixed setup, excluded from scored run frames and wall time. Scored runs
start with no achievements. Pre-earned story flags and Hall of Fame progress are
rejected. A scenario's hash identifies it, but does not certify its provenance.

## Observation and memory

Visual observations contain a screenshot, current run frame, and public progress
and budget status. Structured observations additionally include map ID and local
coordinates, party HP and moves, inventory, money, badges, and battle mode.
These extra fields are assistance, even if a person could obtain them through menus.

Raw enemy memory, event arrays, collision data, map connections, RNG, and policy
recommendations are excluded. Numeric names are the default. Optional local label
tables supply names without making map layouts available. Comparison groups include
the normalized label hash. They cannot mix labelled and unlabelled runs.

Every controlled model request has the same system prompt, current observation,
the previous eight action summaries or validation errors, and an 8,192-byte notebook.
History outside that window is discarded. The model must preserve what it needs
in notes. This is an explicit bounded-memory harness, not the provider's default
chat application's memory behavior. Both providers emit the same controller schema.

No automatic retries of model HTTP calls occur in v0.2. Provider errors stop a run
with a distinct reason. Three consecutive invalid action responses stop an agent
failure. Invalid outputs consume model-call and wall budgets but no game frames.

## Scoring and clocks

Badges require both a badge bit and its corresponding gym victory event.
Elite Four points require their trainer victory flags. Champion completion requires
the Champion event, Hall of Fame map, and an increased Hall of Fame registration
counter. Evidence must persist across two successive frames. Awards are monotonic
and unique, even if the game later clears an event flag or the player loses a rematch.

Story events receive zero points and provide diagnostic milestones. Full campaign
score is 1,000. First-gym runs stop at the first confirmed Boulder Badge for 75.
Badge detection and campaign scoring have synthetic coverage. A full real-ROM
campaign and real victory fixture validation are still outstanding.

Wall time uses a monotonic clock and includes inference, emulator work, recording,
and tool overhead after session creation. Model time covers provider calls.
Emulated seconds use the Game Boy frame rate of 4,194,304 / 70,224 frames per second.
The cartridge's displayed playtime is not used as the benchmark clock.

Frame and action limits are exact. Wall limits are checked before actions and at
every emulated frame. An in-flight synchronous HTTP request can finish after the
wall deadline, but its returned action will not execute. HTTP I/O timeouts are at
most 180 seconds and are bounded by remaining wall time at request start. This is
not a provider billing cancellation guarantee.

## Accounting and reports

Exact requested model IDs, output-token ceilings, prompts, labels, scenario,
emulator, core version and installation origin, core source hash, benchmark version,
memory policy, and all limits are recorded. Core builds are separate comparison
groups. Provider response metadata and token details remain in private decision logs. Internal
reasoning defaults can differ across providers and are not represented as equal
compute. Record this limitation when interpreting a comparison.

Input/output token counts come from successful API responses. Failed calls can
incur unknown usage. Optional prices multiply total input and output counts by
user-supplied rates per million. Cache discounts, provider-specific billing,
taxes, and unknown failed-call charges are not included. Missing prices produce
null cost, never a free-run claim. External MCP usage is unavailable, not zero.

Reports group comparable conditions before aggregating by model. Show completion
rate and mean score, plus median wall time among completed runs only. Exclude
provider errors, infrastructure errors, and interrupted runs from the gameplay
success denominator while reporting their counts separately. Budget exhaustion
and invalid agent outputs are evaluated outcomes. Pilot reports have no automatic
confidence intervals and should include multiple independent trials.

## Replay and artifacts

Each accepted action is recorded with requested and executed frames, controller
input, evaluator evidence, new milestones, screenshot hash, and the prior record
hash. Frames can be truncated at a budget or success boundary. Replays validate
the record chain, replay every executed frame, and compare evidence, screenshots,
milestone frames, action count, final score, and completion evidence.

The chain detects accidental corruption and missing records. It is not signed
attestation against an untrusted submitter. Runs that end during an emulator or
disk failure may have incomplete traces and are classified as infrastructure errors.
There is no crash-resume feature in v0.2. Start a new trial after interruption.

Saved states and images contain user-supplied game data. Keep them outside Git
and do not publish them as part of the source package. A hosted evaluator will
need an explicit artifact-sharing policy before accepting outside submissions.

## Changes from v0.1

Shared core decoding preserves additional nickname symbols, uses `?` for unknown
glyphs, and stops at zero bytes. This changes structured observations and is why
v0.2 results must be compared separately. The allowed fields, scoring, and frame
semantics are unchanged. Legacy action logs remain replayable without core
metadata, with every screenshot and evaluator record checked as before. Replay
verifies recorded behavior, it does not claim that current model observations
match the older decoder or that rerunning a model reproduces its decisions.
