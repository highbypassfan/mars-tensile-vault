# Year-15 controls

## Day and night

Select **SETTLEMENT • time and district controls** → Object Properties → Custom Properties.

| Control | Behavior |
|---|---|
| Local solar hour | 0–24; drives sun position, day/night switch, exposure and lamps |
| Timeline frame 1 / 120 | Keyframed presets: 15:00 / 22:00 |
| Sun strength / Day sky strength | Direct and diffuse daylight independently |
| Day exposure / Night exposure | Photographic exposure, independently |
| Night sky strength | Catalogue sky visibility and environmental illumination |
| Habitat lights | Master switch for ring lights |
| LED brightness | Visible LED-surface brightness; illumination uses Ring light power W |
| LED temperature K | Native blackbody color temperature; default 3900 K |
| LED every L / W | Light every Nth column in each direction; default 3 / 3 |
| LED phase L / W | Offset the selected rows/columns |
| LED checkerboard | Additionally select alternating L+W parity |
| Moon fill | Optional very weak warm-neutral Phobos-like fill, enabled in the presentation preset |
| Exterior haze / Dust storm | Clear exterior haze and stronger dust variant |

The solar-hour property is keyframed. To change a preset permanently, adjust its value and insert a keyframe; an unkeyed edit can be overwritten when scrubbing. The original **LIGHTING • toggle Night sky** properties are now driven by this master control. The duplicate legacy lighting empty does not control the new setup.

**SURFACES • grass and lighting controls** still owns the LED beam angle (160°), beam gain and all-angle residual glow. Its old Grass field/distance controls are retired; use the master settlement controls for new grass. Modeling-preview membrane transparency remains on SURFACES.

The sky remains the packed NASA 4K Deep Star Map. Higher-resolution catalogue textures were deferred to avoid increasing this share file and GPU texture allocation. The existing Gale Crater orientation is retained; the hour slider does not calculate a new star ephemeris. No artificial Earth-like moon disk is added. NASA describes Phobos as roughly one-third the apparent diameter of Earth's Moon, and Deimos as star-like: https://science.nasa.gov/photojournal/crism-views-phobos-and-deimos/

## Districts and grass

Homes, Warehouses, Industry and tanks, Cargo yard, Starships and Grass areas have separate visibility toggles. Geometry is organized in **YEAR 15** collections. Buildings share mesh data; use Make Single User before editing only one instance.

Grass surface spans all designated turf at the existing datum. It stops conservatively inside the pressure perimeter, excludes occupied blocks, walkways, freight routes, and footings, and uses actual lightweight blade geometry:

- Near: 96-blade clumps, to 150 m.
- Mid: 12-blade clumps, to 600 m.
- Far: four-blade clumps, to 3,500 m.
- Beyond that: packed CC0 turf color/normal/roughness remain visible.
- Viewport density is 1.5% of render density. Instances are never realized.

The approach follows the requested discussion's distance-based detail advice: https://www.reddit.com/r/blenderhelp/comments/1r3t76x/how_to_create_a_large_grass_terrain_in_blender/

Grass density multiplier changes all tiers. Each distance can be adjusted independently. Keep Near < Mid < Far. Grass is geometry above the nominal ground, not a raised slab. Footing exclusions include the blade-clump radius. The service apron between the outermost lawn and concrete clamp remains regolith.

Concrete uses aggregate noise, fine pore relief, and varying roughness in world metres. Regolith uses coarse grain plus fine bump. Cable shading combines six strand bundles with much finer helical wire relief; its silhouette remains a cylinder for performance.

## Layout and cameras

50 × 50 columns, 50 m spacing, 200 m ring elevation. The occupied envelope extends about 2.91 km across its outer clamp. The accepted pressure-derived roof is retained. Three interior ships are about 50 m tall, with about 150 m nominal roof clearance. Eight exterior landing pads begin roughly 2.3 km outside the eastern clamp.

Freight is in the southeast, on the landing-field side. Its clear aisles meet east-side airlocks; a regolith perimeter route and landing-field spur complete the connection. Cargo occupies reusable instances on aluminum C-channel pallets. The airlocks remain closed schematic assemblies, not cut or animated operational openings.

Cameras: 01 valley/landing field; 02 civic park and heritage ships; 03 homes; 04 industry; 05 cargo; 06 landing field; 07 distant habitat exterior; 08 exterior apron/airlock; 09 night habitat from the valley. All work with day and night presets.

The native membrane and cage are parametric. Settlement layout and atmosphere exclusion are deliberately fixed to this footprint; moving/resizing the cage alone does not move districts, road connections, light-selection coordinates or grass masks. These are ordinary meshes and node groups that can be edited with standard Blender tools.

## Rendering

Cycles GPU, 256 samples, adaptive sampling, denoising, 32 total/transmission bounces, 8 diffuse bounces, 96 transparent crossings. Final output is 1920 × 1080. Included previews use 96 samples at 65% resolution. The render helper chooses an available GPU or CPU fallback; construction scripts target this workstation and are not necessary to open or render the file.


## Final exterior and night-lighting update

The open valley was widened approximately fivefold. Mesa escarpments are 26–42.5 km from the settlement, with an additional mountain chain 68–98 km away around all azimuths. Gently rolling terrain covers 300 km and the underlying ground extends 1,000 km across, beyond the saved camera views. This is procedural concept terrain, not a survey or Mars DEM. Camera far clipping is extended accordingly.

**Ring illumination now uses matched disk area lights at the visible rings**, driven by the same L/W stride, phase, checkerboard, temperature and night controls. The luminous ring mesh remains visible in camera and glossy reflections; the sampled sources supply diffuse lighting, avoiding double-counting its output. This is an approximation to each annular luminaire's distribution, not a manufacturer's photometric profile.

- Default **LED every L = 3**, **LED every W = 3**. Your saved checkerboard selection is preserved: 145 illuminated rings. Disable checkerboard for all 289 positions in the 3×3 grid.
- **Ring light power W = 9,000** controls actual illumination per active ring independently of **LED brightness = 550**, which controls the visible emitting surface.
- Night exposure is **+4 EV**. Day exposure remains **+0.9 EV**.
- **Airlock apron lights** independently toggles the entrance fixtures; **Apron light power W = 1,800** per fixture. These visibly located lights illuminate the adjacent exterior service ground. They are not hidden global fill.
- **Moon fill** now works with editable azimuth, altitude and power. The visible Phobos disk is illustrative (0.18°), not an ephemeris.
- **Moon presentation boost = 1,000** is intentionally artistic so the exterior landscape reads in the presentation renders. Set it to **1** for the much fainter reference setting. Neither the reference nor the overall star map is an absolute radiometric calibration. Do not interpret the bright preset as measured Phobos illumination.
- **Haze density = 0.000012**; dust is confined to the exterior. Dust storm increases that density; the habitat interior remains clear.

Final camera/control collections are grouped in the Outliner; earlier inspection cameras are archived. Extra light/camera overlays are hidden in the viewport for a cleaner modeling view. Enable Overlays → Extras to see their handles again. The blend opens in a saved camera view with the master controls selected.

The prior moon object had both render and viewport visibility disabled. Both are restored; the night toggle now controls its output. Apron fixtures sit 1.2 m clear of the airlock headers to avoid self-occlusion.


## Viewport LOD and raised-roof update

On **SETTLEMENT • time and district controls**:

| Control | Default | Effect in the viewport only |
|---|---:|---|
| Viewport tether LOD | On | Use coarse shared anchors; final renders retain full detail |
| Viewport tether every L / W | 2 / 2 | Show 625 of 2,500 anchors; set 1 / 1 to show every anchor |
| Viewport tether branches | 4 | Simplified splayed-wire count |
| Viewport tether sides | 4 | Cable cross-section detail |
| Viewport ring segments | 24 | Steel ring detail |

Fittings and solar inserts are omitted from the coarse anchor preview. Switch LOD off to inspect the full assembly. Native **Is Viewport** switches automatically restore all anchors and original detail for final renders, including when the anchor count changes. The setting affects interactive viewports (including rendered viewport previews), not only the named Layout and Modeling workspaces. Those two workspaces open in Solid shading for navigation.

The measured default anchor face workload is about 96% lower: 625 × 718 faces versus 2,500 × 4,689. This is a geometry-count comparison, not an FPS benchmark. The membrane, grass, terrain and other assets can still affect editor responsiveness.

Your 200 m cage and membrane heights are preserved. Sampled ring lights now follow cage height; the exterior haze clearance follows it vertically and has been widened for the current wall. Six existing residential plots have 72–130 m towers. Eight exterior ships and pads have moved exactly 2 km east, and three pad collectors meet one dark-brown trunk to the evaluated eastern freight airlock. The near landing terrain is graded flat. Entrance fixtures and camera 08 were repositioned to the current perimeter; camera 06 follows the moved field. Further footprint changes still require updating the fixed roads, fixtures and districts.

No new preview images were rendered for this update, per the preference for geometry/driver checks. The older previews show the earlier layout.
