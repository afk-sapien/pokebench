# Public replay format 3

A public replay is one file, `replays/<name>.gz`, read by one shared page, `replays/view.html?r=<name>`.
The page is plain JavaScript. It inflates the file with the browser's own `DecompressionStream('gzip')`
and loads nothing else. `<name>` uses only letters, digits, `.`, `_` and `-`, starts with a letter or
digit and is at most 200 characters. The writer is `write_replay` in `src/pokeagent_bench/public_site.py`
and the reader is the block between `// replay decoder begin` and `// replay decoder end` in
`src/pokeagent_bench/replay_assets/replay.html`.

## File

The file is gzip (level 9, modification time 0, so the same replay always gives the same bytes).
Inflated, it holds three parts in order:

1. The header length, a 4 byte little endian unsigned integer.
2. The header, that many bytes of ASCII JSON.
3. The body: every distinct tile, then every screen's tile numbers.

## Header

| Field | Meaning |
| --- | --- |
| `format` | Version of this layout. It is `3`. A reader refuses any other value. |
| `model`, `completed`, `action_policy`, `benchmark` | The scored attempt the replay belongs to. |
| `meta` | Run facts shown above the screen, such as task, label and milestones. |
| `places`, `outcomes` | Text tables. Steps point into them by position. |
| `steps` | One column per field, one entry per decision. See below. |
| `frames` | How to read the body. See below. |

`frames` holds `width` and `height` in pixels (160 by 144 for Game Boy screens), `tile_side` (8),
`palette` (up to 256 colours as `rrggbb` hex), `tiles` (distinct tile count), `count` (screen count)
and `index_bytes` (2, or 4 when there are more than 65,536 tiles).

`steps` holds `decision`, `before_frame`, `after_frame` (game frame counters), `tokens`, `screen` (the
screen number after the step), `actions` (lists of `[button, hold_frames, release_frames, times]`),
`place` and `outcome` (table positions, -1 when absent), `start` (the screen before the first step) and
`breaks` (a map from step position to its first screen, only where that differs from the previous
step's last screen). `cumulative` appears only when the recorded running totals do not equal the sum
of `tokens`.

## Body

Tiles come first: `tiles` blocks of `tile_side * tile_side` bytes. Each byte is a palette position and
each block is row by row. Tiles are numbered in order of first use.

Then come `count` screens. Each is `(width / tile_side) * (height / tile_side)` tile numbers, in
reading order (left to right, then top to bottom), each `index_bytes` long and little endian. Screens
are numbered in order of first use and each distinct screen is stored once.

The body length must be exactly `tiles * tile_side^2 + count * cells * index_bytes`, where `cells` is
the tile count of one screen. A reader refuses a file that does not match, a tile number at or past
`tiles` and a palette position at or past the palette length.

## Old addresses

Replays published before format 3 were self-contained pages at `replays/<name>.html`. That address is
now a small page that opens `view.html?r=<name>` with the same `#` part, so `#d=` (decision), `theme=`
and `tab=` still work.
`scripts/check_replay_tiles.py` compares a new export with the published format 2 pages, screen by
screen in RGBA pixels and step by step in every field.

## Changing the format

Raise `format`, keep the reader refusing versions it does not know, and say here what changed.
