"""One-time change (2026-09-25): real hair and a more natural stance for the observer.

- Hair: the Standing Man asset only has hair painted on a smooth scalp. A
  Geometry Nodes object grows short strands from the posed head mesh wherever
  the head texture is dark (the painted hair), combed back and down along the
  scalp, tapered and frizzed, rendered with the Principled Hair BSDF. The
  painted scalp stays underneath, so gaps still read as hair. Viewport shows 10%.
- Stance: the left leg is twisted 20° inward at the hip (toe direction moves
  from 39° to 20° off straight ahead, sole stays flat).
Only the observer changes; the crowd uses separately baked poses.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/observer_hair_and_stance.py -- out.blend
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gnkit  # noqa: E402

D = bpy.data
RIG = 'PERSON RIG • editable head and neck pose'
HEAD = 'Person • Head_Head_map_0'


def stance():
    rig = D.objects[RIG]
    pb = rig.pose.bones['mixamorig:LeftUpLeg_055']
    pb.rotation_quaternion = pb.rotation_quaternion @ Euler((0, math.radians(20), 0)).to_quaternion()


def hair_material():
    m = D.materials.new('Observer • short dark hair')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    h = nt.nodes.new('ShaderNodeBsdfHairPrincipled')
    h.parametrization = 'MELANIN'
    h.inputs['Melanin'].default_value = 0.88
    h.inputs['Melanin Redness'].default_value = 0.35
    h.inputs['Roughness'].default_value = 0.32
    h.inputs['Radial Roughness'].default_value = 0.35
    h.inputs['Random Color'].default_value = 0.12
    h.inputs['Random Roughness'].default_value = 0.15
    nt.links.new(h.outputs[0], out.inputs['Surface'])
    return m


def forward_dir():
    rig = D.objects[RIG]
    M = rig.matrix_world

    def w(b):
        return M @ rig.pose.bones['mixamorig:' + b].head
    f = (w('RightToeBase_063') - w('RightFoot_062'))            # right foot is closest to the body's facing
    f += (w('LeftToeBase_058') - w('LeftFoot_057'))
    f.z = 0
    return f.normalized()


def hair_tree(head, image, material, back):
    t = gnkit.Tree('Observer • hair strands', inputs=[
        ('Strands per m2', 'NodeSocketFloat', 700000.0),
        ('Length m', 'NodeSocketFloat', 0.025),
        ('Viewport fraction', 'NodeSocketFloat', 0.1),
    ])
    head_geo = t.obj(head)                                   # evaluated, so it follows the pose
    # Hair mask from the painted head texture (dark = hair).
    uv = t.named('UVMap', 'FLOAT_VECTOR')
    tex = t.make('GeometryNodeImageTexture', Image=image, Vector=uv)
    lum = t.math('MULTIPLY', t.math('ADD', t.math('ADD', t.xyz(t.out(tex, 'Color'))[0], t.xyz(t.out(tex, 'Color'))[1]),
                                    t.xyz(t.out(tex, 'Color'))[2]), 1 / 3)
    mask = t.make('ShaderNodeMapRange', Value=lum, From_Min=0.035, From_Max=0.015,   # linear colour: painted hair is very dark
                 To_Min=0.0, To_Max=1.0)
    frac = t.make('GeometryNodeSwitch', props={'input_type': 'FLOAT'}, Switch=t.out(t.node('GeometryNodeIsViewport')))
    t.set(frac, 'False', 1.0)
    t.set(frac, 'True', t.inp('Viewport fraction'))
    density = t.math('MULTIPLY', t.math('MULTIPLY', t.out(mask, 'Result'), t.inp('Strands per m2')), t.out(frac))
    dist = t.make('GeometryNodeDistributePointsOnFaces', props={'distribute_method': 'RANDOM'}, Mesh=head_geo,
                  Density=density, Seed=3)
    pts = t.out(dist, 'Points')
    normal = t.out(dist, 'Normal')
    # Comb direction: back and down, projected onto the scalp, lifted slightly off it.
    comb = t.vmath('NORMALIZE', t.vmath('ADD', (back.x * 0.6, back.y * 0.6, -0.8), (0.0, 0.0, 0.0)))
    along = t.vmath('SUBTRACT', comb, t.vmath('SCALE', normal, scale=t.vmath('DOT_PRODUCT', comb, normal)))
    jitter = t.vmath('SCALE', t.random('FLOAT_VECTOR', (-1.0, -1.0, -1.0), (1.0, 1.0, 1.0), 5), scale=0.2)
    direction = t.vmath('NORMALIZE', t.vmath('ADD', t.vmath('ADD', t.vmath('NORMALIZE', along),
                                                            t.vmath('SCALE', normal, scale=0.15)), jitter))
    # Capture per-point values before instancing.
    align = t.make('FunctionNodeAlignRotationToVector', props={'axis': 'Z'}, Vector=direction)
    line = t.make('GeometryNodeCurvePrimitiveLine', Start=(0.0, 0.0, 0.0), End=(0.0, 0.0, 1.0))
    line = t.make('GeometryNodeResampleCurve', Curve=t.out(line), Count=6)
    length = t.math('MULTIPLY', t.inp('Length m'), t.random('FLOAT', 0.55, 1.3, 7))
    inst = t.make('GeometryNodeInstanceOnPoints', Points=pts, Instance=t.out(line), Rotation=t.out(align),
                  Scale=t.combine(length, length, length))
    curves = t.out(t.make('GeometryNodeRealizeInstances', Geometry=t.out(inst)))
    # Frizz and a slight droop towards the tips.
    param = t.out(t.node('GeometryNodeSplineParameter'), 'Factor')
    noise = t.make('ShaderNodeTexNoise', Vector=t.vmath('SCALE', t.position(), scale=180.0), Scale=1.0, Detail=2.0)
    wiggle = t.vmath('SCALE', t.vmath('SUBTRACT', t.out(noise, 'Color'), (0.5, 0.5, 0.5)),
                     scale=t.math('MULTIPLY', param, 0.012))
    droop = t.combine(0.0, 0.0, t.math('MULTIPLY', t.math('MULTIPLY', param, param), -0.008))
    curves = t.out(t.make('GeometryNodeSetPosition', Geometry=curves, Offset=t.vmath('ADD', wiggle, droop)))
    radius = t.make('ShaderNodeMapRange', Value=param, From_Min=0.0, From_Max=1.0, To_Min=0.00011, To_Max=0.00003)
    curves = t.out(t.make('GeometryNodeSetCurveRadius', Curve=curves, Radius=t.out(radius, 'Result')))
    curves = t.out(t.make('GeometryNodeSetMaterial', Geometry=curves, Material=material))
    return t.finish(curves)


def main():
    stance()
    bpy.context.view_layer.update()
    head = D.objects[HEAD]
    image = next(n.image for n in D.materials['Head_map'].node_tree.nodes
                 if n.bl_idname == 'ShaderNodeTexImage'
                 and any(l.to_socket.name in ('Color', 'A', 'Base Color') for l in n.outputs['Color'].links)
                 and not any(l.to_node.bl_idname == 'ShaderNodeNormalMap' for l in n.outputs['Color'].links))
    back = -forward_dir()
    col = D.objects[RIG].users_collection[0]
    # A Curves (hair) object: Cycles renders curves from hair objects; curves output
    # by a modifier on a mesh object were not rendered in 5.2.
    ob = gnkit.new_object('PERSON • hair strands', col, D.hair_curves.new('PERSON • hair strands'))
    gnkit.modifier(ob, hair_tree(head, image, hair_material(), back), 'Hair • grown from the painted scalp')
    world = ob.matrix_world.copy()
    ob.parent = D.objects[RIG]
    ob.matrix_parent_inverse = D.objects[RIG].matrix_world.inverted()
    ob.matrix_world = world
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    geo = ev.evaluated_geometry()
    count = len(geo.curves.curves) if geo.curves else 0
    print('HAIR image', image.name, 'strands (viewport eval)', count, flush=True)
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
    print('HAIR SAVED', out, flush=True)


if __name__ == '__main__':
    main()
