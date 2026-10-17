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
  #paper-date | Exploratory technical report | Not peer reviewed
]
#v(8pt)
*Abstract*
#paper-abstract
// >>> BODY START
= Introduction

Playing Pokemon requires navigation, resource management, menu operation, battle
tactics, and quest completion. A full campaign tests these skills together, but
early navigation failure can hide later battle ability. PokeBench uses
checkpoints to test them separately. PokeBench Long measures progress through a
full campaign and is outside this report.

The focused pass covered #s("focused.tasks") tasks and #s("focused.starts")
registered starts per model. It produced #s("focused.finished") finished
attempts across #s("focused.models") models. The analysis retains useful results
through routine infrastructure repairs. It records changed conditions and
archived charges rather than discarding the earlier evidence.

The measured ability is agent performance within a declared framework.
Structured observations and mechanical shortcuts reduce the cost of reading
pixels and navigating repetitive menus. Those tools are part of the task.
Results do not establish unaided visual gameplay or model ability independent of
the interface.

= Methods

== Tasks and starting states

The categories were navigation, battle, operations, preparation, and objectives.
Operations measured manual menu use. Preparation measured choices made before
battle. Objectives combined gameplay skills to complete a quest. Every model
received the same registered save and task limits for each starting condition.
The Supporting Information lists task descriptions and actual budgets. The
companion analysis records starting-state and evaluation-specification
checksums.

Curated battle checkpoints specify the player's team, health, moves, and
inventory. Preparation tasks accept a constrained plan and grade the resulting
team with a fixed battle controller. The model does not play those grading
battles. Preparation scores depend on both the plan and reference controller.
They do not estimate the win probability of an optimal player.

Revised forest, cave, boulder, and blocked-route navigation fixtures have
trainers already defeated and random wild encounters disabled. This prevents
incidental battles from becoming the main navigation challenge. Original
navigation attempts remain archived, and their charges remain in accounting.
Other tasks retain their declared game mechanics.

== Agent interface and budgets

Gameplay observations included the current screenshot and structured player
information: local map, party, moves, bag, visible dialogue, and recent actions.
Agents could request further information through inspection. Private evaluator
flags and future random outcomes were excluded. Menu-operation tasks disabled
shortcuts that would solve the tested operation. Strategy tasks allowed
mechanical commands for items, moves, and switching while leaving those choices
to the model.

The pass used current-image presentation and requested low reasoning effort.
Recent context was bounded by #s("focused.context_turns") turns and a configured
#s(
  "release.context",
) token threshold. Context rebuilding avoided paid summarization calls. These
settings do not establish identical hidden computation across providers.
Recorded model identifiers appear in @tbl:focused-identifiers.

Decision limits were the primary task budget, with higher token limits as
spending backstops. Decisions, controller actions, and emulator frames are
different quantities. A run reaching its decision limit is a finished scored
failure, not a pending job. Reported tokens include input and output usage,
including cached input where the provider reports it. They are not converted to
subscription dollars.

== Scoring and aggregation

Gameplay tasks used their recorded completion score. Preparation used the
reference controller's win rate after the model's submitted changes. Registered
variants were averaged within score groups. Groups were averaged within
categories, then categories received equal overall weight. The #s(
  "focused.tasks",
) task entries form #s("focused.score_groups") score groups because a related
operational variant shares a group. Multiple starts do not make one battle count
more than another.

Infrastructure errors were tracked separately from model outcomes. Repaired
attempts replaced affected comparison cells, while original artifacts and
charges remained archived. There were #s("focused.evaluation_errors") unresolved
evaluation errors in the initial matrix. This does not prove that every
interface behavior was correct. Rejected responses can occur inside a completed
attempt, so the audit reports them separately.

== Failure review and repeats

The audit counted rejected response decisions and inspected selected traces. A
rejected response is an interface symptom, not automatically a parser bug.
Repeated movement within one map suggests stalled navigation, but the trace
alone cannot exclude a controller defect.

The repeat check selected #s("repeat.tasks") tasks after examining initial
results: forest navigation, the underleveled Lorelei battle, and move
preparation. Models received additional attempts from the same saves with
unchanged task budgets and the latest repaired runtime. The plan registered #s(
  "repeat.planned",
) additional attempts before execution. These repeats measure variability on
selected conditions. They neither sample all game randomness nor estimate
reliability across the full suite. Repeats are reported separately rather than
giving selected tasks extra leaderboard weight.

= Results

== Overall and category scores

Opus obtained the highest initial overall score, #s("focused.score.opus")%,
followed by Sol at #s("focused.score.sol")% (@tbl:focused-ranking). Category
results showed different strengths. Sol scored highest in battle, while Sonnet
scored highest in preparation (@tbl:focused-categories). These are descriptive
comparisons from recorded starts, not statistical claims of superiority.

#figure(tbl("tbl.focused-ranking"), caption: [Initial focused-pass results.
  Overall score is the equal-category average in percent. Token totals cover
  selected current attempts, excluding archived attempts. Finished includes
  successful and unsuccessful model outcomes.]) <tbl:focused-ranking>

#figure(tbl("tbl.focused-categories"), caption: [Category scores in percent.
  Preparation uses the fixed controller's win rate after a model submission.
  Other categories use task completion scores. Categories receive equal overall
  weight.]) <tbl:focused-categories>

Difficulty was uneven. All models achieved full scores on #s(
  "focused.all_full_score_tasks",
) tasks, while all scored zero on #s("focused.all_zero_tasks") tasks. Easy tasks
provided capability coverage but little separation. Universal failures need
further feasibility and trace review before being attributed to model limits.
Neither extreme alone proves that a task should be removed.

== Failure evidence

The audit found #s("focused.budget_stops") attempts reaching the decision limit
and #s("focused.challenge_failures") ending in a failed task condition. Across
#s("focused.trace_decisions") recorded gameplay decisions, #s(
  "focused.format_error_decisions",
) were rejected for providing no controller action or valid history request.
Errors occurred in #s(
  "focused.runs_with_format_errors",
) runs, with #s("focused.warp_errors") concentrated in Saffron Gym navigation.
This cluster merits focused review rather than attributing every failed task to
formatting.

Selected traces showed distinct problems. Sol and Opus remained on Mt. Moon's
entrance floor when their decision limits expired. Opus's boulder trace recorded
an unsuccessful pushing route and a plan to reset the room. Its species-capture
attempt reached a Pikachu battle but had not caught it at the limit. These
observations establish unfinished progress without assigning sole responsibility
to the model or framework.

The all-zero league-preparation result also concealed partial progress. Its
reference controller reached late opponents, including the Champion, before
losing. This is a limit of the terminal win-rate score, not evidence that the
submitted teams made no progress.

The Lorelei comparison exposed a tactical difference. Sol used Amnesia
repeatedly before attacking and won. Opus used Hypnosis, switched early to
Pikachu, and later lost. Neither attempt recorded a response-format error.
Strategy and resource use are plausible contributors, but a single battle cannot
separate strategy from favorable randomness. The local leaderboard links both
source replays.

== Usage and repairs

The initial pass reported #s("focused.reported_tokens") tokens, including #s(
  "focused.archived_tokens",
) from archived attempts. A further #s("focused.unknown_reserve") tokens were
reserved for interrupted calls with missing usage. This reserve is not measured
consumption. Selected current attempts accounted for #s(
  "focused.selected_tokens",
) tokens.

Recorded repairs included battle-free navigation fixtures, provider timeout and
response diagnostics, and lossless encoding for an oversized memory inspection.
The latter continued the affected run from its checkpoint with cumulative usage.
Routine repairs preserved completed comparisons. The pass nevertheless spans
recorded backend revisions, limiting causal claims about small ranking gaps.

== Matched repeat check

At this report snapshot, #s("repeat.finished") of #s("repeat.planned")
additional attempts were complete, using #s("repeat.tokens") reported tokens.
The table labels unfinished attempts explicitly (@tbl:focused-repeats). Across
#s("repeat.pairs") selected model-task pairs, #s("repeat.changed") had a
completed repeat with a score different from its initial attempt. The full
pattern is reported rather than replacing an unfavorable initial result with a
better repeat.

#figure(tbl("tbl.focused-repeats"), caption: [Matched repeat scores in percent.
  Initial scores are from the main pass. Repeats use the same saves and task
  budgets. Preparation scores are controller win rates. These selected repeats
  do not change main leaderboard weights.]) <tbl:focused-repeats>

== Sensitivity to task selection

Removing each score group in turn left Opus highest and Luna lowest, but changed
some middle rankings (@tbl:focused-sensitivity). The calculation reused existing
outcomes with the same category weighting. These ranges describe dependence on
task selection. They are not confidence intervals and do not measure repeated
model sampling.

#figure(tbl("tbl.focused-sensitivity"), caption: [Rank ranges after omitting
  each score group once. Ties share a rank. The main leaderboard is
  unchanged.]) <tbl:focused-sensitivity>

= Limitations and next steps

The initial ranking supports exploratory comparison. It depends on task
selection, budgets, observations, tools, and the preparation controller. Equal
category weights are a design choice. Most tasks initially had one attempt per
model and registered start. Subscription transports may differ in hidden
reasoning, caching, latency, and model-version behavior. Token totals describe
resource use under these conditions, not universal cost efficiency.

Follow-up diagnostics found that compact model messages omitted task-completion
status and visible-object movement details even when the full trace recorded
them. The message builder has been repaired, but the frozen repair trials and
Long pilot did not use that correction. Their outcomes therefore do not measure
the corrected feedback path. The next useful comparison should verify that path
before another broad pass. Full-game scoring remains a separate PokeBench Long
evaluation rather than another category here.

= Availability

The local leaderboard provides task goals, outcomes, budgets, usage, and replay
links for gameplay attempts. Earlier comparisons remain accessible in its
archive. The analysis contains summaries and checksums rather than ROMs,
emulator states, private model text, or account records. Source generators
reproduce the page and report tables. This revision remains local. The earlier
manuscript is preserved alongside the existing Paper Scaffold toolchain
@scaffold.
// <<< BODY END
#bibliography("references.bib", style: paper-bib-style)
#pagebreak()
#include "si-body.typ"
