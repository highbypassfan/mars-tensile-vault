"""One-time change (2026-09-22): solar farm, cable and battery substation.

West of the habitat: a 5.83 km square farm (4× the habitat footprint) of low
east/west "tent" PV rows laid close to the ground, following the terrain, with
access tracks every 500 m and inverter skids at the track junctions. The
collector network is assumed buried. The farm feeds a small substation on its
east edge; one surface-laid three-core HV cable on concrete sleepers runs to a
duct vault at the west wall, then underground to a battery substation inside
the dome under the sloping west wall (between the y = -316 spur road and the
y = -625 airlock).
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/photoreal_solar.py -- out.blend
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gnkit  # noqa: E402
from photoreal_freight import MeshBuilder, principled  # noqa: E402

D = bpy.data
FARM_X = (-8430.0, -2600.0)
FARM_Y = (-2915.0, 2915.0)
ROW_PITCH = 4.9
SEG = 40.0
TILT = math.radians(12)
PANEL = 2.0               # slope length of one module, m
FARM_SUB = Vector((-2545.0, -320.0))
# Battery substation inside the dome, under the sloping west wall (12–60 m headroom),
# between the inner ring road (x ≈ -1380), the y = -316 spur and the y = -625 airlock.
BATTERY = (-1362.0, -1236.0, -600.0, -335.0)     # x0, x1, y0, y1
CABLE_Y = -320.0
CABLE_END_X = -1478.0     # duct vault just outside the wall clamp; the cable continues underground


def ground_z(x, y):
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = scene.ray_cast(dg, Vector((x, y, 3000.0)), Vector((0, 0, -1)))
    return loc.z if hit else 0.0


def pv_material():
    m = D.materials.get('Solar • PV module') or D.materials.new('Solar • PV module')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial')
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(bsdf.outputs[0], out.inputs[0])
    uv = N.new('ShaderNodeUVMap')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(uv.outputs[0], sep.inputs[0])

    def m_(op, a, b=None):
        n = N.new('ShaderNodeMath')
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    def gap(coord, count, width):
        f = m_('FRACT', m_('MULTIPLY', coord, count))
        return m_('LESS_THAN', m_('MINIMUM', f, m_('SUBTRACT', 1.0, f)), width)

    u, v = sep.outputs['X'], sep.outputs['Y']
    cells = m_('MAXIMUM', gap(u, 12, 0.035), gap(v, 6, 0.03))
    frame = m_('MAXIMUM', m_('MAXIMUM', m_('LESS_THAN', u, 0.012), m_('GREATER_THAN', u, 0.988)),
               m_('MAXIMUM', m_('LESS_THAN', v, 0.022), m_('GREATER_THAN', v, 0.978)))
    base = N.new('ShaderNodeMix')
    base.data_type = 'RGBA'
    bs = {s.identifier: s for s in base.inputs}
    bs['A_Color'].default_value = (0.008, 0.012, 0.03, 1)
    bs['B_Color'].default_value = (0.06, 0.065, 0.075, 1)
    L.new(cells, bs['Factor_Float'])
    framed = N.new('ShaderNodeMix')
    framed.data_type = 'RGBA'
    fs = {s.identifier: s for s in framed.inputs}
    L.new(next(s for s in base.outputs if s.identifier == 'Result_Color'), fs['A_Color'])
    fs['B_Color'].default_value = (0.55, 0.56, 0.58, 1)
    L.new(frame, fs['Factor_Float'])
    # Settled Martian dust, patchy across the field.
    geo = N.new('ShaderNodeNewGeometry')
    noise = N.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 0.004
    noise.inputs['Detail'].default_value = 6
    L.new(geo.outputs['Position'], noise.inputs['Vector'])
    fine = N.new('ShaderNodeTexNoise')
    fine.inputs['Scale'].default_value = 3.0
    L.new(geo.outputs['Position'], fine.inputs['Vector'])
    dust_amt = m_('MULTIPLY', m_('ADD', m_('MULTIPLY', noise.outputs['Fac'], 0.35), m_('MULTIPLY', fine.outputs['Fac'], 0.1)), 0.6)
    dusty = N.new('ShaderNodeMix')
    dusty.data_type = 'RGBA'
    ds = {s.identifier: s for s in dusty.inputs}
    L.new(next(s for s in framed.outputs if s.identifier == 'Result_Color'), ds['A_Color'])
    ds['B_Color'].default_value = (0.33, 0.18, 0.09, 1)
    L.new(dust_amt, ds['Factor_Float'])
    L.new(next(s for s in dusty.outputs if s.identifier == 'Result_Color'), bsdf.inputs['Base Color'])
    rough = m_('ADD', 0.06, m_('MULTIPLY', dust_amt, 1.2))
    L.new(rough, bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = 0.0
    L.new(frame, bsdf.inputs['Metallic'])
    bsdf.inputs['Specular IOR Level'].default_value = 0.35   # AR-coated glass
    bsdf.inputs['Coat Weight'].default_value = 0.15
    bsdf.inputs['Coat Roughness'].default_value = 0.05
    return m


def pv_segment(col, M):
    """40 m of tent row: west- and east-facing modules on ballasted rails."""
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new('UVMap')
    mats = [M['pv'], M['back'], M['rail'], M['ballast']]
    low = 0.18
    ridge_h = low + PANEL * math.sin(TILT)
    run = PANEL * math.cos(TILT)
    n_mod = int(SEG)
    for side in (-1, 1):
        for k in range(n_mod):
            y0 = -SEG / 2 + k * 1.0 + 0.005
            y1 = y0 + 0.99
            x_low, x_high = side * run, 0.0
            quad = [Vector((x_low, y0, low)), Vector((x_high, y0, ridge_h)),
                    Vector((x_high, y1, ridge_h)), Vector((x_low, y1, low))]
            verts = [bm.verts.new(c) for c in quad]
            f = bm.faces.new(verts if side < 0 else list(reversed(verts)))
            f.material_index = 0
            uvs = [(0, 0), (1, 0), (1, 1), (0, 1)] if side < 0 else [(0, 1), (1, 1), (1, 0), (0, 0)]
            for loop, uvc in zip(f.loops, uvs):
                loop[uv_layer].uv = uvc
            back = [bm.verts.new(c - Vector((0, 0, 0.035))) for c in quad]
            fb = bm.faces.new(list(reversed(back)) if side < 0 else back)
            fb.material_index = 1
    # Ridge rail and ballast blocks every 4 m.
    def box(size, center, mat):
        g = bmesh.ops.create_cube(bm, size=1.0)['verts']
        bmesh.ops.transform(bm, matrix=Matrix.Translation(center) @ Matrix.Diagonal((*size, 1)), verts=g)
        for f in {f for v in g for f in v.link_faces}:
            f.material_index = mats.index(mat)
    box((0.08, SEG, 0.06), Vector((0, 0, ridge_h - 0.07)), M['rail'])
    for s in (-1, 1):
        box((0.06, SEG, 0.05), Vector((s * (run - 0.05), 0, low - 0.06)), M['rail'])
    for k in range(int(SEG // 4)):
        y = -SEG / 2 + 2 + k * 4
        box((0.05, 0.05, ridge_h - 0.1), Vector((0, y, (ridge_h - 0.1) / 2)), M['rail'])
        for s in (-1, 1):
            box((0.35, 0.4, 0.14), Vector((s * (run - 0.05), y, 0.07)), M['ballast'])
    me = D.meshes.new('PV tent row segment 40 m')
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    return gnkit.new_object('ASSET • PV tent row segment 40 m', col, me)


def inverter_skid(col, M):
    mb = MeshBuilder()
    mb.box((6.1, 2.44, 2.6), Vector((0, 0, 1.3 + 0.3)), M['enclosure'])
    mb.box((6.3, 2.6, 0.3), Vector((0, 0, 0.15)), M['concrete'])
    for i in range(6):
        mb.box((0.6, 0.02, 1.2), Vector((-2.5 + i * 1.0, -1.23, 1.4)), M['vent'])
    mb.box((1.8, 1.6, 2.0), Vector((4.3, 0, 1.3)), M['transformer'])
    for i in range(8):
        mb.box((0.04, 1.9, 1.6), Vector((3.5 + i * 0.22, 0, 1.2)), M['transformer'])
    mb.box((7.8, 2.8, 0.3), Vector((0.8, 0, 0.15)), M['concrete'])
    return mb.finish('ASSET • PV inverter and step-up skid', col)


def transformer(mb, c, M, size=(4.0, 3.0, 3.2)):
    sx, sy, sz = size
    mb.box((sx, sy, sz), c + Vector((0, 0, sz / 2 + 0.4)), M['transformer'])
    for i in range(10):
        mb.box((0.05, sy + 1.0, sz * 0.8), c + Vector((-sx / 2 + 0.3 + i * (sx - 0.6) / 9, 0, sz * 0.45 + 0.4)),
               M['transformer'])
    for i in range(3):
        mb.cyl(0.12, 1.2, c + Vector((-sx / 3 + i * sx / 3, 0, sz + 1.0)), 'Z', M['insulator'], 10)
    mb.box((sx + 1.0, sy + 1.4, 0.4), c + Vector((0, 0, 0.2)), M['concrete'])


def fence(mb, M, x0, x1, y0, y1, z, gap=None):
    """Posts every 3 m, top rail and two wires (reads as chain-link at a distance)."""
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        length = math.hypot(bx - ax, by - ay)
        n = max(1, int(length // 3))
        for i in range(n + 1):
            px, py = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
            mb.box((0.06, 0.06, 2.4), Vector((px, py, z + 1.2)), M['fence'])
        cx, cy = (ax + bx) / 2, (ay + by) / 2
        sx, sy = (length, 0.04) if ay == by else (0.04, length)
        for h in (0.8, 1.6, 2.35):
            mb.box((sx, sy, 0.03 if h < 2 else 0.05), Vector((cx, cy, z + h)), M['fence'])


def farm_substation(col, M, z):
    mb = MeshBuilder()
    c = Vector((FARM_SUB.x, FARM_SUB.y, z))
    mb.box((60, 40, 0.15), c + Vector((0, 0, 0.07)), M['gravel'])
    transformer(mb, c + Vector((-12, -8, 0.15)), M)
    transformer(mb, c + Vector((-12, 8, 0.15)), M)
    mb.box((12, 6, 3.6), c + Vector((14, 10, 1.95)), M['enclosure'])            # control building
    for i in range(3):
        mb.box((6.1, 2.44, 2.6), c + Vector((12, -14 + i * 4, 1.45)), M['enclosure'])
    for gx in (-2, 6):                                                            # busbar gantry
        for gy in (-14, 14):
            mb.box((0.3, 0.3, 9), c + Vector((gx, gy, 4.65)), M['steel'])
        mb.box((0.3, 28.3, 0.4), c + Vector((gx, 0, 9.0)), M['steel'])
    for i in range(3):
        mb.cyl(0.05, 28, c + Vector((2, -1.2 + i * 1.2, 8.6)), 'Y', M['steel'], 8)
    for sx in (-28, 28):
        for sy in (-18, 18):
            mb.box((0.25, 0.25, 14), c + Vector((sx, sy, 7.1)), M['steel'])         # lightning masts
    fence(mb, M, c.x - 30, c.x + 30, c.y - 20, c.y + 20, z + 0.15)
    mb.box((1.6, 1.6, 1.0), c + Vector((31.5, 0, 0.5)), M['concrete'])            # cable termination
    return mb.finish('Solar farm substation • collector transformers and switchgear', col)


def battery_substation(col, M, z, vault_z):
    x0, x1, y0, y1 = BATTERY
    mb = MeshBuilder()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    mb.box((x1 - x0, y1 - y0, 0.2), Vector((cx, cy, z + 0.1)), M['gravel'])
    # Battery containers near the wall (lowest headroom), 3 columns of paired containers.
    for col_i in range(3):
        x = x0 + 14 + col_i * 28
        row = 0
        while y0 + 14 + row * 13.5 < y1 - 12:
            y = y0 + 14 + row * 13.5
            for off in (-3.2, 3.2):
                mb.box((12.2, 2.44, 2.9), Vector((x, y + off, z + 1.65)), M['battery'])
                for v in range(5):
                    mb.box((1.2, 0.02, 1.8), Vector((x - 4.8 + v * 2.4, y + off + (1.23 if off > 0 else -1.23), z + 1.6)),
                           M['vent'])
            mb.box((3.0, 2.4, 2.4), Vector((x + 8.5, y, z + 1.4)), M['enclosure'])      # PCS skid
            mb.box((16.0, 10.0, 0.25), Vector((x + 1.5, y, z + 0.32)), M['concrete'])
            row += 1
    # Transformers, switchyard gantries and control building on the inner side (most headroom).
    for i in range(3):
        transformer(mb, Vector((x1 - 14, y0 + 40 + i * 22, z + 0.2)), M, (6.0, 4.5, 4.4))
    for gy in (y0 + 110, y1 - 60):
        for gx in (x1 - 30, x1 - 4):
            mb.box((0.4, 0.4, 12), Vector((gx, gy, z + 6.2)), M['steel'])
    for gy in (y0 + 110, y1 - 60):
        mb.box((26.4, 0.5, 0.5), Vector((x1 - 17, gy, z + 12)), M['steel'])
    mb.box((20, 8, 4.2), Vector((x1 - 16, y1 - 22, z + 2.3)), M['enclosure'])       # control building
    mb.box((3.0, 3.0, 1.0), Vector((x0 + 3.0, y1 - 8.0, z + 0.5)), M['concrete'])   # cable duct pit from the wall
    fence(mb, M, x0, x1, y0, y1, z + 0.2)
    # Outside the wall: the HV cable drops into a duct vault and runs under the foundation.
    mb.box((4.0, 3.0, 1.4), Vector((CABLE_END_X - 1.0, CABLE_Y, vault_z + 0.7)), M['concrete'])
    return mb.finish('Battery substation • storage, transformers and switchyard', col)


def rows_tree(segment_col, skid_col, ground_ob):
    t = gnkit.Tree('YEAR15 • solar farm rows', inputs=[('Viewport fraction', 'NodeSocketFloat', 0.02)])
    w, h = FARM_X[1] - FARM_X[0], FARM_Y[1] - FARM_Y[0]
    nx, ny = int(w // ROW_PITCH), int(h // SEG)
    grid = t.make('GeometryNodeMeshGrid', Size_X=w, Size_Y=h, Vertices_X=nx, Vertices_Y=ny)
    cx, cy = (FARM_X[0] + FARM_X[1]) / 2, (FARM_Y[0] + FARM_Y[1]) / 2
    moved = t.make('GeometryNodeTransform', Geometry=t.out(grid), Translation=(cx, cy, 0.0))
    pts = t.out(t.make('GeometryNodeMeshToPoints', Mesh=t.out(moved)))
    x, y, _ = t.xyz(t.position())

    def band(coord, period, half_width, offset):
        f = t.math('FLOORED_MODULO', t.math('SUBTRACT', coord, offset), period)
        return t.math('LESS_THAN', t.math('MINIMUM', f, t.math('SUBTRACT', period, f)), half_width)

    tracks = t.math('MAXIMUM', band(y, 500.0, 26.0, FARM_Y[0] + 250), band(x, 2915.0, 8.0, FARM_X[0] + 2915))
    viewport = t.out(t.node('GeometryNodeIsViewport'))
    frac = t.make('GeometryNodeSwitch', props={'input_type': 'FLOAT'}, Switch=viewport)
    t.set(frac, 'False', 1.0)
    t.set(frac, 'True', t.inp('Viewport fraction'))
    thin = t.math('GREATER_THAN', t.random('FLOAT', 0.0, 1.0, 3), t.out(frac))
    pts = t.out(t.make('GeometryNodeDeleteGeometry', props={'domain': 'POINT'}, Geometry=pts,
                       Selection=t.math('MAXIMUM', tracks, thin)))
    ground = t.obj(ground_ob)

    def ray(dy):
        px, py, _ = t.xyz(t.position())
        r = t.make('GeometryNodeRaycast', Source_Position=t.combine(px, t.math('ADD', py, dy), 3000.0),
                   Ray_Direction=(0.0, 0.0, -1.0), Ray_Length=8000.0)
        t.link(ground, r.inputs[0])
        return t.xyz(t.out(r, 'Hit Position'))[2]

    z0, z1, zc = ray(-SEG / 2), ray(SEG / 2), ray(0.0)
    pitch = t.math('ARCTAN2', t.math('SUBTRACT', z1, z0), SEG)
    px, py, _ = t.xyz(t.position())
    placed = t.make('GeometryNodeSetPosition', Geometry=pts, Position=t.combine(px, py, zc))
    seg = t.make('GeometryNodeCollectionInfo', props={'transform_space': 'ORIGINAL'}, Collection=segment_col,
                 Separate_Children=False, Reset_Children=True)
    rows = t.make('GeometryNodeInstanceOnPoints', Points=t.out(placed), Instance=t.out(seg),
                  Rotation=t.combine(pitch, 0.0, 0.0))

    # Inverter skids at track junctions (500 m grid).
    sk = t.make('GeometryNodeMeshGrid', Size_X=w - 500, Size_Y=h - 500, Vertices_X=int(w // 500), Vertices_Y=int(h // 500))
    sk = t.make('GeometryNodeTransform', Geometry=t.out(sk), Translation=(cx, cy, 0.0))
    skp = t.out(t.make('GeometryNodeMeshToPoints', Mesh=t.out(sk)))
    sx, sy, _ = t.xyz(t.position())
    r = t.make('GeometryNodeRaycast', Source_Position=t.combine(sx, t.math('ADD', sy, 0.0), 3000.0),
               Ray_Direction=(0.0, 0.0, -1.0), Ray_Length=8000.0)
    t.link(ground, r.inputs[0])
    skp = t.make('GeometryNodeSetPosition', Geometry=skp, Position=t.out(r, 'Hit Position'))
    skid = t.make('GeometryNodeCollectionInfo', props={'transform_space': 'ORIGINAL'}, Collection=skid_col,
                  Separate_Children=False, Reset_Children=True)
    skids = t.make('GeometryNodeInstanceOnPoints', Points=t.out(skp), Instance=t.out(skid))
    return t.finish(t.join(t.out(rows), t.out(skids)))


def tracks_tree(ground_ob, road_mat):
    """Compacted access tracks through the farm, draped on the terrain."""
    t = gnkit.Tree('YEAR15 • solar farm tracks')
    w, h = FARM_X[1] - FARM_X[0], FARM_Y[1] - FARM_Y[0]
    cx, cy = (FARM_X[0] + FARM_X[1]) / 2, (FARM_Y[0] + FARM_Y[1]) / 2
    strips = []
    for k in range(int(h // 500) + 1):
        y = FARM_Y[0] + 250 + k * 500
        if y > FARM_Y[1]:
            break
        g = t.make('GeometryNodeMeshGrid', Size_X=w + 60, Size_Y=7.0, Vertices_X=int(w // 20), Vertices_Y=2)
        strips.append(t.out(t.make('GeometryNodeTransform', Geometry=t.out(g), Translation=(cx + 30, y, 0.0))))
    g = t.make('GeometryNodeMeshGrid', Size_X=7.0, Size_Y=h, Vertices_X=2, Vertices_Y=int(h // 20))
    strips.append(t.out(t.make('GeometryNodeTransform', Geometry=t.out(g), Translation=(cx, cy, 0.0))))
    # Cable service track from the farm substation to the battery substation.
    g = t.make('GeometryNodeMeshGrid', Size_X=CABLE_END_X - FARM_SUB.x, Size_Y=5.0, Vertices_X=40, Vertices_Y=2)
    strips.append(t.out(t.make('GeometryNodeTransform', Geometry=t.out(g),
                               Translation=((CABLE_END_X + FARM_SUB.x) / 2, CABLE_Y - 6.0, 0.0))))
    mesh = t.join(*strips)
    ground = t.obj(ground_ob)
    px, py, _ = t.xyz(t.position())
    r = t.make('GeometryNodeRaycast', Source_Position=t.combine(px, py, 3000.0), Ray_Direction=(0.0, 0.0, -1.0),
               Ray_Length=8000.0)
    t.link(ground, r.inputs[0])
    lifted = t.vmath('ADD', t.out(r, 'Hit Position'), (0.0, 0.0, 0.04))
    placed = t.make('GeometryNodeSetPosition', Geometry=mesh, Position=lifted)
    mat = t.make('GeometryNodeSetMaterial', Geometry=t.out(placed), Material=road_mat)
    return t.finish(t.out(mat))


def cable_tree(ground_ob, cable_mat, sleeper_col):
    """Three HV cores on concrete sleepers from the farm substation to the battery yard."""
    t = gnkit.Tree('YEAR15 • HV cable to battery substation')
    start, end = FARM_SUB.x + 32.0, CABLE_END_X - 3.0
    ground = t.obj(ground_ob)
    cores = []
    line = t.make('GeometryNodeCurvePrimitiveLine', Start=(start, CABLE_Y, 0.0), End=(end, CABLE_Y, 0.0))
    res = t.make('GeometryNodeResampleCurve', Curve=t.out(line), Count=160)
    px, py, _ = t.xyz(t.position())
    r = t.make('GeometryNodeRaycast', Source_Position=t.combine(px, py, 3000.0), Ray_Direction=(0.0, 0.0, -1.0),
               Ray_Length=8000.0)
    t.link(ground, r.inputs[0])
    hz = t.xyz(t.out(r, 'Hit Position'))[2]
    base = t.make('GeometryNodeSetPosition', Geometry=t.out(res), Position=t.combine(px, py, hz))
    for dy in (-0.45, 0.0, 0.45):
        moved = t.make('GeometryNodeSetPosition', Geometry=t.out(base), Offset=(0.0, dy, 0.42))
        cores.append(t.out(moved))
    prof = t.make('GeometryNodeCurvePrimitiveCircle', Resolution=12, Radius=0.11)
    tube = t.make('GeometryNodeCurveToMesh', Curve=t.join(*cores), Profile_Curve=t.out(prof), Fill_Caps=True)
    tube = t.make('GeometryNodeSetMaterial', Geometry=t.out(tube), Material=cable_mat)
    sleepers_pts = t.make('GeometryNodeResampleCurve', Curve=t.out(base))
    menu = gnkit.enabled(sleepers_pts.inputs, 'Mode')
    for value in ('Length', 'LENGTH'):
        try:
            menu.default_value = value
            break
        except TypeError:
            continue
    t.set(sleepers_pts, 'Length', 6.0)
    sp = t.out(t.make('GeometryNodeCurveToPoints', Curve=t.out(sleepers_pts), props={'mode': 'EVALUATED'}), 'Points')
    sl = t.make('GeometryNodeCollectionInfo', props={'transform_space': 'ORIGINAL'}, Collection=sleeper_col,
                Separate_Children=False, Reset_Children=True)
    sleepers = t.make('GeometryNodeInstanceOnPoints', Points=sp, Instance=t.out(sl))
    return t.finish(t.join(t.out(tube), t.out(sleepers)))


def main():
    M = {
        'pv': pv_material(),
        'back': principled('Solar • module backsheet', (0.7, 0.7, 0.68), 0.6),
        'rail': principled('Solar • galvanised racking', (0.5, 0.51, 0.52), 0.45, 1.0, 20.0, 0.2),
        'ballast': D.materials['Perimeter foundation • cast concrete'],
        'concrete': D.materials['Perimeter foundation • cast concrete'],
        'enclosure': principled('Power • white equipment enclosure', (0.72, 0.72, 0.7), 0.5, 0.0, 2.0, 0.08),
        'battery': principled('Power • battery container', (0.62, 0.64, 0.64), 0.45, 0.0, 1.5, 0.08),
        'vent': principled('Power • louvre vents', (0.06, 0.06, 0.065), 0.6, 0.6),
        'transformer': principled('Power • transformer grey', (0.23, 0.26, 0.27), 0.45, 0.3, 4.0, 0.12),
        'insulator': principled('Power • porcelain insulator', (0.45, 0.2, 0.1), 0.2),
        'steel': D.materials['Solar • galvanised racking'] if 'Solar • galvanised racking' in D.materials else None,
        'fence': principled('Power • chain-link fence', (0.4, 0.4, 0.42), 0.5, 1.0),
        'gravel': D.materials['Road • dark brown compacted regolith'],
    }
    M['steel'] = D.materials['Solar • galvanised racking']
    cable_mat = principled('Power • HV cable jacket', (0.02, 0.02, 0.022), 0.55, 0.0, 30.0, 0.1)
    ground_ob = D.objects['Valley • gentle outer hills and continuous distant ground']

    assets = gnkit.collection('ASSET • solar farm parts', exclude=True)
    seg_col = gnkit.collection('ASSET • PV segment', parent=assets)
    skid_col = gnkit.collection('ASSET • PV skid', parent=assets)
    sleeper_col = gnkit.collection('ASSET • cable sleeper', parent=assets)
    pv_segment(seg_col, M)
    inverter_skid(skid_col, M)
    mb = MeshBuilder()
    mb.box((0.3, 2.0, 0.3), Vector((0, 0, 0.15)), M['concrete'])
    mb.finish('ASSET • cable sleeper', sleeper_col)

    col = gnkit.collection('YEAR 15 • Solar farm and power')
    farm = gnkit.new_object('Solar farm • east-west PV rows and inverter skids', col)
    gnkit.modifier(farm, rows_tree(seg_col, skid_col, ground_ob), 'PV rows • shared instances')
    tracks = gnkit.new_object('Solar farm • access tracks', col)
    gnkit.modifier(tracks, tracks_tree(ground_ob, M['gravel']), 'Tracks draped on terrain')
    cable = gnkit.new_object('Power cable • farm substation to battery substation', col)
    gnkit.modifier(cable, cable_tree(ground_ob, cable_mat, sleeper_col), 'HV cable on sleepers')
    bpy.context.view_layer.update()
    farm_substation(col, M, ground_z(FARM_SUB.x, FARM_SUB.y))
    battery_substation(col, M, 0.0, ground_z(CABLE_END_X, CABLE_Y))   # interior floor is flat at z = 0

    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('SOLAR SAVED', out, flush=True)


if __name__ == '__main__':
    main()
