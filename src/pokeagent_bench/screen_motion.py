"""Conservative screen translation estimates from image pixels only.

This is not a player coordinate reader. Animations, fades, and repeated textures
can be ambiguous. Unknown estimates remain null and never drive controller input.
"""

from io import BytesIO

import numpy as np
from PIL import Image


def estimate_screen_translation(before, after):
    a = np.asarray(Image.open(BytesIO(before)).convert("L"), dtype=np.int16)
    b = np.asarray(Image.open(BytesIO(after)).convert("L"), dtype=np.int16)

    def edge(x):
        out = np.zeros(x.shape, dtype=bool)
        out[:, 1:] |= np.abs(x[:, 1:] - x[:, :-1]) >= 32
        out[1:, :] |= np.abs(x[1:, :] - x[:-1, :]) >= 32
        return out

    ea, eb = edge(a), edge(b)
    h, w = a.shape
    scores = []
    for dx, dy in [(d, 0) for d in range(-48, 49)] + [(0, d) for d in range(-48, 49) if d]:
        xa, xb = max(0, -dx), max(0, dx)
        ya, yb = max(0, -dy), max(0, dy)
        ww, hh = w - abs(dx), h - abs(dy)
        av, bv = a[ya : ya + hh, xa : xa + ww], b[yb : yb + hh, xb : xb + ww]
        mask = ea[ya : ya + hh, xa : xa + ww] | eb[yb : yb + hh, xb : xb + ww]
        n = int(mask.sum())
        score = float((np.abs(av - bv)[mask] <= 4).mean()) if n >= 300 else 0
        scores.append((score, dx, dy, n))
    scores.sort(reverse=True)
    best, second = scores[:2]
    zero = next(s[0] for s in scores if s[1:3] == (0, 0))
    if best[0] < 0.9 or (best[1:3] != (0, 0) and (best[0] - second[0] < 0.08 or best[0] - zero < 0.12)):
        return None
    return {
        "dx_pixels": best[1],
        "dy_pixels": best[2],
        "edge_match_fraction": round(best[0], 3),
        "separation": round(best[0] - second[0], 3),
    }
