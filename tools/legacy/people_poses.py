"""Bake static crowd meshes from the rigged Standing Man (used by photoreal_people.py).

Each pose adds rotations (degrees, bone-local X/Y/Z) on top of the frozen import
stance ('rest' resets a bone to its rest orientation), then every deformed part is evaluated and joined into one mesh with its
feet at the origin, facing the rig's original direction.
"""
import math

import bmesh
import bpy
from mathutils import Euler, Matrix

RIG = 'PERSON RIG • editable head and neck pose'
P = 'mixamorig:'
SKIP = ('Teeth',)          # hidden inside the head; saves ~7k faces per person

LEG = {'Left': '_055', 'Right': '_060'}
KNEE = {'Left': '_056', 'Right': '_061'}
FOOT = {'Left': '_057', 'Right': '_062'}
LEVEL = {P + 'Neck_05': 'rest', P + 'Head_06': 'rest'}   # rest pose has the head level


def _stride(front, back):
    return {
        **LEVEL,
        P + front + 'UpLeg' + LEG[front]: (-20, 0, 0), P + front + 'Leg' + KNEE[front]: (6, 0, 0),
        P + back + 'UpLeg' + LEG[back]: (14, 0, 0), P + back + 'Leg' + KNEE[back]: (16, 0, 0),
        P + back + 'Foot' + FOOT[back]: (-8, 0, 0),
    }


POSES = {
    'standing': LEVEL,
    'skyward': {},
    'walking left foot forward': _stride('Left', 'Right'),
    'walking right foot forward': _stride('Right', 'Left'),
}


def bake(name, extra):
    rig = bpy.data.objects[RIG]
    saved = {pb.name: pb.rotation_quaternion.copy() for pb in rig.pose.bones}
    for bone, rot in extra.items():
        pb = rig.pose.bones[bone]
        if rot == 'rest':
            pb.rotation_quaternion = (1, 0, 0, 0)
        else:
            pb.rotation_quaternion = pb.rotation_quaternion @ Euler([math.radians(a) for a in rot]).to_quaternion()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    origin = rig.matrix_world.to_translation()
    to_local = Matrix.Translation(-origin)
    out = bmesh.new()
    mats = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or ob.parent != rig or any(s in ob.name for s in SKIP):
            continue
        ev = ob.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
        me.transform(to_local @ ob.matrix_world)
        offset = len(mats)
        for m in me.materials:
            mats.append(m)
        tmp = bmesh.new()
        tmp.from_mesh(me)
        for f in tmp.faces:
            f.material_index += offset
        tmp_me = bpy.data.meshes.new('tmp')
        tmp.to_mesh(tmp_me)
        tmp.free()
        out.from_mesh(tmp_me)
        bpy.data.meshes.remove(tmp_me)
        bpy.data.meshes.remove(me)
    zmin = min(v.co.z for v in out.verts)
    bmesh.ops.translate(out, vec=(0, 0, -zmin), verts=out.verts)
    mesh = bpy.data.meshes.new(name)
    out.to_mesh(mesh)
    out.free()
    for m in mats:
        mesh.materials.append(m)
    for pb in rig.pose.bones:
        pb.rotation_quaternion = saved[pb.name]
    bpy.context.view_layer.update()
    return mesh
