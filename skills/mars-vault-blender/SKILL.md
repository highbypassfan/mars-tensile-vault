---
name: mars-vault-blender
description: Inspect, edit and render the Mars tensile-vault Blender share project, preserving its native controls, lighting and asset packaging. Use for this project's Blender scene and reusable tooling.
---

# Mars tensile-vault Blender workflow

The working share project is `D:/Obsidian/output/mars-tensile-vault-share`. Default to `mars-tensile-vault.blend`, and preserve user-created variants. Recheck the current files and Git status rather than assuming the saved scene is unchanged.

Read `docs/SCENE-TOOLS.md` for the inspection, variant and preview commands in `tools/vault.py`, and run `inspect` to discover the exact current controls and cameras. Read `docs/CONTROLS.md` before changing appearance or layout. For code changes outside these helpers, use background Blender with `--factory-startup --disable-autoexec --python-exit-code 1`, write to a new file, and keep a backup before replacing the main blend.

## Constraints that matter

- **One control panel.** Look controls are Geometry Nodes inputs on the `CONTROLS` modifier of **CONTROLS • Mars vault**; its node group only passes geometry through. Drivers read `modifiers["CONTROLS"].properties.inputs.Socket_N.value`, so look up identifiers by input name. Structure lives on the TENSILE CAGE and MEMBRANE modifiers. Do not add structural controls to CONTROLS: any driver from CONTROLS into the membrane makes every look edit re-evaluate the membrane (about 2.5 s).
- **Day/night is the `Night` checkbox only.** Nothing is keyframed. Do not reintroduce timeline presets or keyframed controls; that was the original usability problem.
- **Keep drivers simple expressions** (`is_simple_expression`), so the file works without Python auto-run. Use `fmod`, not `%`.
- **Driver F-curves must have no keyframe points.** Blender snaps an F-curve input within 0.01 of a keyframe to that key, so stray (0,0)/(1,1) keys silently zeroed every driven value below 0.01 (haze density, ply thickness). Call `fc.keyframe_points.clear()` after `driver_add`, and check with a scan when things "do nothing".
- In the world shader, Texture Coordinate → Normal points back toward the camera; negate it to get the view direction. The existing horizon ramp uses |z| and is unaffected.
- The exterior haze volume forms most of the visible daytime sky, and Dust storm makes it thicker. Sky-colour changes must also go into `YEAR15 • exterior-only dust`, not only the world.
- Preserve the user's L/W stride, phase and checkerboard choices; 3×3 does not mean 289 active rings when checkerboard is on. Visible LED emission and actual ring illumination power are separate controls. Apron fixtures must stay clear of the opaque airlock headers.
- Moon presentation boost is artistic, not calibrated Phobos illumination. Star orientation is illustrative, not a live ephemeris.
- The cage and pressure-derived membrane are parametric, but the city layout, grass masks, road and airlock connections, haze cavity and sampled-source positions are fixed to the 50×50 footprint.
- Keep grass, people, rocks, freight and PV rows as shared instances; never realise them. Each scatter has a viewport fraction and (people, freight, rocks) an Is Viewport switch to low-poly stand-in collections; renders use full detail. Budget the viewport: it was ~16 M triangles / 70 k instances after tools/legacy/perf_pass.py; profile new additions with `depsgraph.object_instances` before shipping.
- Watch old node groups for hidden scatters: the cage group once emitted 3.7 M invisible 5 cm pebbles (98% of all instances). The legacy sampled ring lights (2,500 objects, 15 k drivers) are gone; the LED ring meshes are the only ring light source.
- Scatter or build new geometry with `tools/legacy/gnkit.py` (Geometry Nodes from Python). In 5.2 some node modes are menu inputs (e.g. Resample Curve → Mode), and Collection Info with Separate Children orders instances by object name, so asset names carry numeric prefixes.
- People are baked static poses of the Standing Man rig. Reset neck and head bones to rest for a level gaze, because offsets in bone-local axes are unreliable. Instances vary clothing and skin through Object Info → Random in the outfit/Body/Head materials.
- The corner welds are computed in the wall shader: they fan radially from the corner anchor, with the count derived from the node-group attribute `WallGroundReach`. Named attributes stored early in the membrane tree may not exist yet on the wall geometry (e.g. `Spacing L`), so compute such values in the shader.
- `Mesh.materials.clear()` resets every face's material index to 0. Set slots before `bm.to_mesh()` (see photoreal_buildings.Shell.finish).
- Saving a file opened from `renders/` rewrites relative image paths to `//renders/assets/...`, which turns the night sky magenta. After any pipeline started from a backup, reset the sky EXRs to `//assets/sky/<name>` (photoreal_render_settings.py does this) and check with `vault.py inspect`.
- Render cost (RX 5700 XT, 1080p): ~40 s of scene preparation (scatter evaluation), then ~3 s per sample. GPU memory peaks around 4.3 GB. Slow renders are not memory failures; keep the saved sample count modest.
- Hair or any curves meant for Cycles must be generated on a **Curves (hair) object** (`bpy.data.hair_curves`); curves output by a Geometry Nodes modifier on a mesh object show in the viewport but did not render in 5.2. The observer's hair (`PERSON • hair strands`, tools/legacy/observer_hair_and_stance.py) grows from the painted-hair area of the head texture.
- Find cage and membrane objects by unique prefix, because the user renames them.
- When baking evaluated meshes, resolve material pointers with `mat.original` before releasing the temporary meshes. Dangling evaluated material pointers have crashed Blender.
- Scripts in `tools/legacy/` are one-time migrations, not repeatable operations.
- Preserve packed assets and credit records. The sky EXRs are external (`//assets/sky/…`) and must be committed; write test blends inside the project folder, or those relative paths render magenta. User-supplied Poliigon maps are excluded from the public package. The blend is about 85 MB after the photoreal and buildings passes (baked people poses add about 14 MB, towers about 2 MB); check the size against GitHub's 100 MiB limit.

Use low-resolution GPU previews to iterate, covering both a ground-level interior view and an exterior or night view when lighting or the membrane changes. Look at the rendered images rather than trusting completion logs. This is a visual concept model, not a validated structural design. Publishing authorization comes from the current conversation, not this skill.
