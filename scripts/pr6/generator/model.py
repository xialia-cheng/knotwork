"""Stroke model = centre lines + widths + timings + 2x raster fields.

Single source of truth for every renderer in this package:

  fields.npz   per stroke: bbox, distance to centre line (2x supersampled),
               arc-length parameter (2x), so a frame is a pure numpy threshold
  strokes.json the editable description (order / timing / pathData)

The bitmap and vector candidates share their timeline, but their rasterized
silhouettes differ; actual Android handoff fidelity requires device validation.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (  # noqa: E402
    DP_CONTENT,
    DP_INSET,
    DP_VIEWPORT,
    INK_DAY,
    INK_NIGHT,
    TOTAL_MS,
    arclen,
    bezier_path_data,
    catmull_rom_to_bezier,
    component_mask,
    load_artwork,
    path_through,
    rdp,
    resample,
    save_json,
    smooth_polyline,
    skeleton_of,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEF_DELIVER = os.path.normpath(os.path.join(_HERE, "..", ".."))
OUT = os.environ.get("DELIVER_DIR") or _DEF_DELIVER
WORK = os.environ.get("WORK_DIR") or os.path.join(_HERE, "cache")
SS = 2  # raster supersample for coverage / reveal antialiasing

STROKES = [
    dict(id="zi-01", order=1, comp=1, glyph="织", name="丝旁 · 撇折一",
         way=[[260, 444], [174, 594], [304, 554]],
         hint="top tip -> down-left -> turn -> up-right"),
    dict(id="zi-02", order=2, comp=1, glyph="织", name="丝旁 · 撇折二",
         way=[[245, 614], [214, 732], [318, 708]],
         hint="starts tucked under the previous stroke, then sweeps right"),
    dict(id="zi-03", order=3, comp=8, glyph="织", name="丝旁 · 短横",
         way=[[155, 845], [295, 798]], hint="short rising bar, lower left"),
    dict(id="zi-04", order=4, comp=7, glyph="织", name="丝旁 · 提",
         way=[[320, 864], [423, 733]], hint="rising stroke leading into 只"),
    dict(id="zhi-05", order=5, comp=3, glyph="织", name="只 · 口 竖",
         way=[[392, 481], [390, 643]], hint="left side of the 口"),
    dict(id="zhi-06", order=6, comp=3, glyph="织", name="只 · 口 横折",
         way=[[392, 481], [562, 478], [562, 643]], hint="top bar then right side"),
    dict(id="zhi-07", order=7, comp=3, glyph="织", name="只 · 口 底横",
         way=[[390, 643], [562, 643]], hint="closes the 口 along the bottom"),
    dict(id="zhi-08", order=8, comp=5, glyph="织", name="只 · 八",
         way=[[527, 735], [662, 857], [733, 556]], hint="one continuous V"),
    dict(id="wen-09", order=9, comp=2, glyph="问", name="问 · 点",
         way=[[754, 449], [805, 490]], hint="dot at the top left of 门"),
    dict(id="wen-10", order=10, comp=4, glyph="问", name="问 · 门",
         way=[[881, 469], [1050, 468], [1098, 620], [1098, 787], [968, 855]],
         hint="left tip -> top -> right side -> bottom hook"),
    dict(id="wen-11", order=11, comp=6, glyph="问", name="问 · 口 竖",
         way=[[840, 596], [839, 737]], hint="left side of the inner 口"),
    dict(id="wen-12", order=12, comp=6, glyph="问", name="问 · 口 横折",
         way=[[840, 596], [981, 596], [981, 737]], hint="top bar then right side"),
    dict(id="wen-13", order=13, comp=6, glyph="问", name="问 · 口 底横",
         way=[[839, 737], [981, 737]], hint="closes the inner 口"),
]

ANCHOR_EPS = float(os.environ.get("ANCHOR_EPS", "0.35"))
SMOOTH_WIN = int(os.environ.get("SMOOTH_WIN", "3"))
SMOOTH_IT = int(os.environ.get("SMOOTH_IT", "1"))
OVERLAP_MS = 18
FLOOR_MS = 62


def eval_catmull(segs, step=1.2):
    pts = []
    for i, (p0, c1, c2, p3) in enumerate(segs):
        n = max(4, int(np.hypot(*(p3 - p0)) / step) + 1)
        t = np.linspace(0.0, 1.0, n)[:, None]
        mt = 1 - t
        seg = (mt ** 3) * p0 + 3 * (mt ** 2) * t * c1 + 3 * mt * (t ** 2) * c2 + (t ** 3) * p3
        pts.append(seg if i == 0 else seg[1:])
    return np.vstack(pts)


def raster_fields(shape, points, ss=SS, pad=42.0):
    """Return (bbox, dist[ss], s[ss]) for one stroke centre line.

    dist = distance from a supersampled sample point to the polyline (continuous
    pixel coordinates, pixel centres at +0.5).
    s    = arc-length position of the nearest point on the polyline, in pixels.
    """
    h, w = shape
    pts = np.asarray(points, dtype=np.float64)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    x0 = max(0, int(math.floor(pts[:, 0].min() - pad)))
    x1 = min(w, int(math.ceil(pts[:, 0].max() + pad)) + 1)
    y0 = max(0, int(math.floor(pts[:, 1].min() - pad)))
    y1 = min(h, int(math.ceil(pts[:, 1].max() + pad)) + 1)
    sw, sh = (x1 - x0) * ss, (y1 - y0) * ss
    dist = np.full((sh, sw), np.inf, dtype=np.float32)
    param = np.zeros((sh, sw), dtype=np.float32)
    xs_grid = (np.arange(sw) + 0.5) / ss + x0
    ys_grid = (np.arange(sh) + 0.5) / ss + y0
    for i in range(len(pts) - 1):
        a, b = pts[i] + 0.5, pts[i + 1] + 0.5
        ab = b - a
        L2 = float(ab @ ab)
        # local window
        bx0 = max(0, int((min(a[0], b[0]) - pad - x0) * ss) - 1)
        bx1 = min(sw, int((max(a[0], b[0]) + pad - x0) * ss) + 2)
        by0 = max(0, int((min(a[1], b[1]) - pad - y0) * ss) - 1)
        by1 = min(sh, int((max(a[1], b[1]) + pad - y0) * ss) + 2)
        if bx1 <= bx0 or by1 <= by0:
            continue
        xs = xs_grid[bx0:bx1][None, :]
        ys = ys_grid[by0:by1][:, None]
        if L2 == 0:
            t = np.zeros((by1 - by0, bx1 - bx0))
        else:
            t = np.clip(((xs - a[0]) * ab[0] + (ys - a[1]) * ab[1]) / L2, 0.0, 1.0)
        px = a[0] + t * ab[0]
        py = a[1] + t * ab[1]
        d = np.hypot(xs - px, ys - py)
        sub = dist[by0:by1, bx0:bx1]
        m = d < sub
        sub[m] = d[m]
        param[by0:by1, bx0:bx1][m] = (cum[i] + t[m] * seg[i]).astype(np.float32)
    return (x0, y0, x1, y1), dist, param


def main():
    art = load_artwork()
    H, W = art.shape
    ink = art.ink
    comp_cache = {}

    def comp_skel(comp):
        if comp not in comp_cache:
            m = component_mask(art, comp)
            sk, org = skeleton_of(m)
            comp_cache[comp] = (sk, org, m)
        return comp_cache[comp]

    import cv2

    built = []
    for spec in STROKES:
        sk, org, m = comp_skel(spec["comp"])
        raw = path_through(sk, org, spec["way"])
        dense_raw, _ = resample(raw, 3.0)
        smoothed = smooth_polyline(dense_raw, window=SMOOTH_WIN, iterations=SMOOTH_IT)
        anchors = [tuple(p) for p in rdp(smoothed, ANCHOR_EPS)]
        for end in (tuple(raw[0]), tuple(raw[-1])):
            if all(math.dist(end, a) > 0.5 for a in anchors):
                anchors.insert(0 if end == tuple(raw[0]) else len(anchors), end)
        segs = catmull_rom_to_bezier(anchors)
        smooth = eval_catmull(segs, step=1.2)
        dt = cv2.distanceTransform(m.astype(np.uint8), cv2.DIST_L2, 5)
        radii = [float(dt[int(round(y)), int(round(x))]) for x, y in smooth]
        radii = [r for r in radii if r > 0]
        base_w = float(2.0 * np.median(radii)) if radii else 44.0
        bbox, dist, param = raster_fields((H, W), smooth)
        reach = base_w / 2.0 + 26.0
        sub = dist <= reach
        rows = np.nonzero(sub.any(axis=1))[0]
        cols = np.nonzero(sub.any(axis=0))[0]
        r0 = int(rows[0]) // SS * SS
        r1 = ((int(rows[-1]) + 1 + SS - 1) // SS) * SS
        c0 = int(cols[0]) // SS * SS
        c1 = ((int(cols[-1]) + 1 + SS - 1) // SS) * SS
        x0, y0, _, _ = bbox
        bbox = (x0 + c0 // SS, y0 + r0 // SS, x0 + c1 // SS, y0 + r1 // SS)
        dist = np.ascontiguousarray(dist[r0:r1, c0:c1])
        param = np.ascontiguousarray(param[r0:r1, c0:c1])
        L = float(param.max())
        built.append(dict(spec=spec, smooth=smooth, anchors=anchors, segs=segs,
                          L=L, bbox=bbox, dist=dist, param=param, comp_mask=m,
                          base_w=base_w))

    # ---- width fit ---------------------------------------------------------
    def coverage(i, width, ss=SS):
        x0, y0, x1, y1 = built[i]["bbox"]
        cov = built[i]["dist"] <= width / 2.0
        return (x0, y0, x1, y1), cov.reshape(y1 - y0, ss, x1 - x0, ss).mean(axis=(1, 3))

    def composite_widths(widths, shape=(H, W)):
        out = np.zeros(shape, dtype=np.float32)
        for i, w in enumerate(widths):
            bb, cov = coverage(i, w)
            x0, y0, x1, y1 = bb
            out[y0:y1, x0:x1] = np.maximum(out[y0:y1, x0:x1], cov)
        return out >= 0.5

    widths = [b["base_w"] for b in built]

    # coarse search of a global scale, then per-stroke refinement
    best = (1e18, 1.0)
    for f in np.arange(0.92, 1.121, 0.02):
        diff = int(np.count_nonzero(composite_widths([w * f for w in widths]) ^ ink))
        if diff < best[0]:
            best = (diff, float(f))
    widths = [w * best[1] for w in widths]
    print(f"[width] base scale {best[1]:.2f} diff {best[0]}")

    for i in range(len(widths)):
        cand = (None, widths[i])
        for f in np.arange(0.94, 1.061, 0.01):
            trial = list(widths)
            trial[i] = widths[i] * f
            comp = composite_widths(trial)
            # only judge the area this stroke can influence
            x0, y0, x1, y1 = built[i]["bbox"]
            pad = int(widths[i])
            sx0, sy0 = max(0, x0 - pad), max(0, y0 - pad)
            sx1, sy1 = min(W, x1 + pad), min(H, y1 + pad)
            diff = int(np.count_nonzero(comp[sy0:sy1, sx0:sx1] ^ ink[sy0:sy1, sx0:sx1]))
            if cand[0] is None or diff < cand[0]:
                cand = (diff, widths[i] * f)
        widths[i] = cand[1]

    final = composite_widths(widths)
    ink_px = int(np.count_nonzero(ink))
    both = int(np.count_nonzero(final & ink))
    union = int(np.count_nonzero(final | ink))
    print("[width] per-stroke px", [round(w, 1) for w in widths])
    print(f"[coverage] IoU={both/union:.5f} missing={int(np.count_nonzero(ink & ~final))} "
          f"extra={int(np.count_nonzero(final & ~ink))} ink={ink_px}")

    # ---- timings -----------------------------------------------------------
    lens = np.array([b["L"] for b in built])
    span = TOTAL_MS + OVERLAP_MS * (len(built) - 1)
    durs = np.maximum(FLOOR_MS, lens / lens.sum() * span)
    durs *= span / durs.sum()
    times, t = [], 0.0
    for d in durs:
        times.append((round(t), round(t + d)))
        t += d - OVERLAP_MS
    times[-1] = (times[-1][0], TOTAL_MS)

    # ---- serialise ---------------------------------------------------------
    from PIL import Image

    mask_dir = os.path.join(OUT, "01-源文件/masks")
    os.makedirs(mask_dir, exist_ok=True)
    strokes_json = []
    npz = {}
    for i, b in enumerate(built):
        spec = b["spec"]
        w = widths[i]
        bb, cov1 = coverage(i, w)
        x0, y0, x1, y1 = bb
        mask = np.zeros((H, W), dtype=np.uint8)
        mask[y0:y1, x0:x1] = (cov1 * 255).astype(np.uint8)
        own = (mask > 127) & (art.labels == spec["comp"])
        # normalised reveal field (0..255) limited to the stroke's own ink
        fld = np.zeros((H, W), dtype=np.uint8)
        pnorm = b["param"] / max(b["L"], 1e-6)
        pnorm = pnorm.reshape(y1 - y0, SS, x1 - x0, SS).mean(axis=(1, 3))
        fld[y0:y1, x0:x1] = (pnorm * 255.0).clip(0, 255).astype(np.uint8)
        fld = np.where(own, fld, 0)
        Image.fromarray(mask).save(os.path.join(mask_dir, f"{spec['id']}-mask.png"))
        Image.fromarray(fld).save(os.path.join(mask_dir, f"{spec['id']}-field.png"))
        alpha_cov = np.where(own, art.alpha, 0).astype(np.uint8)
        Image.fromarray(
            np.dstack([art.rgba[..., 0], art.rgba[..., 1], art.rgba[..., 2], alpha_cov])
        ).save(os.path.join(mask_dir, f"{spec['id']}-ink.png"))

        strokes_json.append(dict(
            id=spec["id"], order=spec["order"], glyph=spec["glyph"], name=spec["name"],
            hint=spec["hint"], component=int(spec["comp"]),
            startMs=int(times[i][0]), endMs=int(times[i][1]),
            durationMs=int(times[i][1] - times[i][0]),
            lengthPx=round(b["L"], 2),
            widthPx=round(float(w), 2),
            widthDp=round(float(w) * DP_CONTENT / 1254.0, 3),
            overlapsPrevious=bool(spec["id"] in ("zi-02", "zhi-06", "zhi-07", "wen-12", "wen-13")),
            pathPx=[[round(float(x), 2), round(float(y), 2)] for x, y in b["anchors"]],
            pathSmoothPx=[[round(float(x), 2), round(float(y), 2)] for x, y in b["smooth"]],
            pathDataPx=bezier_path_data(b["segs"]),
            pathDataDp=bezier_path_data(b["segs"], transform=lambda p: dp(p[0], p[1]), nd=3),
            mask=os.path.relpath(os.path.join(mask_dir, f"{spec['id']}-mask.png"), OUT),
            field=os.path.relpath(os.path.join(mask_dir, f"{spec['id']}-field.png"), OUT),
        ))
        key = spec["id"].replace("-", "_")
        npz[f"{key}_bbox"] = np.asarray(b["bbox"], dtype=np.int32)
        npz[f"{key}_dist"] = b["dist"]
        npz[f"{key}_param"] = b["param"]

    data = dict(
        brand="织问 / Knotwork",
        description="逐笔书写式揭示动画：全部几何由用户原图推导，未重新打字或重新设计。",
        sourceImage=dict(path="01-源文件/original/当前透明字标.png",
                         sha256="6f2e1f949796feab05b8f0d015dd64a52343db38b5bd1ba89c6b20bdd564f96b",
                         size=[1254, 1254],
                         note="项目从用户 JPEG 提取的 alpha 资源；字形处 RGB 未改动"),
        referenceJpeg=dict(path="01-源文件/original/用户提供的开屏原图.jpg",
                           sha256="26e338db469052cb18a0030aecd42054521ec329efa469e14056db85eef1d452",
                           size=[1254, 1254]),
        viewportPx=dict(width=1254, height=1254, contentBox=[129, 421, 1124, 888]),
        splashViewportDp=dict(viewport=DP_VIEWPORT, inset=DP_INSET, content=DP_CONTENT,
                              note="与现有 @drawable/brand_startup_foreground 的几何一致（108dp 视口 / 16.25dp inset）"),
        colors=dict(day=dict(ink=INK_DAY, background="#FAF5ED"),
                    night=dict(ink=INK_NIGHT, background="#171225")),
        animation=dict(totalDurationMs=TOTAL_MS,
                       easing="每笔沿弧长线性推进；书写节奏由每笔时长表体现",
                       overlapMs=OVERLAP_MS,
                       reveal="笔尖沿中心线前进，露出原图自身像素",
                       frameSamplesMs=[0, 250, 500, 750, 1000]),
        strokes=strokes_json,
        fidelity=dict(iou=round(both / union, 5),
                      missingPx=int(np.count_nonzero(ink & ~final)),
                      extraPx=int(np.count_nonzero(final & ~ink)),
                      note=("两种口径不要混用：本字段是布尔阈值口径（2× 超采样、覆盖率≥0.5，用于逐笔宽度拟合），"
                            "IoU 0.9502；07-验证与调研/metrics.json 的 vector 字段是抗锯齿渲染 + 0.5 阈值口径，"
                            "IoU 0.94978，**以 metrics.json 为准**；两者差异只来自边缘 1px 的判定。"),
                      metricsOfRecord="07-验证与调研/metrics.json"),
    )
    save_json(os.path.join(OUT, "01-源文件/strokes.json"), data)

    # centre-line SVG
    os.makedirs(os.path.join(OUT, "01-源文件/original"), exist_ok=True)
    colors = ["#e11d48", "#ea580c", "#ca8a04", "#16a34a", "#0891b2", "#2563eb", "#7c3aed",
              "#db2777", "#0d9488", "#65a30d", "#c026d3", "#0284c7", "#b45309"]
    svg = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           'width="1254" height="1254" viewBox="0 0 1254 1254">',
           '<rect width="1254" height="1254" fill="#FAF5ED"/>',
           '<image xlink:href="original/当前透明字标.png" x="0" y="0" width="1254" height="1254" opacity="0.16"/>']
    for i, s in enumerate(strokes_json):
        col = colors[i % len(colors)]
        d = s["pathDataPx"]
        svg.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{s["widthPx"]:.1f}" '
                   f'stroke-linecap="round" stroke-linejoin="round" opacity="0.5"/>')
        svg.append(f'<path d="{d}" fill="none" stroke="#111" stroke-width="1.6" stroke-dasharray="7 6"/>')
        mx, my = s["pathSmoothPx"][0]
        svg.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="10" fill="#111"/>')
        svg.append(f'<text x="{mx+14:.1f}" y="{my-10:.1f}" font-family="sans-serif" font-size="30" '
                   f'fill="#111" font-weight="bold">{s["order"]}</text>')
        ex, ey = s["pathSmoothPx"][-1]
        svg.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="6" fill="none" stroke="#111" stroke-width="2"/>')
    svg.append("</svg>")
    with open(os.path.join(OUT, "01-源文件/centerlines.svg"), "w", encoding="utf-8") as f:
        f.write("\n".join(svg))

    lines = ["order,id,glyph,name,startMs,endMs,durationMs,lengthPx,widthPx,widthDp"]
    for s in strokes_json:
        lines.append(f'{s["order"]},{s["id"]},{s["glyph"]},"{s["name"]}",{s["startMs"]},'
                     f'{s["endMs"]},{s["durationMs"]},{s["lengthPx"]},{s["widthPx"]},{s["widthDp"]}')
    with open(os.path.join(OUT, "01-源文件/strokes-timeline.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Preserve the float32 fields used by the reference renderer.
    os.makedirs(WORK, exist_ok=True)
    np.savez_compressed(os.path.join(WORK, "fields.npz"),
                        distScale=np.float32(1.0), paramScale=np.float32(1.0),
                        ids=np.array([b["spec"]["id"] for b in built]),
                        widths=np.array(widths), **npz)
    # Export masks and pixel times from the same float fields after saving metadata.
    from export_pixel_timeline import export
    from pathlib import Path

    export(Path(OUT) / "01-源文件" / "pixel-timeline")
    print("[ok]", os.path.join(OUT, "01-源文件/strokes.json"))
    for s in strokes_json:
        print(f'  {s["order"]:2d} {s["id"]:8s} {s["startMs"]:4d}-{s["endMs"]:4d}ms '
              f'len={s["lengthPx"]:7.1f} w={s["widthPx"]:5.1f}px {s["widthDp"]:.2f}dp')


def dp(x, y):
    s = DP_CONTENT / 1254.0
    return (DP_INSET + x * s, DP_INSET + y * s)


if __name__ == "__main__":
    main()
