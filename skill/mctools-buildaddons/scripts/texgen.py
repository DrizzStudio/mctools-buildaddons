"""Original procedural pixel-art generators for Bedrock add-on textures.

Everything here is drawn from scratch with math and a seeded random generator; no vanilla
Minecraft assets and no third-party art are used or copied, so the output is free to use
(CC0) in any add-on. Textures are generated on a 16x16 grid and upscaled with
nearest-neighbour to 32/64/128 px if requested.
"""

from __future__ import annotations
import colorsys
import hashlib
import random

from mclib import LICENSE_NOTE, SOFTWARE_NOTE, hex_to_rgb, upscale

GRID = 16
TRANSPARENT = (0, 0, 0, 0)

ITEM_STYLES = ["gem", "ingot", "orb", "potion", "sword", "wand"]
BLOCK_STYLES = ["stone", "bricks", "planks", "ore", "metal", "crystal"]

FIXED = {
    "white": (255, 255, 255),
    "wood": (122, 84, 48),
    "wooddark": (84, 56, 30),
    "metal": (190, 194, 204),
    "metaldark": (120, 124, 138),
    "cork": (160, 110, 60),
    "corkdark": (112, 74, 38),
    "glass": (205, 225, 240),
}


def clamp(v):
    return max(0, min(255, int(round(v))))


def mul(color, f):
    return tuple(clamp(c * f) for c in color)


def mix(a, b, t):
    return tuple(clamp(a[i] * (1 - t) + b[i] * t) for i in range(3))


def make_palette(base):
    pal = {
        "light": mix(base, (255, 255, 255), 0.40),
        "base": base,
        "shadow": mul(base, 0.68),
        "dark": mul(base, 0.45),
    }
    pal.update(FIXED)
    pal["outline"] = mix(mul(base, 0.28), (0, 0, 0), 0.35)
    return pal


def seed_to_int(*parts) -> int:
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def color_from_seed(seed) -> tuple:
    h = (seed_to_int(seed, "hue") % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.62, 0.86)
    return (clamp(r * 255), clamp(g * 255), clamp(b * 255))


# ----------------------------------------------------------------------------- item silhouettes
# Each function returns {(x, y): tone}. Shapes stay inside 1..14 so a 1px outline fits in 16x16.


def _rows_to_tones(spans, tone_fn):
    tones = {}
    for y, (x0, x1) in spans.items():
        for x in range(x0, x1 + 1):
            tones[(x, y)] = tone_fn(x, y)
    return tones


def shape_gem():
    spans = {2: (5, 10), 3: (4, 11), 4: (3, 12), 5: (2, 13), 6: (2, 13), 7: (3, 12), 8: (4, 11), 9: (5, 10), 10: (5, 10), 11: (6, 9), 12: (7, 8), 13: (7, 8)}

    def tone(x, y):
        if y <= 3:
            return "light"
        if y == 6:
            return "light" if x <= 7 else "base"
        return "base" if x <= 7 else "shadow"

    tones = _rows_to_tones(spans, tone)
    tones[(5, 3)] = tones[(4, 4)] = "white"
    return tones


def shape_ingot():
    tones = {}
    for y, (x0, x1) in {4: (5, 14), 5: (4, 13), 6: (3, 12)}.items():
        for x in range(x0, x1 + 1):
            tones[(x, y)] = "light"
    for y in range(7, 12):
        for x in range(2, 12):
            tones[(x, y)] = "base"
        tones[(12, y)] = "shadow"
        tones[(13, y)] = "shadow"
    for x in range(6, 10):
        tones[(x, 5)] = "white"
    for x in range(3, 11):
        tones[(x, 11)] = "shadow"
    return tones


def shape_orb():
    tones = {}
    for y in range(1, 15):
        for x in range(1, 15):
            d = ((x - 7.5) ** 2 + (y - 7.5) ** 2) ** 0.5
            if d <= 6.3:
                hd = ((x - 5.2) ** 2 + (y - 5.2) ** 2) ** 0.5
                tones[(x, y)] = "light" if hd < 2.8 else ("base" if hd < 7.2 else "shadow")
    for pos in ((4, 4), (5, 4), (4, 5)):
        if pos in tones:
            tones[pos] = "white"
    return tones


def shape_potion():
    tones = {}
    for x in range(6, 10):
        tones[(x, 1)] = "corkdark"
        tones[(x, 2)] = "cork"
    for y in (3, 4):
        for x in range(6, 10):
            tones[(x, y)] = "glass"
    for y in range(5, 15):
        for x in range(1, 15):
            if ((x - 7.5) ** 2 + (y - 9.6) ** 2) ** 0.5 <= 5.1:
                if y <= 6:
                    tones[(x, y)] = "glass"
                else:
                    t = (x + y) / 30.0
                    tones[(x, y)] = "light" if t < 0.45 else ("base" if t < 0.68 else "shadow")
    tones[(5, 8)] = "white"
    tones[(5, 9)] = "light"
    return tones


def shape_sword():
    tones = {}
    for i in range(8):
        tones[(6 + i, 9 - i)] = "light"
        if i < 7:
            tones[(7 + i, 9 - i)] = "base"
    for i in range(5):
        tones[(3 + i, 8 + i)] = "metal"
        tones[(4 + i, 8 + i)] = "metaldark"
    for i in range(3):
        tones[(4 - i, 11 + i)] = "wood"
        tones[(5 - i, 11 + i)] = "wooddark"
    tones[(1, 14)] = "metal"
    tones[(2, 14)] = "metaldark"
    return tones


def shape_wand():
    tones = {}
    for i in range(8):
        tones[(3 + i, 12 - i)] = "wood"
        tones[(4 + i, 12 - i)] = "wooddark"
    for y in range(1, 7):
        for x in range(8, 14):
            d = ((x - 11.0) ** 2 + (y - 3.6) ** 2) ** 0.5
            if d <= 2.5:
                hd = ((x - 10.0) ** 2 + (y - 2.6) ** 2) ** 0.5
                tones[(x, y)] = "light" if hd < 1.6 else ("base" if hd < 3.2 else "shadow")
    tones[(10, 2)] = "white"
    return tones


ITEM_SHAPES = {"gem": shape_gem, "ingot": shape_ingot, "orb": shape_orb, "potion": shape_potion, "sword": shape_sword, "wand": shape_wand}


def render_item_grid(style, base, rng):
    pal = make_palette(base)
    tones = ITEM_SHAPES[style]()
    grid = [[TRANSPARENT] * GRID for _ in range(GRID)]
    for (x, y), tone in tones.items():
        color = pal[tone]
        if tone in ("base", "light", "shadow") and rng.random() < 0.10:
            color = mul(color, 0.93 if rng.random() < 0.5 else 1.07)
        grid[y][x] = (*color, 255)
    # 1px outline drawn outside the silhouette
    for y in range(GRID):
        for x in range(GRID):
            if (x, y) in tones:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + dx, y + dy) in tones:
                    grid[y][x] = (*pal["outline"], 255)
                    break
    return grid


# ----------------------------------------------------------------------------- block textures (opaque, 16x16)


def _opaque(rows):
    return [[(*px, 255) for px in row] for row in rows]


def block_stone(base, rng, jitter=0.10):
    rows = [[mul(base, 1 + rng.uniform(-jitter, jitter)) for _ in range(GRID)] for _ in range(GRID)]
    for _ in range(7):
        x, y = rng.randrange(GRID), rng.randrange(GRID)
        for dx, dy in ((0, 0), (1, 0), (0, 1)):
            rows[(y + dy) % GRID][(x + dx) % GRID] = mul(base, 0.78)
    for _ in range(6):
        x, y = rng.randrange(GRID), rng.randrange(GRID)
        rows[y][x] = mul(base, 1.16)
    return rows


def block_bricks(base, rng):
    mortar = mix((205, 205, 200), base, 0.22)
    tone_cache = {}
    rows = []
    for y in range(GRID):
        row = []
        r, yy = y // 4, y % 4
        for x in range(GRID):
            xs = x + (r % 2) * 4
            if yy == 3 or xs % 8 == 7:
                row.append(mul(mortar, 1 + rng.uniform(-0.03, 0.03)))
                continue
            key = (xs // 8, r)
            if key not in tone_cache:
                tone_cache[key] = rng.uniform(0.90, 1.10)
            color = mul(base, tone_cache[key] * (1 + rng.uniform(-0.05, 0.05)))
            if yy == 0:
                color = mix(color, (255, 255, 255), 0.10)
            row.append(color)
        rows.append(row)
    return rows


def block_planks(base, rng):
    rows = [[None] * GRID for _ in range(GRID)]
    for board in range(4):
        tone = rng.uniform(0.92, 1.08)
        joint = rng.randrange(2, 14)
        for yy in range(4):
            y = board * 4 + yy
            for x in range(GRID):
                if yy == 3:
                    rows[y][x] = mul(base, 0.55)
                elif x == joint:
                    rows[y][x] = mul(base, 0.62)
                else:
                    rows[y][x] = mul(base, tone * (1 + rng.uniform(-0.04, 0.04)))
        for _ in range(3):
            y = board * 4 + rng.randrange(3)
            x0, length = rng.randrange(GRID), rng.randrange(3, 6)
            for k in range(length):
                rows[y][(x0 + k) % GRID] = mul(base, tone * 0.86)
    return rows


def block_ore(base, rng):
    rows = block_stone((128, 128, 132), rng, jitter=0.08)
    pal = make_palette(base)
    for _ in range(4):
        cx, cy = rng.randrange(2, 13), rng.randrange(2, 13)
        cells = {(cx, cy)}
        for dx, dy in rng.sample([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)], 3):
            cells.add((cx + dx, cy + dy))
        for (x, y) in cells:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) not in cells and 0 <= nx < GRID and 0 <= ny < GRID:
                    rows[ny][nx] = mul((128, 128, 132), 0.62)
        for (x, y) in cells:
            rows[y][x] = pal["light"] if (x, y) == min(cells, key=lambda p: p[0] + p[1]) else (pal["shadow"] if (x, y) == max(cells, key=lambda p: p[0] + p[1]) else pal["base"])
    return rows


def block_metal(base, rng):
    rows = []
    for y in range(GRID):
        row = []
        for x in range(GRID):
            color = mul(base, 1 + rng.uniform(-0.03, 0.03))
            if y % 2 == 0 and rng.random() < 0.35:
                color = mul(color, 1.06)
            if x == 0 or y == 0:
                color = mix(color, (255, 255, 255), 0.30)
            elif x == GRID - 1 or y == GRID - 1:
                color = mul(color, 0.62)
            elif x == 1 or y == 1:
                color = mul(color, 0.90)
            row.append(color)
        rows.append(row)
    for cx, cy in ((3, 3), (12, 3), (3, 12), (12, 12)):
        rows[cy][cx] = mul(base, 0.50)
        rows[cy - 1][cx - 1] = mix(base, (255, 255, 255), 0.55)
    for x in range(4, 12):
        rows[8][x] = mul(base, 0.78)
    return rows


def block_crystal(base, rng):
    pal = make_palette(base)
    rows = []
    for y in range(GRID):
        row = []
        for x in range(GRID):
            t = (x + y) / 30.0
            color = mix(pal["light"], pal["shadow"], t)
            if (x - y) % 8 in (0, 1):
                color = mix(color, (255, 255, 255), 0.22)
            if (x + y) % 11 == 0:
                color = mul(color, 0.88)
            if x in (0, GRID - 1) or y in (0, GRID - 1):
                color = mul(color, 0.72)
            row.append(color)
        rows.append(row)
    for _ in range(3):
        rows[rng.randrange(2, 14)][rng.randrange(2, 14)] = (255, 255, 255)
    return rows


BLOCK_FUNCS = {"stone": block_stone, "bricks": block_bricks, "planks": block_planks, "ore": block_ore, "metal": block_metal, "crystal": block_crystal}


# ----------------------------------------------------------------------------- public API


def default_color(style):
    return {
        "stone": (128, 128, 132), "bricks": (168, 84, 66), "planks": (176, 134, 80), "ore": (222, 60, 96),
        "metal": (170, 176, 190), "crystal": (90, 200, 230), "gem": (216, 30, 91), "ingot": (214, 170, 60),
        "orb": (110, 90, 230), "potion": (80, 180, 90), "sword": (160, 200, 230), "wand": (230, 120, 220),
    }[style]


def metadata(kind, style, name):
    return {"Software": SOFTWARE_NOTE, "Title": f"{name} ({kind}/{style})", "Copyright": LICENSE_NOTE}


def generate(kind: str, style: str, color_hex: str | None = None, size: int = 16, seed: str = "") -> list:
    """Return RGBA pixel rows (list of rows of (r, g, b, a)) for the requested texture."""
    styles = ITEM_STYLES if kind == "item" else BLOCK_STYLES
    if style not in styles:
        raise SystemExit(f"Unknown {kind} style {style!r}. Choose one of: {', '.join(styles)}")
    if size < 16 or size > 128 or size & (size - 1):
        raise SystemExit("--size must be a power of two between 16 and 128 (16, 32, 64, 128).")
    base = hex_to_rgb(color_hex) if color_hex else default_color(style)
    rng = random.Random(seed_to_int(kind, style, base, seed))
    if kind == "item":
        grid = render_item_grid(style, base, rng)
    else:
        grid = _opaque(BLOCK_FUNCS[style](base, rng))
    return upscale(grid, size // GRID)


def make_pack_icon(seed: str, size: int = 256) -> list:
    """Original pack icon: gradient background with a shaded orb, derived from the seed."""
    base = color_from_seed(seed)
    top, bottom = mul(base, 0.55), mul(base, 0.18)
    rows = []
    for y in range(size):
        t = y / (size - 1)
        color = mix(top, bottom, t)
        rows.append([(*color, 255)] * size)
    rng = random.Random(seed_to_int(seed, "icon"))
    orb = render_item_grid("orb", base, rng)
    factor = size // GRID * 3 // 4
    orb_big = upscale(orb, max(1, factor))
    off = (size - len(orb_big)) // 2
    for y, row in enumerate(orb_big):
        for x, px in enumerate(row):
            if px[3]:
                rows[off + y][off + x] = px
    for i in range(size):  # thin frame
        for k in range(4):
            for pos in ((k, i), (size - 1 - k, i), (i, k), (i, size - 1 - k)):
                rows[pos[0]][pos[1]] = (*mix(base, (255, 255, 255), 0.35), 255)
    return rows
