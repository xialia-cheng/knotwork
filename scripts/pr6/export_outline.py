"""Generate experimental AVD from bitmap timing contours (not product-ready)."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

root = Path(__file__).resolve().parents[2]
assets = root / 'catalog/src/main/res/drawable-nodpi'
a = np.asarray(Image.open(assets / 'brand_mark.png').convert('RGBA'))
hi = np.asarray(Image.open(assets / 'brand_stroke_time_hi.png').convert('L'))
lo = np.asarray(Image.open(assets / 'brand_stroke_time_lo.png').convert('L'))
t = (hi.astype(np.uint16) << 8) | lo.astype(np.uint16)
source = a[..., 3] >= 128
step = 20
slices = []
for lower in range(0, 1001, step):
    selected = source & (t >= lower) & (t < lower + step)
    if not np.any(selected):
        continue
    contours, _ = cv2.findContours(selected.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    paths = []
    for contour in contours:
        contour = cv2.approxPolyDP(contour, .25, True)[:, 0, :]
        if len(contour) < 3:
            raise ValueError('degenerate contour requires explicit pixel rectangles')
        points = 16.25 + contour * (75.5 / 1254.0)
        paths.append('M' + ' L'.join(f'{x:.3f},{y:.3f}' for x, y in points) + ' Z')
    start = min(999, lower + step - 1)
    slices.append((lower, start, ' '.join(paths)))
for folder, color in [('drawable', '#30238A'), ('drawable-night', '#D2CCFF')]:
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<!-- Experimental contour slices; not yet validated on Android. -->',
             '<animated-vector xmlns:android="http://schemas.android.com/apk/res/android"',
             '    xmlns:aapt="http://schemas.android.com/aapt">',
             '    <aapt:attr name="android:drawable">',
             '        <vector android:width="108dp" android:height="108dp"',
             '            android:viewportWidth="108" android:viewportHeight="108">']
    for lower, _, path in slices:
        lines.append(f'            <path android:name="part_{lower}" android:fillColor="{color}" '
                     f'android:strokeColor="{color}" android:strokeWidth="0.0301" '
                     f'android:strokeLineJoin="round" android:fillType="evenOdd" android:pathData="{path}"/>')
    lines.extend(['        </vector>', '    </aapt:attr>'])
    for lower, start, _ in slices:
        lines.extend([f'    <target android:name="part_{lower}">',
                      '        <aapt:attr name="android:animation">',
                      '            <objectAnimator android:propertyName="fillAlpha"',
                      f'                android:startOffset="{start}" android:duration="1"',
                      '                android:valueFrom="0" android:valueTo="1"',
                      '                android:valueType="floatType" />',
                      '        </aapt:attr>', '    </target>'])
    lines.append('</animated-vector>')
    path = root / 'app/src/main/res' / folder / 'brand_startup_mark_animated.xml'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(path, path.stat().st_size, 'slices', len(slices))
