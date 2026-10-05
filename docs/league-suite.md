# Elite Four to Champion

Package 0.25.0 and benchmark red-v0.35-experimental add a sixth task, Become
Champion. The observation and bounded conversation policies are unchanged.
The five-task red-basic-v1 definition and its registered comparison are preserved.

The new task starts in Lorelei's entrance room before speaking to her, with
all eight badges, a healthy party, full move PP, no Elite Four victories and
zero Hall of Fame entries. The goal is to defeat Lorelei, Bruno, Agatha, Lance,
and the Champion, then finish Hall of Fame registration.

The selected checkpoint comes from an archived PokeSim Red Ember run. It is a
first League attempt, not the old level-100 rematch fixture. Preparation uses
120 no-input frames to finish the archived arrival animation, followed by the
standard one-frame checkpoint render. It preserves the party, bag and existing
nicknames. No memory edits, added items, artificial healing or level changes are
used. The agent is instructed not to assign new nicknames.

| Pokemon | Level | Moves |
| --- | ---: | --- |
| Snorlax | 58 | Double Edge, Hyper Beam, Rest, Surf |
| Graveler | 53 | Earthquake, Explosion, Rock Throw, Selfdestruct |
| Charizard | 55 | Cut, Slash, Strength, Flamethrower |
| Vileplume | 31 | Absorb, Poisonpowder, Stun Spore, Sleep Powder |
| Parasect | 30 | Scratch, Stun Spore, Leech Life, Spore |
| Weezing | 41 | Tackle, Smog, Sludge, Smokescreen |

The starting supplies include five Full Restores, five Revives, one Max Potion
and one Elixer. This is an uneven campaign party, not a competitively optimized
team. Difficulty is provisionally hard. The default token ceiling is 3000000,
with the same 1000-decision and one-hour wall limits as the basic suite. Input
including cached tokens and output count toward the allowance. Success ends the
trial immediately. Caps require calibration through model trials.

## Verification and scoring

A fresh isolated PokeSim policy completed all five battles and registered the
first championship in 9596 controller actions and 260955 emulated frames.
Its exact controller replay independently reproduced the completed outcome.
These offline checks consume no model tokens and do not count as model results.
Both prepared bundles additionally rerun the reference and verify a no-input
negative trial. A reference proves the checkpoint is solvable, not that every
model or controller strategy will succeed.

Success uses the existing Champion milestone: the Champion victory flag, a new
Hall of Fame registration relative to the starting save, and presence in the
Hall of Fame map must agree for two consecutive game frames. Entering the final
room, beating only the Elite Four, or reaching the Champion without winning
receives no completion point. The League fixture validator rejects rematches,
previously beaten Elite Four members, missing badges, injured parties, active
battles and unsettled arrival screens. Hidden grading flags remain private.

Each task scores one completion point. The six-task report averages per-task
pass rates equally, without selecting the best repeat. Results from a five-task
suite must not be pooled into a six-task ranking or represented as a completed
six-task trial. Models need matching fixture, settings and runtime versions.

## Local bundles and commands

Three suite IDs are available:

- `red-basic-v1`: the original five tasks, unchanged.
- `red-league-v1`: the League task alone.
- `red-basic-plus-league-v1`: all six tasks, 6750000 tokens maximum per model per sweep.

The corresponding prepared development bundles live under `data/`. Definitions,
runner and reports ship in the Python package. ROMs, saves and generated game
data remain private. A compatible local archived save is needed to reproduce
this checkpoint import. This does not yet distribute public benchmark fixtures.

```sh
uv run pokeagent suite catalog --suite-id red-league-v1
PYTHONPATH=src .venv/bin/python scripts/prepare_league_fixture.py \
  --rom /path/to/pokered.gb --state /path/to/pre-league.state \
  --pokesim /path/to/pokesim --output data/new-league-curation
uv run pokeagent suite prepare --suite-id red-league-v1 \
  --rom /path/to/pokered.gb --bindings data/new-league-curation/bindings.json \
  --output data/new-league-suite
uv run pokeagent suite run --suite data/red-league-v1 \
  --rom /path/to/pokered.gb --game-data /path/to/game-data \
  --models gpt-5.6-luna gpt-5.6-terra gpt-5.6-sol --repeats 1 \
  --total-token-budget 9000000 --output data/league-pilot --dry-run
```

The last command only registers a proposed plan. Removing `--dry-run` makes
subscription model calls. Adding the fixture does not launch new model trials.
For all six tasks, prepare with the `red-basic-plus-league-v1` suite ID and a
bindings file containing all six task IDs. Report generation automatically uses
the selected suite's tasks, token caps and scoring denominator.

## Menu interface revision

Package 0.26.0 and red-v0.36-experimental add explicit item-use and party-switch
commands to reduce mechanical menu decisions. The League checkpoint and scoring
remain unchanged. See [menu costs, commands and verification](menu-shortcuts.md).
The original v0.35 attempts retain their frozen runtime and results. Compare
models using matching controller revisions.
