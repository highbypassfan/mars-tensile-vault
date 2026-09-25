# Reusable scene tools

Run these from the repository directory with ordinary Python. Each one starts a separate background Blender with factory settings and script auto-run disabled. They never save over the input blend or overwrite an existing output, so give each run a new output name. No extra Python packages are needed.

```powershell
python tools/vault.py inspect --output renders/scene-report.json
python tools/vault.py preview --camera 08 --night --width 960 --samples 32 --output renders/apron-night.png
python tools/vault.py variant --settings renders/settings.json --output renders/lighting-variant.blend
```

Use `--blend path/to/other.blend` to work on a variant. If the wrong Blender version is picked up, pass `--blender path/to/blender.exe` or set `BLENDER_EXE`.

**inspect** writes a JSON report with:

- every control on **CONTROLS • Mars vault**, grouped by panel, with value, limits and description
- cameras, units and render settings
- image packing and missing paths, and linked libraries
- the evaluated day and night states (exposure and powered lights)
- a count of drivers that would need Python auto-execution (expected: none)

It saves no changes.

**Settings JSON** maps control names, exactly as the panel shows them, to values:

```json
{
  "Night": true,
  "LED every L": 2,
  "LED every W": 2,
  "Night exposure": 4.5
}
```

Every edit is validated before any is applied; unknown names, wrong types, non-finite numbers and out-of-range values are rejected. Values are set directly, with no keyframes, so the timeline stays irrelevant. `--night` and `--day` are shortcuts for the `Night` checkbox.

**preview** applies the same settings temporarily, renders one camera with an available GPU (CPU fallback) and writes an 8-bit PNG. Camera identifiers such as `02` or `08` must be unique. **variant** saves the modified scene as a new blend.

These tools change the look controls only. They do not regenerate the settlement or touch the cage or membrane structure. Check previews visually before promoting a variant to the main file. No helper publishes files or changes Git state.
