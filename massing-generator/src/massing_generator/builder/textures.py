"""
Procedural, tileable material textures (no downloads).

Generates a set of seamless PNGs into ./textures used by the HQ renderer:
    grass, dirt, brick, stucco, wood, shingle, concrete, paver, bark

Run directly to (re)generate:  python textures.py
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

try:
    from .paths import TEXTURES_DIR as TEX_DIR
except ImportError:  # running as a standalone script
    from paths import TEXTURES_DIR as TEX_DIR

SIZE = 512
RNG = np.random.default_rng(7)


# ----------------------------------------------------------------------------
# noise helpers (tileable)
# ----------------------------------------------------------------------------
def _wrap_blur(arr, radius):
    """Gaussian blur that wraps around edges -> seamless."""
    img = Image.fromarray(np.uint8(np.clip(arr, 0, 255)))
    # tile 3x3, blur, crop center for seamless wrap
    big = Image.new("L", (SIZE * 3, SIZE * 3))
    for a in range(3):
        for b in range(3):
            big.paste(img, (a * SIZE, b * SIZE))
    big = big.filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(big.crop((SIZE, SIZE, SIZE * 2, SIZE * 2)), float)


def fractal(scales=(6, 14, 30, 60), weights=(0.5, 0.25, 0.15, 0.1), seed=None):
    """Sum of blurred random layers -> tileable fractal value noise (0..1)."""
    rng = np.random.default_rng(seed) if seed is not None else RNG
    out = np.zeros((SIZE, SIZE), float)
    for sc, w in zip(scales, weights):
        layer = rng.random((SIZE, SIZE)) * 255
        out += w * _wrap_blur(layer, sc)
    out -= out.min()
    out /= max(out.max(), 1e-6)
    return out


def _tint(noise, lo, hi):
    """Map 0..1 noise into an RGB range [lo..hi] (each a 3-tuple)."""
    lo, hi = np.array(lo, float), np.array(hi, float)
    rgb = lo[None, None, :] + noise[:, :, None] * (hi - lo)[None, None, :]
    return np.uint8(np.clip(rgb, 0, 255))


def _save(arr, name):
    """Write a texture PNG, but never clobber one that already exists.

    User-supplied textures dropped into TEX_DIR take precedence; regeneration
    is opt-in via `generate_all(overwrite=True)` (CLI: `--force`).
    """
    path = os.path.join(TEX_DIR, f"{name}.png")
    if os.path.exists(path):
        return
    Image.fromarray(arr, "RGB").save(path)


# ----------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------
def grass():
    n = fractal((5, 12, 26), (0.5, 0.3, 0.2), seed=1)
    blades = fractal((2, 4), (0.6, 0.4), seed=11)
    img = _tint(n * 0.65 + blades * 0.35, (62, 102, 48), (104, 150, 70))
    _save(img, "grass")


def dirt():
    n = fractal((5, 12, 28), (0.45, 0.3, 0.25), seed=2)
    img = _tint(n, (78, 58, 38), (138, 108, 74))
    _save(img, "dirt")


def concrete():
    n = fractal((8, 20, 50), (0.4, 0.35, 0.25), seed=3)
    img = _tint(n, (150, 150, 150), (200, 200, 200))
    _save(img, "concrete")


def stucco():
    n = fractal((6, 16, 40), (0.4, 0.35, 0.25), seed=4)
    img = _tint(n, (214, 206, 190), (240, 234, 222))
    _save(img, "stucco")


def brick():
    img = Image.new("RGB", (SIZE, SIZE), (198, 190, 180))  # light mortar
    d = ImageDraw.Draw(img)
    bw, bh, gap = 88, 34, 6
    rng = np.random.default_rng(20)
    rows = SIZE // (bh + gap) + 1
    for r in range(rows):
        y0 = r * (bh + gap)
        off = (bw // 2) if r % 2 else 0
        for c in range(-1, SIZE // (bw + gap) + 2):
            x0 = c * (bw + gap) + off
            base = rng.integers(-12, 12)
            col = (164 + base, 74 + base // 2, 58 + base // 2)
            d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=col)
    arr = np.asarray(img, float)
    grain = (fractal((10, 22), (0.6, 0.4), seed=21)[:, :, None] - 0.5) * 14
    _save(np.uint8(np.clip(arr + grain, 0, 255)), "brick")


def shingle():
    img = Image.new("RGB", (SIZE, SIZE), (58, 64, 70))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(30)
    th, tw, gap = 34, 46, 3
    rows = SIZE // th + 1
    for r in range(rows):
        y0 = r * th
        off = (tw // 2) if r % 2 else 0
        for c in range(-1, SIZE // tw + 2):
            x0 = c * tw + off
            sh = rng.integers(-10, 10)
            col = (56 + sh, 62 + sh, 70 + sh)
            d.rounded_rectangle([x0, y0, x0 + tw - gap, y0 + th - gap],
                                radius=3, fill=col)
            d.line([x0, y0 + th - gap, x0 + tw - gap, y0 + th - gap],
                   fill=(34, 37, 41), width=2)
    arr = np.asarray(img, float)
    grain = (fractal((12, 26), (0.6, 0.4), seed=31)[:, :, None] - 0.5) * 9
    _save(np.uint8(np.clip(arr + grain, 0, 255)), "shingle")


def _streaks(seed, lo, hi):
    """Vertical wood-like streaks (tileable)."""
    base = RNG  # noqa
    rng = np.random.default_rng(seed)
    col = rng.random((1, SIZE)) * 255
    streak = np.repeat(col, SIZE, axis=0)
    streak = _wrap_blur(streak, 1.5)
    rings = fractal((40, 80), (0.6, 0.4), seed=seed + 1)
    n = 0.6 * (streak / 255.0) + 0.4 * rings
    n -= n.min(); n /= max(n.max(), 1e-6)
    return _tint(n, lo, hi)


def wood():
    _save(_streaks(40, (120, 80, 44), (180, 132, 80)), "wood")


def bark():
    _save(_streaks(50, (60, 44, 30), (104, 78, 52)), "bark")


_MATERIALS = {
    "grass": grass, "dirt": dirt, "concrete": concrete, "stucco": stucco,
    "brick": brick, "shingle": shingle, "wood": wood, "bark": bark,
}


def generate_all(overwrite=False):
    """Generate the procedural textures.

    Existing PNGs are preserved by default so user-supplied textures survive a
    run. Pass `overwrite=True` to force-regenerate every material.
    """
    os.makedirs(TEX_DIR, exist_ok=True)
    for name, fn in _MATERIALS.items():
        path = os.path.join(TEX_DIR, f"{name}.png")
        if os.path.exists(path):
            if not overwrite:
                continue
            os.remove(path)  # _save skips existing files; clear it first
        fn()
    print(f"Textures written to {TEX_DIR}")


if __name__ == "__main__":
    import sys

    generate_all(overwrite="--force" in sys.argv)
