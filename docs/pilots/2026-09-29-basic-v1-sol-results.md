# Basic five-task suite pilot

The owner narrowed the active suite to five easy and medium tasks. No advanced
or endurance tasks are included. One Sol attempt per task exercised the actual
suite runner and report pipeline after fixture verification and unit tests.

Configuration: gpt-5.6-sol, medium effort, bounded gameplay policy, eight-response
segments, 12000 observed-context threshold, zero paid summaries. Each task began
with a fresh pinned save, notebook and conversation. The batch ceiling was
3750000 reported input plus output tokens. Cached input counts toward it.

| Task | Passed | Model decisions | Tokens |
| --- | --- | ---: | ---: |
| starter | Yes | 13 | 118,979 |
| wild-battle | Yes | 6 | 48,046 |
| heal | Yes | 9 | 83,645 |
| parcel | Yes | 101 | 1,014,963 |
| brock | Yes | 10 | 95,133 |

Total: 1360766 reported tokens and 139 model decisions. All five tasks completed.
Exact delivered text and screenshot pairs, state reconstruction, conversation
ordering, usage totals and controller replays passed for every task. No manual
intervention, automatic retry or budget extension occurred during model play.
This is one pilot sweep, not a measured reliability estimate or model ranking.

The healing objective grades full HP, cleared status and the original party at
Viridian Center after control returns. It does not grade PP. Blackout and party
replacement disqualify an attempt. The healthy Brock fixture begins during the
battle introduction before the first attack. Offline controller-only references
and idle negative traces passed for all five fixtures.

The frozen pilot source hash is
a754cb6c8f74b80497ec195977f06f8bcd64f824a7675f16f698ff7f5aa44e7b.
Later report-only changes prevent stale replay links and add download attributes.
A later CLI change returns a failing process status for batch infrastructure
errors. These changes did not alter the frozen model runtime or any trial.

Validation: 249 tests passed and 2 were skipped. Ruff and whitespace checks passed.
The 0.24.0 Python wheel built successfully. Browser checks confirmed the task
details, completed coverage, score and Brock replay link.

Report: http://127.0.0.1:8942/basic-suite-v1.html
JSON and CSV downloads contain suite attempt summaries. Historical starter
pilots are shown separately and excluded from this suite's score. Raw traces,
images and emulator states remain private and excluded from Git.
