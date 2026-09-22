# Reusable scene tools

Run from the repository directory with ordinary Python. These helpers open a separate background Blender process, avoiding add-on startup errors. They never save over the input blend or overwrite an existing output. Use a new output filename each run. They require Blender 5.2-compatible scene APIs and no extra Python packages.

```powershell
python tools/vault.py inspect --output renders/scene-report.json
python tools/vault.py preview --camera 08 --frame 120 --width 960 --samples 32 --output renders/apron-night.png
python tools/vault.py variant --frame 120 --settings renders/settings.json --output renders/lighting-variant.blend
```

Use `--blend path/to/other.blend` to inspect/render a variant. Supply `--blender path/to/blender.exe` or set `BLENDER_EXE` if executable discovery chooses the wrong installed version.

The report lists exact control names, current values and stored limits, cameras, unit scale, render settings, image packing/missing paths, linked libraries, mesh sharing, and evaluated day/night ring counts. Hidden powered lights are diagnostic candidates, not necessarily errors: intentional viewport hiding is included. The report evaluates frames 1 and 120 but saves no changes.

Settings JSON uses an exact object name or unique prefix:

```json
{
  "SETTLEMENT • time and district controls": {
    "Local solar hour": 22.0,
    "LED every L": 3,
    "LED every W": 3,
    "Night exposure": 4.0
  }
}
```

Read the report for current exact property names and types. The editor rejects unknown properties, ambiguous object prefixes, invalid types, nonfinite numbers, values outside stored limits, and driven properties. All requested edits are validated before application. Numeric and toggle changes are **keyframed at the requested frame**, so time scrubbing does not discard them. This also means Blender's normal interpolation applies between keys; these are frame-specific presets, not global replacements of animation.

Preview accepts the same `--settings` for temporary render experiments without saving a blend. It selects an available Cycles GPU, falling back to CPU, and writes an 8-bit PNG. Camera identifiers such as `02` or `08` must be unique. The input file's aspect ratio is preserved.

These tools edit native custom controls; they do not regenerate the settlement or rerun historical migration scripts. Read YEAR15-CONTROLS.md before changing the habitat footprint. Inspect previews visually before promoting a variant to the main share file. No helper publishes files or changes Git state.

