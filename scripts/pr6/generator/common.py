"""Shared geometry / raster helpers for the 织问 stroke-reveal animation build.

Everything is derived from the user's original artwork only:
  * 01-原图/用户提供的开屏原图.jpg   (untouched visual truth)
  * 01-原图/当前透明字标.png         (alpha extracted from that JPEG by the project)

No glyph is re-typeset, re-designed or generated: the centre lines come from the
skeleton of the alpha mask, and the bitmap-reveal frames re-use the PNG's own
pixels.
"""
from __future__ import annotations

import heapq
import json
import math
import os
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image
from skimage.morphology import skeletonize

# The caller supplies the versioned source explicitly; never use a stale handoff.
PNG_SRC = os.environ["WORDMARK_PNG"]

# ---- project integration constants (from the handoff snapshot) -------------
DP_VIEWPORT = 108.0  # adaptive-icon foreground viewport used by the app today
DP_INSET = 16.25  # 16.25dp inset on all four sides
DP_CONTENT = DP_VIEWPORT - 2 * DP_INSET  # 75.5dp square that holds brand_mark
INK_DAY = "#30238A"
INK_NIGHT = "#D2CCFF"
BG_DAY = "#FAF5ED"
BG_NIGHT = "#171225"
TOTAL_MS = 1000

NB8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


# --------------------------------------------------------------------------- #
# artwork / masks
# --------------------------------------------------------------------------- #
@dataclass
class Artwork:
    rgba: np.ndarray  # HxWx4 uint8
    alpha: np.ndarray  # HxW uint8
    ink: np.ndarray  # HxW bool (alpha > 127)
    labels: np.ndarray  # HxW int32 connected components
    stats: np.ndarray  # N x 5 (x, y, w, h, area)
    n: int

    @property
    def shape(self):
        return self.ink.shape


def load_artwork() -> Artwork:
    im = Image.open(PNG_SRC).convert("RGBA")
    rgba = np.asarray(im).copy()
    alpha = rgba[..., 3]
    ink = alpha > 127
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)
    return Artwork(rgba, alpha, ink, labels, stats, n)


def component_mask(art: Artwork, comp: int) -> np.ndarray:
    return art.labels == comp


def skeleton_of(mask: np.ndarray):
    """Return (skeleton bool array, bbox (x0,y0)) for a single component mask."""
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sk = skeletonize(mask[y0:y1, x0:x1])
    return sk, (int(x0), int(y0))


# --------------------------------------------------------------------------- #
# skeleton graph + Dijkstra between waypoints
# --------------------------------------------------------------------------- #
def _snap(pts: np.ndarray, p) -> int:
    d = (pts[:, 0] - p[0]) ** 2 + (pts[:, 1] - p[1]) ** 2
    return int(np.argmin(d))


def shortest_path(sk: np.ndarray, origin, a, b):
    """Dijkstra over skeleton pixels from skeleton-space point a to b (y,x)."""
    pts = np.argwhere(sk)
    index = {(int(y), int(x)): i for i, (y, x) in enumerate(pts)}
    start = _snap(pts, a)
    goal = _snap(pts, b)
    dist = np.full(len(pts), np.inf)
    prev = np.full(len(pts), -1, dtype=np.int32)
    dist[start] = 0.0
    pq = [(0.0, start)]
    while pq:
        d, i = heapq.heappop(pq)
        if d > dist[i] + 1e-12:
            continue
        if i == goal:
            break
        y, x = pts[i]
        for dy, dx in NB8:
            j = index.get((y + dy, x + dx))
            if j is None:
                continue
            nd = d + (math.sqrt(2.0) if dy and dx else 1.0)
            if nd < dist[j] - 1e-12:
                dist[j] = nd
                prev[j] = i
                heapq.heappush(pq, (nd, j))
    if not np.isfinite(dist[goal]):
        raise RuntimeError("no skeleton path between the requested waypoints")
    path = []
    i = goal
    while i != -1:
        path.append((int(pts[i][1]), int(pts[i][0])))  # (x, y)
        i = int(prev[i])
    return path[::-1]


def path_through(sk, origin, waypoints):
    """Concatenate Dijkstra legs between consecutive waypoints (absolute px)."""
    x0, y0 = origin
    abs_w = [(int(x), int(y)) for x, y in waypoints]
    out = []
    for a, b in zip(abs_w, abs_w[1:]):
        leg = shortest_path(sk, origin, (a[1] - y0, a[0] - x0), (b[1] - y0, b[0] - x0))
        leg = [(x + x0, y + y0) for x, y in leg]
        if out:
            leg = leg[1:]
        out.extend(leg)
    return out


# --------------------------------------------------------------------------- #
# polyline utilities
# --------------------------------------------------------------------------- #
def rdp(points, eps):
    """Ramer-Douglas-Peucker on an (N,2) float array."""
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 3:
        return pts.tolist()
    keep = np.zeros(len(pts), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = pts[i], pts[j]
        ab = b - a
        L = np.hypot(*ab)
        seg = pts[i + 1 : j]
        if L == 0:
            d = np.hypot(*(seg - a).T)
        else:
            d = np.abs(ab[0] * (a[1] - seg[:, 1]) - ab[1] * (a[0] - seg[:, 0])) / L
        k = int(np.argmax(d))
        if d[k] > eps:
            keep[i + 1 + k] = True
            stack.append((i, i + 1 + k))
            stack.append((i + 1 + k, j))
    return pts[keep].tolist()


def resample(points, step):
    pts = np.asarray(points, dtype=np.float64)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    n = max(2, int(round(total / step)) + 1)
    ss = np.linspace(0.0, total, n)
    x = np.interp(ss, s, pts[:, 0])
    y = np.interp(ss, s, pts[:, 1])
    return np.stack([x, y], axis=1), total


def smooth_polyline(points, window=5, iterations=2, pin_ends=True):
    """Mild moving-average smoothing of a pixel-staircase centre line.

    The skeleton of a raster is pixel-quantised; feeding it straight into a
    Catmull-Rom fit produces sub-pixel wobble in the exported pathData.  Two
    passes with a 5-sample window (samples are ~3 px apart) remove that without
    measurably moving the centre line.
    """
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < window + 2:
        return pts
    k = np.ones(window) / window
    out = pts.copy()
    for _ in range(iterations):
        padded = np.vstack([out[:1].repeat(window // 2, axis=0), out,
                            out[-1:].repeat(window // 2, axis=0)])
        sm = np.stack([np.convolve(padded[:, i], k, mode="valid") for i in (0, 1)], axis=1)
        if pin_ends:
            sm[0], sm[-1] = out[0], out[-1]
        out = sm
    return out


def arclen(points):
    pts = np.asarray(points, dtype=np.float64)
    return float(np.hypot(*np.diff(pts, axis=0).T).sum())


def catmull_rom_to_bezier(anchors):
    """Uniform Catmull-Rom -> cubic Bézier segments through every anchor."""
    P = [np.asarray(p, dtype=np.float64) for p in anchors]
    if len(P) < 2:
        return None
    ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    segs = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        c1 = p1 + (p2 - p0) / 6.0
        c2 = p2 - (p3 - p1) / 6.0
        segs.append((p1, c1, c2, p2))
    return segs


def _fmt(v: float, nd=2):
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def bezier_path_data(segs, transform=None, nd=2):
    """SVG/vector-drawable pathData (M + C...) from Catmull-Rom segments."""
    if not segs:
        return ""
    pts = [segs[0][0]] + [s[3] for s in segs]
    if transform is not None:
        segs = [tuple(transform(p) for p in s) for s in segs]
    out = ["M" + ",".join(_fmt(v, nd) for v in segs[0][0])]
    for _, c1, c2, p in segs:
        out.append(
            "C"
            + ",".join(_fmt(v, nd) for v in (*c1, *c2, *p))
        )
    return "".join(out)


# --------------------------------------------------------------------------- #
# stroke ribbons (used for the bitmap mask reveal and for the AVD simulation)
# --------------------------------------------------------------------------- #
def capsule_mask(shape, points, width, supersample=2):
    """Union of round capsules along a polyline -> boolean mask (True = inked).

    `points` are in *index* coordinates (the same space as `np.argwhere(mask)`),
    so the continuous position of pixel (i, j) is (j + 0.5, i + 0.5).
    Rasterised from a distance test, so caps and joins are exactly round like
    `strokeLineCap=round` / `strokeLineJoin=round`.
    """
    h, w = shape
    r = width / 2.0
    ss = max(1, int(supersample))
    mask = np.zeros((h * ss, w * ss), dtype=bool)
    pts = np.asarray(points, dtype=np.float64) + 0.5
    pad = int(math.ceil(r)) + 2
    for a, b in zip(pts, pts[1:]):
        x0 = max(0, int(math.floor(min(a[0], b[0]) - pad)) * ss)
        x1 = min(w * ss, int(math.ceil(max(a[0], b[0]) + pad)) * ss)
        y0 = max(0, int(math.floor(min(a[1], b[1]) - pad)) * ss)
        y1 = min(h * ss, int(math.ceil(max(a[1], b[1]) + pad)) * ss)
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        cx = (xs + 0.5) / ss
        cy = (ys + 0.5) / ss
        ab = b - a
        L2 = float(ab @ ab)
        if L2 == 0:
            t = np.zeros_like(cx)
        else:
            t = np.clip(((cx - a[0]) * ab[0] + (cy - a[1]) * ab[1]) / L2, 0.0, 1.0)
        px = a[0] + t * ab[0]
        py = a[1] + t * ab[1]
        mask[y0:y1, x0:x1] |= ((cx - px) ** 2 + (cy - py) ** 2) <= r * r
    if ss > 1:
        cov = mask.reshape(h, ss, w, ss).mean(axis=(1, 3))
        return cov >= 0.5
    return mask


def reveal_field(shape, points, soft=2.0):
    """Per-pixel normalised progress along a stroke path.

    Value = arc-length position (0..1) of the nearest point on the centre line,
    which is what makes the reveal follow the stroke instead of sweeping the
    screen.  `soft` widens the interpolation so the pen tip gets 1-2 px of
    antialiasing instead of a staircase.
    """
    h, w = shape
    pts = np.asarray(points, dtype=np.float64) + 0.5
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = max(s[-1], 1e-9)
    dist = np.full((h, w), np.inf)
    param = np.zeros((h, w))
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        x0 = max(0, int(math.floor(min(a[0], b[0]) - soft)))
        x1 = min(w, int(math.ceil(max(a[0], b[0]) + soft)))
        y0 = max(0, int(math.floor(min(a[1], b[1]) - soft)))
        y1 = min(h, int(math.ceil(max(a[1], b[1]) + soft)))
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        xs = xs + 0.5
        ys = ys + 0.5
        ab = b - a
        L2 = float(ab @ ab)
        if L2 == 0:
            t = np.zeros_like(xs, dtype=np.float64)
        else:
            t = np.clip(((xs - a[0]) * ab[0] + (ys - a[1]) * ab[1]) / L2, 0.0, 1.0)
        px = a[0] + t * ab[0]
        py = a[1] + t * ab[1]
        d = np.hypot(xs - px, ys - py)
        m = d < dist[y0:y1, x0:x1]
        dist[y0:y1, x0:x1][m] = d[m]
        param[y0:y1, x0:x1][m] = (s[i] + t[m] * seg[i]) / total
    return param, dist


def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
