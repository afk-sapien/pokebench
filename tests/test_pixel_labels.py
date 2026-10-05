from io import BytesIO

import numpy as np
from PIL import Image
import pytest

from pokeagent_bench.pixel_labels import label_visible_patch


def png(array):
    stream = BytesIO()
    Image.fromarray(array).save(stream, format="PNG")
    return stream.getvalue()


def test_labels_follow_visible_pixels_and_include_provenance():
    patch = np.random.default_rng(4).integers(0, 255, (8, 6, 3), dtype=np.uint8)
    screen = np.zeros((24, 24, 3), dtype=np.uint8)
    screen[4:12, 12:18] = patch
    result = label_visible_patch(png(screen), png(patch), "synthetic object")
    assert result["detections"] == [{"label": "synthetic object", "bounds_xyxy": [12, 4, 18, 12]}]
    assert len(result["template_sha256"]) == len(result["screenshot_sha256"]) == 64
    screen[4:12, 12:18] = 0
    assert label_visible_patch(png(screen), png(patch), "synthetic object")["detections"] == []


def test_occluded_or_changed_patches_are_not_reported_as_visible():
    patch = np.random.default_rng(4).integers(0, 255, (8, 6, 3), dtype=np.uint8)
    partial = patch.copy()
    partial[0, 0] = 0
    assert label_visible_patch(png(partial), png(patch), "object")["detections"] == []
    assert label_visible_patch(png(patch[:4]), png(patch), "object")["detections"] == []


def test_uniform_template_cannot_label_blank_screens():
    blank = png(np.zeros((8, 8, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="nonuniform"):
        label_visible_patch(blank, blank, "object")
