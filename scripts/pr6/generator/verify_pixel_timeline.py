"""Check exported source alpha, time bounds, stroke endpoints and both themes."""
import json
import os
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation
from common import load_artwork
from render import Model, load_original, render_frame, save_png

base = Path(os.environ['DELIVER_DIR'])
assets = base / '01-源文件' / 'pixel-timeline'
model = Model()
art = load_artwork()
rgba, _ = load_original()
encoded = np.asarray(Image.open(assets / 'pixel_timeline.png').convert('RGBA'))
hi = np.asarray(Image.open(assets / 'time_hi.png').convert('L'))
lo = np.asarray(Image.open(assets / 'time_lo.png').convert('L'))
assert np.array_equal(hi, encoded[..., 0])
assert np.array_equal(lo, encoded[..., 1])
activation = (hi.astype(np.uint16) << 8) | lo
owner = encoded[..., 2]
visible = art.alpha > 0
assert np.array_equal(owner > 0, visible)
union = np.zeros_like(art.alpha)
for index, stroke in enumerate(model.strokes):
    image = np.asarray(Image.open(base / '01-源文件' / 'masks' / (stroke['meta']['id'] + '-ink.png')).convert('RGBA'))
    selected = owner == index + 1
    mask_dir = base / '01-源文件' / 'masks'
    mask = np.asarray(Image.open(mask_dir / (stroke['meta']['id'] + '-mask.png')).convert('L'))
    field = np.asarray(Image.open(mask_dir / (stroke['meta']['id'] + '-field.png')).convert('L'))
    assert np.array_equal(mask, image[..., 3])
    duration = max(stroke['meta']['endMs'] - stroke['meta']['startMs'], 1)
    expected_field = np.clip((activation.astype(np.float32) - stroke['meta']['startMs']) / duration, 0, 1)
    assert np.array_equal(field, np.where(selected, np.rint(expected_field * 255), 0).astype(np.uint8))
    assert np.array_equal(image[..., 3], np.where(selected, art.alpha, 0))
    assert np.array_equal(image[selected], art.rgba[selected])
    union = np.maximum(union, image[..., 3])
    assert np.all(activation[selected] >= stroke['meta']['startMs'])
    assert np.all(activation[selected] <= stroke['meta']['endMs'])
assert np.array_equal(union, art.alpha)
inner = binary_dilation(art.labels == 6, iterations=8) & visible
assert not np.any(inner & (activation <= 750))
assert not np.any(inner & (activation < 826))
times = sorted({0, 250, 500, 750, 999, 1000} | {s['meta'][key] for s in model.strokes for key in ('startMs', 'endMs')})
previous = np.zeros_like(visible)
frames_dir = assets / 'verification-frames'
frames_dir.mkdir(exist_ok=True)
for t in times:
    current = model.reveal_alpha(t, mode='bitmap') > 0.5
    assert not np.any(previous & ~current), f'nonmonotonic at {t}'
    for index, stroke in enumerate(model.strokes):
        if t < stroke['meta']['startMs']:
            assert not np.any(current & (owner == index + 1)), (t, stroke['meta']['id'])
    previous = current
    for theme in ('light', 'dark'):
        save_png(render_frame(model, t, 'bitmap', theme, rgba), str(frames_dir / f'{theme}-{t:04d}.png'), size=480)
assert np.array_equal(previous, visible)
pre_final = model.reveal_alpha(999, mode='bitmap') > 0.5
night = render_frame(model, 1000, 'bitmap', 'dark', rgba)
night_bg = np.array([0x17, 0x12, 0x25], dtype=np.float32) / 255.0
night_ink = np.array([0xD2, 0xCC, 0xFF], dtype=np.float32) / 255.0
expected_night = night_bg * (1.0 - rgba[..., 3:4]) + night_ink * rgba[..., 3:4]
assert np.allclose(night, expected_night, atol=1e-6)
out = {
    'frame_times_ms': times,
    'frames_per_theme': len(times),
    'original_alpha_pixels': int(visible.sum()),
    'unowned_alpha_pixels': int((visible & (owner == 0)).sum()),
    'overlap_policy': 'one owner per pixel: nearest stroke; order breaks ties',
    'ink_union_alpha_equal': bool(np.array_equal(union, art.alpha)),
    'inner_before_826ms': int((inner & (activation < 826)).sum()),
    'remaining_pixels_after_999ms': int((visible & ~pre_final).sum()),
    'night_tint': '#D2CCFF',
    'night_composite_max_error': float(np.max(np.abs(night - expected_night))),
    'note': 'Bitmap reference only; Android rendering and system handoff are not verified.'
}
(assets / 'verification.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=2))
