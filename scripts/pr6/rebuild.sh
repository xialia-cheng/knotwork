#!/usr/bin/env bash
# Rebuild all exported time textures and the experimental AVD from the source PNG.
# Set PR6_WORKDIR to an empty writable directory; generated reference evidence stays there.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
: "${PR6_WORKDIR:?Set PR6_WORKDIR to a writable work directory}"
mkdir -p "$PR6_WORKDIR/01-源文件" "$PR6_WORKDIR/cache"
export DELIVER_DIR="$PR6_WORKDIR"
export WORK_DIR="$PR6_WORKDIR/cache"
export WORDMARK_PNG="$root/catalog/src/main/res/drawable-nodpi/brand_mark.png"
printf '%s  %s\n' '6f2e1f949796feab05b8f0d015dd64a52343db38b5bd1ba89c6b20bdd564f96b' \
  "$WORDMARK_PNG" | sha256sum --check --status
python3 "$root/scripts/pr6/generator/model.py"
python3 "$root/scripts/pr6/generator/verify_pixel_timeline.py"
cp "$PR6_WORKDIR/01-源文件/pixel-timeline/time_hi.png" "$root/catalog/src/main/res/drawable-nodpi/brand_stroke_time_hi.png"
cp "$PR6_WORKDIR/01-源文件/pixel-timeline/time_lo.png" "$root/catalog/src/main/res/drawable-nodpi/brand_stroke_time_lo.png"
python3 "$root/scripts/pr6/export_outline.py"
python3 "$root/scripts/pr6/seam_postprocess.py"
