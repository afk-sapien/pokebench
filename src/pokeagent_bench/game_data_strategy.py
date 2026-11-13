"""Generate strategy data from a checkout of https://github.com/pret/pokered.

Copied from PokeSim so that setup needs no PokeSim checkout. Keep the output byte identical.
Only map geometry and game constants are exported, never ROM images.
"""
import re

DEBUG_BLOCK = re.compile(r"^IF DEF\(_DEBUG\)\n.*?^(?:ELSE\n(.*?)^)?ENDC\n", re.M | re.S)


def release_source(text):
    """Drop debug build blocks, such as the pokeyellow warps out of the player's room."""
    return DEBUG_BLOCK.sub(lambda match: match[1] or "", text)


def generate(src, revision):
    def read(path):
        return release_source((src / path).read_text(encoding="utf-8"))

    def constants(path):
        return {name: int(value, 16) for name, value in re.findall(
            r"^\s*(?:const|map_const)\s+(\w+).*?\x3b\s*\$([\dA-Fa-f]+)", read(path), re.M)}

    maps = constants("constants/map_constants.asm")
    species = constants("constants/pokemon_constants.asm")
    items = constants("constants/item_constants.asm")
    items.update({f"HM{i + 1:02d}": 0xC4 + i for i in range(5)})
    types = constants("constants/type_constants.asm")
    dex = {name: int(value) for name, value in re.findall(
        r"const DEX_(\w+).*?\x3b\s*(\d+)", read("constants/pokedex_constants.asm"))}
    moves = {}
    for name, effect, power, typ, accuracy, pp in re.findall(
        r"^\s*move\s+(\w+),\s*(\w+),\s*(\d+),\s*(\w+),\s*(\d+),\s*(\d+)",
        read("data/moves/moves.asm"), re.M):
        moves[len(moves) + 1] = dict(name=name, effect=effect, power=int(power), type=types[typ],
                                    accuracy=int(accuracy), pp=int(pp))
    effects = {"SUPER_EFFECTIVE": 2, "NOT_VERY_EFFECTIVE": 0.5, "NO_EFFECT": 0}
    matchups = [[types[a], types[b], effects[c]] for a, b, c in re.findall(
        r"db\s+(\w+),\s*(\w+),\s*(\w+)", read("data/types/type_matchups.asm"))]
    mons = {}
    move_ids = {move['name']: mid for mid, move in moves.items()}
    learnsets = {name.replace('_', '').upper(): [(int(level), move_ids[move]) for level, move in re.findall(r'\bdb\s+(\d+),\s*(\w+)', block) if move in move_ids]
                 for name, block in re.findall(r'^(\w+)EvosMoves:\n(.*?)(?=^\w+EvosMoves:|\Z)', read('data/pokemon/evos_moves.asm'), re.M | re.S)}
    for path in sorted((src / "data/pokemon/base_stats").glob("*.asm")):
        lines = [line.split(chr(59))[0].strip() for line in path.read_text(encoding="utf-8").splitlines()]
        fields = [line[3:].strip() for line in lines if line.startswith("db ")]
        name = fields[0].removeprefix("DEX_")
        if name not in species:
            continue
        hm_names = set(re.findall(r"\b(CUT|FLY|SURF|STRENGTH|FLASH)\b", " ".join(lines)))
        hms = [mid for mid, move in moves.items() if move["name"] in hm_names]
        mons[species[name]] = dict(name=name, dex=dex[name], hms=hms, growth=fields[6].removeprefix("GROWTH_"), types=[types[t.strip()] for t in fields[2].split(",")],
                                  catch_rate=int(fields[3]), stats=[int(v) for v in fields[1].split(",")],
                                  initial_moves=[move_ids[v.strip()] for v in fields[5].split(',') if v.strip() in move_ids],
                                  learnset=learnsets.get(name.replace('_', ''), []))
    events = {}
    index = 0
    for line in read("constants/event_constants.asm").splitlines():
        line = line.split(chr(59))[0].strip()
        if line.startswith(("const_next ", "const_skip")):
            parts = line.split(maxsplit=1)
            expr = parts[1] if len(parts) > 1 else "1"
            expr = re.sub(r"\$([\da-fA-F]+)", r"0x\1", expr)
            if not re.fullmatch(r"[\dxXa-fA-F +\-]+", expr):
                raise ValueError(expr)
            value = sum(int(term, 0) for term in expr.replace("-", "+-").replace(" ", "").split("+") if term)
            index = value if parts[0] == "const_next" else index + value
        elif line.startswith("const EVENT_"):
            events[line.split()[1]] = index
            index += 1
    prices = [int(v) for v in re.findall(r"^\s*bcd3\s+(\d+)", read("data/items/prices.asm"), re.M)]
    marts = {}
    for name, stock in re.findall(r"(\w+)ClerkText::\s*\n\s*script_mart ([^\n]+)", read("data/items/marts.asm")):
        marts[name] = [items[v.strip()] for v in stock.split(",") if v.strip() in items]

    def aliases(text, label_pattern, value_pattern):
        out = {}
        pending = []
        for line in text.splitlines():
            label = re.match(label_pattern, line)
            if label:
                pending.append(label[1])
            val = re.search(value_pattern, line)
            if val and pending:
                for key in pending:
                    out[key] = val[1]
                pending = []
        return out

    blocks = aliases(read("gfx/tilesets.asm"), r"(\w+)_Block::", r'INCBIN "([^\"]+\.bst)"')
    collisions = aliases(read("data/tilesets/collision_tile_ids.asm"), r"(\w+)_Coll::", r"coll_tiles (.+)")
    tilesets = [v for v in re.findall(r"^\s*tileset (\w+),", read("data/tilesets/tileset_headers.asm"), re.M)]
    tileset_names = {name: i for i, name in enumerate(re.findall(
        r"^\s*const (\w+)", read("constants/tileset_constants.asm"), re.M))}
    dimensions = {n: (int(w), int(h)) for n, w, h in re.findall(
        r"map_const (\w+),\s*(\d+),\s*(\d+)", read("constants/map_constants.asm"))}
    map_blocks = aliases(read("maps.asm"), r"(\w+)_Blocks:", r'INCBIN "([^\"]+\.blk)"')
    world = {}
    object_ids = {}
    for header in sorted((src / "data/maps/headers").glob("*.asm")):
        match = re.search(r"map_header (\w+), (\w+), (\w+)", header.read_text(encoding="utf-8"))
        if not match:
            continue
        name, symbol, tile_symbol = match.groups()
        obj = read(f"data/maps/objects/{name}.asm")
        object_map = re.search(r"def_warps_to (\w+)", obj)
        if object_map and object_map[1] in maps:
            symbol = object_map[1]
        if name not in map_blocks:
            continue
        ts = tilesets[tileset_names[tile_symbol]]
        width, height = dimensions[symbol]
        raw = (src / map_blocks[name]).read_bytes()
        bst = (src / blocks[ts]).read_bytes()
        if len(raw) < width * height:
            # The original north/south underground map omits its last block row.
            raw += raw[-width:] * ((width * height - len(raw) + width - 1) // width)
        allowed = [int(v, 16) for v in re.findall(r"\$([\da-fA-F]+)", collisions[ts])]
        tiles = [[bst[raw[(y // 2) * width + x // 2] * 16 + (y % 2) * 8 + (x % 2) * 2 + 4]
                  for x in range(width * 2)] for y in range(height * 2)]
        obj = read(f"data/maps/objects/{name}.asm")
        object_ids.update({symbol: i for i, symbol in enumerate(re.findall(r"const_export (\w+)", obj))})
        warps = [[int(x), int(y), maps.get(dest, -1), int(warp) - 1] for x, y, dest, warp in re.findall(
            r"warp_event\s+(\d+),\s*(\d+),\s*(\w+),\s*(\d+)", obj)]
        inactive_warps = [[int(x), int(y)] for x, y in re.findall(
            r"warp_event\s+(\d+),\s*(\d+),[^\n]*inaccessible", obj)]
        backgrounds = [[int(x), int(y), text] for x, y, text in re.findall(
            r"bg_event\s+(\d+),\s*(\d+),\s*(\w+)", obj)]
        connections = [[dr, maps[dest], int(offset)] for dr, dest, offset in re.findall(
            r"connection (\w+), \w+, (\w+), (-?\d+)", header.read_text(encoding="utf-8"))]
        objects = [[int(x), int(y), sprite, movement, text] for x, y, sprite, movement, text in re.findall(
            r"object_event\s+(\d+),\s*(\d+),\s*(\w+),\s*(\w+),\s*\w+,\s*(\w+)", obj)]
        opened_blocks = {
            "LoreleisRoom": [(2, 0, 0x05, "EVENT_BEAT_LORELEIS_ROOM_TRAINER_0")],
            "BrunosRoom": [(2, 0, 0x05, "EVENT_BEAT_BRUNOS_ROOM_TRAINER_0")],
            "AgathasRoom": [(2, 0, 0x0E, "EVENT_BEAT_AGATHAS_ROOM_TRAINER_0")],
            "VictoryRoad1F": [(4, 6, 0x1D, "EVENT_VICTORY_ROAD_1_BOULDER_ON_SWITCH")],
            "VictoryRoad2F": [(3, 4, 0x15, "EVENT_VICTORY_ROAD_2_BOULDER_ON_SWITCH1"), (11, 7, 0x1D, "EVENT_VICTORY_ROAD_2_BOULDER_ON_SWITCH2")],
            "VictoryRoad3F": [(3, 5, 0x1D, "EVENT_VICTORY_ROAD_3_BOULDER_ON_SWITCH1")],
        }.get(name, [])
        opened_tiles = [[flag, bx * 2 + dx, by * 2 + dy, bst[block * 16 + dy * 8 + dx * 2 + 4]]
                        for bx, by, block, flag in opened_blocks for dx in range(2) for dy in range(2)]
        switch_blocks = {
            "PokemonMansion1F": [(12, 6, 0x0E, 0x2D), (8, 3, 0x2D, 0x0E), (10, 8, 0x2D, 0x0E), (13, 13, 0x2D, 0x0E)],
            "PokemonMansion2F": [(4, 2, 0x0E, 0x5F), (9, 4, 0x54, 0x0E), (3, 11, 0x5F, 0x0E)],
            "PokemonMansion3F": [(7, 2, 0x0E, 0x5F), (7, 5, 0x5F, 0x0E)],
            "PokemonMansionB1F": [(13, 8, 0x0E, 0x2D), (6, 11, 0x0E, 0x5F), (4, 3, 0x5F, 0x0E), (8, 8, 0x54, 0x0E)],
        }.get(name, [])
        switch_tiles = [[[bx * 2 + dx, by * 2 + dy, bst[block[mode] * 16 + dy * 8 + dx * 2 + 4]]
                         for bx, by, *block in switch_blocks for dx in range(2) for dy in range(2)] for mode in range(2)]
        doors = []
        floor_match = re.fullmatch(r"SilphCo(\d+)F", name)
        if floor_match and floor_match[1] != "1":
            script = read(f"scripts/{name}.asm")
            coords = re.search(r"\.GateCoordinates:\n(.*?)db -1", script, re.S)
            door_flags = [e for e in events if e.startswith(f"EVENT_SILPH_CO_{floor_match[1]}_UNLOCKED_DOOR")]
            if coords:
                points = re.findall(r"dbmapcoord\s+(\d+),\s*(\d+)", coords[1])
                if len(points) != len(door_flags):
                    raise ValueError(f"Door count mismatch in {name}")
                doors = [[int(x) * 2, int(y) * 2, flag] for (x, y), flag in zip(points, door_flags)]
        forced = []
        if name in ("RocketHideoutB2F", "RocketHideoutB3F", "ViridianGym"):
            script = read(f"scripts/{name}.asm")
            directions = {"LEFT": (-1, 0), "RIGHT": (1, 0), "UP": (0, -1), "DOWN": (0, 1)}
            for x, y, label in re.findall(r"map_coord_movement\s+(\d+),\s*(\d+),\s*(\w+)", script):
                sequence = script.split(label + ":", 1)[1].split("db -1", 1)[0]
                tx, ty = int(x), int(y)
                for direction, count in re.findall(r"db PAD_(\w+),\s*(\d+)", sequence):
                    dx, dy = directions[direction]
                    tx += dx * int(count)
                    ty += dy * int(count)
                forced.append([int(x), int(y), tx, ty])
        world[maps[symbol]] = dict(name=name, symbol=symbol, tileset=tile_symbol, width=width * 2,
                                  height=height * 2, tiles=tiles, passable=allowed,
                                  warps=warps, inactive_warps=inactive_warps, connections=connections, objects=objects, backgrounds=backgrounds, forced_moves=forced, locked_doors=doors, switch_tiles=switch_tiles, opened_tiles=opened_tiles)
    toggles = []
    for w in world.values():
        path = src / 'data/wild/maps' / (w['name'] + '.asm')
        encounters = []
        active = False
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if 'def_grass_wildmons' in line:
                    active = True
                if 'end_grass_wildmons' in line:
                    active = False
                match = re.match(r'\s*db\s+(\d+),\s*(\w+)', line)
                if active and match and match[2] in species:
                    encounters.append([species[match[2]], int(match[1])])
        # Both Red and Blue land encounters are included for compatible partner searches.
        w['encounters'] = sorted(set(tuple(p) for p in encounters))
    for line in read("data/maps/toggleable_objects.asm").splitlines():
        match = re.match(r"\s*toggleable_objects_for (\w+)", line)
        if match:
            toggle_map = maps[match[1]]
        # Lines that name the object by number are skipped. The source has one, marked unused,
        # and the generator that built the leaderboard data skipped it. PokeSim now keeps it.
        match = re.match(r"\s*toggle_object_state (\w+),", line)
        if match:
            toggles.append([toggle_map, object_ids[match[1]]])
    pairs = [[ts, int(a, 16), int(b, 16)] for ts, a, b in re.findall(
        r"db (\w+), \$([\da-fA-F]+), \$([\da-fA-F]+)",
        read("data/tilesets/pair_collision_tile_ids.asm"))]
    ledges = [[dr.lower(), int(a, 16), int(b, 16)] for dr, a, b in re.findall(
        r"db SPRITE_FACING_(\w+),\s*\$([\da-fA-F]+),\s*\$([\da-fA-F]+)",
        read("data/tilesets/ledge_tiles.asm"))]
    return dict(source="https://github.com/pret/pokered", revision=revision, moves=moves, matchups=matchups,
        species=mons, events=events, items=items, prices={i + 1: p for i, p in enumerate(prices)},
        marts=marts, maps=maps, world=world, toggle_objects=toggles, collision_pairs=pairs, ledges=ledges)
