# Controls reference

Everything is edited in three places, all in the **Modifier tab** (wrench icon) of the Properties editor:

| Object (Outliner) | Modifier | What it controls |
|---|---|---|
| **CONTROLS • Mars vault** | CONTROLS | Look of the scene: day/night, sky, lights, districts, grass, film optics, viewport speed |
| **TENSILE CAGE & GROUND ETC** | PARAMETERS • edit here | Structure: column grid, spacing, height, anchors, cables, ring LEDs |
| **MEMBRANE • pressure-derived panels…** | LIVE • follows original cage controls | Membrane and foundation detail: concrete pad, clamps, Kevlar, airlocks |

The blend opens with CONTROLS selected. Structure is kept separate because re-evaluating the membrane takes a few seconds; look controls update almost instantly.

No Python auto-execution is needed. All drivers are simple expressions and nothing is keyframed. The timeline is not used for day and night.

## CONTROLS • Mars vault

### Time of day

| Control | Default | Notes |
|---|---:|---|
| **Night** | off | **The single day/night switch.** It switches the world to the star catalogue, turns off the Sun, lights the ring LEDs, apron floods, windows and Phobos fill, and swaps exposure. |
| Day solar hour | 15 | Sun position in daytime (12 = noon). Sunlight fades to zero at 06:00 and 18:00. It has no effect at night. |
| Sun strength / Day sky strength | 4 / 0.85 | Direct and diffuse daylight |
| Day exposure / Night exposure | +0.9 / +4 EV | Photographic exposure for each state |

### Sky and atmosphere

| Control | Default | Notes |
|---|---:|---|
| Day sky blue | 0.35 | A faint bluish zenith and the **blue aureole around the Sun** seen from Mars. It works in two places: the world sky, and a forward-scattering blue lobe in the exterior dust, which is where the real effect comes from. 0 gives a pure butterscotch sky. |
| Skybox mountains | on | Procedural distant ranges on the horizon, beyond the modelled mesas. They are hazy by day and a dark silhouette against the stars at night. |
| Skybox mountain height deg | 4.2 | Tallest peak above the horizon. The modelled mesas rise about 2° in the ground-level views, so smaller values hide the skybox ranges behind them. |
| Skybox mountain haze | 0.5 | How far the ranges fade into the sky colour (1 = invisible) |
| Night sky strength | 0.08 | Overall catalogue sky gain, including its contribution to lighting |
| Star foreground gain / Milky Way gain | 0.55 / 0.32 | The 16k bright-star layer and the 4k extended background, independently |
| Exterior haze / Haze density | on / 5e-6 | Dust volume outside the habitat only; the interior stays clear. 5e-6 gives a clear day with soft aerial perspective; about 1.5e-5 gives a dusty afternoon. |
| Dust storm | off | Multiplies haze density by 13 |

### Moon (Phobos)

Moon fill, Moon fill strength, **Moon presentation boost** (1000; set 1 for the faint physical reference), Moon azimuth/altitude deg, and Show Phobos disk (an illustrative 0.18° disk). The boost is artistic, not calibrated Phobos illumination.

### Habitat lights (night)

| Control | Default | Notes |
|---|---:|---|
| Habitat lights | on | Master switch for ring lighting |
| LED brightness | 550 | Visible glow of the LED strips. It also drives the cage's hidden LED Strength input. |
| Ring light power W | 9000 | Actual illumination per active ring, independent of the visible glow |
| LED temperature K | 3900 | Blackbody colour for the rings and apron floods |
| LED every L / W | 3 / 3 | Light every Nth ring in each direction |
| LED phase L / W | 0 / 0 | Offset of the selected rows and columns |
| LED checkerboard | on | Also keep only alternating L+W parity (145 of the 289 3×3 positions) |
| LED beam angle deg / beam gain / ambient glow fraction | 160 / 1.6 / 0.08 | Downward cone, brightness scale, faint all-angle glow |
| Ring mesh illumination gain | 1 | Converts ring power to mesh radiance (artistic calibration) |
| Airlock apron lights / Apron light power W | on / 1800 | Visible exterior floods at the vehicle airlocks |

### Districts

Visibility toggles for Homes, Warehouses, Industry and tanks, Cargo yard (the stacked freight yard), Starships, Grass areas, **People** (off by default), **Rock field** and **Solar farm and power**. Buildings share mesh data; use Make Single User before editing one instance.

### Grass detail

Near / Mid / Far grass distance m (150 / 600 / 3,500) and Grass density multiplier. Near uses 96-blade clumps, Mid 12-blade and Far 4-blade; beyond Far, only the textured turf surface remains. Distances are measured from the render camera. Keep Near < Mid < Far. Instances are never realised.

### Membrane optics

Film IOR (1.4), Film haze per ply, Film reflection roughness and strength, and Aramid translucency (the Kevlar bundles). This is a thin-sheet approximation of a free-standing ETFE laminate, not measured ETFE optical data.

### Viewport performance

Viewport tether LOD (on), every L / W (2 / 2), branches, sides and ring segments. These affect interactive viewports only; final renders always use full detail. The default shows 625 of the 2,500 anchors with about 96% fewer anchor faces.

Automatic viewport reductions (no control needed): the membrane uses a half-resolution copy of its per-bay patch (`SOURCE • ring-cut quad patch • viewport`), and people, freight and rocks use stand-ins. With default settings the viewport draws about 16 M triangles and 70 k instances (the crowd adds about 5 M).

## Scene detail objects

Each has its own small modifier for tuning. All use shared instances, which are never realised. In the viewport they show a fraction of their instances, and people, freight and rocks are swapped for light stand-ins (`ASSET • … viewport stand-ins` collections, chosen by an Is Viewport switch). Final renders always use the full assets.

| Object | Modifier inputs |
|---|---|
| People • residents and workers | Walkway / street / park people per m² (0.006 / 0.002 / 0.003, about 8,000 people), viewport fraction |
| Rock field • scattered basalt cobbles and boulders | Density per m² (0.02, about a million rocks over 10 × 10 km), viewport fraction, max size |
| Freight yard • stacked pallet blocks and forklifts | Viewport fraction. The layout is a baked point cloud: each point has a `kind` (0–9: wrapped ×2, drums, steel, pipe, bags, bricks, ingots, forklift, loaded forklift) and a `yaw` attribute |
| Solar farm • east-west PV rows and inverter skids | Viewport fraction. Rows follow the terrain by raycast; tracks every 500 m plus a central spine |

The people are four baked poses of the embedded rigged figure (standing, looking up, two walking strides; `tools/legacy/people_poses.py`). Clothing and skin vary per instance through the shader's Object Info → Random. The original rig, **PERSON RIG**, is still editable for close-up shots.

## Buildings

`photoreal_buildings.py` generates the shared building meshes. Editing **SOURCE • three storey residential** changes all 218 homes, and the three **SOURCE • residential tower** meshes are shared by the six towers. Facade colour varies per building through Object Info → Random in **Colony • ceramic coated facade**. Lit windows use a per-pane `window_seed` face attribute in **Colony • window glazing**, whose Emission Strength is still driven by Night. The halls use **Colony • ribbed metal cladding**.

## Structure: TENSILE CAGE modifier

Panels 01–06 set the grid (50 × 50 anchors at 50 m), roof height (200 m), perimeter profile and corners, anchor parts, rims and ground, and airlock size and spacing. Further panels cover cable hardware, roof-cap reinforcement, pressure and cable sizing, ring LEDs, and square-panel membrane film. Panels 07–08 are legacy features that are switched off.

The membrane samples a saved, smoothed Cloth pressure result cut to a 50 m bay. It is a reusable pressure-derived shape, not a new structural solve for each edit. Changes to column count, spacing, cap diameter and height stay live.

**The city masterplan is fixed to the 50 × 50 footprint.** Districts, roads, grass masks, the haze cavity and apron fixtures do not regenerate when the cage is resized.

## Membrane and foundation: MEMBRANE modifier

Only the membrane's own inputs are shown; inputs that mirror the cage are hidden and driven.

| Input | Default |
|---|---:|
| Roof rise m | 12.5 |
| Collar surface width m | 1.0 (four-ply collar around each ring insert) |
| Kevlar pitch m / Kevlar width m | 0.65 / 0.035 |
| Concrete pad width / crest width / pad height m | 6 / 0.8 / 1 |
| Clamp band height / plate thickness / gap m | 0.5 / 0.06 / 0.03 |
| Ground reinforcement strip m | 5 (four-ply band above the clamp) |
| Vehicle airlocks | on (size and spacing come from the cage's Airlock panel) |
| Clear viewport membrane | on (nearly transparent membrane in Material Preview; renders unaffected) |

**Welds:** the wall is tiled from welded panels. Vertical welds on the straight walls sit on the anchor rows. Horizontal welds come every Spacing W of profile arc length and continue round the corners. Each corner's vertical welds fan radially from the corner anchor, with their count chosen to keep ground-level panels about Spacing L wide, so the corner panels taper upward and every reinforcement line tees into an anchor.

The same clamp cross-section follows the full perimeter, including corners, with two rows of bolt heads at 1 m spacing. The membrane and clamp share 1,024 perimeter samples, with a maximum centreline deviation of 0.031 mm. This is visual geometry, not an engineered anchorage.

## Cameras

01 valley and landing field · 02 civic park and heritage ships · 03 residential boulevard · 04 industrial district · 05 cargo yard · 06 landing field · 07 habitat from mesa · 08 exterior apron and freight airlock · 09 night habitat from the valley · 10 solar farm and battery substation · 11 battery substation and HV cable · 12 freight yard forklift aisle · 13 homes and residential tower. All work in both day and night. Older inspection cameras are in the ARCHIVE collection.

## Rendering

Cycles GPU, 128 samples, adaptive sampling (noise threshold 0.03), denoising, 32 total and transmission bounces, 8 diffuse bounces, and 96 transparent crossings, at 1920 × 1080. `tools/render.py` picks a GPU (OptiX, CUDA, HIP, Metal or oneAPI) and falls back to CPU.

Performance: peak memory is about 3 GB. On an RX 5700 XT a 1080p frame spends ~20 s preparing the scene (the scatters are evaluated at full density) and then ~3 s per sample. Don't keep a viewport in Rendered mode while rendering with F12 on an 8 GB card. Raise Max Samples for final stills if the denoised result is blotchy. CPU rendering works (the scene fits easily in 32 GB of RAM) but is several times slower than a mid-range GPU.

## Sky orientation

The night sky is NASA SVS Deep Star Maps 2020, oriented for Gale Crater (−4.59° latitude, 137.44° E) at 2026-09-20 00:00 UTC using the IAU 2009 rotation (NAIF pck00010). The matrix is in `docs/sky-orientation.json`. Night does not compute a star ephemeris, and the map is not radiometrically calibrated. The two EXRs in `assets/sky` are external files and must stay beside the blend.

## Landscape

The ground material (Mars • compacted ochre regolith) is procedural in world space: kilometre-scale dust and basalt-sand patches, darker drifts, grain, wind ripples, fine gravel and slope darkening. Larger stones are real instanced rocks. The mesas, ridges and boulders (Mesa • layered sedimentary stone) use noise-warped strata, laminae, joint cracks, desert varnish, and dust mantling their flat tops.

The mesa escarpments are 26–42.5 km away, with a mountain chain at 68–98 km. Rolling terrain covers 300 km, and the ground extends 1,000 km. The skybox ranges sit beyond all of that. Everything is procedural concept terrain, not a Mars DEM.

This is an architectural visualization, not a validated pressure structure or landing-site design.

## How this file was built

The scripts in `tools/legacy/` were each run once, in order, on the previous file. Use them as references, not as repeatable operations:

1. `consolidate_controls.py`: the single CONTROLS panel and the Night checkbox
2. `fix_driver_curves.py`: removed stray keyframes from every driver F-curve. They snapped any driven value below 0.01 to zero, so the exterior haze and dust storm never rendered.
3. `corner_seams.py`: welds around the corners
4. `photoreal_terrain.py`, `photoreal_rocks.py`, `photoreal_freight.py`, `photoreal_people.py`, `photoreal_solar.py`, `photoreal_controls.py`, `photoreal_cameras.py`, `photoreal_buildings.py`, `photoreal_render_settings.py` (shared helpers: `gnkit.py`, `people_poses.py`).
5. `perf_pass.py`: removed a hidden 3.7 M-instance pebble scatter from the cage group and the 2,500 legacy sampled ring lights (with their 15,000 drivers and the Annular toggle), and added viewport stand-ins. They were last run as one chain from `renders/before-photoreal-assets.blend`, which is not in the repository.
