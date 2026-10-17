# Provider recovery v058

This change continues the existing focused pass. Finished trials stay intact.
Only the three errored attempts are retried, with their original results and
charges retained. Gameplay rules, observations, task caps and graders stay the same.

The bounded providers now allow up to 600 seconds per response, limited by the
remaining trial wall time. The previous 180 second cutoff could terminate a slow
response. Waiting longer does not send another generation request or advance the
game. This applies to both subscription providers and is recorded in the manifest.

OpenAI failed turns now retain their service error and thread and turn IDs.
Transport timeouts retain the same IDs. Unknown usage remains unknown and is
reserved conservatively. We do not silently retry an in-flight generation.
Claude rejected structured responses are saved in decision records for diagnosis.

The observed Haiku warp error was not a verified grader bug. It stopped at
(10,16), believed a nearby object was Sabrina, and repeatedly asked for human
confirmation. The target is (9,9). We preserve this failure and allow one fresh
attempt as requested, without adding route hints or changing the finish condition.

Archived incomplete usage reserves remain in the spending ledger after retries.
The remaining Claude cells have queue priority, subject to the existing pilot
checks and two-worker limit per provider. Local results link the original errors
alongside their replacements.


## Lossless inspection repair v059

Sol's capture-and-prepare attempt stopped before call 506 because rendering its
memory inspection as an indented tree exceeded 64,000 UTF-8 bytes. The underlying
information fit within the limit. Oversized inspections now use compact JSON for
the inspection section only. Every field and history entry is retained. Ordinary
observations and small inspections keep their existing readable presentation.
The same 64,000 byte limit still applies after encoding. No model summary call,
truncation, hint, or game action is introduced.

The failed boundary can be continued through an explicitly archived checkpoint
migration because no call was in flight and usage and controller logs are complete.
The continuation retains the original model session, 505 decisions, usage, game
state and remaining limits. The original failure and checkpoint remain archived.
