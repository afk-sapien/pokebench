#import "config.typ": *
#import "stats.typ": lit, s
#import "assets.typ": tbl
#set page(paper: "a4", margin: 23mm, numbering: "1")
#set text(font: "Libertinus Serif", size: 10.5pt)
#set par(justify: true, leading: 0.62em)
#set heading(numbering: "1.")
#align(center)[
  #set par(justify: false)
  #text(size: 21pt, weight: "bold", paper-title)
  #parbreak()
  #paper-authors.map(a => a.name).join(", ")
  #parbreak()
  #paper-date | Development technical report | Not peer reviewed
]
#v(8pt)
*Abstract*
#paper-abstract
// >>> BODY START
= Introduction

A game-playing agent must choose useful actions, remember their consequences,
and recover when its plan fails. A full Pokemon campaign combines navigation,
team management, battles, and long-term objectives. It also creates an
evaluation problem: an early navigation failure prevents observation of later
battle skills. PokeBench uses checkpoint tasks to expose these skills
independently, alongside longer tasks that retain their dependencies.

The intended construct is decision making within a specified agent framework.
Structured observations and menu shortcuts reduce the burden of reading pixels
and navigating repetitive menus. They also change the task. Results from this
track cannot establish unaided visual gameplay ability or the intrinsic ability
of a model independent of its tools. The benchmark must publish those tools,
observation rules, and budgets with every result.

Historical development evidence covers #s("models.historical") models. This
report describes the current implementation and that evidence. The active
catalog contains #s("catalog.active") tasks, of which #s(
  "catalog.scored",
) contribute to the historical development ranking. The remaining #s(
  "catalog.experimental",
) are experimental candidates. A separate archive preserves #s(
  "catalog.retired",
) retired tasks. The public presentation can show one catalog without pretending
that every task has the same validation status.

= Methods

== Environment and checkpoints

Each task starts from an emulator state with a declared objective. Fixture
metadata record the game checksum, emulator and core versions, save checksum,
setup procedure, and reference controller trace. Evaluation checks use private
state and are kept outside the agent observation allowlist. A badge already
present in the starting save does not count as new progress.

Curated battle tasks may deliberately alter the player's initial team, move
power points, health, or inventory. These changes occur during offline fixture
construction and are recorded in provenance. Opponent behavior remains game
behavior. A reference replay proves that a particular controller trajectory can
win from the checkpoint. It does not prove that a fixed strategy always wins,
that the task is easy, or that the reference is optimal.

Only controller actions advance a scored run. Observations do not advance game
time. Save loading, setup waits, and offline fixture edits are distinct from
scored gameplay. A declared runtime and unchanged initial state are required for
a deterministic replay claim.

== Agent observations and actions

The structured gameplay track supplies the current screen and selected facts
about the player, local map, visible interaction state, party, moves, inventory,
and recent actions. Some facts are retrieved through tools instead of being
repeated in every prompt. The observation contract must enumerate these fields.
Private victory flags, future random outcomes, and reference policies are not
agent inputs.

Actions include bounded movement, interaction, dialogue advancement, move
selection, Pokemon switching, and item use. Shortcuts execute ordinary
controller inputs and report the observed outcome. They do not choose the best
item or Pokemon for the agent. Dialogue advancement collects continuation text
and stops at choices that require a decision. This design tests whether the
agent chooses a useful action while reducing the cost of issuing each
intermediate button.

Navigation assistance also changes what is being tested. Local map facts make
spatial planning more accessible than screenshot-only play. These observations
must be identical across compared models. If a later implementation supplies a
route plan or automatic battle strategy, it requires a separately identified
protocol rather than silently replacing the present task.

== Context and stopping rules

The runner maintains bounded interaction context and explicit working memory.
Recent decisions, current facts, action feedback, and model-authored notes are
retained according to a declared policy. A context rotation must preserve its
recorded handoff rather than claim to preserve an unlimited conversation. Memory
contents remain fallible agent statements. The evaluator must not repair a plan
by inserting private task knowledge into that memory.

A token threshold applies to reported input plus output usage. Cached input is
not added again on top of total input usage. A completed in-flight call can
cross the threshold, so the threshold is not a guarantee of an exact maximum.
Another decision is blocked after the threshold is reached. Additional limits on
decisions, actions, frames, elapsed time, and prolonged lack of progress bound
trials that would otherwise continue indefinitely.

A gameplay failure, budget stop, and infrastructure error are different
outcomes. An invalid response or unavailable provider does not establish that
the model lost the battle. Error handling preserves the original attempt and its
known usage. A retry must have its own identifier and a stated eligibility rule.
Unreported usage stays unknown rather than being replaced with zero.

== Scoring and comparison

Task success is a private objective predicate, not a model's claim of success.
Battle objectives require the relevant victory evidence. Capture objectives
require the intended encounter to produce the added Pokemon. Resource and
recovery tasks can forbid blackout, party replacement, or any fainting,
depending on the declared task. Merely leaving a battle or reaching a map after
a blackout cannot substitute for the specified objective.

For a release comparison, compute each model's success fraction within a task
across the shared starting variants and registered attempts. Average those
fractions across tasks so that a task with more variants does not receive more
weight. Report the number of evaluated tasks and missing attempts beside the
score. Experimental tasks remain visible but do not enter the primary ranking
until the inclusion rule is satisfied.

The historical development ranking selects declared cohorts by task and retains
matching coverage across models. Its retrospective curation and changing
framework versions prevent treating that aggregate as a fresh controlled release
experiment. Publication should preserve the historical table, then present a
separate frozen release comparison without blending their results.

== Randomness and calibration

Paired starts mean that every model receives the same registered checkpoints.
They do not force identical outcomes after different actions. Action timing can
change a deterministic emulator's later random sequence. Nearby timing variants
also need not be independent random samples. A winning path found after a
failure is evidence of feasibility, not a valid replacement for the failed
trial.

Calibration compares a frozen reference policy with simple attack policies on
held-out starts. Both reliability and separation matter. A task that a simple
baseline reliably wins may be a useful basic control but adds little evidence of
advanced tactical skill. Conversely, failure by every model can indicate a
useful frontier challenge, an unreliable fixture, or an interface defect. Replay
and reference checks are needed before interpreting the result.

== Cost and provenance

Report token usage, decisions, controller actions, game frames, and active wall
time alongside success. Subscription usage is not a direct cash invoice.
Provider-rate estimates must carry their rate-card date, cache treatment,
coverage, and units. Cross-provider token counts and effort settings are not
necessarily equivalent measures of computation. A cost-to-success comparison
must use matched tasks and complete accounting, with unknown cost shown
explicitly.

The analysis consumes sanitized frozen summaries. It excludes game binaries,
emulator saves, screenshots, prompts, responses, credentials, and local private
paths. Input and artifact hashes support provenance checks but are not external
attestation. This manuscript uses Paper Scaffold @scaffold, which generates
result tables and guards numerical claims against changes in their analysis
inputs.

= Development results

== Audited decision-task pilot

The decision-task pilot contains #s("pilot.attempts") attempts across #s(
  "pilot.tasks",
) tasks and #s("pilot.models") models. The exact provider model identifiers and
reported usage appear in @tbl:pilot. Each task-model pair has one starting
condition and one attempt. All included rows passed the replay, input-delivery,
conversation-order, and state-update audits.

Astra completed #s("pilot.astra.wins") of #s("pilot.astra.trials") tasks. Terra
completed #s("pilot.terra.wins") of #s("pilot.terra.trials"), while Luna
completed #s("pilot.luna.wins") of #s("pilot.luna.trials"). These outcomes
support testing the candidates further. They do not distinguish the stronger
pair or estimate repeated-attempt reliability for an individual task. Aggregate
pilot usage was #s("pilot.tokens") reported tokens.

#figure(tbl("tbl.pilot"), caption: [Audited development pilot. The pass
  denominator is distinct tasks, not repeated trials of one task. Token totals
  include reported input and output usage. This is not the frozen release
  evaluation.]) <tbl:pilot>

== Reference-policy evidence

The initial decision-task calibration sweep is shown in @tbl:calibration.
Reference wins varied across the shared starts, despite each released fixture
having a winning reference trajectory. Healthy capture was sometimes successful
with immediate ball throwing. These observations caution against labeling every
candidate a difficult reasoning test. The route reference used the simulation's
privileged offline policy and is not a model result.

#figure(tbl("tbl.calibration"), caption: [Development calibration of
  experimental tasks on shared timing variants. Reference strategies and simple
  baselines were fixed for this sweep. These are development starts, not
  held-out reliability estimates. Recovery-detour results compare a privileged
  simulation reference with its travel path without the recovery
  stop.]) <tbl:calibration>

The separate tactical Lorelei candidate had stronger held-out evidence. Its
frozen reference won #s("calibration.tactical") of #s("calibration.starts")
starts. The direct attacker won #s("calibration.attack-first"), and the attacker
using type information won #s("calibration.type-aware-attacker"). The remaining
reference loss and a later successful diagnostic trajectory are both retained.
The diagnostic does not change the calibration score or establish perfect play.

= Frozen release evaluation

Controlled release results are pending. The registered protocol
`pokebench-v1-beta` freezes #s("release.models") model identifiers and #s(
  "release.tasks",
) tasks, with #s("release.variants") fresh timing variants per task. This
creates #s("release.planned") planned attempts. No development attempt is
imported into these prospective results. The protocol records source,
checkpoint, game, prompt, response-schema, and fixture-registration hashes.

The approved aggregate budget is #s("release.budget") reported tokens. The sum
of all per-attempt thresholds is #s("release.maximum") tokens, so the registered
matrix is a staged plan rather than a promise to finish every attempt under the
approved cap. A task-first schedule evaluates paired variants and rotates model
order within each variant. Only eligible tasks with identical completed,
replay-verified and accounted variant coverage across all registered models
enter the aggregate. Incomplete coverage stays visible. A partial aggregate must
state which tasks it covers and cannot represent the entire catalog.

Both providers use the gameplay track, the same prompt and response-schema
hashes, and bounded text observations. The context policy retains at most #s(
  "release.turns",
) turns per segment and rotates at the declared #s("release.context") context
threshold. It requests #s("release.summaries") paid summaries. Deterministic
checkpoint packets carry current state and retained memory between segments. The
protocol records transport and memory-policy identifiers so that these choices
can be reproduced.

The provider model identifiers appear in @tbl:models. Requested effort is
medium. Haiku exposes no adjustable effort, which is recorded as unavailable
rather than medium. Claude Code has a #s("release.claude_output") output-token
limit per call, while the Codex transport records no adapter output cap. These
are declared provider differences, not evidence of equal computational effort.
Claude access was listed by the official client, with representative smoke tests
recorded separately from task completion.

No gameplay retries or paid fallback are permitted. Infrastructure errors and
incomplete accounting stop the sweep, while every raw attempt is retained. The
controller reserves #s("release.reserve") tokens for an in-flight response, but
one response can still cross a decision-boundary threshold. Per-task Wilson
intervals are descriptive because timing variants are paired conditions rather
than independent random samples. Only #s("release.eligible") tasks are eligible
for the primary score. Experimental tasks remain excluded. Release outcomes must
be reported with these limits before making claims about relative ability.

= Limitations

PokeBench evaluates a model with an agent framework, not an isolated model.
Changing summaries, memory retention, menu automation, or map observations can
change performance. An ablation can measure the effect of a particular change
only when the other conditions are held fixed. The earlier development sequence
changed several components together and does not provide that causal evidence.

The tasks sample one game and a curated set of situations. Models may have seen
Pokemon strategies during training. Success can reflect recalled knowledge,
online planning, or both. Task selection after observing failures can overfit
the evaluated model set. Development and final evaluation starts should
therefore remain distinct, and later task changes should create a new release.

Stochastic outcomes limit the meaning of a single win or loss. Deterministic
replay verifies execution but does not remove this evaluation uncertainty.
Ceiling effects remain in the pilot, and several reference policies are not
reliably successful across candidate starts. The report does not claim that the
current catalog separates every model tier or proves human-level gameplay.

= Availability and next validation

A release should provide source code, a machine-readable protocol, sanitized
attempt summaries, analysis commands, and the technical report. The website
should show one catalog with task status, model coverage, results, and replay
links where distributable. Users must supply a compatible game ROM. Game assets
and private account records are not part of the source distribution.

The registered validation is a staged cross-provider run with shared fresh
starts. Its results can replace the pending release section through the same
audited export and manuscript build. The earlier manuscript sources and all
development inputs remain archived so readers can trace how the protocol
changed.
// <<< BODY END
#bibliography("references.bib", style: paper-bib-style)
#pagebreak()
#include "si-body.typ"
