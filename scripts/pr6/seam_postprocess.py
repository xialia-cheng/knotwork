"""Offline clipping experiment; generated resources are not yet device validated."""
import os
from pathlib import Path
import re
from PIL import Image
import numpy as np

root = Path(__file__).resolve().parents[2]
out_dir = Path(os.environ.get('AVD_OUT_DIR') or (root / 'build' / 'pr6-avd'))
a = np.asarray(Image.open(root / 'catalog/src/main/res/drawable-nodpi/brand_mark.png').convert('RGBA'))[:, :, 3] >= 128
height, width = a.shape
padded = np.pad(a, 1, constant_values=False)
edges = {}

def add(xs, ys, start_delta, end_delta):
    for x, y in zip(xs.tolist(), ys.tolist()):
        start = (x + start_delta[0], y + start_delta[1])
        end = (x + end_delta[0], y + end_delta[1])
        edges.setdefault(start, []).append(end)

for neighbor, start_delta, end_delta in [
    (padded[:-2, 1:-1], (0, 0), (1, 0)),
    (padded[1:-1, 2:], (1, 0), (1, 1)),
    (padded[2:, 1:-1], (1, 1), (0, 1)),
    (padded[1:-1, :-2], (0, 1), (0, 0)),
]:
    ys, xs = np.nonzero(a & ~neighbor)
    add(xs, ys, start_delta, end_delta)
scale = 75.5 / 1254.0
fmt = lambda n: f"{16.25 + n * scale:.2f}".rstrip('0').rstrip('.')
paths = []
contours = []
while edges:
    start = min(edges)
    current = start
    runs = []
    direction = None
    while True:
        candidates = edges[current]
        end = candidates.pop()
        if not candidates:
            del edges[current]
        new_direction = (end[0] - current[0], end[1] - current[1])
        if new_direction != direction:
            runs.append([new_direction, end])
        else:
            runs[-1][1] = end
        direction = new_direction
        current = end
        if current == start:
            break
    contours.append([start] + [end for _, end in runs])
    path = f'M{fmt(start[0])},{fmt(start[1])}'
    for (dx, dy), end in runs:
        path += ('H' + fmt(end[0])) if dx else ('V' + fmt(end[1]))
    paths.append(path + 'Z')
clip = ''.join(paths)
print('clip contour chars', len(clip), 'contours', len(paths))
if len(clip) > 32000:
    raise ValueError('clip path exceeds Android string pool limit')
for folder in ('drawable', 'drawable-night'):
    source = (out_dir / folder / 'brand_startup_mark_animated.xml').read_text()
    if '<clip-path' in source or 'android:strokeWidth="0.0301"' not in source:
        raise ValueError('run export_outline.py to generate clean source before seam postprocessing')
    source = source.replace('android:strokeWidth="0.0301"', 'android:strokeWidth="0.2"')
    source = source.replace('            android:viewportWidth="108" android:viewportHeight="108">',
                            '            android:viewportWidth="108" android:viewportHeight="108">\n'
                            '            <group>\n'
                            f'                <clip-path android:pathData="{clip}"/>')
    source = source.replace('        </vector>', '            </group>\n        </vector>')
    out = out_dir / folder / 'brand_startup_mark_animated.xml'
    out.write_text(source)
    print(folder, 'clip_contours', len(paths), 'bytes', out.stat().st_size)
