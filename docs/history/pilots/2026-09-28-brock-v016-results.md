# Brock battle pilot results

These are the first model runs from the PokeSim-generated Brock battle checkpoint.
They are separate from the earlier Rattata encounter. The budget was 250,000
reported tokens per model, including cached input, with the same frozen runtime,
prompt, visual inputs, controls, medium effort and Codex CLI 0.157.0 for all four.
The objective was to defeat Brock and earn the Boulder Badge.

The first screenshot shows Geodude because the checkpoint starts after Brock's
introduction, at the battle command menu. The party is wounded: level 12 Squirtle
starts at 8/34 HP, with five other Pokemon available. The reference is winnable.

| Model | Badge earned | Decisions | Actions | Reported tokens | Stop reason |
| --- | --- | --- | --- | --- | --- |
| Luna | No | 24 | 24 | 235,246 | token_budget |
| Terra | No | 22 | 24 | 231,046 | token_budget |
| Sol | No | 22 | 24 | 239,787 | token_budget |
| Astra | No | 22 | 40 | 242,148 | token_budget |

Combined usage was 948,227 reported tokens. Accounting was
complete. Each controller trace replayed, every supplied image was verified
against the actual client conversation, and all model settings matched except
model identity. No automatic retries, extra hints or budget extensions occurred.
The earlier wild-battle results remain unchanged. The new task and budget differ,
so these outcomes do not isolate the effect of increasing the token cap.

Review: `http://127.0.0.1:8942/brock-v016-review.html`.

## Battle victory versus badge registration

Sol and Astra defeated Brock, as shown in their victory screens and experience
gains. Neither reached the point where the game sets the badge and gym-event
flags before its budget stop. Their formal badge scores remain zero. This is
not evidence that they could not win the battle. Astra recovered after Squirtle
fainted by using another party member. Sol finished with Squirtle still alive.

Luna defeated Geodude but spent many short inputs on level-up dialogue and
stopped during the announcement of Brock's next Pokemon. Terra reached Onix
and stopped during its attack resolution. Every action trace stayed in Pewter
Gym. There were no context-summary calls. These are single-attempt observations.

Future reports should continue distinguishing opponent defeat, trainer victory
and reward registration. A battle-only objective could stop at verified trainer
victory, while a badge objective includes the reward dialogue. Changing that
scoring rule should be declared before a new trial, not applied retroactively.
