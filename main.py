#!/usr/bin/env python3
"""THE WORLD TODAY - Tuesday 17 November 2026, the whole day on one page.

A make.fun entry for "Sum up 17 November's world news in one image".
This program draws a complete broadsheet front page - masthead, hero
story, illustrated panels, a dotted world map and an In Brief column -
using nothing but the Python standard library, and writes it as a PNG
to /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png).

Every letter is drawn from the stroke typeface defined below, every
picture is drawn from polygons and circles in this file, and the output
is byte-for-byte deterministic: no clocks, no randomness, no network.
"""

import math
import os
import struct
import zlib

# ---------------------------------------------------------------- canvas

SS = 2                      # supersampling factor (anti-aliasing)
W = 1024 * SS               # internal canvas, 2048 x 2048
H = 1024 * SS

PAPER = (246, 240, 224)     # warm newsprint cream
PAPER_LT = (251, 247, 236)  # lighter panel cream
INK = (23, 33, 55)          # deep navy ink
INK_SOFT = (52, 66, 88)
SLATE = (84, 98, 118)       # secondary text
RED = (176, 52, 40)         # editorial accent red
OCHRE = (208, 148, 52)
TEAL = (34, 92, 84)
SEA = (88, 138, 132)
SKY = (238, 229, 203)
RULE = (178, 166, 138)      # hairline colour
NAVY = (28, 44, 70)         # map panel background
CREAM = (240, 234, 214)     # text on navy
SMOKE = (148, 148, 142)

BUF = bytearray(W * H * 3)


def _set(px, py, rgb):
    i = (py * W + px) * 3
    BUF[i] = rgb[0]
    BUF[i + 1] = rgb[1]
    BUF[i + 2] = rgb[2]


def _blend(px, py, rgb, a):
    """Alpha-blend rgb over the buffer at (px, py); a in 0..255."""
    i = (py * W + px) * 3
    ia = 255 - a
    BUF[i] = (BUF[i] * ia + rgb[0] * a) // 255
    BUF[i + 1] = (BUF[i + 1] * ia + rgb[1] * a) // 255
    BUF[i + 2] = (BUF[i + 2] * ia + rgb[2] * a) // 255


def fill_all(rgb):
    row = bytes(rgb) * W
    for y in range(H):
        BUF[y * W * 3:(y + 1) * W * 3] = row


def fill_rect(x, y, w, h, rgb):
    """Filled rectangle in 1024-space coordinates."""
    x0 = max(0, int(round(x * SS)))
    y0 = max(0, int(round(y * SS)))
    x1 = min(W, int(round((x + w) * SS)))
    y1 = min(H, int(round((y + h) * SS)))
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(rgb) * (x1 - x0)
    for py in range(y0, y1):
        i = (py * W + x0) * 3
        BUF[i:i + len(row)] = row


def fill_polygon(points, rgb):
    """Scanline polygon fill; points are (x, y) in 1024-space, y down."""
    pts = [(x * SS, y * SS) for (x, y) in points]
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for py in range(y0, y1 + 1):
        yc = py + 0.5
        xs = []
        for i in range(n):
            xa, ya = pts[i]
            xb, yb = pts[(i + 1) % n]
            if ya == yb:
                continue
            if (ya <= yc < yb) or (yb <= yc < ya):
                xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(round(xs[k])))
            xb = min(W - 1, int(round(xs[k + 1])))
            if xb < xa:
                continue
            i = (py * W + xa) * 3
            BUF[i:i + (xb - xa + 1) * 3] = bytes(rgb) * (xb - xa + 1)


def fill_ellipse(cx, cy, rx, ry, rgb, alpha=255):
    """Filled ellipse in 1024-space; alpha<255 blends (soft blotches)."""
    cx, cy, rx, ry = cx * SS, cy * SS, rx * SS, ry * SS
    x0 = max(0, int(cx - rx - 1))
    x1 = min(W - 1, int(cx + rx + 1))
    y0 = max(0, int(cy - ry - 1))
    y1 = min(H - 1, int(cy + ry + 1))
    for py in range(y0, y1 + 1):
        dy = (py + 0.5 - cy) / ry
        if abs(dy) >= 1.0:
            continue
        dx = rx * math.sqrt(1.0 - dy * dy)
        xa = max(x0, int(round(cx - dx)))
        xb = min(x1, int(round(cx + dx)))
        if alpha >= 255:
            i = (py * W + xa) * 3
            BUF[i:i + (xb - xa + 1) * 3] = bytes(rgb) * (xb - xa + 1)
        else:
            for px in range(xa, xb + 1):
                _blend(px, py, rgb, alpha)


def fill_circle(cx, cy, r, rgb, alpha=255):
    fill_ellipse(cx, cy, r, r, rgb, alpha)


def thick_line(xa, ya, xb, yb, width, rgb):
    """A line with round caps, drawn as a quad plus two end discs."""
    dx, dy = xb - xa, yb - ya
    length = math.hypot(dx, dy)
    if length == 0:
        fill_circle(xa, ya, width / 2, rgb)
        return
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    fill_polygon([(xa + nx, ya + ny), (xb + nx, yb + ny),
                  (xb - nx, yb - ny), (xa - nx, ya - ny)], rgb)
    fill_circle(xa, ya, width / 2, rgb)
    fill_circle(xb, yb, width / 2, rgb)


def polyline(points, width, rgb):
    for i in range(len(points) - 1):
        thick_line(points[i][0], points[i][1],
                   points[i + 1][0], points[i + 1][1], width, rgb)


def stroke_rect(x, y, w, h, width, rgb):
    polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)],
             width, rgb)


def downsample_png():
    """Box-downsample the SS canvas to 1024x1024 and encode as PNG."""
    ow, oh = 1024, 1024
    raw = bytearray()
    for oy in range(oh):
        raw.append(0)
        y0 = oy * SS
        for ox in range(ow):
            x0 = ox * SS
            r = g = b = 0
            for dy in range(SS):
                base = ((y0 + dy) * W + x0) * 3
                for dx in range(SS):
                    i = base + dx * 3
                    r += BUF[i]
                    g += BUF[i + 1]
                    b += BUF[i + 2]
            n = SS * SS
            raw += bytes((r // n, g // n, b // n))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", ow, oh, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
           + chunk(b"IEND", b""))
    return png


# ---------------------------------------------------------------- typeface
# A stroke typeface drawn by this program. Glyph space: cap height 100,
# x-height 64, descenders to -30, y grows UP from the baseline. Each glyph
# is (advance, [stroke polylines], [filled dots (cx, cy, r)]).

def _arc(cx, cy, rx, ry, a0, a1, n=14):
    """Points along an elliptical arc, angles in degrees, y up."""
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def _ell(cx, cy, rx, ry):
    return _arc(cx, cy, rx, ry, 0, 360, 26)


GLYPHS = {
    # ---------------------------------------------------------- capitals
    'A': (74, [[(2, 0), (37, 100), (72, 0)], [(15, 36), (59, 36)]], []),
    'B': (70, [[(10, 0), (10, 100)],
               [(10, 100), (36, 100)] + _arc(36, 77, 22, 23, 90, -90),
               [(10, 54), (38, 54)] + _arc(38, 27, 24, 27, 90, -90)], []),
    'C': (72, [_arc(38, 50, 34, 50, 52, 308)], []),
    'D': (74, [[(8, 0), (8, 100)],
               [(8, 100), (34, 100)] + _arc(34, 50, 32, 50, 90, -90)], []),
    'E': (62, [[(58, 100), (8, 100), (8, 0), (60, 0)],
               [(8, 52), (50, 52)]], []),
    'F': (58, [[(58, 100), (8, 100), (8, 0)], [(8, 52), (48, 52)]], []),
    'G': (76, [_arc(39, 50, 35, 50, 48, 312), [(45, 44), (74, 44), (74, 18)]], []),
    'H': (74, [[(8, 0), (8, 100)], [(66, 0), (66, 100)],
               [(8, 52), (66, 52)]], []),
    'I': (28, [[(14, 0), (14, 100)], [(4, 100), (24, 100)],
               [(4, 0), (24, 0)]], []),
    'J': (54, [[(50, 100), (50, 30)] + _arc(28, 30, 22, 30, 0, -160)], []),
    'K': (70, [[(8, 0), (8, 100)], [(64, 100), (14, 48)],
               [(26, 58), (66, 0)]], []),
    'L': (58, [[(8, 100), (8, 0), (58, 0)]], []),
    'M': (88, [[(6, 0), (6, 100), (44, 36), (82, 100), (82, 0)]], []),
    'N': (76, [[(8, 0), (8, 100), (68, 0), (68, 100)]], []),
    'O': (78, [_ell(39, 50, 35, 50)], []),
    'P': (66, [[(10, 0), (10, 100)],
               [(10, 100), (36, 100)] + _arc(36, 75, 22, 25, 90, -90)], []),
    'Q': (78, [_ell(39, 50, 35, 50), [(46, 24), (76, -4)]], []),
    'R': (68, [[(10, 0), (10, 100)],
               [(10, 100), (36, 100)] + _arc(36, 75, 22, 25, 90, -90),
               [(34, 50), (66, 0)]], []),
    'S': (66, [[(58, 86), (46, 98), (26, 99), (12, 88), (11, 72),
                (20, 60), (46, 46), (57, 34), (54, 16), (38, 3),
                (18, 3), (6, 14)]], []),
    'T': (66, [[(4, 100), (62, 100)], [(33, 100), (33, 0)]], []),
    'U': (74, [[(8, 100), (8, 36)] + _arc(37, 36, 29, 36, 180, 360)
               + [(66, 100)]], []),
    'V': (72, [[(2, 100), (36, 0), (70, 100)]], []),
    'W': (96, [[(2, 100), (18, 0), (48, 70), (78, 0), (94, 100)]], []),
    'X': (68, [[(6, 100), (62, 0)], [(62, 100), (6, 0)]], []),
    'Y': (68, [[(4, 100), (34, 52), (64, 100)], [(34, 52), (34, 0)]], []),
    'Z': (66, [[(6, 100), (60, 100), (6, 0), (62, 0)]], []),
    # ---------------------------------------------------------- lowercase
    'a': (56, [_ell(26, 30, 24, 30), [(50, 64), (50, 0)]], []),
    'b': (58, [[(8, 0), (8, 100)], _ell(32, 30, 24, 30)], []),
    'c': (52, [_arc(27, 32, 23, 32, 55, 305)], []),
    'd': (58, [_ell(26, 30, 24, 30), [(50, 100), (50, 0)]], []),
    'e': (54, [[(6, 36), (48, 36)],
               [(48, 38), (38, 58), (20, 63), (8, 51), (5, 34),
                (10, 15), (24, 4), (40, 6), (49, 16)]], []),
    'f': (34, [[(36, 92), (26, 101), (15, 97), (12, 84), (12, 0)],
               [(2, 64), (30, 64)]], []),
    'g': (58, [_ell(27, 34, 23, 30),
               [(50, 64), (50, -2), (42, -20), (26, -27), (12, -22),
                (8, -12)]], []),
    'h': (58, [[(8, 0), (8, 100)],
               [(8, 32), (14, 56), (28, 64), (42, 57), (48, 38),
                (48, 0)]], []),
    'i': (26, [[(13, 64), (13, 0)]], [(13, 86, 5)]),
    'j': (30, [[(21, 64), (21, -8), (14, -24), (2, -26), (-3, -15)]],
          [(21, 86, 5)]),
    'k': (54, [[(8, 100), (8, 0)], [(46, 64), (13, 29)],
               [(23, 40), (48, 0)]], []),
    'l': (26, [[(13, 100), (13, 0)]], []),
    'm': (84, [[(6, 64), (6, 0)],
               [(6, 34), (12, 57), (24, 64), (34, 57), (38, 36),
                (38, 0)],
               [(38, 34), (44, 57), (56, 64), (66, 57), (70, 36),
                (70, 0)]], []),
    'n': (58, [[(8, 64), (8, 0)],
               [(8, 34), (14, 57), (28, 64), (42, 57), (48, 38),
                (48, 0)]], []),
    'o': (56, [_ell(28, 32, 24, 32)], []),
    'p': (58, [[(8, 64), (8, -30)], _ell(32, 32, 24, 32)], []),
    'q': (58, [_ell(26, 32, 24, 32), [(50, 64), (50, -30), (57, -36)]], []),
    'r': (38, [[(8, 64), (8, 0)],
               [(8, 38), (15, 58), (27, 64), (37, 59)]], []),
    's': (50, [[(43, 53), (33, 63), (17, 63), (8, 53), (9, 41),
                (19, 32), (35, 25), (42, 15), (35, 4), (19, 2),
                (8, 9)]], []),
    't': (34, [[(18, 88), (18, 13), (24, 3), (34, 3)],
               [(4, 64), (32, 64)]], []),
    'u': (58, [[(8, 64), (8, 28), (14, 8), (27, 2), (41, 7),
                (48, 22)], [(48, 64), (48, 0)]], []),
    'v': (52, [[(2, 64), (26, 0), (50, 64)]], []),
    'w': (74, [[(2, 64), (12, 0), (37, 46), (62, 0), (72, 64)]], []),
    'x': (50, [[(4, 64), (46, 0)], [(46, 64), (4, 0)]], []),
    'y': (54, [[(2, 64), (27, 16)], [(52, 64), (27, 16), (27, -12),
               (20, -26), (8, -27), (2, -19)]], []),
    'z': (50, [[(4, 64), (46, 64), (4, 0), (48, 0)]], []),
    # ---------------------------------------------------------- digits
    '0': (68, [_ell(34, 50, 28, 50)], []),
    '1': (46, [[(10, 74), (27, 98), (27, 0)], [(9, 0), (45, 0)]], []),
    '2': (62, [[(12, 82), (24, 97), (40, 96), (50, 80), (42, 58),
                (16, 26), (8, 6), (8, 0), (56, 0)]], []),
    '3': (62, [[(12, 86), (26, 99), (42, 96), (48, 82), (38, 64),
                (22, 54), (38, 48), (50, 32), (44, 12), (26, 2),
                (10, 8), (6, 20)]], []),
    '4': (66, [[(44, 100), (12, 28), (62, 28)], [(44, 100), (44, 0)]], []),
    '5': (60, [[(52, 100), (14, 100), (12, 58), (24, 67), (40, 65),
                (50, 49), (44, 18), (28, 4), (12, 8), (6, 20)]], []),
    '6': (62, [[(48, 90), (32, 100), (18, 88), (11, 60), (9, 34)],
               _ell(31, 27, 22, 27)], []),
    '7': (60, [[(6, 100), (54, 100), (26, 0)]], []),
    '8': (62, [_ell(31, 74, 19, 25), _ell(31, 28, 24, 28)], []),
    '9': (62, [_ell(31, 72, 22, 27),
               [(53, 68), (51, 38), (42, 13), (26, 3), (11, 9)]], []),
    # ---------------------------------------------------------- punctuation
    '.': (22, [], [(11, 5, 5)]),
    ',': (22, [[(15, 2), (10, -13)]], [(11, 7, 5)]),
    ':': (22, [], [(11, 10, 5), (11, 46, 5)]),
    ';': (22, [[(15, 2), (10, -13)]], [(11, 48, 5), (11, 7, 5)]),
    "'": (16, [[(8, 100), (6, 79)]], []),
    '-': (36, [[(6, 40), (30, 40)]], []),
    '!': (22, [[(11, 100), (11, 27)]], [(11, 6, 5)]),
    '?': (56, [[(10, 84), (24, 99), (40, 94), (44, 76), (34, 58),
                (26, 48), (26, 34)]], [(26, 6, 5)]),
    '(': (30, [_arc(24, 50, 17, 54, 105, 255)], []),
    ')': (30, [_arc(6, 50, 17, 54, -75, 75)], []),
    '/': (36, [[(28, 100), (8, 0)]], []),
    '%': (86, [_ell(19, 78, 13, 16), [(67, 100), (19, 0)],
               _ell(67, 22, 13, 16)], []),
    '$': (60, [[(52, 84), (38, 97), (20, 96), (11, 84), (13, 68),
                (24, 57), (42, 45), (49, 32), (42, 14), (24, 4),
                (10, 9)], [(30, 108), (30, -8)]], []),
    '+': (52, [[(26, 14), (26, 66)], [(6, 40), (46, 40)]], []),
    '°': (30, [_ell(15, 86, 10, 10)], []),
    '·': (20, [], [(10, 34, 4)]),
    '—': (62, [[(4, 40), (58, 40)]], []),
    '–': (46, [[(4, 40), (42, 40)]], []),
    '&': (66, [[(46, 90), (32, 100), (17, 91), (19, 74), (30, 58),
                (50, 34), (54, 17), (42, 4), (24, 6), (12, 18),
                (16, 36), (30, 48)]], []),
    '*': (40, [[(20, 30), (20, 70)], [(8, 40), (32, 60)],
               [(32, 40), (8, 60)]], []),
}

SPACE_ADV = 30

# ---------------------------------------------------------- text engine
# Glyph masks are rasterised once per (char, size, weight) and cached;
# a mask is a list of rows of coverage values 0..255.

_mask_cache = {}


def _glyph_mask(ch, size_px, bold):
    key = (ch, size_px, bold)
    m = _mask_cache.get(key)
    if m is not None:
        return m
    adv, strokes, dots = GLYPHS[ch]
    scale = size_px / 100.0            # glyph units -> output px (1024 sp.)
    w_units = 15.0 if bold else 10.5   # stroke width in glyph units
    hw = w_units / 2.0
    gw = int(math.ceil((adv + w_units) * scale * SS))
    gh = int(math.ceil(140 * scale * SS))
    base = 108.0                       # glyph y of the baseline inside mask
    mask = [[0] * gw for _ in range(gh)]

    def stamp(cx, cy, r):
        x0 = max(0, int((cx - r) * scale * SS))
        x1 = min(gw - 1, int((cx + r) * scale * SS))
        y0 = max(0, int((base - cy - r) * scale * SS))
        y1 = min(gh - 1, int((base - cy + r) * scale * SS))
        for py in range(y0, y1 + 1):
            gy = base - (py + 0.5) / (scale * SS)
            for px in range(x0, x1 + 1):
                gx = (px + 0.5) / (scale * SS)
                d = math.hypot(gx - cx, gy - cy)
                cov = r + 0.75 / (scale * SS) - d
                if cov > 0:
                    v = 255 if cov >= 1.5 / (scale * SS) else int(255 * cov * (scale * SS) / 1.5)
                    if v > mask[py][px]:
                        mask[py][px] = v

    for (cx, cy, r) in dots:
        stamp(cx, cy, r + hw * 0.55)
    for path in strokes:
        for i in range(len(path) - 1):
            ax, ay = path[i]
            bx, by = path[i + 1]
            x0 = max(0, int((min(ax, bx) - hw - 1) * scale * SS))
            x1 = min(gw - 1, int((max(ax, bx) + hw + 1) * scale * SS))
            y0 = max(0, int((base - max(ay, by) - hw - 1) * scale * SS))
            y1 = min(gh - 1, int((base - min(ay, by) + hw + 1) * scale * SS))
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            for py in range(y0, y1 + 1):
                gy = base - (py + 0.5) / (scale * SS)
                row = mask[py]
                for px in range(x0, x1 + 1):
                    gx = (px + 0.5) / (scale * SS)
                    if seg2 == 0:
                        d = math.hypot(gx - ax, gy - ay)
                    else:
                        t = ((gx - ax) * dx + (gy - ay) * dy) / seg2
                        t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                        d = math.hypot(gx - (ax + t * dx), gy - (ay + t * dy))
                    cov = hw + 0.75 / (scale * SS) - d
                    if cov > 0:
                        v = 255 if cov >= 1.5 / (scale * SS) else int(255 * cov * (scale * SS) / 1.5)
                        if v > row[px]:
                            row[px] = v
    m = (mask, adv * scale, base * scale)
    _mask_cache[key] = m
    return m


def text_width(text, size, bold=False, tracking=0.0):
    """Width of a string in 1024-space px. size = cap height in px."""
    total = 0.0
    for ch in text:
        if ch == ' ':
            total += SPACE_ADV * size / 100.0
        elif ch in GLYPHS:
            total += GLYPHS[ch][0] * size / 100.0
        else:
            total += SPACE_ADV * size / 100.0
        total += tracking
    return total - (tracking if text else 0.0)


def draw_text(x, y_base, text, size, rgb, bold=False, tracking=0.0):
    """Draw text with baseline at y_base (1024-space, y down)."""
    cx = x
    for ch in text:
        if ch == ' ':
            cx += SPACE_ADV * size / 100.0 + tracking
            continue
        if ch not in GLYPHS:
            cx += SPACE_ADV * size / 100.0 + tracking
            continue
        mask, adv_px, base_px = _glyph_mask(ch, size, bold)
        ox = int(round(cx * SS))
        oy = int(round(y_base * SS - base_px * SS))
        for r, row in enumerate(mask):
            py = oy + r
            if py < 0 or py >= H:
                continue
            base_i = py * W * 3
            for c, v in enumerate(row):
                if v:
                    px = ox + c
                    if 0 <= px < W:
                        _blend(px, py, rgb, v)
        cx += adv_px + tracking
    return cx


def draw_text_centered(cx, y_base, text, size, rgb, bold=False, tracking=0.0):
    w = text_width(text, size, bold, tracking)
    return draw_text(cx - w / 2, y_base, text, size, rgb, bold, tracking)


def wrap_text(text, size, max_width, bold=False, tracking=0.0):
    """Greedy word wrap; returns a list of lines that fit max_width."""
    lines = []
    cur = ''
    for word in text.split(' '):
        trial = word if not cur else cur + ' ' + word
        if text_width(trial, size, bold, tracking) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_paragraph(x, y_base, text, size, line_h, max_width, rgb,
                   bold=False, tracking=0.0):
    """Wrapped paragraph; returns the baseline y of the last line."""
    y = y_base
    for line in wrap_text(text, size, max_width, bold, tracking):
        draw_text(x, y, line, size, rgb, bold, tracking)
        y += line_h
    return y - line_h


# ---------------------------------------------------------------- world map
# A dotted world map as land spans on a 72 x 24 grid (5 degrees a cell).
# Each span is (row, first col, last col).

MAP_SPANS = [
    # North America
    (1, 3, 8), (1, 10, 20), (1, 25, 29),
    (2, 2, 9), (2, 10, 16), (2, 19, 23), (2, 25, 28),
    (3, 3, 9), (3, 11, 16), (3, 19, 22), (3, 26, 27), (3, 33, 34),
    (4, 5, 10), (4, 12, 21),
    (5, 12, 20), (6, 12, 20), (7, 12, 20),
    (8, 12, 19), (8, 20, 20), (9, 20, 20), (10, 20, 20),
    (9, 13, 17), (10, 14, 17), (11, 16, 18), (12, 18, 19),
    # South America
    (11, 22, 26), (12, 22, 27), (13, 23, 28), (14, 23, 28),
    (15, 23, 27), (16, 23, 26), (17, 23, 25), (18, 23, 25),
    (19, 23, 24), (20, 23, 24), (21, 23, 23),
    # Europe
    (2, 37, 41), (3, 37, 40), (4, 37, 39),
    (5, 34, 35), (6, 34, 35),
    (5, 35, 41), (6, 35, 42), (7, 36, 41), (8, 39, 39),
    (7, 34, 36), (8, 34, 36),
    # Africa
    (8, 35, 45), (9, 35, 46), (10, 36, 46), (11, 36, 45),
    (11, 46, 47), (12, 37, 44), (12, 46, 46), (13, 38, 44),
    (14, 39, 44), (15, 39, 43), (16, 40, 43), (16, 46, 46),
    (17, 40, 42), (17, 46, 46), (18, 40, 43), (19, 40, 42),
    # Middle East and Asia
    (1, 42, 66), (2, 42, 68), (3, 41, 67), (4, 40, 66),
    (5, 42, 60), (6, 43, 56),
    (7, 42, 46), (8, 42, 47), (9, 43, 47), (10, 44, 46),
    (8, 47, 50), (9, 47, 52), (10, 50, 52), (11, 50, 51), (12, 50, 51),
    (10, 54, 56), (11, 54, 56), (12, 54, 55), (13, 54, 54),
    (6, 57, 61), (7, 53, 61), (8, 53, 60), (9, 54, 59), (10, 57, 59),
    (7, 62, 63), (8, 61, 62),
    (11, 60, 60), (12, 60, 60),
    (13, 56, 58), (13, 60, 63), (14, 61, 64),
    # Australia and New Zealand
    (15, 59, 65), (16, 58, 65), (17, 59, 64), (18, 60, 63),
    (20, 69, 70), (21, 70, 70),
]

# (number, col, row, number side) - the day's datelines
MAP_MARKERS = [
    (1, 42, 5, -1),   # Kyiv
    (2, 42, 6, 1),    # Crimea
    (3, 40, 3, -1),   # Tallinn
    (4, 47, 9, 1),    # Hormuz
    (5, 58, 10, -1),  # Shenzhen
    (6, 60, 11, 1),   # Manila
    (7, 20, 9, 1),    # Cape Canaveral
]


def draw_map_panel(x, y, w, h):
    fill_rect(x, y, w, h, NAVY)
    stroke_rect(x + 3, y + 3, w - 6, h - 6, 0.8, CREAM)
    draw_text(x + 14, y + 24, "WHERE IT HAPPENED", 11, CREAM, bold=True,
              tracking=1.6)
    gx, gy = x + 12, y + 34
    gw, gh = w - 24, h - 84
    cw, ch = gw / 72.0, gh / 24.0
    land = set()
    for (r, c0, c1) in MAP_SPANS:
        for c in range(c0, c1 + 1):
            land.add((r, c))
    for (r, c) in land:
        fill_circle(gx + (c + 0.5) * cw, gy + (r + 0.5) * ch,
                    min(cw, ch) * 0.30, CREAM)
    for (num, c, r, side) in MAP_MARKERS:
        mx, my = gx + (c + 0.5) * cw, gy + (r + 0.5) * ch
        fill_circle(mx, my, 4.1, PAPER_LT)
        fill_circle(mx, my, 3.1, RED)
        nx = mx + 5.5 if side > 0 else mx - 11.5
        draw_text(nx, my + 3.4, str(num), 9.5, CREAM, bold=True)
    draw_text(x + 14, y + h - 26, "1 KYIV   2 CRIMEA   3 TALLINN   4 HORMUZ",
              9.5, CREAM, bold=True, tracking=0.6)
    draw_text(x + 14, y + h - 11, "5 SHENZHEN   6 MANILA   7 CAPE CANAVERAL",
              9.5, CREAM, bold=True, tracking=0.6)


# ---------------------------------------------------------------- pictures

def draw_bridge_panel(x, y, w, h):
    fill_rect(x, y, w, h, SKY)
    fill_circle(x + w - 74, y + 34, 17, OCHRE)                    # low sun
    sea_y = y + h * 0.62
    fill_rect(x, sea_y, w, y + h - sea_y, SEA)                    # the strait
    for i in range(9):                                            # wave ticks
        wx = x + 18 + i * (w - 40) / 8.0
        thick_line(wx, sea_y + 12 + (i % 3) * 9, wx + 13,
                   sea_y + 12 + (i % 3) * 9, 1.6, PAPER_LT)
    deck_y = y + h * 0.52
    bx = x + w * 0.60                                             # the break
    # standing towers and cables, left of the break
    for tx in (x + w * 0.20, x + w * 0.44):
        fill_rect(tx - 3, deck_y - 40, 6, 40 + (sea_y - deck_y), INK)
        polyline([(tx, deck_y - 40), (tx - 52, deck_y)], 1.6, INK_SOFT)
        polyline([(tx, deck_y - 40), (tx + 52, deck_y)], 1.6, INK_SOFT)
    fill_rect(x + 8, deck_y - 3, bx - x - 8, 6, INK)              # intact deck
    # fallen span, tipped into the water
    ang = math.radians(24)
    ex = bx + 74 * math.cos(ang)
    ey = deck_y + 74 * math.sin(ang)
    fill_polygon([(bx, deck_y - 3), (ex, ey - 3), (ex, ey + 4),
                  (bx, deck_y + 4)], INK)
    fill_ellipse(ex - 8, sea_y + 3, 8, 3.2, PAPER_LT)             # foam
    fill_ellipse(ex + 7, sea_y + 4, 5.5, 2.4, PAPER_LT)
    # burst at the break
    for k in range(8):
        a = math.radians(k * 45 + 12)
        r1 = 13 if k % 2 == 0 else 6
        thick_line(bx, deck_y - 4, bx + r1 * math.cos(a),
                   deck_y - 4 - r1 * math.sin(a), 2.6,
                   RED if k % 2 == 0 else OCHRE)
    # smoke plume
    for (sx, sy, sr, al) in [(6, -34, 13, 150), (22, -46, 17, 130),
                             (42, -54, 21, 105), (66, -60, 25, 80)]:
        fill_circle(bx + sx, deck_y + sy, sr, SMOKE, alpha=al)
    fill_circle(bx + 13, deck_y - 38, 9, (118, 118, 112), alpha=170)
    # far shore: a low headland on the horizon at right
    fill_polygon([(x + w - 128, sea_y + 3), (x + w - 52, sea_y - 9),
                  (x + w - 8, sea_y - 15), (x + w, sea_y - 15),
                  (x + w, sea_y + 3)], INK)
    # two gulls
    for (gx2, gy2) in [(x + 66, y + 26), (x + 96, y + 18)]:
        polyline([(gx2 - 7, gy2), (gx2 - 3.5, gy2 - 3.5), (gx2, gy2),
                  (gx2 + 3.5, gy2 - 3.5), (gx2 + 7, gy2)], 1.5, INK_SOFT)


def draw_hormuz_strip(x, y, w, h):
    fill_rect(x, y, w, h, SKY)
    fill_rect(x, y + h * 0.58, w, h * 0.42, SEA)
    # distant carrier, left
    cy = y + h * 0.52
    fill_polygon([(x + 8, cy), (x + 92, cy), (x + 84, cy + 7),
                  (x + 16, cy + 7)], SLATE)
    fill_rect(x + 62, cy - 8, 10, 8, SLATE)
    # the tanker
    tx, tw = x + w * 0.36, w * 0.56
    hy = y + h * 0.50
    fill_polygon([(tx, hy), (tx + tw, hy), (tx + tw - 16, hy + 13),
                  (tx + 12, hy + 13)], INK)
    fill_rect(tx + 8, hy - 6, tw - 20, 6, INK)
    for i, col in enumerate((RED, OCHRE, TEAL)):
        fill_rect(tx + 30 + i * 34, hy - 17, 28, 11, col)
    fill_rect(tx + tw - 34, hy - 22, 16, 22, PAPER_LT)            # stern castle
    fill_rect(tx + tw - 30, hy - 19, 8, 5, INK)
    # flames at the stern
    for (fx, fh, col) in [(6, 20, RED), (14, 26, OCHRE), (22, 16, RED)]:
        fill_polygon([(tx + tw - 2 + fx, hy - 4),
                      (tx + tw + 4 + fx, hy - 4 - fh),
                      (tx + tw + 10 + fx, hy - 4)], col)
    fill_circle(tx + tw + 16, hy - 34, 8, SMOKE, alpha=130)
    fill_circle(tx + tw + 26, hy - 40, 10, SMOKE, alpha=95)


def draw_summit_strip(x, y, w, h):
    fill_rect(x, y, w, h, PAPER_LT)
    base = y + h - 8
    rus_blue = (66, 104, 168)
    for i, fx in enumerate((x + w * 0.20, x + w * 0.50, x + w * 0.80)):
        fill_rect(fx - 1, y + 6, 2, base - y - 6, INK)             # pole
        fw, fh = 47, 27
        if i == 0:                                                # Stars and Stripes
            fill_rect(fx + 1, y + 6, fw, fh, PAPER)
            for s in range(3):
                fill_rect(fx + 1, y + 10 + s * 8, fw, 4, RED)
            fill_rect(fx + 1, y + 6, 20, 13, NAVY)
        elif i == 1:                                              # China
            fill_rect(fx + 1, y + 6, fw, fh, RED)
            fill_circle(fx + 11, y + 14, 4, OCHRE)
            fill_circle(fx + 20, y + 10, 2, OCHRE)
            fill_circle(fx + 20, y + 18, 2, OCHRE)
        else:                                                     # Russia
            fill_rect(fx + 1, y + 6, fw, fh // 3, PAPER)
            fill_rect(fx + 1, y + 6 + fh // 3, fw, fh // 3, rus_blue)
            fill_rect(fx + 1, y + 6 + 2 * (fh // 3), fw, fh - 2 * (fh // 3), RED)
    # the table and three seats
    fill_rect(x + w * 0.10, base - 6, w * 0.80, 4, INK)
    for fx in (x + w * 0.20 + 23, x + w * 0.50 + 23, x + w * 0.80 + 23):
        fill_circle(fx, base - 14, 5, INK_SOFT)
        fill_polygon([(fx - 8, base - 6), (fx + 8, base - 6),
                      (fx + 5, base - 12), (fx - 5, base - 12)], INK_SOFT)


# ---------------------------------------------------------------- brief icons

def icon_bank(x, y):
    fill_polygon([(x + 2, y + 10), (x + 17, y + 1), (x + 32, y + 10)], INK)
    for cx in (6, 15, 24):
        fill_rect(x + cx, y + 13, 4, 13, INK)
    fill_rect(x + 2, y + 28, 30, 3, INK)
    polyline([(x + 20, y + 4), (x + 16, y + 14), (x + 21, y + 22)], 2.2, RED)


def icon_chip(x, y):
    stroke_rect(x + 8, y + 8, 18, 18, 2.4, INK)
    fill_rect(x + 14, y + 14, 6, 6, RED)
    for d in (11, 17, 23):
        thick_line(x + d, y + 2, x + d, y + 8, 2.2, INK)
        thick_line(x + d, y + 26, x + d, y + 32, 2.2, INK)
        thick_line(x + 2, y + d, x + 8, y + d, 2.2, INK)
        thick_line(x + 26, y + d, x + 32, y + d, 2.2, INK)


def icon_rocket(x, y):
    fill_polygon([(x + 20, y + 1), (x + 27, y + 12), (x + 25, y + 24),
                  (x + 15, y + 24), (x + 13, y + 12)], INK)
    fill_circle(x + 20, y + 12, 3.4, PAPER)
    fill_polygon([(x + 16, y + 25), (x + 20, y + 33), (x + 24, y + 25)], RED)
    fill_polygon([(x + 18, y + 25), (x + 20, y + 30), (x + 22, y + 25)], OCHRE)
    fill_rect(x + 3, y + 5, 5, 5, SLATE)
    fill_rect(x + 24, y + 3, 5, 5, SLATE)


def icon_pentagon(x, y):
    pts = [(x + 17, y + 2), (x + 32, y + 13), (x + 26, y + 30),
           (x + 8, y + 30), (x + 2, y + 13)]
    for i in range(5):
        thick_line(pts[i][0], pts[i][1], pts[(i + 1) % 5][0],
                   pts[(i + 1) % 5][1], 2.4, INK)
    draw_text_centered(x + 17, y + 24, "!", 15, RED, bold=True)


def icon_gate(x, y):
    fill_rect(x + 4, y + 6, 4, 26, INK)
    fill_polygon([(x + 8, y + 8), (x + 32, y + 15), (x + 32, y + 20),
                  (x + 8, y + 13)], PAPER_LT)
    for i in range(3):
        fill_polygon([(x + 11 + i * 7, y + 9 + i * 1.2),
                      (x + 15 + i * 7, y + 10 + i * 1.2),
                      (x + 15 + i * 7, y + 15 + i * 1.2),
                      (x + 11 + i * 7, y + 14 + i * 1.2)], RED)
    stroke_rect(x + 8, y + 8, 24, 12, 1.2, INK)


def icon_thermo(x, y):
    thick_line(x + 17, y + 3, x + 17, y + 22, 7, PAPER_LT)
    thick_line(x + 17, y + 3, x + 17, y + 22, 2.2, RED)
    fill_circle(x + 17, y + 25, 7, PAPER_LT)
    fill_circle(x + 17, y + 25, 5.4, RED)
    stroke_rect(x + 13, y + 1, 8, 24, 1.4, INK)
    for d in (8, 14, 20):
        thick_line(x + 23, y + d, x + 27, y + d, 1.4, INK)


# ---------------------------------------------------------------- the page

MX = 36.0                    # content margin
CW = 1024.0 - 2 * MX         # content width


def hrule(y, width, rgb=INK, x=MX, w=CW):
    fill_rect(x, y, w, width, rgb)


def compose():
    fill_all(PAPER)
    # faint paper mottling, fixed positions (deterministic)
    for (bx, by, br, al) in [(210, 300, 190, 16), (830, 180, 150, 13),
                             (520, 880, 230, 15), (120, 760, 130, 12),
                             (900, 620, 170, 12)]:
        fill_circle(bx, by, br, PAPER_LT, alpha=al)

    # frame: double rule border
    stroke_rect(10, 10, 1004, 1004, 2.4, INK)
    stroke_rect(17, 17, 990, 990, 0.9, INK)

    # top strip
    draw_text(MX, 48, "VOL. I — No. 17", 10.5, INK_SOFT, bold=True,
              tracking=1.2)
    draw_text_centered(512, 48, "ONE PAGE · THE WHOLE WORLD", 10.5,
                       INK_SOFT, bold=True, tracking=1.6)
    r = "LATE EDITION"
    draw_text(1024 - MX - text_width(r, 10.5, True, 1.2), 48, r, 10.5,
              INK_SOFT, bold=True, tracking=1.2)
    hrule(58, 1.1, RULE)

    # masthead
    draw_text_centered(512, 122, "THE WORLD TODAY", 64, INK, bold=True,
                       tracking=1.0)
    hrule(134, 3.4)
    hrule(141, 1.0)

    # dateline
    draw_text_centered(512, 163, "TUESDAY 17 NOVEMBER 2026", 13.5, INK,
                       bold=True, tracking=3.0)
    draw_text_centered(512, 181, "THE WHOLE DAY'S NEWS — ON A SINGLE PAGE",
                       9.5, SLATE, bold=True, tracking=1.8)
    hrule(190, 1.1, RULE)

    # ---- hero story
    draw_text_centered(512, 216, "UKRAINE WAR — ESCALATION", 12, RED,
                       bold=True, tracking=2.2)
    draw_text_centered(512, 262, "UKRAINE STRIKES THE KERCH BRIDGE;", 41,
                       INK, bold=True)
    draw_text_centered(512, 309, "RUSSIA ANSWERS OVER KYIV", 41, INK,
                       bold=True)
    draw_bridge_panel(MX, 326, 600, 148)
    draw_map_panel(648, 326, 340, 148)
    draw_text_centered(
        512, 492,
        "The Kerch Bridge, linking Russia with occupied Crimea, after the "
        "strike at dawn. Right: the day mapped.", 11, SLATE)
    deck = ("A span of the bridge came down in the morning attack. Hours "
            "later, Russian missiles hit bridges across the Dnipro in "
            "Kyiv, cutting power, water and heating across the capital.")
    lines = wrap_text(deck, 15.5, 880)
    for i, ln in enumerate(lines[:2]):
        draw_text_centered(512, 520 + i * 22, ln, 15.5, INK_SOFT)
    hrule(552, 1.1, RULE)

    # ---- middle band: two illustrated stories
    col2 = 524.0
    colw = 464.0
    thick_line(512, 562, 512, 748, 1.0, RULE)
    draw_text(MX, 572, "MIDDLE EAST — THE STRAIT OF HORMUZ", 10.5, RED,
              bold=True, tracking=1.4)
    draw_text(col2, 572, "DIPLOMACY — ASEAN AND APEC", 10.5, RED,
              bold=True, tracking=1.4)
    draw_text(MX, 600, "TANKER MINED IN HORMUZ;", 20.5, INK, bold=True)
    draw_text(MX, 625, "THIRD US CARRIER ARRIVES", 20.5, INK, bold=True)
    draw_text(col2, 600, "TRUMP IN MANILA — XI AND PUTIN", 20.5, INK,
              bold=True)
    draw_text(col2, 625, "TO MEET HIM IN SHENZHEN", 20.5, INK, bold=True)
    draw_hormuz_strip(MX, 636, colw, 48)
    draw_summit_strip(col2, 636, colw, 48)
    draw_paragraph(MX, 708,
                   "A tanker struck a mine near the strait and two ships "
                   "caught fire, as the carrier USS Theodore Roosevelt "
                   "reached the region.", 14, 17.5, colw, INK_SOFT)
    draw_paragraph(col2, 708,
                   "The president arrived for the ASEAN summit, and a "
                   "three-way meeting with Xi Jinping and Vladimir Putin "
                   "was confirmed for Thursday in Shenzhen, on the "
                   "sidelines of APEC.", 14, 17.5, colw, INK_SOFT)
    hrule(758, 1.1, RULE)

    # ---- in brief
    hdr = "IN BRIEF — THE REST OF THE DAY"
    hw = text_width(hdr, 13, True, 2.0)
    draw_text_centered(512, 786, hdr, 13, INK, bold=True, tracking=2.0)
    hrule(780, 1.0, RULE, x=MX, w=(1024 - hw) / 2 - MX - 14)
    hrule(780, 1.0, RULE, x=(1024 + hw) / 2 + 14,
          w=(1024 - hw) / 2 - MX - 14)

    briefs = [
        (icon_bank, "JPMORGAN BLAMES A SOFTWARE BUG FOR OUTAGE",
         "Monday's banking disruption was a software bug, the bank "
         "said — not a cyber attack."),
        (icon_chip, "NVIDIA'S FIRST EARNINGS OF THE POST-HUANG ERA",
         "The chipmaker reported its first results since founder "
         "Jensen Huang stepped aside."),
        (icon_rocket, "VULCAN ROCKET FAILS; 40 LEO SATELLITES LOST",
         "ULA's rocket broke up after launch, destroying Amazon's "
         "whole Leo internet payload."),
        (icon_pentagon, "PENTAGON FAILS ITS AUDIT FOR A NINTH YEAR",
         "Auditors again could not account for more than $4.8 "
         "trillion in assets."),
        (icon_gate, "ESTONIA TO SHUT RUSSIAN BORDER POSTS ON 1 DEC.",
         "Tallinn cited a suspected sabotage plot against a drone "
         "factory."),
        (icon_thermo, "1.5°C CLIMATE LIMIT WILL BE MISSED — CHATHAM HOUSE",
         "The think tank says the Paris ceiling is now beyond reach "
         "on current pledges."),
    ]
    col_x = [MX, 360.0, 684.0]
    for idx, (icon, head, body) in enumerate(briefs):
        bx = col_x[idx % 3]
        by = 812.0 if idx < 3 else 900.0
        icon(bx, by - 26)
        hl = wrap_text(head, 12, 262, bold=True)
        for i, ln in enumerate(hl[:2]):
            draw_text(bx + 42, by + i * 15, ln, 12, INK, bold=True)
        bl = wrap_text(body, 11.5, 300)
        for i, ln in enumerate(bl[:3]):
            draw_text(bx, by + 36 + i * 14, ln, 11.5, INK_SOFT)

    # footer
    hrule(972, 1.0, RULE)
    draw_text_centered(512, 992,
                       "Drawn and typeset entirely by software — no "
                       "photographs · THE WORLD TODAY · Tuesday "
                       "17 November 2026", 9.5, SLATE, tracking=0.6)


def main():
    compose()
    png = downsample_png()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "entry.png"), "wb") as f:
        f.write(png)


if __name__ == "__main__":
    main()
