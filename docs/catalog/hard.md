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

In Seafoam Islands only the two B3F holes gate Articuno. The boulder puzzles on the upper
floors are optional, so they earn no milestone. The B3F milestones count in order, so a run
that fills the east hole first earns that point only after it also fills the west hole.

## Scripted references

`scripts/reference_hard_tasks.py` plays each task with the same assisted commands a model
gets, one decision per command. It makes no model calls. It replays the native inputs
through the catalog runner and writes the reference proof next to the private start.

```sh
uv run python scripts/reference_hard_tasks.py --rom ROM --game-data GAME_DATA \
  --fixtures FIXTURES --output OUTPUT --tasks navigation-hard-victory-road navigation-hard-seafoam
```
