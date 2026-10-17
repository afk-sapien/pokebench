# Sol parcel roundtrip with a million-token allowance

Sol completed the task. It collected Oak's Parcel in Viridian City, returned it
to Professor Oak, and received the Pokedex. The evaluator confirmed collection,
parcel removal, the delivery flag, a Pokedex and no battle. The run stopped on
completion at 875,922 reported tokens across 133 decisions. It did not spend the
full 1,000,000-token allowance.

| Attempt | Token ceiling | Reported tokens | Decisions | Outcome |
| --- | ---: | ---: | ---: | --- |
| Earlier pilot | 250,000 | 245,291 | 39 | Route 1, parcel not collected |
| New attempt | 1,000,000 | 875,922 | 133 | Parcel delivered, Pokedex received |

The new attempt began from the identical post-starter checkpoint. It used the
same frozen source, model gpt-5.6-sol, medium effort, prompt, catalog, observation
policy and fresh-decision memory configuration. It did not resume the exhausted
pilot. The user requested the larger token ceiling. Supporting caps rose to
400 calls, 6,000 raw actions, 480,000 game frames and 7,200 wall seconds so they
would not preempt that allowance. The previous 100-call limit would have stopped
this trajectory before its completion.

Sol reached Viridian City, searched several buildings, acquired the parcel and
returned south through Route 1. It chose to flee encounters when Charmander's
HP was low. After returning to Pallet Town, it found the laboratory and spoke
to Oak. Searching for buildings and navigating took many decisions, so completion
does not establish efficient planning or a reliable success rate. The trial used
1,188 raw actions and 32,925 game frames. Wall duration was 918.76 seconds.

Every one of the 133 recorded text/image pairs was verified together in an
actual client message. All calls had complete usage accounting, no context
summary calls occurred, and the full controller trace replayed with matching
screenshots and evaluator evidence. All configuration fields except run limits
matched the earlier pilot. There was no reset credit, route hint, state edit,
helper model or additional attempt in this budget extension experiment.

This provides a successful replayable solution from the parcel checkpoint.
The original fixture metadata records its reference-pending status at creation,
which remains unchanged. The successful trace is preserved separately rather
than rewriting historical scenario or run manifests.

Both token and supporting ceilings changed, and model sampling can change the
trajectory. One failed attempt and one successful attempt do not isolate budget
as the sole cause or establish a minimum required allowance. The original
250,000-token failure remains in the comparison and review.

[Watch both attempts](http://127.0.0.1:8942/parcel-v024-1m-review.html#run=parcel-roundtrip-v024-sol-1m-01&decision=1).
The declared protocol is `2026-09-28-parcel-v024-1m-protocol.md`. Sanitized findings
are in `paper/analysis/inputs/parcel-v024-1m-audit.json`. Raw states, client logs,
frozen runtime and replay artifacts remain local and ignored by Git.

Validation passed 192 repository tests, with two optional emulator checks skipped,
and lint. The rebuilt paper has 5,680 main-text words, Flesch-Kincaid grade 10.9
and reading ease 38. The scaffold verification gate passed.
