from copy import deepcopy
import io

from PIL import Image
import pytest

from pokeagent_bench.session import Session


def blank_evidence():
    return {"valid": True, "badges": 0, "gym_flags": [False] * 8,
            "elite": {name: False for name in ("Lorelei", "Bruno", "Agatha", "Lance")},
            "champion": False, "hall_of_fame": 0, "map_id": 0,
            "story": {"starter": False, "pokedex": False, "silph_co": False, "surf": False}}


class FakeEngine:
    def __init__(self):
        self.frame = 0
        self.state = blank_evidence()
        self.inputs = []
        self.closed = False
        self.on_tick = None

    def press(self, button):
        self.inputs.append(("press", button, self.frame))

    def release(self, button):
        self.inputs.append(("release", button, self.frame))

    def tick(self):
        self.frame += 1
        if self.on_tick:
            self.on_tick(self)

    def evidence(self):
        return deepcopy(self.state)

    def structured(self, labels=None):
        return {"location": {"map_id": 0, "x": self.frame, "y": 0}, "party": [], "inventory": []}

    def screenshot(self):
        output = io.BytesIO()
        Image.new("RGB", (160, 144), (self.frame % 256, 50, 80)).save(output, format="PNG")
        return output.getvalue()

    def save(self):
        return f"fake-state-{self.frame}".encode()

    def close(self):
        self.closed = True


@pytest.fixture
def engine():
    return FakeEngine()


@pytest.fixture
def session(tmp_path, engine):
    run = Session(engine, tmp_path / "run", {"name": "fake", "rom_sha256": "fake"})
    yield run
    run.close()
