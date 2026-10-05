"""Benchmark observation allowlist over PokeSim Core's game facts and emulator."""
from __future__ import annotations

from pathlib import Path

from pokesim_core.emulator import GameBoy
from pokesim_core.gen1 import (
    BADGES,
    W_BADGES,
    W_EVENT_FLAGS,
    event_set,
    W_CUR_MAP,
    W_IS_IN_BATTLE,
    W_MONEY,
    W_PLAYER_NAME,
    W_PARTY_COUNT,
    W_DEX_OWNED,
    W_ENEMY_MON,
    W_BATTLE_TYPE,
    decode_text,
    flag_bits,
    W_X,
    W_Y,
    bcd,
    read_bag,
    read_party,
    read_progress,
)


def structured(memory, labels=None):
    """Select agent-visible fields explicitly, even when the core adds more facts."""
    labels = labels or {}

    def name(kind, number):
        entry = labels.get(kind, {}).get(str(number), f"#{number}")
        return entry.get("name", f"#{number}") if isinstance(entry, dict) else entry

    party = []
    for mon in read_party(memory):
        if mon["species"] == 0 or not 1 <= mon["level"] <= 100:
            continue
        party.append({
            "species_id": mon["species"], "species": name("species", mon["species"]),
            "nickname": mon["nick"], "hp": mon["hp"], "max_hp": mon["max_hp"],
            "level": mon["level"], "status": mon["status"],
            "moves": [{"id": move, "name": name("moves", move), "pp": mon["pp"][index]}
                      for index, move in enumerate(mon["moves"]) if move],
        })
    bag = [{"id": item, "name": name("items", item), "quantity": quantity}
           for item, quantity in read_bag(memory)]
    battle = memory[W_IS_IN_BATTLE]
    return {
        "location": {"map_id": memory[W_CUR_MAP], "map_name": name("maps", memory[W_CUR_MAP]),
                     "x": memory[W_X], "y": memory[W_Y]},
        "party": party, "inventory": bag, "money": bcd(memory[W_MONEY:W_MONEY + 3]),
        "badges": [badge for i, badge in enumerate(BADGES) if memory[W_BADGES] & (1 << i)],
        "battle": {"kind": {0: "none", 1: "wild", 2: "trainer", 255: "lost"}.get(battle, "transition")},
    }


class RedEngine(GameBoy):
    """Keep benchmark policy outside the reusable emulator implementation."""

    def __init__(self, rom: Path, state: bytes | None = None):
        self.initial_screen = None
        super().__init__(rom, state, allowed_games=("red",))

    def screenshot(self):
        return self.initial_screen if self.initial_screen is not None else super().screenshot()

    def tick(self, frames=1, *, render=True):
        result = super().tick(frames, render=render)
        self.initial_screen = None
        return result

    def evidence(self):
        return read_progress(self.memory)

    def structured(self, labels=None):
        return structured(self.memory, labels)

    def challenge_evidence(self, objective):
        if objective['kind'] in ('guarded-milestones','encounter-capture','resource-route'):
            from .gameplay import ui_state
            bag=dict(read_bag(self.memory))
            return {'battle':self.memory[W_IS_IN_BATTLE], 'battle_type':self.memory[W_BATTLE_TYPE],
                    'map_id':self.memory[W_CUR_MAP], 'overworld':ui_state(self.memory)['kind']=='overworld',
                    'enemy_species':self.memory[W_ENEMY_MON],
                    'balls':sum(bag.get(i,0) for i in (1,2,3,4)),
                    'party':[{k:list(m[k]) if k=='dvs' else m[k] for k in ('species','trainer_id','dvs','hp','max_hp','status')}
                             for m in read_party(self.memory)]}
        if objective['kind'] == 'battle-milestone':
            return {'battle': self.memory[W_IS_IN_BATTLE],
                    'surviving': any(mon['hp'] > 0 for mon in read_party(self.memory))}
        if objective['kind'] in ('reach-map', 'purchase', 'obtain-item'):
            from .gameplay import ui_state
            bag = dict(read_bag(self.memory))
            keys = objective.get('item_ids', [objective.get('item_id', 0)])
            return {'map_id': self.memory[W_CUR_MAP], 'battle': self.memory[W_IS_IN_BATTLE],
                    'overworld': ui_state(self.memory)['kind'] == 'overworld',
                    'surviving': any(mon['hp'] > 0 for mon in read_party(self.memory)),
                    'items': {str(key): bag.get(key, 0) for key in keys},
                    'money': bcd(bytes(self.memory[W_MONEY:W_MONEY + 3]))}
        if objective["kind"] == "heal":
            from .gameplay import ui_state
            return {"map_id": self.memory[W_CUR_MAP], "battle": self.memory[W_IS_IN_BATTLE],
                    "overworld": ui_state(self.memory)["kind"] == "overworld",
                    "party": [{key: list(mon[key]) if key == "dvs" else mon[key]
                               for key in ("species", "trainer_id", "dvs", "hp", "max_hp", "status")}
                              for mon in read_party(self.memory)]}
        if objective["kind"] == "wild-battle":
            return {"battle": self.memory[W_IS_IN_BATTLE], "battle_type": self.memory[W_BATTLE_TYPE],
                    "enemy_species": self.memory[W_ENEMY_MON],
                    "party": [{key: mon[key] for key in ("species", "hp", "experience")}
                              for mon in read_party(self.memory)]}
        if objective["kind"] in ("opening", "capture"):
            flags = self.memory[W_EVENT_FLAGS:W_EVENT_FLAGS + 0x140]
            bag = dict(read_bag(self.memory))
            return {"player_name": decode_text(self.memory[W_PLAYER_NAME:W_PLAYER_NAME + 11]),
                    "party_count": self.memory[W_PARTY_COUNT],
                    "party_species": [mon["species"] for mon in read_party(self.memory)],
                    "owned": sorted(flag_bits(bytes(self.memory[W_DEX_OWNED:W_DEX_OWNED + 19]))),
                    "parcel": bag.get(0x46, 0), "parcel_delivered": event_set(flags, 56),
                    "balls": sum(bag.get(item, 0) for item in (1, 2, 3, 4)),
                    "battle": self.memory[W_IS_IN_BATTLE], "battle_type": self.memory[W_BATTLE_TYPE],
                    "enemy_species": self.memory[W_ENEMY_MON]}
        if objective["kind"] == "location":
            return {"location": [self.memory[W_CUR_MAP], self.memory[W_X], self.memory[W_Y]]}
        flags = self.memory[W_EVENT_FLAGS:W_EVENT_FLAGS + 0x140]
        return {"event": event_set(flags, objective["event_id"]), "battle": self.memory[W_IS_IN_BATTLE]}
