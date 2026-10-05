"""Player-facing structured information, isolated from the visual benchmark.

The catalog is private. Only fields selected below can reach an agent.
"""
from copy import deepcopy
import json
import re
from pathlib import Path

from pokesim_core.menus import menu_options as core_menu_options
from pokesim_core.gen1 import read_party, W_IS_IN_BATTLE, W_X, W_Y, W_CUR_MAP
from pokesim_core.gen1_ui import read_battler, read_screen, read_sprites, read_storage

from .core import digest, encoded
from .game import structured

POLICY = "player-information-v036"
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
    return {"revision": manifest["source_revision"],
            "labels": {key: tables[key] for key in ("maps", "species", "moves", "items")},
            "moves": {key: {field: value[field] for field in ("name", "type", "power", "accuracy", "pp", "effect")}
                      for key, value in strategy["moves"].items()},
            "world": {key: {field: value[field] for field in ("passable", "warps", "objects", "backgrounds")}
                      for key, value in strategy["world"].items()}}


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
    grid = [["." if tiles[(2 * row + 1) * 20 + 2 * col] in world["passable"] else "#"
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
        appearance = {"SPRITE_POKE_BALL": "ball-shaped object", "SPRITE_POKEDEX": "book-shaped object",
                      "SPRITE_BOULDER": "boulder", "SPRITE_FOSSIL": "fossil-shaped object"}.get(raw, "person or object")
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
    return {"available": True, "origin": {"x": left, "y": top}, "rows": ["".join(row) for row in grid],
            "legend": {".": "walkable terrain", "#": "blocked terrain", "@": "you", "O": "visible object",
                       "S": "fixed interactable", "E": "exit or stairs, destination unknown"},
            "objects": objects, "exits": exits,
            "caveat": "Terrain is local. Objects can block movement. Special directional collisions may apply."}


def known_map(history, map_id, x, y):
    """Compact recall of observed terrain only. Question marks remain unknown."""
    cells = history.get("tiles", {}).get(str(map_id), {})
    points = {(int(key.split(",")[0]), int(key.split(",")[1])): value for key, value in cells.items()}
    points[(x, y)] = "@"
    left, right = max(x - 16, min(px for px, py in points)), min(x + 16, max(px for px, py in points))
    top, bottom = max(y - 16, min(py for px, py in points)), min(y + 16, max(py for px, py in points))
    return {"map_id": int(map_id), "origin": {"x": left, "y": top},
            "rows": ["".join(points.get((px, py), "?") for px in range(left, right + 1)) for py in range(top, bottom + 1)],
            "legend": "? unseen, # blocked terrain, . walkable terrain, E observed exit, S fixed interactable, @ current position. Historical terrain may change."}


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
