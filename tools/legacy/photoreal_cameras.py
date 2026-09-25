"""One-time change (2026-09-22): presentation cameras for the photoreal additions.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/photoreal_cameras.py -- out.blend
"""
import sys

import bpy
from mathutils import Vector

CAMERAS = {
    '10 • solar farm and battery substation': ((-2470.0, -120.0, 24.0), (-2720.0, -430.0, 0.0), 30.0),
    '11 • battery substation under the west wall': ((-1150.0, -250.0, 28.0), (-1310.0, -500.0, 0.0), 26.0),
    '12 • freight yard forklift aisle': ((874.0, -866.6, 1.7), (910.0, -866.6, 1.6), 24.0),
    '13 • homes and residential tower': ((330.0, 330.0, 1.7), (250.0, 255.0, 30.0), 24.0),
}


def main():
    col = next(c for c in bpy.data.collections if c.name.startswith('CAMERAS • 01'))
    col.name = 'CAMERAS • 01–13 final views'
    for name, (loc, target, lens) in CAMERAS.items():
        cam = bpy.data.objects.get(name)
        if cam is None:
            cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
            col.objects.link(cam)
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        cam.data.clip_end = 1.0e6
        cam.data.clip_start = 0.1
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('CAMERAS SAVED', out, flush=True)


if __name__ == '__main__':
    main()
