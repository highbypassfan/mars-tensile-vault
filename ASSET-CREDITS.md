# Asset credits and reuse information

## Habitat concept and custom geometry

Inspired by Casey Handmer's tensile-vault concept for Mars settlements. This visualization is an independent study, not an endorsement or a construction design. Membrane panels, anchors, concrete perimeter, clamping bands, vehicle airlocks, aluminum pallets, procedural landscape, worker and scene assembly were developed for this project, with AI assistance. The aluminum pallets follow the project owner's drawings and use four C-channel runners.

## Library assets

The following assets were obtained from 3DAssets.dev, whose publisher identifies its models as **CC0 1.0 Universal**. Their materials, proportions and supporting geometry were modified in this scene.

- [Shrink-wrapped pallet of cartons](https://3dassets.dev/assets/self-storage-facility-and-loading-bay-self-storage-fac-7e99dbd0). Wooden bases were replaced with custom aluminum pallets.
- [Tracked bulldozer](https://3dassets.dev/assets/demolition-and-site-clearance-demolition-and-site-clea-b80ffe3a). Retained in the scene's asset collection; its default visibility may be off.
- [Reclamation Yard ribbed salvage drum](https://3dassets.dev/packs/reclamation-yard).
- [CC0 license text](https://creativecommons.org/publicdomain/zero/1.0/).

The publisher discloses AI assistance for these library models. They are not photogrammetric scans or validated mechanical designs.

## Curiosity rover

The Curiosity_static.glb model and its textures were supplied by the project owner and embedded in the scene. The original source/license was not included with that supplied copy. No additional license or ownership claim is asserted here for the rover. Verify its original license before reusing it independently.

No blanket redistribution or modification license is asserted for the entire scene. Individual third-party licenses, where identified above, remain applicable.

## Astronomical sky

NASA/Goddard Space Flight Center Scientific Visualization Studio, Ernie Wright: [Deep Star Maps 2020](https://svs.gsfc.nasa.gov/4851/). The 4k linear EXR is embedded in the blend; the original can be downloaded from that page. Acknowledgement and source credit are retained here; consult NASA's media usage guidelines for downstream use. Catalogue contributors are credited on the source page.

Mars orientation coefficients: NASA/JPL NAIF `pck00010.tpc` (IAU 2009). Kernel copies were obtained from the [SpiceyPy test-kernel mirror](https://github.com/AndrewAnnex/SpiceyPyTestKernels); the implementation uses the Mars polynomial directly and has no SpiceyPy dependency. `naif0012.tls` is retained as the leap-second reference.

## Ground and concrete texture maps

[Concrete](https://polyhaven.com/a/concrete) and [Aerial Ground Rock](https://polyhaven.com/a/aerial_ground_rock), by Rob Tuytel / Poly Haven, are licensed [CC0](https://polyhaven.com/license). Their 2k diffuse, roughness, and displacement images are packed into the blend. Ground color was adjusted for Mars; displacement images drive bump relief. Grass blades and turf shading are custom geometry/shaders created for this scene.


## Standing person

[Standing Man](https://sketchfab.com/3d-models/standing-man-8401da7cb2564fc08681836cbeff39bc) by [zhuoyi0904](https://sketchfab.com/zhuoyi0904), licensed [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). Downloaded GLB supplied by the project owner. Modified here: static pose, upward neck/head rotation, meter scaling, placement, and roughness adjustments. Model geometry, rig and textures are embedded in the share blend. No endorsement by the asset creator is implied.


## Starships

[Space X Starship and Super Heavy (crew + cargo)](https://blendswap.com/blend/27853), by **Anyll Markevich / gallus-gallus**, **CC0**. Source supplied by the project owner; license verified on the source page. Only crew/cargo ships are used, without launch flames or boosters. Geometry was consolidated for instancing; stainless-steel and thermal materials were adapted for the current Cycles version. This is a historical speculative Starship model, not current flight hardware.

## Year-15 turf

[Leafy Grass](https://polyhaven.com/a/leafy_grass), **Charlotte Baglioni / Poly Haven**, **CC0**. Packed 2K diffuse, roughness and normal maps provide distant turf detail; blades are custom shared geometry. The supplied Poliigon grass was tested locally and is **not included** in the final publicly shared blend. Its source files remain untouched in the owner's asset folder.

Year-15 concrete and regolith materials are procedural. Earlier CC0 surface maps remain in legacy data but no longer drive the active concrete/regolith materials. New settlement buildings, roads, mesa geometry and grass LOD meshes were created for this project.
