# Experimental startup animation generation

This rebuild derives the time textures and source-outline vector candidate from
`catalog/src/main/res/drawable-nodpi/brand_mark.png`. It never fetches a cached
field from another machine. The per-stroke float fields and verification frames
are written to the caller's chosen working directory, not committed.

Install the pinned Python generation-only dependencies in `generator/requirements.txt`.
Run `PR6_WORKDIR=/path/to/a/writable/directory scripts/pr6/rebuild.sh` from the
repository. The script validates the source image hash, rebuilds float fields,
exports complete original-pixel ownership, verifies endpoints and night tint,
updates the two compact time textures, exports both AVD resources, and clips
overlapping slices to the source silhouette to prevent visible seams.

The AVD traces the alpha threshold in 20 ms slices and uses a solid color; it is
not an exact pixel/RGB reproduction. The Compose candidate samples the original
PNG with the compact time textures. Device playback, layer handoff, reduced
motion, and the final screenshot baselines must still be independently checked.
