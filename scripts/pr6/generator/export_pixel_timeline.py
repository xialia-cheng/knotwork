"""Export a deterministic, original-pixel stroke timeline from the float fields.

Each nontransparent source pixel belongs to the nearest stroke. Overlapping
strokes have one owner (ties follow the order in strokes.json); each pixel's
activation is clamped to its owner's start/end time. The PNG encodes an unsigned
16-bit millisecond timestamp in R/G, owner+1 in B, and opaque alpha. The color
and shape are always read from the original RGBA PNG, never from reconstructed
13-layer ink. This file is an experimental asset; AVD handoff is not validated.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from common import load_artwork
from render import Model


def export(out_dir: Path):
    model = Model()
    art = load_artwork()
    height, width = art.alpha.shape
    best = np.full((height, width), np.inf, dtype=np.float32)
    owner = np.full((height, width), -1, dtype=np.int16)
    arc = np.zeros((height, width), dtype=np.float32)
    visible = art.alpha > 0
    for index, stroke in enumerate(model.strokes):
        x0, y0, x1, y1 = stroke['bbox']
        h, w = y1 - y0, x1 - x0
        distance = stroke['dist'].reshape(h, 2, w, 2).transpose(0, 2, 1, 3).reshape(h, w, 4)
        parameter = stroke['param'].reshape(h, 2, w, 2).transpose(0, 2, 1, 3).reshape(h, w, 4)
        nearest = np.argmin(distance, axis=2)
        d = np.take_along_axis(distance, nearest[..., None], axis=2)[..., 0]
        p = np.take_along_axis(parameter, nearest[..., None], axis=2)[..., 0]
        update = (d < best[y0:y1, x0:x1]) & visible[y0:y1, x0:x1]
        best[y0:y1, x0:x1][update] = d[update]
        owner[y0:y1, x0:x1][update] = index
        arc[y0:y1, x0:x1][update] = p[update]
    # Some antialiased source pixels lie outside all cropped field bounds.
    # Assign them by nearest sampled original-derived centerline rather than
    # discarding them or revealing all leftovers in a final forced switch.
    missing = visible & (owner < 0)
    fallback_count = int(np.count_nonzero(missing))
    if fallback_count:
        samples, labels, arcs = [], [], []
        for index, stroke in enumerate(model.strokes):
            points = np.asarray(stroke['meta']['pathSmoothPx'], dtype=np.float32)
            length = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
            samples.append(points)
            labels.append(np.full(len(points), index, dtype=np.int16))
            arcs.append(length.astype(np.float32))
        tree = cKDTree(np.concatenate(samples))
        ys, xs = np.nonzero(missing)
        _, nearest = tree.query(np.column_stack([xs, ys]))
        owner[ys, xs] = np.concatenate(labels)[nearest]
        arc[ys, xs] = np.concatenate(arcs)[nearest]
    assert np.all(owner[visible] >= 0)
    activation = np.zeros((height, width), dtype=np.uint16)
    counts = []
    max_rounding_error = 0.0
    for index, stroke in enumerate(model.strokes):
        selected = visible & (owner == index)
        meta = stroke['meta']
        progress = np.clip(arc[selected] / max(stroke['L'], 1e-6), 0.0, 1.0)
        times = meta['startMs'] + progress * (meta['endMs'] - meta['startMs'])
        rounded = np.rint(times)
        if len(times):
            max_rounding_error = max(max_rounding_error, float(np.max(np.abs(rounded - times))))
        activation[selected] = rounded.astype(np.uint16)
        counts.append(dict(id=meta['id'], pixels=int(selected.sum()), start=meta['startMs'], end=meta['endMs']))
        assert np.all(activation[selected] >= meta['startMs'])
        assert np.all(activation[selected] <= meta['endMs'])
    encoded = np.zeros((height, width, 4), dtype=np.uint8)
    encoded[..., 0] = activation >> 8
    encoded[..., 1] = activation & 255
    encoded[..., 2] = np.where(visible, owner + 1, 0)
    encoded[..., 3] = 255
    out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(encoded, 'RGBA').save(out_dir / 'pixel_timeline.png', optimize=True)
    Image.fromarray(encoded[..., 0], 'L').save(out_dir / 'time_hi.png', optimize=True)
    Image.fromarray(encoded[..., 1], 'L').save(out_dir / 'time_lo.png', optimize=True)
    # Produce per-stroke diagnostic assets from the same ownership map. Their
    # union is the original alpha; the runtime uses the compact time map.
    mask_dir = out_dir.parent / 'masks'
    for index, stroke in enumerate(model.strokes):
        selected = owner == index
        rgba = art.rgba.copy()
        rgba[..., 3] = np.where(selected, art.alpha, 0).astype(np.uint8)
        name = stroke['meta']['id']
        Image.fromarray(rgba, 'RGBA').save(mask_dir / (name + '-ink.png'))
        Image.fromarray(rgba[..., 3], 'L').save(mask_dir / (name + '-mask.png'))
        meta = stroke['meta']
        duration = max(meta['endMs'] - meta['startMs'], 1)
        relative = np.clip((activation.astype(np.float32) - meta['startMs']) / duration, 0, 1)
        field = np.where(selected, np.rint(relative * 255), 0).astype(np.uint8)
        Image.fromarray(field, 'L').save(mask_dir / (name + '-field.png'))
    # Byte-exact reconstruction without a final_exact shortcut.
    decoded = np.asarray(Image.open(out_dir / 'pixel_timeline.png').convert('RGBA'))
    decoded_owner = decoded[..., 2]
    decoded_time = (decoded[..., 0].astype(np.uint16) << 8) | decoded[..., 1].astype(np.uint16)
    assert np.array_equal(decoded_time, activation)
    assert np.array_equal(decoded_owner > 0, visible)
    reconstructed = art.rgba.copy()
    # This is the normal per-pixel timeline at the end, with no special
    # final-frame shortcut. Keep the source RGB (including transparent RGB).
    shown = (decoded_owner > 0) & (decoded_time <= model.total)
    reconstructed[..., 3] = np.where(shown, art.alpha, 0).astype(np.uint8)
    assert np.array_equal(reconstructed, art.rgba)
    stats = {
        'source': '01-源文件/original/当前透明字标.png',
        'pixels_alpha_gt_zero': int(visible.sum()),
        'fallback_nearest_centerline_pixels': fallback_count,
        'unassigned_alpha_pixels': int(np.count_nonzero(visible & (decoded_owner == 0))),
        'alpha_or_rgba_diff_pixels_at_end': int(np.count_nonzero(np.any(reconstructed != art.rgba, axis=2))),
        'future_stroke_11_early_pixels_at_750ms': int(np.count_nonzero((decoded_owner == 11) & (decoded_time <= 750))),
        'timestamp_resolution_ms': 1,
        'timestamp_max_rounding_error_ms': round(max_rounding_error, 6),
        'timestamp_capacity_ms': int(np.iinfo(np.uint16).max),
        'source_unchanged': True,
        'strokes': counts,
    }
    (out_dir / 'pixel_timeline_report.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    base = Path(os.environ.get('DELIVER_DIR') or Path(__file__).resolve().parents[2])
    export(base / '01-源文件' / 'pixel-timeline')
