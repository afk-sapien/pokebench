"""Player-facing structured information, isolated from the visual benchmark.

The catalog is private. Only fields selected below can reach an agent.
"""
from copy import deepcopy
import json
import re
from pathlib import Path

from pokecore.menus import menu_options as core_menu_options
from pokecore.gen1 import read_party, W_IS_IN_BATTLE, W_X, W_Y, W_CUR_MAP
from pokecore.gen1_ui import read_battler, read_screen, read_sprites, read_storage

from .core import digest, encoded
from .game import structured

POLICY = "player-information-v064"
# What a player sees for each map sprite. A sprite kind that names a look or an outfit keeps
# its name. A sprite named after a person, a group or a job that only the place or the
# dialogue reveals is shown as a plain look, so no name or role reaches the model.
SPRITE_LOOKS = {
    "SPRITE_YOUNGSTER": "youngster", "SPRITE_GIRL": "girl", "SPRITE_LITTLE_GIRL": "little girl",
    "SPRITE_LITTLE_BOY": "little boy", "SPRITE_BRUNETTE_GIRL": "brunette girl",
    "SPRITE_BALDING_GUY": "balding man", "SPRITE_MIDDLE_AGED_MAN": "middle-aged man",
    "SPRITE_MIDDLE_AGED_WOMAN": "middle-aged woman", "SPRITE_GRAMPS": "old man",
    "SPRITE_GRANNY": "old woman", "SPRITE_COOLTRAINER_M": "young man",
    "SPRITE_COOLTRAINER_F": "young woman", "SPRITE_BEAUTY": "beauty", "SPRITE_GENTLEMAN": "gentleman",
    "SPRITE_SUPER_NERD": "super nerd", "SPRITE_HIKER": "hiker", "SPRITE_BIKER": "biker",
    "SPRITE_SWIMMER": "swimmer", "SPRITE_SAILOR": "sailor", "SPRITE_FISHER": "fisher",
    "SPRITE_GAMBLER": "gambler", "SPRITE_GAMBLER_ASLEEP": "sleeping man", "SPRITE_CHANNELER": "channeler",
    "SPRITE_ROCKER": "rocker", "SPRITE_SCIENTIST": "scientist", "SPRITE_COOK": "cook",
    "SPRITE_WAITER": "waiter", "SPRITE_NURSE": "nurse", "SPRITE_GUARD": "guard",
    "SPRITE_GAMEBOY_KID": "boy", "SPRITE_FISHING_GURU": "old man",
    "SPRITE_RED": "boy", "SPRITE_BLUE": "boy", "SPRITE_OAK": "old man", "SPRITE_DAISY": "girl",
    "SPRITE_MOM": "woman", "SPRITE_MR_FUJI": "old man", "SPRITE_GIOVANNI": "man", "SPRITE_KOGA": "man",
    "SPRITE_LANCE": "man", "SPRITE_BRUNO": "man", "SPRITE_LORELEI": "woman", "SPRITE_AGATHA": "old woman",
    "SPRITE_ROCKET": "man in black", "SPRITE_GYM_GUIDE": "man", "SPRITE_CLERK": "man",
    "SPRITE_BIKE_SHOP_CLERK": "man", "SPRITE_LINK_RECEPTIONIST": "woman",
    "SPRITE_SAFARI_ZONE_WORKER": "man", "SPRITE_SILPH_WORKER_M": "man", "SPRITE_SILPH_WORKER_F": "woman",
    "SPRITE_SILPH_PRESIDENT": "man", "SPRITE_WARDEN": "old man", "SPRITE_CAPTAIN": "man",
    "SPRITE_BIRD": "bird", "SPRITE_MONSTER": "Pokemon", "SPRITE_FAIRY": "Pokemon", "SPRITE_SEEL": "Pokemon",
    "SPRITE_SNORLAX": "large Pokemon",
    "SPRITE_POKE_BALL": "ball-shaped object", "SPRITE_POKEDEX": "book-shaped object",
    "SPRITE_BOULDER": "boulder", "SPRITE_FOSSIL": "fossil-shaped object", "SPRITE_OLD_AMBER": "small object",
    "SPRITE_PAPER": "paper", "SPRITE_CLIPBOARD": "clipboard",
}
PAIR_LEGEND ="walkable floor. A step directly between a : cell and a , cell is refused, in both directions"
TYPES = {0: "Normal", 1: "Fighting", 2: "Flying", 3: "Poison", 4: "Ground", 5: "Rock",
         7: "Bug", 8: "Ghost", 20: "Fire", 21: "Water", 22: "Grass", 23: "Electric",
         24: "Psychic", 25: "Ice", 26: "Dragon"}
ITEM_HELP = {"POTION": "Restores 20 HP to a conscious Pokemon.", "SUPER_POTION": "Restores 50 HP.",
             "HYPER_POTION": "Restores 200 HP.", "MAX_POTION": "Fully restores HP.",
             "MAX_REVIVE": "Revives with full HP.",
             "ELIXER": "Restores up to 10 PP to each move of one Pokemon.",
             "MAX_ELIXER": "Fully restores PP to each move of one Pokemon.",
             "FULL_RESTORE": "Fully restores HP and cures status.", "REVIVE": "Revives with half maximum HP.",
             "ANTIDOTE": "Cures poison.", "BURN_HEAL": "Cures burn.", "ICE_HEAL": "Cures freeze.",
             "AWAKENING": "Wakes a sleeping Pokemon.", "PARLYZ_HEAL": "Cures paralysis.",
             "FULL_HEAL": "Cures status.", "POKE_BALL": "Attempts to catch a wild Pokemon.",
             "GREAT_BALL": "Attempts to catch a wild Pokemon with improved odds.",
             "ULTRA_BALL": "Attempts to catch a wild Pokemon with improved odds.",
             "ESCAPE_ROPE": "Leaves a compatible cave or dungeon.", "REPEL": "Temporarily reduces wild encounters."}


def load_catalog(path):
    root = Path(path)
    bundle = json.loads((root / "current.json").read_text())["bundle"]
    if not re.fullmatch(r"[0-9a-f]{64}", bundle):
        raise ValueError("Invalid game data bundle")
    root = root / "bundles" / bundle
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema") != 1 or manifest.get("source_revision") != "a1a22aaf84d1675bcdbaeb194592379d586d838e":
        raise ValueError("Unsupported game data revision")
    data = {}
    for name in ("tables", "strategy"):
        raw = (root / (name + ".json")).read_bytes()
        if digest(raw) != manifest["files"][name + ".json"]:
            raise ValueError("Game data checksum mismatch")
        data[name] = json.loads(raw)
    strategy, tables = data["strategy"], data["tables"]
    world = {key: {field: value[field] for field in ("passable", "warps", "objects", "backgrounds", "tileset")}
             for key, value in strategy["world"].items()}
    for value in world.values():
        rows = [(a, b) for tileset, a, b in strategy["collision_pairs"] if tileset == value["tileset"]]
        value["pair_floors"] = pair_floors(rows, value["passable"])
    return {"revision": manifest["source_revision"],
            "labels": {key: tables[key] for key in ("maps", "species", "moves", "items")},
            "moves": {key: {field: value[field] for field in ("name", "type", "power", "accuracy", "pp", "effect")}
                      for key, value in strategy["moves"].items()},
            "world": world}


def pair_floors(rows, passable):
    """Floor glyphs that show the Gen 1 tile pair collisions of one map exactly.

    The game refuses a step between the two tiles of a pair, in either direction.
    Pairs whose tiles are not both walkable only matter while surfing, so they are left out.
    Every tileset's pairs form one complete bipartite group, so one glyph per side is exact:
    a step is blocked exactly when one cell shows ':' and the other ','. The glyph depends
    only on the tile, never on where the player stands.
    """
    neighbours = {}
    for a, b in rows:
        if a in passable and b in passable and a != b:
            neighbours.setdefault(a, set()).add(b)
            neighbours.setdefault(b, set()).add(a)
    if not neighbours:
        return {}
    side = {min(neighbours): 0}
    queue = [min(neighbours)]
    while queue:
        tile = queue.pop()
        for other in neighbours[tile]:
            if other not in side:
                side[other] = 1 - side[tile]
                queue.append(other)
    groups = [{tile for tile, value in side.items() if value == index} for index in (0, 1)]
    if len(side) != len(neighbours) or any(neighbours[tile] != groups[1 - side[tile]] for tile in side):
        raise ValueError("Tile pair collisions cannot be shown with two floor glyphs")
    first = min(groups, key=lambda group: (len(group), min(group)))
    return {tile: ":" if tile in first else "," for tile in sorted(side)}


def status_name(value):
    names = [name for bit, name in ((8, "poisoned"), (16, "burned"), (32, "frozen"), (64, "paralyzed")) if value & bit]
    if value & 7:
        names.insert(0, "asleep")
    return names or ["healthy"]


def menu_options(memory, screen, kind=None):
    return core_menu_options(memory, screen, kind, party_reader=read_party)


def ui_state(memory):
    if not memory[0xFF40] & 128 or memory[0xFF47] in (0, 85, 170, 255):
        return {"kind": "transition", "text": [], "cursor_tile": None,
                "selected_text": None, "visible_choices": []}
    screen = read_screen(memory)
    rows, cursor = screen["rows"], screen["cursor"]
    battle = memory[W_IS_IN_BATTLE] in (1, 2)
    kind = "overworld"
    pokedex = "HT" in rows[6] and "WT" in rows[8] and bool(rows[2].strip())
    if pokedex:
        kind = "dialogue"
    elif any(row[2:19:2] in ("ABCDEFGHI", "abcdefghi") for row in rows):
        kind = "naming"
    elif cursor:
        if "FIGHT" in rows[14] and "RUN" in rows[16]:
            kind = "battle_menu"
        elif battle and cursor[0] == 5 and 13 <= cursor[1] <= 16:
            kind = "move_menu"
        else:
            kind = "menu"
    elif screen["textbox"] or battle:
        kind = "dialogue"
    elif screen["pause"]:
        kind = "menu"
    elif memory[0xC102] == 255:
        kind = "modal"
    visible_rows = rows[13:] if kind == "dialogue" and not battle and not pokedex else rows
    text = [row.rstrip() for row in visible_rows if row.strip()] if kind != "overworld" else []
    choices = []
    if kind == "battle_menu":
        choices = ["FIGHT", "PKMN", "ITEM", "RUN"]
    elif cursor:
        choices = [option["text"] for option in menu_options(memory, screen, kind)]
    selected = rows[cursor[1]][cursor[0]:].replace(">", " ").strip() if cursor else None
    if kind == "menu":
        selected = next((option["text"] for option in menu_options(memory, screen, kind)
                         if option["cursor"] == list(cursor)), selected)
    if kind == "battle_menu":
        selected = {(9, 14): "FIGHT", (15, 14): "PKMN", (9, 16): "ITEM", (15, 16): "RUN"}.get(tuple(cursor))
    return {"kind": kind, "panel": "pokedex" if pokedex else None, "text": text, "cursor_tile": list(cursor) if cursor else None,
            "selected_text": selected,
            "visible_choices": choices}


def move_details(move, pp, slot, catalog):
    entry = catalog["moves"].get(str(move), {})
    return {"slot": slot, "id": move, "name": entry.get("name", f"#{move}"), "pp": pp,
            "base_pp": entry.get("pp"), "type": TYPES.get(entry.get("type"), "unknown"),
            "power": entry.get("power"), "accuracy_percent": entry.get("accuracy"),
            "effect": entry.get("effect", "unknown").removesuffix("_EFFECT").replace("_", " ").lower()}


def owned_mon(mon, catalog, slot):
    name = catalog["labels"]["species"].get(str(mon["species"]), f"#{mon['species']}")
    if isinstance(name, dict):
        name = name.get("name", "unknown")
    result = {"slot": slot, "species": name, "nickname": mon.get("nick", ""), "level": mon["level"],
              "hp": mon["hp"], "status": status_name(mon["status"]),
              "types": list(dict.fromkeys(TYPES.get(t, "unknown") for t in mon["types"])),
              "moves": [move_details(move, mon["pp"][i], i + 1, catalog) for i, move in enumerate(mon["moves"]) if move]}
    if "max_hp" in mon:
        result["max_hp"] = mon["max_hp"]
    return result


def local_map(memory, catalog, ui):
    if ui["kind"] != "overworld" or memory[W_IS_IN_BATTLE]:
        return {"available": False, "reason": "Map is covered by the current interface."}
    sprites = read_sprites(memory)
    if sprites[0]["walk_counter"]:
        return {"available": False, "reason": "Player is between tiles. Wait for the step to finish."}
    world = catalog["world"].get(str(memory[W_CUR_MAP]))
    if world is None:
        return {"available": False, "reason": "Unsupported map."}
    x, y = memory[W_X], memory[W_Y]
    left, top = x - 4, y - 4
    tiles = read_screen(memory)["tiles"]
    # Live bottom-left subtiles include changes such as cut trees and opened doors.
    arrows = {"FACILITY": {0x20: "v", 0x21: "^", 0x30: ">", 0x31: "<"},
              "GYM": {0x3C: "^", 0x3D: "<", 0x4C: "v", 0x4D: ">"}}.get(world.get("tileset"), {})
    floors = world.get("pair_floors", {})
    # Read only on-screen graphics. Never include scripted paths or destinations.
    grid = [[arrows.get(tiles[(2 * row + 1) * 20 + 2 * col],
                        floors.get(tiles[(2 * row + 1) * 20 + 2 * col], ".")
                        if tiles[(2 * row + 1) * 20 + 2 * col] in world["passable"] else "#")
             for col in range(10)] for row in range(9)]
    objects = []
    def inside(px, py):
        return left <= px < left + 10 and top <= py < top + 9
    for sprite in sprites[1:]:
        if (not sprite["picture"] or sprite["image"] == 255 or
                not 0 <= sprite["screen_x"] < 160 or not 0 <= sprite["screen_y"] < 140):
            continue
        px, py = sprite["x"], sprite["y"]
        if not inside(px, py):
            continue
        index = sprite["slot"] - 1
        raw = world["objects"][index][2] if index < len(world["objects"]) else ""
        appearance = SPRITE_LOOKS.get(raw, "person or object")
        objects.append({"id": f"object-{sprite['slot']}", "x": px, "y": py, "appearance": appearance})
        grid[py - top][px - left] = "O"
    for px, py, *_ in world["backgrounds"]:
        if inside(px, py):
            objects.append({"id": f"background-{px}-{py}", "x": px, "y": py, "appearance": "sign or fixed interactable"})
            grid[py - top][px - left] = "S"
    exits = []
    for px, py, *_ in world["warps"]:
        if inside(px, py):
            exits.append({"x": px, "y": py})
            grid[py - top][px - left] = "E"
    grid[4][4] = "@"
    legend = {".": "walkable terrain", "#": "blocked terrain", "@": "you", "O": "visible object",
              "S": "fixed interactable", "E": "exit or stairs, destination unknown",
              "^ v < >": "visible floor arrows pointing up, down, left, right"}
    if floors:
        legend[": ,"] = PAIR_LEGEND
        # "@" hides the floor under the player, and that floor decides which steps are refused.
        under = floors.get(tiles[9 * 20 + 8])
        if under:
            legend["@"] = f"you, standing on {under} floor"
    return {"available": True, "origin": {"x": left, "y": top}, "rows": ["".join(row) for row in grid],
            "legend": legend, "objects": objects, "exits": exits,
            "caveat": "Terrain is local. Objects can block movement. Special directional collisions may apply."}


def known_map(history, map_id, x, y):
    """Compact recall of observed terrain only. Question marks remain unknown."""
    cells = history.get("tiles", {}).get(str(map_id), {})
    points = {(int(key.split(",")[0]), int(key.split(",")[1])): value for key, value in cells.items()}
    points[(x, y)] = "@"
    left, right = max(x - 16, min(px for px, py in points)), min(x + 16, max(px for px, py in points))
    top, bottom = max(y - 16, min(py for px, py in points)), min(y + 16, max(py for px, py in points))
    rows = ["".join(points.get((px, py), "?") for px in range(left, right + 1)) for py in range(top, bottom + 1)]
    legend = "? unseen, # blocked terrain, . walkable terrain, E observed exit, S fixed interactable, ^ v < > observed floor arrows, @ current position. Historical terrain may change."
    if any(":" in row or "," in row for row in rows):
        legend += " : and , walkable floor, no direct step between them."
    return {"map_id": int(map_id), "origin": {"x": left, "y": top}, "rows": rows, "legend": legend}


def observe_gameplay(session):
    from .working_memory import recall
    memory, catalog = session.engine.memory, session.gameplay_catalog
    base = structured(memory, catalog["labels"])
    ui = ui_state(memory)
    party = [owned_mon(mon, catalog, i + 1) for i, mon in enumerate(read_party(memory))
             if mon["species"] and 1 <= mon["level"] <= 100]
    battle = base["battle"]
    if memory[W_IS_IN_BATTLE] in (1, 2):
        active = read_battler(memory)
        index = memory[0xCC2F]
        if active["species"] and 1 <= active["level"] <= 100 and 0 <= index < len(party):
            current = owned_mon(active, catalog, index + 1)
            current["nickname"] = party[index]["nickname"]
            party[index] = current
            battle["active_party_slot"] = index + 1
        # Enemy information is the visible HUD text, never the hidden enemy struct.
        battle["visible_hud"] = [row.strip() for row in read_screen(memory)["rows"][:4] if row.strip()]
        hp_tiles = read_screen(memory)["tiles"][40:52]
        start = hp_tiles.index(98) + 1 if 98 in hp_tiles else -1
        bar = hp_tiles[start:start + 6] if start >= 0 else []
        battle["opponent_hp_bar"] = ({"filled_pixels": sum(tile - 99 for tile in bar), "total_pixels": 48}
            if len(bar) == 6 and all(99 <= tile <= 107 for tile in bar) else None)
    for item in base["inventory"]:
        key = item["name"].upper().replace(" ", "_").replace("é", "E")
        item["description"] = ITEM_HELP.get(key, "No built-in description. Inspect the game's item interface.")
    view = local_map(memory, catalog, ui)
    history = session.gameplay_memory
    map_id = str(base["location"]["map_id"])
    if history.get("last_map", map_id) != map_id:
        history["map_ready_after"] = session.frame + 120
    history["last_map"] = map_id
    if session.frame < history.get("map_ready_after", 0):
        view = {"available": False, "reason": "Map transition is settling. Request wait before using the map."}
    history.setdefault("visited", {})[map_id] = base["location"]["map_name"]
    if view["available"]:
        known = history.setdefault("tiles", {}).setdefault(map_id, {})
        for dy, row in enumerate(view["rows"]):
            for dx, cell in enumerate(row):
                if cell in ("@", "O"):
                    continue
                known[f"{view['origin']['x'] + dx},{view['origin']['y'] + dy}"] = cell
        while len(known) > 4096:
            del known[next(iter(known))]
        while len(history["tiles"]) > 64:
            del history["tiles"][next(iter(history["tiles"]))]
    dialogue = history.setdefault("dialogue", [])
    if ui["kind"] == "dialogue" and ui["text"]:
        entry = {"map_id": int(map_id), "text": ui["text"]}
        if not dialogue or entry != {k: v for k, v in dialogue[-1].items() if k != "frame"}:
            dialogue.append({"frame": session.frame, **entry})
            del dialogue[:-64]
    result = {"policy": POLICY, "location": {**base["location"],
              "facing": {0: "down", 4: "up", 8: "left", 12: "right"}.get(memory[0xC109], "unknown")},
              "screen": ui, "local_map": view, "party": party, "bag": base["inventory"],
              "money": base["money"], "badges": base["badges"], "battle": battle,
              "memory": {"visited_maps": history["visited"], "recent_dialogue": dialogue[-2:],
                         "known_map": known_map(history, map_id, base["location"]["x"], base["location"]["y"]) if view["available"] else None,
                         "recent_movements": history.get("movements", []),
                         "working_memory": recall(history, int(map_id)),
                         "agent_plan": deepcopy(history.get("agent_plan")),
                         "plan_revisions": deepcopy(history.get("plan_revisions", []))},
              "inspect_topics": ["party", "bag", "storage", "map", "memory"]}
    topic = session.gameplay_inspection
    if topic == "storage":
        storage = read_storage(memory)
        result["inspection"] = {"topic": topic, "active_box": storage["active_box"],
            "boxes": [{"box": box["box"], "available": box["available"],
                       "pokemon": [owned_mon(mon, catalog, mon["slot"]) for mon in box["pokemon"]
                                   if mon["species"] and 1 <= mon["level"] <= 100]} for box in storage["boxes"]]}
    elif topic in ("party", "bag"):
        result["inspection"] = {"topic": topic, "data": result[topic]}
    elif topic == "map":
        result["inspection"] = {"topic": topic, "map_id": int(map_id), "previously_seen_tiles": history.get("tiles", {}).get(map_id, {})}
    elif topic == "memory":
        result["inspection"] = {"topic": topic, "visited_maps": history["visited"], "dialogue": dialogue,
                                "working_memory": recall(history, int(map_id), inspect=True)}
    if session.gameplay_result:
        result["last_command"] = session.gameplay_result
    return result


def catalog_hash(catalog):
    return digest(encoded(catalog))
