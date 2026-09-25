"""One-time change (2026-09-25): straighter posture and a natural look-up for the observer.

Measured on joint positions (bone axes of this Mixamo rig don't follow the mesh):
knees 7° forward, torso reclined 5–9°, neck jutting 13° forward with the head
tipped back from the top of it. New targets (forward lean in degrees, per
segment): shins and thighs vertical; spine -3/-2/-1; neck -4 (straight, slightly
back); head -36 (tilted back so the skull sits behind the plane of the back).
Each bone is rotated about the body's left-right axis through its joint, bottom
up; feet are then re-planted where they were and the shirt print re-centred.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/observer_posture.py -- out.blend
"""
import math
import sys

import bpy
from mathutils import Matrix, Vector

D = bpy.data
RIG = 'PERSON RIG • editable head and neck pose'
P = 'mixamorig:'


def main():
    rig = D.objects[RIG]
    vl = bpy.context.view_layer

    def w(b, tail=False):
        pb = rig.pose.bones[P + b]
        return rig.matrix_world @ (pb.tail if tail else pb.head)

    lat = w('RightUpLeg_060') - w('LeftUpLeg_055')
    lat.z = 0
    lat.normalize()
    fwd = Vector((0, 0, 1)).cross(lat).normalized()
    toes = (w('RightToeBase_063') + w('LeftToeBase_058')) / 2 - (w('RightFoot_062') + w('LeftFoot_057')) / 2
    if fwd.dot(toes) < 0:
        fwd = -fwd
    axis = Vector((0, 0, 1)).cross(fwd).normalized()      # rotating +θ about this tilts "up" towards fwd

    def lean(a, b):
        d = b - a
        return math.degrees(math.atan2(d.dot(fwd), d.z))

    def rotate(bone, degrees):
        pb = rig.pose.bones[P + bone]
        pivot = w(bone)
        R = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(degrees), 4, axis) @ Matrix.Translation(-pivot)
        pb.matrix = rig.matrix_world.inverted() @ R @ rig.matrix_world @ pb.matrix
        vl.update()

    def lean_down(a, b):
        d = b - a                          # for segments that hang downward (thigh, shin)
        return math.degrees(math.atan2(d.dot(fwd), -d.z))

    def set_down(bone, a_fn, b_fn, target):
        delta = target - lean_down(a_fn(), b_fn())
        rotate(bone, -delta)               # +θ tilts an upward vector forward, so a downward one backward
        return -delta

    def set_lean(bone, a_fn, b_fn, target):
        delta = target - lean(a_fn(), b_fn())
        rotate(bone, delta)
        return delta

    feet_before = {s: (w(s + 'Foot_' + n), w(s + 'ToeBase_' + t)) for s, n, t in
                   (('Left', '057', '058'), ('Right', '062', '063'))}
    low_before = min(p.z for pair in feet_before.values() for p in pair)
    ankles_before = (feet_before['Left'][0] + feet_before['Right'][0]) / 2
    report = {}
    # Legs: thigh then shin vertical, then restore each foot's pitch so it stays flat.
    for side, up, leg, foot, toe in (('Left', 'LeftUpLeg_055', 'LeftLeg_056', 'LeftFoot_057', 'LeftToeBase_058'),
                                     ('Right', 'RightUpLeg_060', 'RightLeg_061', 'RightFoot_062', 'RightToeBase_063')):
        a = set_down(up, lambda u=up: w(u), lambda l=leg: w(l), 0.0)
        b = set_down(leg, lambda l=leg: w(l), lambda f=foot: w(f), 0.0)
        rotate(foot, -(a + b))            # undo the rotations above it: foot keeps its world orientation
        report[side + ' thigh/shin change'] = (round(a, 1), round(b, 1))
    # Spine, neck, head.
    for bone, a, b, target in (('Spine_02', 'Spine_02', 'Spine1_03', -3.0), ('Spine1_03', 'Spine1_03', 'Spine2_04', -2.0),
                               ('Spine2_04', 'Spine2_04', 'Neck_05', -1.0), ('Neck_05', 'Neck_05', 'Head_06', -4.0)):
        report[bone] = round(set_lean(bone, lambda a=a: w(a), lambda b=b: w(b), target), 1)
    report['Head_06'] = round(set_lean('Head_06', lambda: w('Head_06'), lambda: w('HeadTop_End_07'), -36.0), 1)
    # Re-plant: same lowest foot point and same ankle position on the ground.
    low_after = min(p.z for s, n, t in (('Left', '057', '058'), ('Right', '062', '063'))
                    for p in (w(s + 'Foot_' + n), w(s + 'ToeBase_' + t)))
    ankles_after = (w('LeftFoot_057') + w('RightFoot_062')) / 2
    shift = Vector((ankles_before.x - ankles_after.x, ankles_before.y - ankles_after.y, low_before - low_after))
    rig.location += shift
    vl.update()
    # Re-centre the shirt print projector on the new upper back (keep its orientation).
    proj = D.objects.get('PERSON • shirt logo projector')
    if proj:
        centre = (w('Spine1_03') + w('Spine2_04')) / 2
        centre.z += 0.04
        m = proj.matrix_world.copy()
        m.translation = centre
        proj.matrix_world = m
    skull_behind = (w('Head_06') - w('Neck_05')).dot(fwd)
    print('POSTURE', report, 'rig shift', tuple(round(v, 3) for v in shift),
          'skull base fwd of neck base m', round(skull_behind, 3),
          'head top fwd of neck base m', round((w('HeadTop_End_07') - w('Neck_05')).dot(fwd), 3), flush=True)
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
    print('POSTURE SAVED', out, flush=True)


if __name__ == '__main__':
    main()
