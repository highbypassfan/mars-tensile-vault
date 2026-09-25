"""One-time change (2026-09-22): scattered basalt rock field outside the habitat.

Eight procedural rock meshes (shared, never realised) are instanced over a
10 × 10 km area, dropped onto the valley terrain by raycast. Sizes follow a
heavy-tailed distribution (mostly 10–30 cm cobbles, occasional 1.5 m boulders).
Rocks thin out near the pressure wall (construction-cleared zone) and stay
off roads, aprons, landing pads, the solar farm, its substation and the
HV cable. Density falls off beyond 1.5 km from the wall to keep render prep fast.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/photoreal_rocks.py -- out.blend
"""
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gnkit  # noqa: E402

D = bpy.data
HALF = 5000.0            # scatter half-width, m
WALL = 1470.0            # outer ground edge of the pressure wall, m
# Kept clear (x0, x1, y0, y1): solar farm + its substation, HV cable corridor, battery substation.
CLEAR = [(-8450.0, -2500.0, -3000.0, 3000.0), (-2520.0, -1470.0, -345.0, -300.0)]


def rock_meshes(col, material):
    rng = random.Random(7)
    obs = []
    for i in range(8):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=4, radius=0.5)
        seed = Vector((rng.uniform(0, 100), rng.uniform(0, 100), rng.uniform(0, 100)))
        squash = rng.uniform(0.45, 0.8)
        stretch = rng.uniform(0.8, 1.3)
        for v in bm.verts:
            n = v.co.normalized()
            big = noise.fractal(n * 1.2 + seed, 0.6, 2.0, 3)
            small = noise.fractal(n * 5.0 + seed, 0.5, 2.0, 3)
            v.co = n * (0.5 + 0.18 * big + 0.04 * small)
            v.co.x *= stretch
            v.co.z *= squash
            # Facets: pull toward a few random planes for fractured faces.
            if v.co.z < -0.12:
                v.co.z = -0.12 - 0.02 * (v.co.z + 0.12)
        me = D.meshes.new(f'Basalt rock {i}')
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(material)
        ob = gnkit.new_object(f'ASSET • basalt rock {i}', col, me)
        ob.location = (i * 3.0, 0, -100)   # parked; Collection Info resets children
        obs.append(ob)
    return obs


def main():
    rock_mat = D.materials['Mesa • layered sedimentary stone']
    assets = gnkit.collection('ASSET • basalt rocks', exclude=True)
    rock_meshes(assets, rock_mat)
    field_col = gnkit.collection('YEAR 15 • Rock field')
    ground = [D.objects['Valley • gentle outer hills and continuous distant ground'],
              D.objects['Mars valley • continuous basin floor']]
    clear = [D.objects[n] for n in ('Roads • airlock approaches and external perimeter service route',
                                     'Landing field • pads and access roads',
                                     'Freight • continuous cargo aisles aligned to east airlocks',
                                     'Freight • raised-roof airlock road connection')]
    tree = scatter_tree_with_sources(assets, ground, clear)
    ob = gnkit.new_object('Rock field • scattered basalt cobbles and boulders', field_col)
    gnkit.modifier(ob, tree, 'Rock scatter')
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('ROCKS SAVED', out, flush=True)


def scatter_tree_with_sources(assets, ground_objs, clear_objs):
    t = gnkit.Tree('YEAR15 • rock field scatter', inputs=[
        ('Density per m2', 'NodeSocketFloat', 0.02),
        ('Viewport fraction', 'NodeSocketFloat', 0.01),
        ('Max size m', 'NodeSocketFloat', 1.6),
    ])
    ground = t.join(*[t.obj(o) for o in ground_objs])
    clear = t.join(*[t.obj(o) for o in clear_objs])
    return _build(t, assets, ground, clear)


def _build(t, rocks_col, ground, keep_clear):
    grid = t.make('GeometryNodeMeshGrid', Size_X=2 * HALF, Size_Y=2 * HALF, Vertices_X=201, Vertices_Y=201)
    x, y, _ = t.xyz(t.position())
    edge = t.math('SUBTRACT', t.math('MAXIMUM', t.math('ABSOLUTE', x), t.math('ABSOLUTE', y)), WALL)
    cleared = t.make('ShaderNodeMapRange', Value=edge, From_Min=40.0, From_Max=450.0, To_Min=0.0, To_Max=1.0)
    clump = t.make('ShaderNodeTexNoise', Vector=t.position(), Scale=0.0015, Detail=3.0)
    clumping = t.make('ShaderNodeMapRange', Value=t.out(clump, 'Fac'), From_Min=0.3, From_Max=0.7,
                      To_Min=0.25, To_Max=1.6)
    # Full density out to ~1.5 km beyond the wall, thinning to 20% by 4 km (far rocks are sub-pixel).
    falloff = t.make('ShaderNodeMapRange', Value=edge, From_Min=1500.0, From_Max=4000.0, To_Min=1.0, To_Max=0.2)
    density = t.math('MULTIPLY', t.math('MULTIPLY', t.out(cleared, 'Result'), t.out(clumping, 'Result')),
                     t.math('MULTIPLY', t.inp('Density per m2'), t.out(falloff, 'Result')))
    frac = t.make('GeometryNodeSwitch', props={'input_type': 'FLOAT'},
                  Switch=t.out(t.node('GeometryNodeIsViewport')))
    t.set(frac, 'False', 1.0)
    t.set(frac, 'True', t.inp('Viewport fraction'))
    density = t.math('MULTIPLY', density, t.out(frac))
    dist = t.make('GeometryNodeDistributePointsOnFaces', props={'distribute_method': 'RANDOM'},
                  Mesh=t.out(grid), Density=density, Seed=11)
    pts = t.out(dist, 'Points')

    prox = t.make('GeometryNodeProximity', props={'target_element': 'FACES'})
    t.link(keep_clear, prox.inputs[0])
    px, py, _ = t.xyz(t.position())
    on_road = t.math('LESS_THAN', t.out(prox, 'Distance'), 7.0)
    blocked = on_road
    for x0, x1, y0, y1 in CLEAR:
        inside = t.math('MULTIPLY',
                        t.math('MULTIPLY', t.math('GREATER_THAN', px, x0), t.math('LESS_THAN', px, x1)),
                        t.math('MULTIPLY', t.math('GREATER_THAN', py, y0), t.math('LESS_THAN', py, y1)))
        blocked = t.math('MAXIMUM', blocked, inside)
    drop = t.make('GeometryNodeDeleteGeometry', props={'domain': 'POINT'}, Geometry=pts, Selection=blocked)
    pts = t.out(drop)

    src = t.combine(px, py, 3000.0)
    ray = t.make('GeometryNodeRaycast', Source_Position=src, Ray_Direction=(0.0, 0.0, -1.0), Ray_Length=8000.0)
    t.link(ground, ray.inputs[0])
    size = t.math('ADD', 0.09, t.math('MULTIPLY', t.math('POWER', t.random('FLOAT', 0.0, 1.0, 3), 5.0),
                                      t.math('SUBTRACT', t.inp('Max size m'), 0.09)))
    sunk = t.vmath('ADD', t.out(ray, 'Hit Position'), t.combine(0.0, 0.0, t.math('MULTIPLY', size, -0.22)))
    setpos = t.make('GeometryNodeSetPosition', Geometry=pts, Position=sunk)
    keep = t.make('GeometryNodeDeleteGeometry', props={'domain': 'POINT'}, Geometry=t.out(setpos),
                  Selection=t.math('SUBTRACT', 1.0, t.out(ray, 'Is Hit')))
    rocks = t.make('GeometryNodeCollectionInfo', props={'transform_space': 'ORIGINAL'},
                   Collection=rocks_col, Separate_Children=True, Reset_Children=True)
    rot = t.combine(t.random('FLOAT', -0.25, 0.25, 4), t.random('FLOAT', -0.25, 0.25, 5),
                    t.random('FLOAT', 0.0, 6.2832, 6))
    inst = t.make('GeometryNodeInstanceOnPoints', Points=t.out(keep), Instance=t.out(rocks), Pick_Instance=True,
                  Instance_Index=t.random('INT', 0, 7, 8), Rotation=rot,
                  Scale=t.combine(size, t.math('MULTIPLY', size, t.random('FLOAT', 0.7, 1.2, 9)), size))
    return t.finish(t.out(inst))


if __name__ == '__main__':
    main()
