"""Curated checkpoint objectives and private success evidence."""
from copy import deepcopy

from .game import BADGES
from .scoring import Evaluator


def validate_objective(value):
    if not isinstance(value, dict):
        raise ValueError("An objective must be an object")
    objective = deepcopy(value)
    kind = objective.get("kind")
    required = {"guarded-milestones": {"kind", "targets", "no_faints", "description"},
                "encounter-capture": {"kind", "description"},
                "resource-route": {"kind", "map_id", "description"},
                "battle-milestone": {"kind", "target", "description"}, "milestone": {"kind", "target", "description"},
                "reach-map": {"kind", "map_id", "description"},
                "purchase": {"kind", "item_id", "quantity", "unit_price", "map_id", "description"},
                "obtain-item": {"kind", "item_ids", "description"},
                "location": {"kind", "map_id", "x", "y", "description"},
                "trainer": {"kind", "event_id", "description"},
                "opening": {"kind", "target", "description"},
                "capture": {"kind", "description"},
                "heal": {"kind", "map_id", "description"},
                "wild-battle": {"kind", "description"}}.get(kind)
    if required is None or set(objective) != required:
        raise ValueError("Unsupported objective or unexpected fields")
    if not isinstance(objective["description"], str) or not 1 <= len(objective["description"]) <= 1000:
        raise ValueError("An objective needs a short player-facing description")
    if kind == 'guarded-milestones':
        targets=objective['targets']
        if not isinstance(targets,list) or not targets or any(not isinstance(t,str) for t in targets) or len(targets)!=len(set(targets)) or type(objective['no_faints']) is not bool:
            raise ValueError('Invalid guarded battle targets')
        for target in targets:
            validate_objective({'kind':'milestone','target':target,'description':'Target validation'})
    elif kind in ("milestone", "battle-milestone"):
        allowed = {f"badge:{name.lower()}" for name in BADGES}
        allowed.update(f"elite:{name}" for name in ("lorelei", "bruno", "agatha", "lance"))
        allowed.add("champion")
        if objective["target"] not in allowed:
            raise ValueError("Unknown milestone target")
    elif kind == "opening":
        if objective["target"] not in ("starter", "parcel", "parcel-roundtrip"):
            raise ValueError("Unknown opening objective")
    elif kind == 'obtain-item':
        items = objective['item_ids']
        if (not isinstance(items, list) or not 1 <= len(items) <= 10
                or any(type(i) is not int or not 1 <= i <= 255 for i in items) or len(set(items)) != len(items)):
            raise ValueError('Invalid target item IDs')
    elif kind == 'purchase':
        for key, lower, upper in [('item_id', 1, 255), ('quantity', 1, 99), ('unit_price', 1, 999999), ('map_id', 0, 255)]:
            if type(objective[key]) is not int or not lower <= objective[key] <= upper:
                raise ValueError(f'Invalid purchase {key}')
    elif kind not in ("capture", "wild-battle", "encounter-capture"):
        bounds = ({"event_id": 2559} if kind == "trainer" else {"map_id": 255} if kind in ("heal", "reach-map", "resource-route")
                  else {"map_id": 255, "x": 255, "y": 255})
        for key, maximum in bounds.items():
            if type(objective[key]) is not int or not 0 <= objective[key] <= maximum:
                raise ValueError(f"Invalid objective {key}")
    return objective


def evidence(engine, objective=None):
    state = engine.evidence()
    if objective and objective["kind"] in ("guarded-milestones", "encounter-capture", "resource-route", "battle-milestone", "location", "trainer", "opening", "capture", "wild-battle", "heal", "reach-map", "purchase", "obtain-item"):
        state["challenge"] = engine.challenge_evidence(objective)
    return state


class ChallengeEvaluator:
    """Award one normalized challenge point after two confirming game frames."""

    def __init__(self, initial, objective):
        self.objective = validate_objective(objective)
        self.progress = Evaluator(initial)
        self.baseline = deepcopy(initial)
        self.initial_keys = self.progress.initial_keys
        self.previous = False
        self.awarded = {}
        self.previous_capture = deepcopy(initial.get("challenge", {}))
        self.captured_species = None
        self.parcel_collected = False
        self.battle_xp_earned = False
        self.battle_ended = False
        self.battle_won = False
        self.battle_disqualified = False
        self.healing_disqualified = False
        self.adventure_disqualified = False
        empty_starter = (self.objective["kind"] == "opening" and self.objective["target"] == "starter"
                         and initial["challenge"]["party_count"] == 0
                         and bool(initial["challenge"]["player_name"])
                         and initial["map_id"] in (0, 37, 38, 40)
                         and not initial["story"]["starter"])
        if not initial["valid"] and not empty_starter:
            raise ValueError("Checkpoint must start in a valid game state")
        if self.objective["kind"] == "opening" and self.objective["target"] == "parcel":
            if initial["challenge"]["parcel"] != 1 or initial["challenge"]["parcel_delivered"]:
                raise ValueError("Parcel checkpoint must start with Oak's undelivered parcel")
        if self.objective["kind"] == "opening" and self.objective["target"] == "parcel-roundtrip":
            facts = initial["challenge"]
            if (not initial["story"]["starter"] or initial["story"]["pokedex"]
                    or facts["parcel"] != 0 or facts["parcel_delivered"]
                    or facts["party_count"] != 1 or facts["party_species"] not in ([153], [176], [177])):
                raise ValueError("Parcel roundtrip requires one starter before parcel collection or delivery")
        if self.objective["kind"] == "capture":
            facts = initial["challenge"]
            if (facts["party_count"] != 1 or len(facts["owned"]) != 1 or facts["balls"] < 1
                    or not initial["story"]["pokedex"]):
                raise ValueError("First-catch checkpoint requires one owned starter, a Pokedex, and balls")
        if self.objective["kind"] == "wild-battle":
            facts = initial["challenge"]
            if (facts["battle"] != 1 or facts["battle_type"] != 0
                    or not 1 <= facts["enemy_species"] <= 190
                    or not facts["party"] or not any(mon["hp"] > 0 for mon in facts["party"])):
                raise ValueError("Wild-battle checkpoint must start in a live normal wild encounter")
        if self.objective["kind"] == "heal":
            party = initial["challenge"]["party"]
            if (not party or not any(mon["hp"] > 0 for mon in party)
                    or all(mon["hp"] == mon["max_hp"] and not mon["status"] for mon in party)):
                raise ValueError("Healing checkpoint needs a surviving, damaged or afflicted party")
        if self.objective['kind'] in ('reach-map', 'purchase', 'obtain-item'):
            facts = initial['challenge']
            if not facts['surviving'] or facts['battle'] == 255:
                raise ValueError('Adventure checkpoint requires a surviving party')
            if self.objective['kind'] == 'reach-map' and facts['map_id'] == self.objective['map_id']:
                raise ValueError('Navigation checkpoint already reached the destination')
            if self.objective['kind'] == 'purchase':
                if facts['money'] < self.objective['quantity'] * self.objective['unit_price']:
                    raise ValueError('Shopping checkpoint cannot afford the target purchase')
            if self.objective['kind'] == 'obtain-item' and any(facts['items'].values()):
                raise ValueError('Checkpoint already owns a target item')
        if self.objective['kind'] == 'battle-milestone':
            facts = initial['challenge']
            if facts['battle'] != 2 or not facts['surviving']:
                raise ValueError('Single-attempt battle must start in a live trainer battle')
        if self.objective['kind'] in ('guarded-milestones','encounter-capture','resource-route'):
            facts=initial['challenge']
            if not facts['party'] or not any(m['hp']>0 for m in facts['party']) or facts['battle']==255:
                raise ValueError('Decision task requires a surviving party')
            if self.objective['kind']=='guarded-milestones':
                if self.objective['no_faints'] and any(m['hp']==0 for m in facts['party']):
                    raise ValueError('No-faint task must start with every Pokemon alive')
                if any(target in self.progress.initial_keys for target in self.objective['targets']):
                    raise ValueError('A target was completed before the task')
            if self.objective['kind']=='encounter-capture':
                if facts['battle']!=1 or facts['battle_type']!=0 or not facts['balls'] or len(facts['party'])>=6:
                    raise ValueError('Capture task requires a live normal encounter, balls and party space')
            if self.objective['kind']=='resource-route' and facts['map_id']==self.objective['map_id']:
                raise ValueError('Resource route already reached its destination')
        if self.reached(initial):
            raise ValueError("Checkpoint already satisfies its objective")
        if self.objective["kind"] == "trainer" and initial["challenge"]["event"]:
            raise ValueError("Trainer victory flag is already set")

    def reached(self, state):
        if not state["valid"]:
            return False
        kind = self.objective["kind"]
        if kind in ('guarded-milestones','encounter-capture','resource-route'):
            facts=state['challenge']
            if self.battle_disqualified:
                return False
            if kind=='guarded-milestones':
                return all(target in self.progress.candidates(state) for target in self.objective['targets'])
            if kind=='resource-route':
                return facts['battle']==0 and facts['overworld'] and facts['map_id']==self.objective['map_id']
            return self.captured_species is not None and facts['battle']==0 and len(facts['party'])==len(self.baseline['challenge']['party'])+1
        if kind in ('reach-map', 'purchase', 'obtain-item'):
            facts = state['challenge']
            if self.adventure_disqualified or not facts['surviving'] or facts['battle'] != 0 or not facts['overworld']:
                return False
            if kind == 'reach-map':
                return facts['map_id'] == self.objective['map_id']
            initial = self.baseline['challenge']
            if kind == 'purchase':
                key = str(self.objective['item_id'])
                return (facts['map_id'] == self.objective['map_id']
                        and facts['items'][key] - initial['items'][key] >= self.objective['quantity']
                        and initial['money'] - facts['money'] >= self.objective['quantity'] * self.objective['unit_price'])
            return any(facts['items'][str(key)] > 0 for key in self.objective['item_ids'])
        if kind in ("milestone", "battle-milestone"):
            return (not self.battle_disqualified and self.objective["target"] in self.progress.candidates(state))
        if kind == "opening":
            facts = state["challenge"]
            if self.objective["target"] == "starter":
                return state["story"]["starter"] and facts["party_count"] == 1 and facts["party_species"][0] in (153, 176, 177)
            return ((self.objective["target"] == "parcel" or self.parcel_collected)
                    and facts["parcel_delivered"] and facts["parcel"] == 0
                    and state["story"]["pokedex"] and facts["battle"] == 0)
        if kind == "capture":
            facts = state["challenge"]
            return (self.captured_species is not None and facts["battle"] == 0
                    and facts["party_count"] == 2 and self.captured_species in facts["party_species"]
                    and len(facts["owned"]) > len(self.baseline["challenge"]["owned"]))
        if kind == "wild-battle":
            return self.battle_won and state["challenge"]["battle"] == 0
        if kind == "heal":
            facts = state["challenge"]
            return (not self.healing_disqualified and facts["map_id"] == self.objective["map_id"]
                    and facts["battle"] == 0 and facts["overworld"] and bool(facts["party"])
                    and all(mon["hp"] == mon["max_hp"] and mon["max_hp"] > 0 and not mon["status"]
                            for mon in facts["party"]))
        if kind == "location":
            return state["challenge"]["location"] == [self.objective[key] for key in ("map_id", "x", "y")]
        return state["challenge"]["event"] and state["challenge"]["battle"] == 0

    def observe(self, state, frame, wall_seconds):
        if self.objective['kind'] in ('guarded-milestones','encounter-capture','resource-route'):
            facts=state['challenge']
            original=self.baseline['challenge']
            identities=lambda mons: sorted((m['species'],m['trainer_id'],tuple(m['dvs'])) for m in mons)
            if facts['battle']==255 or not any(m['hp']>0 for m in facts['party']):
                self.battle_disqualified=True
            if self.objective['kind']=='guarded-milestones':
                if identities(facts['party'])!=identities(original['party']):
                    self.battle_disqualified=True
                if self.objective['no_faints'] and any(m['hp']==0 for m in facts['party']):
                    self.battle_disqualified=True
            if self.objective['kind']=='encounter-capture':
                previous=self.previous_capture
                count=len(original['party'])
                if (previous['battle']==1 and facts['battle_type']==0 and len(facts['party'])==count+1
                        and identities(facts['party'][:count])==identities(original['party'])
                        and facts['party'][-1]['species']==original['enemy_species']):
                    self.captured_species=original['enemy_species']
                if facts['battle']==0 and self.captured_species is None:
                    self.battle_disqualified=True
                self.previous_capture=deepcopy(facts)
        if self.objective['kind'] == 'battle-milestone':
            facts = state['challenge']
            if facts['battle'] == 255 or not facts['surviving']:
                self.battle_disqualified = True
        if self.objective['kind'] in ('reach-map', 'purchase', 'obtain-item'):
            facts = state['challenge']
            if facts['battle'] == 255 or not facts['surviving']:
                self.adventure_disqualified = True
        if self.objective["kind"] == "heal":
            facts = state["challenge"]
            party = facts["party"]
            identities = lambda mons: sorted((m["species"], m["trainer_id"], tuple(m["dvs"])) for m in mons)
            if (facts["battle"] == 255 or not any(mon["hp"] > 0 for mon in party)
                    or identities(party) != identities(self.baseline["challenge"]["party"])):
                self.healing_disqualified = True
        if self.objective["kind"] == "opening" and self.objective["target"] == "parcel-roundtrip":
            facts = state["challenge"]
            if state["valid"] and facts["parcel"] == 1 and not facts["parcel_delivered"]:
                self.parcel_collected = True
        if self.objective["kind"] == "wild-battle" and not self.battle_ended:
            facts = state["challenge"]
            baseline = self.baseline["challenge"]
            party = facts["party"]
            same_party = ([mon["species"] for mon in party]
                          == [mon["species"] for mon in baseline["party"]])
            if (not state["valid"] or not same_party or facts["battle"] not in (0, 1)
                    or facts["battle_type"] != 0
                    or facts["enemy_species"] != baseline["enemy_species"]):
                self.battle_disqualified = True
            # Generation I awards experience for a knockout, but not a capture or escape.
            # Credit must be earned before this initial encounter ends.
            if facts["battle"] == 1 and same_party and not self.battle_disqualified:
                self.battle_xp_earned |= any(
                    mon["experience"] > old["experience"]
                    for mon, old in zip(party, baseline["party"])
                )
            if facts["battle"] == 0:
                self.battle_ended = True
                self.battle_won = (self.battle_xp_earned and not self.battle_disqualified
                                   and any(mon["hp"] > 0 for mon in party))
        if self.objective["kind"] == "capture":
            facts = state["challenge"]
            previous = self.previous_capture
            # A new party member must appear during a real wild encounter, not as a gift.
            if (state["valid"] and previous["battle"] == 1 and previous["battle_type"] == 0
                    and facts["party_count"] == 2
                    and facts["party_species"][:1] == self.baseline["challenge"]["party_species"]
                    and facts["party_species"][1] == previous["enemy_species"]
                    and len(facts["owned"]) > len(self.baseline["challenge"]["owned"])):
                self.captured_species = facts["party_species"][1]
            self.previous_capture = deepcopy(facts)
        reached = self.reached(state)
        if reached and self.previous and not self.awarded:
            award = {"id": "challenge:complete", "points": 1, "frame": frame,
                     "wall_seconds": round(wall_seconds, 6)}
            self.awarded[award["id"]] = award
            return [award]
        self.previous = reached
        return []

    @property
    def score(self):
        return len(self.awarded)

    def complete(self, goal):
        return bool(self.awarded)
