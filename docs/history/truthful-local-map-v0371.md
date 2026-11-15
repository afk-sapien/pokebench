# Truthful local map, v0.37.1

A prompt dry-run of `navigation-victory-road`, `navigation-pewter-to-lavender` and `objectives-cinnabar-gym` replayed each reference route through the runner with a scripted provider. No model was called. Every step of each route can be read from the prompt or found by playing. Four parts of the rendered state told the model something false, and v0.37.1 fixes all four.

| Render | Before | Since v0.37.1 |
| --- | --- | --- |
| Overworld ledge | `#` blocked terrain | `v`, `<` or `>` in its hop direction, with a ledge legend line |
| Pokemon Mansion 3F broken floor | `.` walkable terrain | `o` with its own gap legend line |
| Hole legend in the text packet | `O: visible hole` beside `O: visible object` | `o: visible hole in the floor` |
| Boulder pushed into a hole | "Moved 0 tiles, then blocked" | the object change `no longer visible`, and no blocked square |

## Ledges

The ROM's ledge table lists the tiles the game hops. In the overworld tileset the player hops a square whose bottom-left tile is 0x36 or 0x37 going down, 0x27 going left, or 0x0D or 0x1D going right. The map marks those tiles with the arrow of their hop direction. The `navigation-pewter-to-lavender` reference route hops 9 ledges that the old map drew as blocked terrain.

Floor arrows now appear in the legend only on the tilesets that draw them, the facility and gym tilesets. The ledge arrows and floor arrows therefore never share a map.

## Mansion 3F

Pokemon Mansion 3F draws its broken floor and the map border as tile 0x11, which the game data lists as walkable. The map's script drops the player to 1F from three of those squares, (16,14), (17,14) and (19,14). The map marks every visible 0x11 square on 3F as `o` with the legend "visible gap in the floor. Some gap squares drop you to a lower floor". Only on-screen graphics are read, so the three scripted squares are not singled out.

## Text packet and movement result

Legend keys are map glyphs, so the text packet now prints them as they are. The earlier capitalized form turned the hole glyph `o` into the object glyph `O`.

A move result now also reports an object that was visible before the move, is gone after it, and whose old square is still on screen. That is how a boulder pushed into a Victory Road or Seafoam hole looks. An object that only scrolled out of view is not reported. When the player did not move, the outcome reads "Player position unchanged. Visible objects moved or disappeared. Check the updated map before treating the move as blocked."
