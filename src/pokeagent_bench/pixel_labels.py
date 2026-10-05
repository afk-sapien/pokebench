"""Offline, exact pixel-template labels for assisted-vision experiments.

Templates are private human annotations of visible sprite patches. This module
never reads emulator memory or chooses controller actions. It is deliberately
not connected to the benchmark runner until a separately versioned assisted
track and broader validation are available.
"""

from io import BytesIO

import numpy as np
from PIL import Image

from .core import digest


def exact_pixel_matches(screenshot: bytes, template: bytes):
    """Return visible patch bounds, without interpreting absent matches."""
    with Image.open(BytesIO(screenshot)) as image:
        screen = np.asarray(image.convert("RGB"))
    with Image.open(BytesIO(template)) as image:
        patch = np.asarray(image.convert("RGB"))
    height, width = patch.shape[:2]
    if height < 4 or width < 4 or len(np.unique(patch.reshape(-1, 3), axis=0)) < 2:
        raise ValueError("A template must contain a nonuniform visible patch")
    if height > screen.shape[0] or width > screen.shape[1]:
        return []
    candidates = np.all(screen[: screen.shape[0] - height + 1, : screen.shape[1] - width + 1] == patch[0, 0], axis=2)
    bounds = []
    for y, x in np.argwhere(candidates):
        if np.array_equal(screen[y : y + height, x : x + width], patch):
            bounds.append([int(x), int(y), int(x + width), int(y + height)])
    return bounds


def label_visible_patch(screenshot: bytes, template: bytes, label: str):
    """Attach a supplied human label only where the whole patch matches."""
    if not isinstance(label, str) or not label.strip() or len(label) > 80:
        raise ValueError("Supply a short object label")
    return {
        "method": "exact-visible-pixel-template-v1",
        "screenshot_sha256": digest(screenshot),
        "template_sha256": digest(template),
        "label_source": "human-annotated-private-template",
        "detections": [{"label": label, "bounds_xyxy": bounds} for bounds in exact_pixel_matches(screenshot, template)],
    }
