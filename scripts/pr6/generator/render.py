"""Frame renderer for the 织问 stroke animation.

Two render modes share one geometry and one timeline:

  bitmap  – the project's own transparent wordmark PNG revealed stroke by stroke.
            At t = 100% the output is the untouched original artwork.
  vector  – a raster simulation of exactly what the AnimatedVectorDrawable
            (strokeWidth + trimPath) will draw, so the system-splash candidate can
            be inspected and diffed without a device.

Usage
  python3 render.py frames  --mode bitmap --theme light --out DIR --times 0,250,500,750,1000
  python3 render.py sequence --mode vector --theme light --out DIR --fps 60 --size 480
  python3 render.py diff    --mode vector --theme light --out DIR
  python3 render.py metrics            # fidelity numbers as JSON
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import INK_DAY, INK_NIGHT, BG_DAY, BG_NIGHT, load_artwork  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEF_DELIVER = os.path.normpath(os.path.join(_HERE, "..", ".."))
WORK = os.environ.get("WORK_DIR") or os.path.join(_HERE, "cache")
DELIVER = os.environ.get("DELIVER_DIR") or _DEF_DELIVER
SS = 2
EDGE_PX = 1.3  # antialias width of the pen tip, in px
EDGE_COV = 0.9  # antialias width of the stroke silhouette, in px

THEMES = {
    "light": dict(bg=BG_DAY, ink=INK_DAY),
    "dark": dict(bg=BG_NIGHT, ink=INK_NIGHT),
}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def load_fields(path):
    """读取场缓存；兼容 float32 与 uint16 量化两种存储。

    uint16 版把距离按 DIST_SCALE、弧长按 PARAM_SCALE 量化（见 model.py 的 CACHE_QUANT），
    体积约为 float32 的 1/4，用于随包分发；解出后仍是 float32，渲染/指标口径不变。
    """
    z = np.load(path, allow_pickle=False)
    dist_scale = float(z["distScale"]) if "distScale" in z.files else 1.0
    param_scale = float(z["paramScale"]) if "paramScale" in z.files else 1.0
    out = {}
    for k in z.files:
        if k in ("distScale", "paramScale"):
            continue
        a = z[k]
        if k.endswith("_dist"):
            out[k] = a.astype(np.float32) / dist_scale if a.dtype == np.uint16 else a.astype(np.float32)
        elif k.endswith("_param"):
            out[k] = a.astype(np.float32) / param_scale if a.dtype == np.uint16 else a.astype(np.float32)
        else:
            out[k] = a
    return out


class Model:
    def __init__(self):
        self.data = json.load(open(os.path.join(DELIVER, "01-源文件/strokes.json"), encoding="utf-8"))
        # 缓存优先用 WORK_DIR，其次用包内 tools/cache（随包提供，避免首次必须重跑 model.py）
        here = os.path.dirname(os.path.abspath(__file__))
        for cand in (os.path.join(WORK, "fields.npz"), os.path.join(here, "cache", "fields.npz")):
            if os.path.exists(cand):
                z = load_fields(cand)
                break
        else:
            raise SystemExit(
                "找不到 fields.npz：先运行 `python3 model.py`（或 `bash run_all.sh`）重建缓存"
            )
        self.strokes = []
        for s in self.data["strokes"]:
            key = s["id"].replace("-", "_")
            self.strokes.append(
                dict(meta=s, bbox=tuple(int(v) for v in z[f"{key}_bbox"]),
                     dist=z[f"{key}_dist"], param=z[f"{key}_param"],
                     L=float(s["lengthPx"]), width=float(s["widthPx"]))
            )
        self.total = float(self.data["animation"]["totalDurationMs"])
        self.pixel_time = None
        timeline = os.path.join(DELIVER, "01-源文件/pixel-timeline/pixel_timeline.png")
        if os.path.exists(timeline):
            from PIL import Image
            encoded = np.asarray(Image.open(timeline).convert("RGBA"))
            self.pixel_time = ((encoded[..., 0].astype(np.uint16) << 8) | encoded[..., 1], encoded[..., 2])

    def progress(self, t_ms):
        out = []
        for st in self.strokes:
            a, b = st["meta"]["startMs"], st["meta"]["endMs"]
            d = max(b - a, 1e-6)
            out.append(min(1.0, max(0.0, (t_ms - a) / d)))
        return out

    def reveal_alpha(self, t_ms, mode="vector"):
        """Return a 1x float alpha map (0..1) of the revealed ink."""
        if mode == "bitmap":
            if self.pixel_time is None:
                raise SystemExit("pixel_timeline.png missing: run export_pixel_timeline.py")
            timing, owner = self.pixel_time
            if t_ms <= 0:
                return np.zeros(timing.shape, dtype=np.float32)
            return ((owner > 0) & (timing <= t_ms)).astype(np.float32)
        progs = self.progress(t_ms)
        H = W = 1254
        alpha = np.zeros((H, W), dtype=np.float32)
        for st, p in zip(self.strokes, progs):
            x0, y0, x1, y1 = st["bbox"]
            h, w = (y1 - y0) * SS, (x1 - x0) * SS
            if h <= 0 or w <= 0:
                continue
            half = (st["width"] if mode == "vector" else st["width"] + 24.0) / 2.0
            # pen tip: front of the revealed arc length, soft by EDGE_PX.
            # p = 0 -> 0 everywhere (no ghost ink at the pen-down point),
            # p = 1 -> front clears the round end cap, so the stroke is complete.
            front = p * (st["L"] + half + 2.0)
            rev = np.clip((front - st["param"]) / EDGE_PX, 0.0, 1.0)
            cov = np.clip((half - st["dist"]) / EDGE_COV + 0.5, 0.0, 1.0)
            a2 = rev * cov
            a1 = a2.reshape(y1 - y0, SS, x1 - x0, SS).mean(axis=(1, 3))
            alpha[y0:y1, x0:x1] = np.maximum(alpha[y0:y1, x0:x1], a1)
        return alpha


def load_original():
    art = load_artwork()
    return art.rgba.astype(np.float32) / 255.0, art


def render_frame(model, t_ms, mode, theme, rgba=None):
    th = THEMES[theme]
    bg = np.array(hex_rgb(th["bg"]), dtype=np.float32) / 255.0
    ink = np.array(hex_rgb(th["ink"]), dtype=np.float32) / 255.0
    H = W = 1254
    # Bitmap preview always consumes the exported schedule, including at the
    # end: do not hide missing pixels by swapping in the full original image.
    a = model.reveal_alpha(t_ms, mode=mode)
    if mode == "bitmap":
        if rgba is None:
            rgba, _ = load_original()
        rgb = rgba[..., :3] if theme == "light" else np.broadcast_to(ink, rgba[..., :3].shape)
        out = bg[None, None, :] * (1.0 - rgba[..., 3:4]) + rgb * rgba[..., 3:4]
        # remember the artwork's own colour, only its coverage is animated
        out = out * a[..., None] + bg[None, None, :] * (1.0 - a[..., None])
        return out
    cov = a[..., None]
    return bg[None, None, :] * (1.0 - cov) + ink[None, None, :] * cov


def save_png(arr, path, size=None):
    from PIL import Image

    img = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")
    if size:
        img = img.resize((size, size), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return img


def cmd_frames(args):
    m = Model()
    rgba, art = load_original()
    times = [float(x) for x in args.times.split(",")]
    made = []
    for t in times:
        arr = render_frame(m, t, args.mode, args.theme, rgba)
        p = os.path.join(args.out, f"{args.mode}-{args.theme}-{int(t):04d}ms.png")
        save_png(arr, p, size=args.size)
        made.append(p)
    print(json.dumps({"frames": made}, ensure_ascii=False, indent=1))


def cmd_sequence(args):
    m = Model()
    rgba, _ = load_original()
    os.makedirs(args.out, exist_ok=True)
    fps = args.fps
    total = args.duration
    hold = args.hold
    n = int(round(total / 1000.0 * fps))
    files = []
    for i in range(n + 1):
        t = min(total, i * 1000.0 / fps)
        arr = render_frame(m, t, args.mode, args.theme, rgba)
        p = os.path.join(args.out, f"f{i:04d}.png")
        save_png(arr, p, size=args.size)
        files.append(p)
    for j in range(int(hold / 1000.0 * fps)):
        p = os.path.join(args.out, f"f{n + 1 + j:04d}.png")
        save_png(render_frame(m, total, args.mode, args.theme, rgba), p, size=args.size)
        files.append(p)
    print(json.dumps({"frames": len(files), "dir": args.out, "fps": fps}, ensure_ascii=False))


def cmd_metrics(args):
    from scipy import ndimage

    m = Model()
    rgba, art = load_original()
    ink = art.ink
    a_vec = m.reveal_alpha(1e9, mode="vector") > 0.5
    reveal = m.reveal_alpha(1e9, mode="bitmap") > 0.5
    a_bit = ink & reveal  # the artwork's own pixels are what gets revealed
    out = {"totalMs": m.total, "inkPixels": int(ink.sum())}

    def stats(mask, name):
        miss = ink & ~mask
        extra = mask & ~ink
        iou = float((ink & mask).sum() / max((ink | mask).sum(), 1))
        d_miss = ndimage.distance_transform_edt(~mask)
        d_extra = ndimage.distance_transform_edt(~ink)
        px2dp = 75.5 / 1254.0
        out[name] = dict(
            iou=round(iou, 5),
            missingPx=int(miss.sum()),
            extraPx=int(extra.sum()),
            missingMaxPx=round(float(d_miss[miss].max()), 2) if miss.any() else 0.0,
            missingP99Px=round(float(np.percentile(d_miss[miss], 99)), 2) if miss.any() else 0.0,
            missingMeanPx=round(float(d_miss[miss].mean()), 2) if miss.any() else 0.0,
            extraMaxPx=round(float(d_extra[extra].max()), 2) if extra.any() else 0.0,
            extraMaxDp=round(float(d_extra[extra].max()) * px2dp, 3) if extra.any() else 0.0,
            missingP99Dp=round(float(np.percentile(d_miss[miss], 99)) * px2dp, 3) if miss.any() else 0.0,
            missingMaxDp=round(float(d_miss[miss].max()) * px2dp, 3) if miss.any() else 0.0,
        )

    stats(a_vec, "vector")
    stats(a_bit, "bitmap")
    # the bitmap path must hand over to the artwork itself at the end: verify
    th = THEMES["light"]
    bg = np.array(hex_rgb(th["bg"]), dtype=np.float32) / 255.0
    final = render_frame(m, m.total, "bitmap", "light", rgba)
    base = bg[None, None, :] * (1.0 - rgba[..., 3:4]) + rgba[..., :3] * rgba[..., 3:4]
    delta = np.abs(final - base)
    out["bitmapFinal"] = dict(
        maxChannelDiff=round(float(delta.max()), 6),
        pixelsDiffering=int(np.count_nonzero(delta.max(axis=2) > 1e-6)),
        note="由导出的逐像素时间表正常重建末帧；没有最终强切",
    )
    print(json.dumps(out, ensure_ascii=False, indent=1))
    os.makedirs(WORK, exist_ok=True)
    with open(os.path.join(WORK, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


def cmd_diff(args):
    """Overlay + heat-map of a rendered end state against the user's original."""
    from PIL import Image, ImageDraw

    m = Model()
    rgba, art = load_original()
    vec = m.reveal_alpha(1e9, mode=args.mode)
    orig = rgba[..., 3]
    h, w = orig.shape
    # 1) overlay: original in red channel, vector in green -> yellow where equal
    ov = np.zeros((h, w, 3), dtype=np.float32)
    ov[..., 0] = orig
    ov[..., 1] = vec
    ov[..., 2] = np.minimum(orig, vec) * 0.25
    tag = args.mode
    p1 = os.path.join(args.out, f"diff-overlay-{tag}.png")
    save_png(ov, p1)
    # 2) flat difference map
    diff = np.zeros((h, w, 3), dtype=np.float32)
    diff[..., :] = 1.0
    inter = (orig > 0.5) & (vec > 0.5)
    diff[inter] = [0.82, 0.82, 0.82]
    diff[(orig > 0.5) & ~(vec > 0.5)] = [0.0, 0.55, 0.0]
    diff[(vec > 0.5) & ~(orig > 0.5)] = [0.86, 0.0, 0.0]
    p2 = os.path.join(args.out, f"diff-flat-{tag}.png")
    save_png(diff, p2)
    # 3) crop of one glyph at 3x with legend
    x0, y0, x1, y1 = m.data["viewportPx"]["contentBox"]
    pad = 20
    crop = (max(0, y0 - pad), min(h, y1 + pad), max(0, x0 - pad), min(w, x1 + pad))
    for tag, p in (("overlay", p1), ("flat", p2)):
        im = Image.open(p).crop((crop[2], crop[0], crop[3], crop[1]))
        im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
        d = ImageDraw.Draw(im)
        d.text((8, 8), f"user original = red | {args.mode} = green | match = grey/yellow",
               fill=(0, 0, 0))
        im.save(os.path.join(args.out, f"diff-{tag}-zoom.png"))
    print(json.dumps({"overlay": p1, "flat": p2}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("frames")
    f.add_argument("--mode", default="bitmap", choices=["bitmap", "vector"])
    f.add_argument("--theme", default="light", choices=list(THEMES))
    f.add_argument("--out", required=True)
    f.add_argument("--times", default="0,250,500,750,1000")
    f.add_argument("--size", type=int, default=1254)
    f.set_defaults(func=cmd_frames)

    s = sub.add_parser("sequence")
    s.add_argument("--mode", default="vector", choices=["bitmap", "vector"])
    s.add_argument("--theme", default="light", choices=list(THEMES))
    s.add_argument("--out", required=True)
    s.add_argument("--fps", type=int, default=60)
    s.add_argument("--duration", type=int, default=1000)
    s.add_argument("--hold", type=int, default=400)
    s.add_argument("--size", type=int, default=480)
    s.set_defaults(func=cmd_sequence)

    d = sub.add_parser("diff")
    d.add_argument("--mode", default="vector", choices=["bitmap", "vector"])
    d.add_argument("--theme", default="light", choices=list(THEMES))
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_diff)

    mm = sub.add_parser("metrics")
    mm.set_defaults(func=cmd_metrics)

    args = ap.parse_args()
    if hasattr(args, "out"):
        os.makedirs(args.out, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
