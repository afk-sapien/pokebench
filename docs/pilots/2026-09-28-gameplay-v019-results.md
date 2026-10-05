# Structured gameplay retest results

The v019 retest used the current player-information-v018.1 policy and the
unchanged red-v0.18-experimental runtime. Four models received one original
bedroom starter attempt and one wounded-party Brock attempt each. All used
medium effort, fresh decision contexts, the subscription client and a
250,000-token cap per attempt. The protocol was recorded before model calls.

All eight controller traces replayed exactly. Every recorded structured input and current image matched the actual client history. Reported usage was 1,930,285 tokens out of the 2,000,000 allocation. Accounting was complete. No retries were run.

| Model | Task | Tokens | Decisions | Result |
| --- | --- | ---: | ---: | --- |
| Luna | Brock | 224,301 | 47 | Boulder Badge confirmed. |
| Luna | Starter | 243,506 | 56 | No formal completion. Final map Oaks Lab, party count 0. |
| Terra | Brock | 248,553 | 32 | Brock defeated. Token stop before the badge flag. |
| Terra | Starter | 241,645 | 40 | No formal completion. Final map Pallet Town, party count 0. |
| Sol | Brock | 243,534 | 39 | Brock defeated. Token stop before the badge flag. |
| Sol | Starter | 241,756 | 45 | No formal completion. Final map Oaks Lab, party count 0. |
| Astra | Brock | 241,604 | 36 | Brock defeated. Token stop before the badge flag. |
| Astra | Starter | 245,386 | 41 | No formal completion. Final map Pallet Town, party count 0. |

All four models left the bedroom and reached Pallet Town. Luna entered Oak's
lab without obtaining a starter. Sol followed Oak into the lab and stopped
during the introduction. Terra and Astra stopped during Oak's introductory
dialogue in Pallet Town. Every final party was empty.

All four models visibly defeated Brock. Only Luna completed the unchanged badge
objective. Brock's game script awards the badge after the TM34 reward dialogue,
so visible victory and badge receipt text are earlier than the confirmed flag.
The [pinned game script](https://github.com/pret/pokered/blob/a1a22aaf84d1675bcdbaeb194592379d586d838e/scripts/PewterGym.asm)
confirms this ordering. No scoring rule was changed after seeing the results.

Luna first received a visible victory observation after 100,636 reported tokens. It used another 123,665 tokens before formal completion. This separates combat progress from the considerable dialogue interaction cost. These timestamps refer to observations supplied to the model, not the first intermediate emulator frame on which a message appeared.

No model completed both short tasks, so the declared prerequisite for the
long attempt failed. The separate 1,000,000-token allocation was not used.

The earlier v016 visual Brock runs also had a 250,000-token cap. Two showed
visible victory and none completed the badge objective. This retest showed
four visible victories and one formal completion, but information, controls and
context policies differ. One attempt per model and task does not isolate the
cause of improvement or establish a reliable model ranking. Starter performance
still does not justify a full opening-to-gym test under the declared gate.

The next experiment should isolate dialogue interaction cost and navigation
memory separately. Preserve these runs and predeclare any changed observation,
control or scoring policy before new calls. Do not retrospectively convert a
visible victory into a completed badge objective.

[Open the local review](http://127.0.0.1:8942/gameplay-v019-review.html).
The protocol is in `2026-09-28-gameplay-v019-protocol.md`. Sanitized evidence is
in `paper/analysis/inputs/gameplay-v019-audit.json`. ROMs, screenshots, saves,
generated game data and raw client histories remain private and ignored by Git.
