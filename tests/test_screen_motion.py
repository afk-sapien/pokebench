from io import BytesIO

import numpy as np
from PIL import Image
import pytest

from pokeagent_bench.core import Limits
from pokeagent_bench.runner import run
from pokeagent_bench.screen_motion import estimate_screen_translation
from pokeagent_bench.session import Session
from pokeagent_bench.visual_feedback import normalize_notes


def png(array):
    data = BytesIO()
    Image.fromarray(array).save(data, format="PNG")
    return data.getvalue()


@pytest.mark.parametrize("dx,dy", [(0, 0), (16, 0), (-24, 0), (0, 14), (0, -32)])
def test_translation_recovers_observed_pixel_shift_without_game_facts(dx, dy):
    original = np.random.default_rng(42).integers(0, 256, (144, 160), dtype=np.uint8)
    shifted = np.zeros_like(original)
    h, w = original.shape
    xa, xb = max(0, -dx), max(0, dx)
    ya, yb = max(0, -dy), max(0, dy)
    shifted[yb : yb + h - abs(dy), xb : xb + w - abs(dx)] = original[ya : ya + h - abs(dy), xa : xa + w - abs(dx)]
    result = estimate_screen_translation(png(original), png(shifted))
    assert (result["dx_pixels"], result["dy_pixels"]) == (dx, dy)
    assert result["edge_match_fraction"] > 0.99


def test_blank_transition_and_ambiguous_texture_do_not_invent_motion():
    blank = png(np.zeros((144, 160), dtype=np.uint8))
    assert estimate_screen_translation(blank, blank) is None
    random = png(np.random.default_rng(42).integers(0, 256, (144, 160), dtype=np.uint8))
    assert estimate_screen_translation(random, blank) is None
    stripes = png(np.tile(np.array([0, 255], dtype=np.uint8), (144, 80)))
    assert estimate_screen_translation(stripes, stripes) is None


def test_stagnation_guard_stops_before_another_paid_request(tmp_path, engine):
    initial = engine.screenshot()
    engine.screenshot = lambda: initial

    class Provider:
        provider = "test"
        model = "fixture"
        visual_feedback = True
        motion_feedback = True
        stagnation_guard = True
        normalize_notes = staticmethod(normalize_notes)

        def decide(self, *args):
            return (
                {"actions": [{"button": "wait", "hold_frames": 1, "release_frames": 0}], "notes": None},
                {"input_tokens": 10, "output_tokens": 2},
                {},
            )

        def close(self):
            pass

    session = Session(engine, tmp_path / "run", {}, limits=Limits(max_stagnant_decisions=3))
    result = run(session, Provider())
    assert result["stop_reason"] == "observation_stagnation_budget"
    assert result["usage"]["calls"] == result["actions"] == result["frames"] == 3
    assert result["usage"]["input_tokens"] == 30
    assert engine.inputs == []


def test_new_views_reset_stagnation_budget(tmp_path, engine):
    class Provider:
        provider = "test"
        model = "fixture"
        visual_feedback = True
        stagnation_guard = True

        def decide(self, *args):
            return (
                {"actions": [{"button": "wait", "hold_frames": 1, "release_frames": 0}], "notes": None},
                {"input_tokens": 10, "output_tokens": 2},
                {},
            )

        def close(self):
            pass

    session = Session(engine, tmp_path / "run", {}, limits=Limits(max_stagnant_decisions=2, max_model_calls=4))
    result = run(session, Provider())
    assert result["stop_reason"] == "model_call_budget"
    assert result["usage"]["calls"] == 4
