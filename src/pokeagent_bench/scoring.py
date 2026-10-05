"""Private, monotonic scoring using confirmed flags rather than battle-end guesses."""
from .game import BADGES


class Evaluator:
    def __init__(self, initial):
        self.baseline = initial
        self.previous = set()
        self.awarded = {}
        self.initial_keys = self.candidates(initial)

    def candidates(self, state):
        if not state["valid"]:
            return set()
        keys = {f"badge:{name.lower()}" for i, name in enumerate(BADGES)
                if state["badges"] & (1 << i) and state["gym_flags"][i]}
        keys.update(f"elite:{name.lower()}" for name, won in state["elite"].items() if won)
        keys.update(f"story:{name}" for name, done in state["story"].items() if done)
        if (state["champion"] and state["map_id"] == 118
                and state["hall_of_fame"] > self.baseline["hall_of_fame"]):
            keys.add("champion")
        return keys

    def observe(self, state, frame, wall_seconds):
        candidates = self.candidates(state)
        confirmed = (self.previous & candidates) - self.initial_keys - self.awarded.keys()
        self.previous = candidates
        new = []
        for key in sorted(confirmed):
            points = 75 if key.startswith("badge:") else 50 if key.startswith("elite:") else 200 if key == "champion" else 0
            award = {"id": key, "points": points, "frame": frame, "wall_seconds": round(wall_seconds, 6)}
            self.awarded[key] = award
            new.append(award)
        return new

    @property
    def score(self):
        return sum(row["points"] for row in self.awarded.values())

    def complete(self, goal):
        return ("badge:boulder" if goal == "first-gym" else "champion") in self.awarded
