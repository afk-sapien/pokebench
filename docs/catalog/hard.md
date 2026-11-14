# PokeBench Hard

PokeBench Hard is a third table for longer focused tasks, such as a whole dungeon or a
multi-step story chain. It never changes PokeBench or PokeBench Long. Its tasks live in
`src/pokeagent_bench/catalogs/hard/`, and the Short catalog, its hashes and its runtime
version stay the same.

## Scoring

Each Hard task lists ordered milestones in its catalog entry, for example the floors of a
dungeon and its exit. A milestone is a fixed check on game memory: map, position, event
flags, bag items, badges, story flags and League wins. A run earns one point for each
milestone, in order, and each one must hold on two different frames. The task score is the
share of milestones reached. A run that blacks out or reaches its decision cap keeps the
points it already earned.

The model sees only the task goal, the same screen and the same text it sees in PokeBench.
It never sees the milestones, their checks or a running score. A start state that already
meets a milestone is refused.

Category scores use the same rules as PokeBench: equal weight for each task in a category,
then the mean of the four ranked categories. Operations has no Hard task yet, so the Hard
average covers the categories that have tasks. Check coverage before comparing averages.

## Commands

```sh
uv run pokebench catalog --benchmark pokebench-hard
uv run pokebench run --model MODEL --suite hard --dry-run
```

Each Hard task needs a checked start state and a scripted reference run that reaches every
milestone. Its decision cap is about five times the reference, and its token budget is
15,000 tokens per allowed decision. No model has run the suite yet, and no Hard result is
published.

## Tasks

| Task | Start | Milestones | Reference decisions | Cap |
| --- | --- | --- | --- | --- |
| Cross all of Victory Road | 1F entrance, every boulder switch unsolved | 6 | 236 | 1,200 |
| Reach Articuno in Seafoam Islands | 1F west entrance, no boulder in any hole | 6 | 83 | 420 |
| Reach Giovanni in Silph Co. | 1F front door, every Card Key door locked, no Card Key | 5 | 76 | 380 |
| Travel from Pewter City to Lavender Town | Pewter Pokemon Center, early story, Cut and Flash party | 6 | 221 | 1,100 |
| Defeat the Elite Four and the Champion with no items | Lorelei's room, empty bag, six level 56 Pokemon | 5 | 100 | 500 |

In Seafoam Islands only the two B3F holes gate Articuno. The boulder puzzles on the upper
floors are optional, so they earn no milestone. The B3F milestones count in order, so a run
that fills the east hole first earns that point only after it also fills the west hole.

In Silph Co. beaten trainers stand at both ends of the 5F corridor that holds the Card Key.
The only way in is the 5F pad at (9, 15): ride it to 9F and back, then step off it downward.
The text map shows warp pads as exits with no destination, as the screen does, and Card Key
doors as `D`. Giovanni's room on 11F opens only from the west hall, which only the second
pad in the 7F room behind a locked 3F door reaches.

From Pewter City to Lavender Town the start is before the S.S. Ticket, so a guard still blocks
the robbed house in Cerulean City. Nobody knows Fly, the Saffron City gates are shut and Snorlax
blocks Route 12, so Rock Tunnel is the only way in. On Mt. Moon B2F the two fossils fill the
only gap north, and taking one makes the Super Nerd take the other. Cut clears the small trees
in Cerulean City at (19, 28) and on Route 9 at (5, 8). The text map shows them as `T`. Rock
Tunnel shows no terrain until Flash, as the screen shows none.

The Elite Four task starts from the Short League start with the bag and money emptied, so HP
and PP carry through all five battles. Recover and Rest are the only healing. No party move is
a one-hit knockout, a fixed-damage move, Hyper Beam or Explosion. The level is set so the
scripted reference just wins: it picks the strongest typed move each turn, heals below a third
of its HP and switches to the healthiest strong Pokemon. At level 56 it ends with one Pokemon
standing, and at level 54 it blacks out against the Champion. A League win is read from the
game's own defeat flags, and the last point also needs a new Hall of Fame record.

## Scripted references

`scripts/reference_hard_tasks.py` plays each task with the same assisted commands a model
gets, one decision per command. It makes no model calls. It replays the native inputs
through the catalog runner and writes the reference proof next to the private start.

```sh
uv run python scripts/reference_hard_tasks.py --rom ROM --game-data GAME_DATA \
  --fixtures FIXTURES --output OUTPUT --tasks navigation-hard-victory-road navigation-hard-seafoam
```
