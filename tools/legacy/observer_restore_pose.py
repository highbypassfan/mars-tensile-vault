"""One-time change (2026-09-30): put the observer back in the pose he had before
observer_posture.py and the inward left foot (commit 72f7b38), keeping his hair.

Copies every pose bone's transform, the rig's placement and the shirt-print
projector from an older copy of the share file.
  git show 72f7b38:mars-tensile-vault.blend > old.blend
  blender -b --factory-startup --disable-autoexec mars-tensile-vault.blend --python-exit-code 1 \
      --python tools/legacy/observer_restore_pose.py -- old.blend out.blend
"""
import sys

import bpy

D = bpy.data
RIG = 'PERSON RIG • editable head and neck pose'
PROJ = 'PERSON • shirt logo projector'


def main():
    old_path, out = sys.argv[sys.argv.index('--') + 1:][:2]
    with D.libraries.load(old_path, link=False) as (src, dst):
        dst.objects = [RIG, PROJ]
    old_rig, old_proj = dst.objects
    rig = D.objects[RIG]
    for pb in rig.pose.bones:
        ob = old_rig.pose.bones.get(pb.name)
        if ob:
            pb.location, pb.rotation_quaternion, pb.rotation_euler, pb.scale = \
                ob.location, ob.rotation_quaternion, ob.rotation_euler, ob.scale
    # Local transforms only: the appended copies come without their parents.
    rig.matrix_parent_inverse = old_rig.matrix_parent_inverse.copy()
    rig.matrix_basis = old_rig.matrix_basis.copy()
    proj = D.objects.get(PROJ)
    if proj and old_proj:
        proj.matrix_parent_inverse = old_proj.matrix_parent_inverse.copy()
        proj.matrix_basis = old_proj.matrix_basis.copy()
    for o in (old_rig, old_proj):
        if o:
            D.objects.remove(o)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
    print('POSE RESTORED', out, flush=True)


if __name__ == '__main__':
    main()
