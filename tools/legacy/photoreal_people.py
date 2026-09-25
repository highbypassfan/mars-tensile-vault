"""One-time change (2026-09-22): populate the settlement with people.

Bakes static poses of the embedded Standing Man (standing, looking up at the
roof, two walking strides; see people_poses.py) and scatters them as shared
instances on the concrete walkways, the regolith streets (not the freight
yard) and the park turf.
Clothing and skin vary per instance through the shader's Object Info Random,
so one mesh gives a varied crowd. Viewport shows a fraction for speed.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/photoreal_people.py -- out.blend
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gnkit  # noqa: E402
import people_poses  # noqa: E402

D = bpy.data


def random_tint(nt, image_node, bsdf, stops, mask_lo=None, mask_hi=None, other_range=None):
    """Multiply the texture by a per-instance palette colour (optionally only where it is bright)."""
    N, L = nt.nodes, nt.links
    info = N.new('ShaderNodeObjectInfo')
    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    cr = ramp.color_ramp
    while len(cr.elements) < len(stops):
        cr.elements.new(0.5)
    for i, (e, col) in enumerate(zip(cr.elements, stops)):
        e.position = i / len(stops)
        e.color = (*col, 1)
    L.new(info.outputs['Random'], ramp.inputs['Fac'])
    tint = N.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    tint.blend_type = 'MULTIPLY'
    sock = {s.identifier: s for s in tint.inputs}
    sock['Factor_Float'].default_value = 1.0
    L.new(image_node.outputs['Color'], sock['A_Color'])
    L.new(ramp.outputs['Color'], sock['B_Color'])
    tinted = next(s for s in tint.outputs if s.identifier == 'Result_Color')
    if mask_lo is None:
        L.new(tinted, bsdf.inputs['Base Color'])
        return
    # Only recolour bright areas (the light-grey shirt); shade the rest (jeans, shoes) slightly.
    lum = N.new('ShaderNodeRGBToBW')
    L.new(image_node.outputs['Color'], lum.inputs[0])
    mask = N.new('ShaderNodeMapRange')
    mask.interpolation_type = 'SMOOTHSTEP'
    L.new(lum.outputs[0], mask.inputs['Value'])
    mask.inputs['From Min'].default_value = mask_lo
    mask.inputs['From Max'].default_value = mask_hi
    shade = N.new('ShaderNodeMath')
    shade.operation = 'MULTIPLY_ADD'
    frac = N.new('ShaderNodeMath')
    frac.operation = 'FRACT'
    scale = N.new('ShaderNodeMath')
    scale.operation = 'MULTIPLY'
    scale.inputs[1].default_value = 7.31
    L.new(info.outputs['Random'], scale.inputs[0])
    L.new(scale.outputs[0], frac.inputs[0])
    L.new(frac.outputs[0], shade.inputs[0])
    shade.inputs[1].default_value = other_range[1] - other_range[0]
    shade.inputs[2].default_value = other_range[0]
    rest = N.new('ShaderNodeMix')
    rest.data_type = 'RGBA'
    rest.blend_type = 'MULTIPLY'
    rs = {s.identifier: s for s in rest.inputs}
    rs['Factor_Float'].default_value = 1.0
    L.new(image_node.outputs['Color'], rs['A_Color'])
    L.new(shade.outputs[0], rs['B_Color'])
    final = N.new('ShaderNodeMix')
    final.data_type = 'RGBA'
    fs = {s.identifier: s for s in final.inputs}
    L.new(next(s for s in rest.outputs if s.identifier == 'Result_Color'), fs['A_Color'])
    L.new(tinted, fs['B_Color'])
    L.new(mask.outputs['Result'], fs['Factor_Float'])
    L.new(next(s for s in final.outputs if s.identifier == 'Result_Color'), bsdf.inputs['Base Color'])


def vary_materials():
    shirts = [(1.3, 1.3, 1.3), (0.2, 0.28, 0.6), (1.1, 0.18, 0.14), (0.6, 0.66, 0.32), (1.7, 0.6, 0.05),
              (0.18, 0.7, 0.7), (0.35, 0.35, 0.37), (1.25, 1.05, 0.8), (0.55, 0.3, 0.75), (1.5, 1.45, 0.5)]
    skin = [(1.0, 1.0, 1.0), (0.92, 0.85, 0.8), (0.78, 0.64, 0.55), (0.6, 0.45, 0.36), (0.42, 0.3, 0.24),
            (1.02, 0.95, 0.9)]
    for name, stops, kw in (('outfit_map', shirts, dict(mask_lo=0.28, mask_hi=0.42, other_range=(0.55, 1.35))),
                            ('Body_map', skin, {}), ('Head_map', skin, {})):
        nt = D.materials[name].node_tree
        bsdf = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
        image = bsdf.inputs['Base Color'].links[0].from_node
        random_tint(nt, image, bsdf, stops, **kw)


def crowd_tree(assets, walk_ob, street_ob, turf_ob):
    t = gnkit.Tree('YEAR15 • crowd scatter', inputs=[
        ('Walkway people per m2', 'NodeSocketFloat', 0.006),
        ('Street people per m2', 'NodeSocketFloat', 0.002),
        ('Park people per m2', 'NodeSocketFloat', 0.003),
        ('Viewport fraction', 'NodeSocketFloat', 0.2),
    ])
    viewport = t.out(t.node('GeometryNodeIsViewport'))
    frac = t.make('GeometryNodeSwitch', props={'input_type': 'FLOAT'}, Switch=viewport)
    t.set(frac, 'False', 1.0)
    t.set(frac, 'True', t.inp('Viewport fraction'))

    def scatter(ob, density, seed):
        sep = t.make('GeometryNodeSeparateComponents', Geometry=t.obj(ob))   # mesh only, not grass instances
        clump = t.make('ShaderNodeTexNoise', Vector=t.position(), Scale=0.02, Detail=2.0)
        factor = t.make('ShaderNodeMapRange', Value=t.out(clump, 'Fac'), From_Min=0.35, From_Max=0.7,
                        To_Min=0.15, To_Max=1.0)
        dist = t.make('GeometryNodeDistributePointsOnFaces', props={'distribute_method': 'POISSON'},
                      Mesh=t.out(sep, 'Mesh'), Distance_Min=1.1,
                      Density_Max=t.math('MULTIPLY', density, t.out(frac)),
                      Density_Factor=t.out(factor, 'Result'), Seed=seed)
        return t.out(dist, 'Points')

    streets = scatter(street_ob, t.inp('Street people per m2'), 7)
    x, y, _ = t.xyz(t.position())
    outside = t.math('GREATER_THAN', t.math('MAXIMUM', t.math('ABSOLUTE', x), t.math('ABSOLUTE', y)), 1420.0)
    freight = t.math('MULTIPLY', t.math('GREATER_THAN', x, 540.0), t.math('LESS_THAN', y, -540.0))
    # Battery substation yard under the west wall (see photoreal_solar.BATTERY).
    battery = t.math('MULTIPLY',
                     t.math('MULTIPLY', t.math('GREATER_THAN', x, -1370.0), t.math('LESS_THAN', x, -1228.0)),
                     t.math('MULTIPLY', t.math('GREATER_THAN', y, -608.0), t.math('LESS_THAN', y, -327.0)))
    freight = t.math('MAXIMUM', freight, battery)
    streets = t.out(t.make('GeometryNodeDeleteGeometry', props={'domain': 'POINT'}, Geometry=streets,
                           Selection=t.math('MAXIMUM', outside, freight)))
    pts = t.join(scatter(walk_ob, t.inp('Walkway people per m2'), 5), streets,
                 scatter(turf_ob, t.inp('Park people per m2'), 6))
    r = t.random('FLOAT', 0.0, 1.0, 12)
    # 0 standing (35%), 1 skyward (10%), 2/3 walking (55%)
    idx = t.math('ADD', t.math('GREATER_THAN', r, 0.35),
                 t.math('ADD', t.math('GREATER_THAN', r, 0.45), t.math('GREATER_THAN', r, 0.725)))
    col = t.make('GeometryNodeCollectionInfo', props={'transform_space': 'ORIGINAL'},
                 Collection=assets, Separate_Children=True, Reset_Children=True)
    s = t.random('FLOAT', 0.93, 1.07, 13)
    inst = t.make('GeometryNodeInstanceOnPoints', Points=pts, Instance=t.out(col), Pick_Instance=True,
                  Instance_Index=idx, Rotation=t.combine(0.0, 0.0, t.random('FLOAT', 0.0, 6.2832, 14)),
                  Scale=t.combine(s, s, s))
    return t.finish(t.out(inst))


def main():
    assets = gnkit.collection('ASSET • crowd poses', exclude=True)
    for i, (name, extra) in enumerate(people_poses.POSES.items()):
        me = people_poses.bake(f'Person pose {i} • {name}', extra)
        gnkit.new_object(f'Person {i} • {name}', assets, me)
    vary_materials()
    col = gnkit.collection('YEAR 15 • People')
    ob = gnkit.new_object('People • residents and workers', col)
    tree = crowd_tree(assets, D.objects['Concrete • walkable street network'],
                      D.objects['Compacted regolith • streets and cargo apron'],
                      D.objects['Grass • full field with three distance detail levels'])
    gnkit.modifier(ob, tree, 'Crowd • shared instances')
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    n = sum(1 for inst in dg.object_instances if inst.is_instance and inst.parent and inst.parent.original == ob)
    out = sys.argv[sys.argv.index('--') + 1]
    print('PEOPLE count', n, flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('PEOPLE SAVED', out, flush=True)


if __name__ == '__main__':
    main()
