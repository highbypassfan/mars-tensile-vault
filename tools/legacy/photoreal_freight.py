"""One-time change (2026-09-22): dense, stacked freight yard with forklifts.

Replaces the sparse single-height pallets with forklift-spaced pallet blocks:
each 50 m bay the old layout used densely becomes a 41 m block of back-to-back
pallet rows separated by 3.6 m forklift aisles, stacked 2–4 high. Bays are
grouped in 2×2 clusters of one cargo type so the yard reads as big piles:
wrapped equipment, drums, rolled steel plate, pipe bundles, bulk bags,
sintered-regolith bricks and aluminium ingots. About 30 forklifts work the
aisles. Everything is shared instances on one point cloud (never realised).
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/photoreal_freight.py -- out.blend
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

D = bpy.data
SPACING = 50.0
ORIGIN = -1225.0          # first anchor row
BLOCK = 20.5              # half-size of a pallet block inside a bay
AISLE_Y = (-630.0, -600.0)  # north truck aisle band (kept clear)


# ---------------------------------------------------------------- materials
def principled(name, color, rough, metal=0.0, noise_scale=None, noise_amt=0.0, bump=0.0):
    m = D.materials.get(name) or D.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    nt.links.new(b.outputs[0], out.inputs[0])
    if noise_scale:
        tex = nt.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = noise_scale
        tex.inputs['Detail'].default_value = 8
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        sock = {s.identifier: s for s in mix.inputs}
        sock['Factor_Float'].default_value = noise_amt
        sock['A_Color'].default_value = (*color, 1)
        nt.links.new(tex.outputs['Color'], sock['B_Color'])
        nt.links.new(next(s for s in mix.outputs if s.identifier == 'Result_Color'), b.inputs['Base Color'])
        if bump:
            bp = nt.nodes.new('ShaderNodeBump')
            bp.inputs['Strength'].default_value = bump
            nt.links.new(tex.outputs['Fac'], bp.inputs['Height'])
            nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m


def materials():
    return {
        'steel': principled('Raw • hot-rolled steel plate', (0.09, 0.085, 0.08), 0.55, 0.9, 6.0, 0.5, 0.15),
        'pipe': principled('Raw • galvanised pipe', (0.55, 0.56, 0.57), 0.38, 1.0, 12.0, 0.25, 0.05),
        'bag': principled('Raw • woven polypropylene bulk bag', (0.78, 0.75, 0.68), 0.85, 0.0, 180.0, 0.25, 0.25),
        'brick': principled('Raw • sintered regolith brick', (0.26, 0.10, 0.05), 0.9, 0.0, 30.0, 0.45, 0.4),
        'ingot': principled('Raw • aluminium ingot', (0.80, 0.80, 0.80), 0.32, 1.0, 20.0, 0.2, 0.05),
        'strap': D.materials['Cargo • restraint webbing'],
        'paint': principled('Forklift • safety yellow paint', (0.75, 0.48, 0.02), 0.4, 0.0, 3.0, 0.15, 0.0),
        'dark': principled('Forklift • dark steel', (0.03, 0.03, 0.03), 0.5, 0.8),
        'rubber': principled('Forklift • tyre rubber', (0.015, 0.015, 0.015), 0.85),
        'glass': principled('Forklift • cab glass', (0.05, 0.06, 0.07), 0.05, 0.0),
    }


# ---------------------------------------------------------------- mesh helpers
class MeshBuilder:
    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def mat(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def box(self, size, center, m, rot_z=0.0):
        geom = bmesh.ops.create_cube(self.bm, size=1.0)['verts']
        M = Matrix.Translation(center) @ Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Diagonal((*size, 1))
        bmesh.ops.transform(self.bm, matrix=M, verts=geom)
        self._assign(geom, m)

    def cyl(self, radius, depth, center, axis, m, segs=12):
        geom = bmesh.ops.create_cone(self.bm, cap_ends=True, segments=segs, radius1=radius, radius2=radius,
                                     depth=depth)['verts']
        rot = {'X': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'Y': Matrix.Rotation(math.pi / 2, 4, 'X'),
               'Z': Matrix.Identity(4)}[axis]
        bmesh.ops.transform(self.bm, matrix=Matrix.Translation(center) @ rot, verts=geom)
        self._assign(geom, m)

    def mesh_copy(self, mesh, offset, mats_map):
        tmp = bmesh.new()
        tmp.from_mesh(mesh)
        bmesh.ops.translate(tmp, vec=offset, verts=tmp.verts)
        me = D.meshes.new('tmp')
        tmp.to_mesh(me)
        tmp.free()
        base = len(self.bm.faces)
        self.bm.from_mesh(me)
        self.bm.faces.ensure_lookup_table()
        for f in self.bm.faces[base:]:
            src = mesh.materials[f.material_index] if f.material_index < len(mesh.materials) else None
            f.material_index = self.mat(mats_map(src))
        D.meshes.remove(me)

    def _assign(self, verts, m):
        idx = self.mat(m)
        faces = {f for v in verts for f in v.link_faces}
        for f in faces:
            f.material_index = idx

    def finish(self, name, col, smooth=False):
        me = D.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        return gnkit.new_object(name, col, me)


def centred_copy(src_ob):
    """Mesh copy of an existing cargo asset, footprint centred on the origin, base at z = 0."""
    me = src_ob.data.copy()
    vs = [v.co for v in me.vertices]
    cx = (min(v.x for v in vs) + max(v.x for v in vs)) / 2
    cy = (min(v.y for v in vs) + max(v.y for v in vs)) / 2
    z0 = min(v.z for v in vs)
    me.transform(Matrix.Translation((-cx, -cy, -z0)))
    return me


def pallet_height(pallet_mesh):
    return max(v.co.z for v in pallet_mesh.vertices) - min(v.co.z for v in pallet_mesh.vertices)


def raw_assets(col, M, pallet_mesh):
    rng = random.Random(3)
    ph = pallet_height(pallet_mesh)

    def on_pallet():
        mb = MeshBuilder()
        mb.mesh_copy(pallet_mesh, Vector((0, 0, 0)), lambda m: m)
        return mb

    out = {}
    # Rolled steel plate, slightly skewed sheets.
    mb = on_pallet()
    z = ph
    for i in range(12):
        t = 0.04
        mb.box((1.14, 0.96, t), Vector((rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), z + t / 2)), M['steel'],
               rng.uniform(-0.02, 0.02))
        z += t + 0.002
    for x in (-0.35, 0.35):
        mb.box((0.04, 1.0, z - ph + 0.02), Vector((x, 0, ph + (z - ph) / 2)), M['strap'])
    out['steel'] = mb.finish('Freight 3 • rolled steel plate', col)
    # Pipe bundle, hexagonal packing.
    mb = on_pallet()
    r = 0.065
    for layer in range(4):
        n = 7 if layer % 2 == 0 else 6
        for k in range(n):
            y = (k - (n - 1) / 2) * 2 * r
            mb.cyl(r, 1.18, Vector((0, y, ph + r + layer * r * 1.732)), 'X', M['pipe'], 10)
    for x in (-0.4, 0.4):
        mb.box((0.04, 1.0, 0.5), Vector((x, 0, ph + 0.26)), M['strap'])
    out['pipe'] = mb.finish('Freight 4 • galvanised pipe bundle', col, smooth=True)
    # Bulk bag: bulged soft cube with lifting loops, built separately then merged.
    bag = bmesh.new()
    bmesh.ops.create_cube(bag, size=1.0)
    bmesh.ops.subdivide_edges(bag, edges=bag.edges[:], cuts=6, use_grid_fill=True)
    for v in bag.verts:
        c = v.co
        side = 1 - max(abs(c.x), abs(c.y)) * 2          # 1 at centre of a face, 0 at edges
        bulge = 1.0 + 0.10 * (1 - abs(2 * c.z)) * max(side, 0.0) ** 0.3
        v.co = Vector((c.x * 0.98 * bulge, c.y * 0.92 * bulge, c.z + 0.5 + ph))
    bag_mesh = D.meshes.new('tmp bag')
    bag.to_mesh(bag_mesh)
    bag.free()
    mb = on_pallet()
    mb.mesh_copy(bag_mesh, Vector((0, 0, 0)), lambda m: M['bag'])
    D.meshes.remove(bag_mesh)
    for sx in (-0.4, 0.4):
        for sy in (-0.36, 0.36):
            mb.box((0.05, 0.05, 0.16), Vector((sx, sy, ph + 1.06)), M['bag'])
    out['bag'] = mb.finish('Freight 5 • bulk bag of processed regolith', col, smooth=True)
    # Sintered regolith bricks.
    mb = on_pallet()
    for layer in range(6):
        for i in range(4):
            for j in range(6):
                shift = 0.075 if layer % 2 else 0.0          # running bond
                mb.box((0.28, 0.15, 0.1), Vector((-0.45 + i * 0.3 - shift, -0.39 + j * 0.156, ph + 0.05 + layer * 0.102)),
                       M['brick'])
    out['brick'] = mb.finish('Freight 6 • sintered regolith bricks', col)
    # Aluminium ingots, cross-stacked.
    mb = on_pallet()
    for layer in range(7):
        across = layer % 2
        for k in range(8 if not across else 10):
            off = (k - (7 if not across else 9) / 2) * (0.13 if not across else 0.11)
            c = Vector((0, off, ph + 0.04 + layer * 0.075)) if not across else Vector((off, 0, ph + 0.04 + layer * 0.075))
            mb.box((1.1, 0.1, 0.07) if not across else (0.1, 0.95, 0.07), c, M['ingot'])
    out['ingot'] = mb.finish('Freight 7 • aluminium ingots', col)
    return out


def forklift(col, M, load_mesh=None, name='Freight 8 • electric forklift'):
    mb = MeshBuilder()
    # Chassis and counterweight (forks point +X).
    mb.box((1.9, 1.1, 0.55), Vector((-0.2, 0, 0.55)), M['paint'])
    mb.box((0.5, 1.1, 0.75), Vector((-1.05, 0, 0.75)), M['paint'])
    mb.box((0.5, 0.5, 0.35), Vector((-0.4, 0, 1.0)), M['dark'])                  # seat
    for sx in (-0.95, 0.55):                                                      # overhead guard posts
        for sy in (-0.48, 0.48):
            mb.box((0.06, 0.06, 1.35), Vector((sx, sy, 1.5)), M['dark'])
    mb.box((1.6, 1.05, 0.05), Vector((-0.2, 0, 2.18)), M['dark'])
    mb.box((0.02, 0.9, 0.8), Vector((0.56, 0, 1.55)), M['glass'])
    for sy in (-0.35, 0.35):                                                      # mast rails
        mb.box((0.1, 0.1, 2.4), Vector((0.85, sy, 1.25)), M['dark'])
    lift = 0.35 if load_mesh else 0.08
    mb.box((0.08, 0.95, 0.5), Vector((0.95, 0, lift + 0.3)), M['dark'])        # carriage
    for sy in (-0.3, 0.3):
        mb.box((1.1, 0.12, 0.05), Vector((1.5, sy, lift)), M['dark'])          # tines
    for sx in (-0.85, 0.55):
        for sy in (-0.5, 0.5):
            mb.cyl(0.28, 0.2, Vector((sx, sy, 0.28)), 'Y', M['rubber'], 16)
    if load_mesh is not None:
        mb.mesh_copy(load_mesh, Vector((1.5, 0, lift + 0.03)), lambda m: m)
    return mb.finish(name, col)


# ---------------------------------------------------------------- layout
def layout(heights, old_points):
    rng = random.Random(21)
    count = {}
    for v in old_points:
        key = (round((v.x - ORIGIN - SPACING / 2) / SPACING), round((v.y - ORIGIN - SPACING / 2) / SPACING))
        count[key] = count.get(key, 0) + 1
    bays = sorted(k for k, c in count.items() if c >= 20)
    kinds = ['wrap1', 'wrap2', 'drum', 'steel', 'pipe', 'bag', 'brick', 'ingot']
    weights = [0.17, 0.13, 0.15, 0.12, 0.1, 0.13, 0.1, 0.1]
    cluster_kind = {}
    pts = []
    lifts = []
    for bx, by in bays:
        cx = ORIGIN + SPACING / 2 + bx * SPACING
        cy = ORIGIN + SPACING / 2 + by * SPACING
        if AISLE_Y[0] - BLOCK < cy < AISLE_Y[1] + BLOCK:
            continue
        ck = (bx // 2, by // 2)
        if ck not in cluster_kind:
            cluster_kind[ck] = rng.choices(range(8), weights)[0]
        base_kind = cluster_kind[ck]
        second = rng.choices(range(8), weights)[0] if rng.random() < 0.25 else base_kind
        rows = []
        y = -BLOCK
        while y + 2.1 <= BLOCK + 0.01:
            rows += [y + 0.525, y + 1.575]
            y += 5.7
        cols = int((2 * BLOCK) // 1.3)
        depletion = rng.random()
        for ri, ry in enumerate(rows):
            kind = base_kind if ri < len(rows) * 0.6 else second
            for ci in range(cols):
                rx = -BLOCK + 0.65 + ci * 1.3
                # Working face: the east end of some rows is partly picked.
                if ci > cols * (0.55 + 0.45 * depletion) and rng.random() < 0.7:
                    continue
                if rng.random() < 0.05:
                    continue
                nominal = heights[kind][1]
                levels = max(1, nominal - (1 if rng.random() < 0.3 else 0))
                yaw = (math.pi if rng.random() < 0.5 else 0.0) + rng.uniform(-0.03, 0.03)
                jitter = Vector((rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), 0))
                for lv in range(levels):
                    pts.append((Vector((cx + rx, cy + ry, lv * heights[kind][0])) + jitter, kind, yaw))
        # Forklifts in this bay's aisles.
        if rng.random() < 0.45:
            ai = rng.randrange(len(rows) // 2)
            ay = -BLOCK + ai * 5.7 + 2.1 + 1.8
            ax = rng.uniform(-BLOCK + 3, BLOCK - 3)
            loaded = rng.random() < 0.5
            lifts.append((Vector((cx + ax, cy + ay, 0)), 9 if loaded else 8,
                          rng.choice((0.0, math.pi)) + (math.pi / 2 if rng.random() < 0.4 else 0.0)))
    return pts + lifts, len(bays)


def main():
    M = materials()
    assets = gnkit.collection('ASSET • freight stacks', exclude=True)
    pallet = D.objects['Aluminum pallet • four opposed C channels.001']
    pallet_mesh = centred_copy(pallet)
    raw = raw_assets(assets, M, pallet_mesh)
    ordered = []
    for i, src in enumerate(('Cargo variant 1 • white wrapped equipment', 'Cargo variant 2 • white wrapped equipment',
                             'Cargo variant 3 • strapped supply drums')):
        me = centred_copy(D.objects[src])
        me.name = f'Freight {i} mesh'
        ordered.append(gnkit.new_object(f'Freight {i} • ' + src.split('• ')[1], assets, me))
    ordered += [raw[k] for k in ('steel', 'pipe', 'bag', 'brick', 'ingot')]
    ordered.append(forklift(assets, M))
    ordered.append(forklift(assets, M, ordered[0].data, 'Freight 9 • electric forklift carrying wrapped load'))
    heights = []
    for ob in ordered[:8]:
        h = max(v.co.z for v in ob.data.vertices) + 0.01
        nominal = 2 if h > 1.2 else (3 if h > 0.75 else 4)
        heights.append((h, nominal))
    heights[5] = (heights[5][0], 2)      # bulk bags: two high
    for ob in ordered:
        ob.location = (0, 0, -50)

    yard = D.objects['Cargo yard • instanced wrapped loads and barrels']
    old = [v.co.copy() for v in yard.data.vertices]
    pts, nbays = layout(heights, old)
    me = D.meshes.new('Freight yard • stack points')
    me.vertices.add(len(pts))
    me.vertices.foreach_set('co', [c for p, _, _ in pts for c in p])
    kind = me.attributes.new('kind', 'INT', 'POINT')
    kind.data.foreach_set('value', [k for _, k, _ in pts])
    yaw = me.attributes.new('yaw', 'FLOAT', 'POINT')
    yaw.data.foreach_set('value', [y for _, _, y in pts])
    old_mesh = yard.data
    yard.data = me
    if old_mesh.users == 0:
        D.meshes.remove(old_mesh)
    yard.name = 'Freight yard • stacked pallet blocks and forklifts'
    yard.modifiers.clear()

    t = gnkit.Tree('YEAR15 • stacked freight instances', inputs=[
        ('Viewport fraction', 'NodeSocketFloat', 0.15)])
    viewport = t.out(t.node('GeometryNodeIsViewport'))
    frac = t.make('GeometryNodeSwitch', props={'input_type': 'FLOAT'}, Switch=viewport)
    t.set(frac, 'False', 1.0)
    t.set(frac, 'True', t.inp('Viewport fraction'))
    thin = t.make('GeometryNodeDeleteGeometry', props={'domain': 'POINT'}, Geometry=t.inp('Geometry'),
                  Selection=t.math('GREATER_THAN', t.random('FLOAT', 0.0, 1.0, 2), t.out(frac)))
    col = t.make('GeometryNodeCollectionInfo', props={'transform_space': 'ORIGINAL'},
                 Collection=assets, Separate_Children=True, Reset_Children=True)
    inst = t.make('GeometryNodeInstanceOnPoints', Points=t.out(thin), Instance=t.out(col), Pick_Instance=True,
                  Instance_Index=t.named('kind', 'INT'), Rotation=t.combine(0.0, 0.0, t.named('yaw')))
    gnkit.modifier(yard, t.finish(t.out(inst)), 'Stacked freight • shared instances')
    out = sys.argv[sys.argv.index('--') + 1]
    print('FREIGHT points', len(pts), 'bays', nbays, 'heights', [(round(h, 2), n) for h, n in heights], flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('FREIGHT SAVED', out, flush=True)


if __name__ == '__main__':
    main()
