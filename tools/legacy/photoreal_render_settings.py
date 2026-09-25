"""One-time change (2026-09-24): lighter default render settings.

At 1920 × 1080 the RX 5700 XT needs ~3 s per sample for this scene, so the old
256 samples meant ~13 min per frame. 128 samples with an adaptive noise
threshold of 0.03 and denoising looks the same after denoising at about half
the time. Raise Render → Sampling → Max Samples for final stills if needed.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/photoreal_render_settings.py -- out.blend
"""
import sys

import bpy

scene = bpy.context.scene
c = scene.cycles
c.samples = 128
c.use_adaptive_sampling = True
c.adaptive_threshold = 0.03
c.use_denoising = True
c.preview_samples = 32
c.use_preview_denoising = True
scene.render.use_persistent_data = False
# The sky maps are external; keep their paths relative to the repository root even
# if this pipeline was started from a backup in renders/.
for name in ('hiptyc_2020_16k.exr', 'milkyway_2020_4k.exr'):
    if name in bpy.data.images:
        bpy.data.images[name].filepath = '//assets/sky/' + name
out = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
print('RENDER SETTINGS SAVED', out, flush=True)
