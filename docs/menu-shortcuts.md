# Gameplay menu shortcuts

Package 0.26.0 and benchmark red-v0.36-experimental add mechanical menu commands
to the structured gameplay track. The model selects the strategy, item, party
slot and move. The adapter executes that selection through normal controller
input. The visual baseline is unchanged.

## What the League runs showed

The audited restart comparison used the same League checkpoint and a three
million reported-token allowance per model. All three stopped at the token
limit without becoming Champion. The following are recorded decision costs,
including cached input and output tokens:

| Model | Total tokens | Directional menu decisions | Tokens for those decisions | Separate FIGHT decisions | Tokens for FIGHT |
| --- | ---: | ---: | ---: | ---: | ---: |
| Luna | 2,983,138 | 3 | 29,139 | 57 | 642,559 |
| Terra | 2,981,853 | 27 | 302,497 | 97 | 1,165,589 |
| Sol | 2,985,543 | 95 | 1,062,807 | 32 | 380,478 |

The directional category counts decisions whose sole action was an arrow press
in an observed menu. The FIGHT category counts decisions whose sole action was
opening FIGHT. All single-button decisions, including confirmations, accounted
for 1,207,432 tokens for Sol. That broader category includes the directional
category and must not be added to it.

Party choices also sometimes appeared as HP values, such as `83 283`, instead
of a Pokemon name. Party choices now carry a one-based slot and the owned
Pokemon's visible nickname. Identical names and HP values remain distinguishable
by slot.

These measurements identify overhead. They do not establish how many tokens
new runs will save or whether a model will win. New model trials are needed for
that comparison.

## Commands

Commands use the existing gameplay command schema. Each has `count: 1`.

| Command | Argument example | Meaning |
| --- | --- | --- |
| `use_item` | `Full Restore:1` | Use exactly one specified item on current party slot 1 |
| `use_item` | `Revive:2` | Use one Revive on current party slot 2 |
| `use_item` | `Elixer:1` | Restore PP with one Elixer on current party slot 1 |
| `switch_pokemon` | `3` | Select current party slot 3 in battle, or swap it into the lead outside battle |
| `use_move` | `2` | Open FIGHT if needed and select move slot 2 |

`use_move` already existed. The model instructions now explicitly tell agents
to use it without a separate FIGHT decision. The new commands are available to
the model provider and through the existing MCP `gameplay_command` tool.

Supported items are Potion, Super Potion, Hyper Potion, Max Potion, Full Restore,
Antidote, Burn Heal, Ice Heal, Awakening, Parlyz Heal, Full Heal, Revive,
Max Revive, Elixer and Max Elixer. Elixir spellings are also accepted. Ether,
TMs, evolution items, capture balls and battle boosts are not included in this
initial interface. Ether would require an additional explicit move target.
The agent can still use ordinary controller commands for other menus.

Slots always refer to the current party. Outside-battle switching changes the
party order, so subsequent choices must use the updated observation. Switching
supports the normal battle menu, a forced replacement and the game's optional
switch prompt. Fainted or already-active battle targets are rejected.

## Bounds and auditability

No RAM writes, added items, artificial healing, automatic target selection,
route planning or hidden enemy information are introduced. A healing or switch
action retains its normal battle turn cost and the opponent's response.
Continue-only text is advanced with the existing dialogue handler. Unexpected
choices are left for the agent.

Each macro is limited to 2400 navigation frames, further bounded by the configured
dialogue frame allowance. Individual controller actions and global action,
frame and wall-time limits still apply. Existing dialogue settling retains its
own configured allowance. A macro can therefore contain multiple recorded
controller actions but needs only one agent decision.

The result reports the selected item and slot, whether the effect completed,
and whether the item was consumed. An unconfirmed effect is not retried
implicitly. Reusing the same operation ID returns the prior result without
executing again. Every raw controller action remains in the replay trace.

## Verification

The regression script reconstructs fourteen saved menu situations from the
audited Sol League attempt using its original controller trace. It verifies
source screenshot hashes, then tests healing, reviving, PP restoration,
ordinary and forced switching, the optional switch prompt, field lead changes,
and starting from partially navigated menus. A fifteenth case checks interruption
at the global frame limit.

Each successful item case consumes exactly one item. The script verifies target
identity, the resulting party or active slot, return to the expected decision
screen, and idempotent operation retries. Every resulting controller trace is
independently replayed. All fifteen cases passed without model calls.

The script requires the retained Sol League run whose decision numbers identify
these regression cases. It is not a generic extractor for arbitrary attempts.
ROMs, saves, generated game data and run artifacts remain private.

```sh
PYTHONPATH=src .venv/bin/python scripts/verify_menu_shortcuts.py \
  --rom /path/to/pokered.gb \
  --run data/league-v1-comparison-restart-01/batch/cell-0003 \
  --game-data /path/to/game-data --output data/new-menu-verification

PYTHONPATH=src .venv/bin/python scripts/analyze_menu_overhead.py \
  --run data/league-v1-comparison-restart-01/batch/cell-0001 \
        data/league-v1-comparison-restart-01/batch/cell-0002 \
        data/league-v1-comparison-restart-01/batch/cell-0003 \
  --output data/new-menu-overhead.json
```

The original League results and frozen runtime remain unchanged. Fresh runs
with these commands use a new harness and observation policy version. Do not
pool their results with the original menu interface when ranking models.
