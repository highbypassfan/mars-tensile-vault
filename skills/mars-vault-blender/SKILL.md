---
name: mars-vault-blender
description: Inspect, edit and render the Mars tensile-vault Blender share project, preserving its native controls, lighting and asset packaging. Use for this project's Blender scene and reusable tooling.
---

# Mars tensile-vault Blender workflow

The working share project is `D:/Obsidian/output/mars-tensile-vault-share`. Default to `mars-tensile-vault.blend`; preserve user-created variants. Recheck current files and Git status rather than assuming the saved scene is unchanged.

Read `docs/SCENE-TOOLS.md` for reusable inspection, variant and preview commands via `tools/vault.py`. Run `inspect` to discover exact current controls and cameras. Read `docs/YEAR15-CONTROLS.md` when changing appearance or layout. The tools create new outputs and never overwrite the input. For code changes outside these helpers, use background Blender with `--factory-startup --disable-autoexec --python-exit-code 1` and a backup before saving.

## Constraints that matter

- Frame 1/day and 120/night are keyframed presets. Time and light edits must survive scrubbing. Preserve the user's L/W stride, phase and checkerboard choices; 3×3 does not imply 289 active sources when checkerboard is on.
- Visible LED emission and actual sampled ring-light power are separate controls. Check hidden flags and collection visibility as well as energy when debugging illumination. Apron fixtures must remain clear of opaque airlock headers.
- Moon presentation boost is artistic, not calibrated Phobos illumination; star orientation is illustrative and not a live ephemeris.
- The cage/pressure-derived membrane are parametric, but city layout, grass masks, road/airlock connections, atmosphere cavity and sampled-source positions are fixed to the 50×50 footprint. Changing cage size alone does not regenerate them.
- Keep grass instances shared, never realize the full field. Camera-dependent blade detail is intentional; preserve the continuous distant turf surface and perimeter/footing exclusions.
- Find cage objects by unique prefix: the user renames them. Blender 5.2 geometry-node modifier inputs may use `modifier.properties.inputs.<identifier>.value` rather than old ID-property syntax.
- When baking evaluated meshes, resolve material pointers with `mat.original` before releasing temporary evaluated meshes. Dangling evaluated material pointers previously crashed Blender.
- Historical tools such as build/finalize/tidy and verify_final_lighting are migrations, not repeatable operations. In particular, the latter moves apron fixtures again if rerun.
- Preserve packed assets and credit records. User-supplied Poliigon maps were excluded from the public package; CC0 Leafy Grass is packed instead. Inspect actual packing before sharing. The blend was near GitHub's ordinary 100 MiB file limit; check current size.

Use low-resolution GPU previews for iteration, including both a ground-level interior and exterior/night view when lighting or membrane changes. Inspect rendered images rather than trusting completion logs. This is a visual concept model, not a validated structural design. Publishing authorization comes from the current conversation, not this skill.
