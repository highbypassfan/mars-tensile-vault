"""One-time fix (2026-09-22): strip identity keyframes from every driver F-curve.

Earlier build scripts left (0,0)-(1,1) keyframes on all driver F-curves. Blender
snaps an F-curve input within 0.01 of a keyframe to that key's value, so any
driven value below 0.01 (Haze density 1.2e-5, Moon fill strength 3e-5, ...)
evaluated as 0: the exterior haze and dust storm never rendered. Without
keyframes a driver passes its value through unchanged.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/fix_driver_curves.py -- out.blend
"""
import sys

import bpy

D = bpy.data
owners = [*D.objects, *D.node_groups, *D.scenes, *D.lights, *D.cameras, *D.meshes,
          *[m.node_tree for m in D.materials if m.node_tree],
          *[w.node_tree for w in D.worlds if w.node_tree]]
fixed = 0
for owner in owners:
    if owner.animation_data:
        for fc in owner.animation_data.drivers:
            if len(fc.keyframe_points):
                fc.keyframe_points.clear()
                fixed += 1
print('FIXED driver curves', fixed, flush=True)
if '--' in sys.argv:
    bpy.ops.wm.save_as_mainfile(filepath=sys.argv[sys.argv.index('--') + 1], compress=True)
