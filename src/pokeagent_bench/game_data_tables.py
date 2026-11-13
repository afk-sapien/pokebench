"""Generate tables.json from pret/pokered constants files.

Copied from PokeSim so that setup needs no PokeSim checkout. Keep the output byte identical.
"""
import re


def pretty(name: str) -> str:
    name = name.replace("_", " ").title()
    fixes = {"Sf ": "S.S. ", "Pokemon": "Pokémon", "Mt ": "Mt. ", "Pokecenter": "Pokémon Center",
             "Mart": "Mart", "Hm": "HM", "Tm": "TM", "1F": "1F", "2F": "2F", "3F": "3F", "4F": "4F",
             "5F": "5F", "6F": "6F", "7F": "7F", "8F": "8F", "9F": "9F", "10F": "10F", "11F": "11F",
             "B1F": "B1F", "B2F": "B2F", "B3F": "B3F", "B4F": "B4F", "Ss ": "S.S. ", "Nidoran M": "Nidoran♂",
             "Nidoran F": "Nidoran♀", "Farfetchd": "Farfetch'd", "Mr Mime": "Mr. Mime"}
    for a, b in fixes.items():
        name = name.replace(a, b)
    return name


def parse(src, path, macro):
    out = {}
    for line in (src / path).read_text(encoding="utf-8").splitlines():
        m = re.match(rf"\s*{macro}\s+([A-Z0-9_]+)\b.*\x3b\s*\$([0-9A-Fa-f]{{2}})", line)
        if m:
            out[int(m.group(2), 16)] = m.group(1)
    return out


def generate(src):
    maps = parse(src / "constants", "map_constants.asm", "map_const")
    trainers = parse(src / "constants", "trainer_constants.asm", "trainer_const")
    moves = {}
    for line in (src / "data/moves/moves.asm").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*move\s+([A-Z0-9_]+),\s*([A-Z0-9_]+),\s*(\d+),\s*([A-Z0-9_]+),\s*(\d+),\s*(\d+)", line)
        if m:
            moves[len(moves) + 1] = {"name": pretty(m.group(1)), "power": int(m.group(3)), "type": pretty(m.group(4)),
                                     "effect": m.group(2)}
    dex = {}
    for line in (src / "constants/pokedex_constants.asm").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*const\s+DEX_([A-Z0-9_]+)\s*\x3b\s*(\d+)", line)
        if m:
            dex[int(m.group(2))] = m.group(1)
    species = parse(src / "constants", "pokemon_constants.asm", "const")
    items = parse(src / "constants", "item_constants.asm", "const")
    for i in range(5):
        items[0xC4 + i] = f"HM{i+1:02d}"
    for i in range(50):
        items[0xC9 + i] = f"TM{i+1:02d}"

    badges = ["Boulder", "Cascade", "Thunder", "Rainbow", "Soul", "Marsh", "Volcano", "Earth"]
    leaders = ["Brock", "Misty", "Lt. Surge", "Erika", "Koga", "Sabrina", "Blaine", "Giovanni"]
    key_items = ["BICYCLE", "TOWN_MAP", "OAKS_PARCEL", "POKEDEX", "SS_TICKET", "GOLD_TEETH", "SECRET_KEY",
                 "CARD_KEY", "LIFT_KEY", "BIKE_VOUCHER", "OLD_ROD", "GOOD_ROD", "SUPER_ROD", "POKE_FLUTE",
                 "SILPH_SCOPE", "ITEMFINDER", "EXP_ALL", "DOME_FOSSIL", "HELIX_FOSSIL", "OLD_AMBER",
                 "HM01", "HM02", "HM03", "HM04", "HM05", "MASTER_BALL", "COIN_CASE"]
    name_to_item = {v: k for k, v in items.items()}

    return {
        "maps": {str(k): pretty(v) for k, v in sorted(maps.items())},
        "species": {str(k): pretty(v) for k, v in sorted(species.items())},
        "items": {str(k): pretty(v) for k, v in sorted(items.items())},
        "trainers": {str(k): pretty(v) for k, v in sorted(trainers.items())},
        "dex": {str(k): pretty(v) for k, v in sorted(dex.items())},
        "notable_trainers": sorted(k for k, v in trainers.items() if v in (
            "RIVAL1", "RIVAL2", "RIVAL3", "BROCK", "MISTY", "LT_SURGE", "ERIKA", "KOGA", "SABRINA", "BLAINE",
            "GIOVANNI", "LORELEI", "BRUNO", "AGATHA", "LANCE")),
        "moves": {str(k): v for k, v in moves.items()},
        "badges": badges,
        "leaders": leaders,
        "key_item_ids": sorted(name_to_item[n] for n in key_items if n in name_to_item),
        "hall_of_fame_map": next(k for k, v in maps.items() if v == "HALL_OF_FAME"),
    }
