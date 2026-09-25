"""One-time change (2026-09-24): detailed residential buildings, towers and facades.

- Rebuilds the shared mesh SOURCE • three storey residential (all 218 homes
  update at once): recessed windows with reveals, frames, mullions and sills,
  floor bands, front balconies with glass balustrades, an entrance canopy,
  parapet, rooftop PV rows, HVAC units and a stair overrun.
- Adds three residential tower meshes (24, 31 and 38 storeys, up to ~130 m)
  built by the same generator, and swaps six home plots for towers.
- Materials: precast panel facade (joints, per-building tint, base dust,
  weathering streaks); ribbed metal cladding for the halls; reflective glazing
  with per-window interiors that light up at random when Night is on.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/photoreal_buildings.py -- out.blend
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from photoreal_freight import principled  # noqa: E402

D = bpy.data
SLOTS = ['facade', 'concrete', 'roof', 'glass', 'pv', 'steel', 'frame', 'balcony']
MATS = {}


# ---------------------------------------------------------------- geometry
class Shell:
    def __init__(self):
        self.bm = bmesh.new()
        self.seed = self.bm.faces.layers.float.new('window_seed')   # per-pane random for lit interiors
        self.rng = random.Random(1)

    def quad(self, pts, slot):
        f = self.bm.faces.new([self.bm.verts.new(p) for p in pts])
        f.material_index = SLOTS.index(slot)
        return f

    def box(self, size, center, slot):
        sx, sy, sz = (s / 2 for s in size)
        c = Vector(center)
        v = [self.bm.verts.new(c + Vector((x, y, z))) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
        for idx in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            f = self.bm.faces.new([v[i] for i in idx])
            f.material_index = SLOTS.index(slot)

    def finish(self, name):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = D.meshes.get(name) or D.meshes.new(name)
        # Set slots first: Mesh.materials.clear() resets every face's material index.
        me.materials.clear()
        for slot in SLOTS:
            me.materials.append(MATS[slot])
        self.bm.to_mesh(me)
        self.bm.free()
        return me


def facade(sh, origin, u_dir, n, width, floors, fh, win_u, win_w, win_h, sill, top, door_u=None):
    """One wall: spandrels, piers and lintels around recessed windows."""
    up = Vector((0, 0, 1))
    depth = 0.2

    def P(u, v, d=0.0):
        return origin + u_dir * u + up * v - n * d

    def rect(u0, u1, v0, v1, slot, d=0.0):
        if u1 - u0 > 1e-4 and v1 - v0 > 1e-4:
            sh.quad([P(u0, v0, d), P(u1, v0, d), P(u1, v1, d), P(u0, v1, d)], slot)

    half = width / 2
    for f in range(floors):
        v0 = f * fh
        openings = []
        for u in win_u:
            if f == 0 and door_u is not None and abs(u - door_u) < 1e-3:
                openings.append((u - 1.3, u + 1.3, v0 + 0.05, v0 + 2.7))
            else:
                openings.append((u - win_w / 2, u + win_w / 2, v0 + sill, v0 + sill + win_h))
        lo = min(o[2] for o in openings) if openings else v0
        hi = max(o[3] for o in openings) if openings else v0 + fh
        rect(-half, half, v0, lo, 'facade')
        rect(-half, half, hi, v0 + fh, 'facade')
        edges = [-half] + [x for o in openings for x in (o[0], o[1])] + [half]
        for a, b in zip(edges[0::2], edges[1::2]):
            rect(a, b, lo, hi, 'facade')
        for u0, u1, a, b in openings:
            rect(u0, u1, lo, a, 'facade')          # below a window inside the band (doors are full height)
            rect(u0, u1, b, hi, 'facade')
            # Reveals, then glass at the back.
            for q in ((P(u0, a), P(u1, a), P(u1, a, depth), P(u0, a, depth)),
                      (P(u1, b), P(u0, b), P(u0, b, depth), P(u1, b, depth)),
                      (P(u0, b), P(u0, a), P(u0, a, depth), P(u0, b, depth)),
                      (P(u1, a), P(u1, b), P(u1, b, depth), P(u1, a, depth))):
                sh.quad(list(q), 'facade')
            before = len(sh.bm.faces)
            rect(u0, u1, a, b, 'glass', depth)
            sh.bm.faces.ensure_lookup_table()
            for f in sh.bm.faces[before:]:
                f[sh.seed] = sh.rng.random()
            fw = 0.06
            mid = (u0 + u1) / 2
            for c, size in (((mid, a + fw / 2), (u1 - u0, fw)), ((mid, b - fw / 2), (u1 - u0, fw)),
                            ((u0 + fw / 2, (a + b) / 2), (fw, b - a)), ((u1 - fw / 2, (a + b) / 2), (fw, b - a)),
                            ((mid, (a + b) / 2), (0.05, b - a))):
                centre = P(c[0], c[1], depth - 0.04)
                sz = u_dir * size[0] + up * size[1] + n * 0.08
                sh.box((abs(sz.x) or 0.08, abs(sz.y) or 0.08, abs(sz.z)), centre, 'frame')
            if b - a < 2.5:                               # window sill
                sz = u_dir * (u1 - u0 + 0.12) + n * 0.28
                sh.box((abs(sz.x) or 0.28, abs(sz.y) or 0.28, 0.05), P(mid, a - 0.03, -0.06), 'concrete')
    # Parapet above the roof.
    rect(-half, half, floors * fh, floors * fh + top, 'facade')


def building(name, w, d, floors, fh=3.4, spacing=4.0, balconies=True, towers=False):
    sh = Shell()
    H = floors * fh
    top = 1.0
    sh.box((w + 0.6, d + 0.6, 0.3), (0, 0, 0.15), 'concrete')
    sides = [  # origin (left end at ground), direction along wall, outward normal, width
        (Vector((-w / 2, -d / 2, 0.3)), Vector((1, 0, 0)), Vector((0, -1, 0)), w),
        (Vector((w / 2, d / 2, 0.3)), Vector((-1, 0, 0)), Vector((0, 1, 0)), w),
        (Vector((w / 2, -d / 2, 0.3)), Vector((0, 1, 0)), Vector((1, 0, 0)), d),
        (Vector((-w / 2, d / 2, 0.3)), Vector((0, -1, 0)), Vector((-1, 0, 0)), d),
    ]
    for i, (o, udir, n, width) in enumerate(sides):
        count = max(1, int((width - 2) // spacing))
        us = [(-(count - 1) / 2 + k) * spacing for k in range(count)]
        centre = o + udir * (width / 2)
        facade(sh, centre, udir, n, width, floors, fh, us, 1.6 if not towers else 1.9, 1.9 if not towers else 2.3,
               0.9 if not towers else 0.7, top, door_u=(min(us, key=abs) if i == 0 else None))
        # Floor bands.
        for f in range(1, floors + 1):
            c = centre + Vector((0, 0, f * fh)) + n * 0.06
            sz = udir * (width + 0.12) + n * 0.12
            sh.box((abs(sz.x), abs(sz.y), 0.24), c, 'concrete')
        # Balconies on the front (and back of towers), every other window.
        if balconies and (i == 0 or (towers and i == 1)):
            for f in range(1, floors):
                for k, u in enumerate(us):
                    if (k + f) % 2 or (towers and f % 1):
                        continue
                    base = centre + udir * u + Vector((0, 0, f * fh)) + n * 0.7
                    sz = udir * 3.0 + n * 1.4
                    sh.box((abs(sz.x), abs(sz.y), 0.18), base, 'concrete')
                    # glass balustrade: front + two ends
                    fr = base + n * 0.68 + Vector((0, 0, 0.6))
                    sz = udir * 3.0 + n * 0.02
                    sh.box((abs(sz.x), abs(sz.y), 1.0), fr, 'balcony')
                    for s in (-1, 1):
                        e = base + udir * (s * 1.49) + Vector((0, 0, 0.6))
                        sz = udir * 0.02 + n * 1.36
                        sh.box((abs(sz.x), abs(sz.y), 1.0), e, 'balcony')
                    rail = fr + Vector((0, 0, 0.52))
                    sz = udir * 3.04 + n * 0.06
                    sh.box((abs(sz.x), abs(sz.y), 0.05), rail, 'frame')
        if i == 0:   # entrance canopy
            door = min(us, key=abs)
            c = centre + udir * door + Vector((0, 0, 3.0)) + n * 1.0
            sz = udir * 4.0 + n * 2.0
            sh.box((abs(sz.x), abs(sz.y), 0.2), c, 'frame')
    # Roof slab (just below the parapet top), parapet inner faces and cap.
    z = H + 0.3
    sh.quad([Vector((-w / 2, -d / 2, z)), Vector((w / 2, -d / 2, z)), Vector((w / 2, d / 2, z)),
             Vector((-w / 2, d / 2, z))], 'roof')
    for sx, sy, lx, ly in ((0, -d / 2 + 0.15, w, 0.3), (0, d / 2 - 0.15, w, 0.3),
                           (-w / 2 + 0.15, 0, 0.3, d), (w / 2 - 0.15, 0, 0.3, d)):
        sh.box((lx, ly, top), (sx, sy, z + top / 2), 'facade')
        sh.box((lx + 0.1, ly + 0.1, 0.08), (sx, sy, z + top + 0.04), 'concrete')
    # Rooftop: PV rows, HVAC units, stair/lift overrun.
    rng = random.Random(len(name))
    rows = max(2, int((d - 6) // 2.6))
    for r in range(rows):
        y = -d / 2 + 2.5 + r * 2.6
        for seg in range(max(1, int((w * 0.55) // 6))):
            x = -w / 2 + 3 + seg * 6.2
            c = Vector((x + 3, y, z + 0.45))
            sh.box((5.8, 1.6, 0.05), c, 'pv')
            sh.box((5.8, 0.05, 0.4), c + Vector((0, -0.75, -0.25)), 'steel')
    for k in range(3 if towers else 2):
        x = w / 2 - 4 - k * 4.5
        sh.box((3.2, 2.2, 1.6), (x, d / 2 - 3.5, z + 0.8), 'steel')
        sh.box((1.2, 1.2, 0.2), (x - 0.6, d / 2 - 3.5, z + 1.7), 'roof')
    sh.box((4.5, 3.5, 3.2), (w / 2 - 5, -d / 2 + 4, z + 1.6), 'facade')
    return sh.finish(name)


# ---------------------------------------------------------------- materials
def tinted_facade():
    """Precast panels: per-building tint, panel joints, base dust, streaks."""
    m = D.materials['Colony • ceramic coated facade']
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial')
    b = N.new('ShaderNodeBsdfPrincipled')
    L.new(b.outputs[0], out.inputs[0])
    tc = N.new('ShaderNodeTexCoord')
    info = N.new('ShaderNodeObjectInfo')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Object'], sep.inputs[0])

    def m_(op, a, b_=None):
        n = N.new('ShaderNodeMath')
        n.operation = op
        for i, v in enumerate((a, b_)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    def mix(a, b_, fac, blend='MIX'):
        n = N.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = blend
        s = {x.identifier: x for x in n.inputs}
        for k, v in (('A_Color', a), ('B_Color', b_), ('Factor_Float', fac)):
            if isinstance(v, tuple):
                s[k].default_value = (*v, 1)
            elif isinstance(v, (int, float)):
                s[k].default_value = v
            else:
                L.new(v, s[k])
        return next(x for x in n.outputs if x.identifier == 'Result_Color')

    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    palette = [(0.78, 0.76, 0.72), (0.70, 0.68, 0.64), (0.74, 0.66, 0.55), (0.66, 0.50, 0.40),
               (0.62, 0.66, 0.62), (0.80, 0.79, 0.77), (0.55, 0.56, 0.58), (0.72, 0.62, 0.50)]
    cr = ramp.color_ramp
    while len(cr.elements) < len(palette):
        cr.elements.new(0.5)
    for i, (e, c) in enumerate(zip(cr.elements, palette)):
        e.position = i / len(palette)
        e.color = (*c, 1)
    L.new(info.outputs['Random'], ramp.inputs['Fac'])
    x, y, z = sep.outputs['X'], sep.outputs['Y'], sep.outputs['Z']
    along = m_('ADD', x, y)
    # Panel joints every 3.0 m horizontally and 1.7 m vertically (two per storey).
    def joint(coord, period, width):
        f = m_('FRACT', m_('DIVIDE', coord, period))
        return m_('LESS_THAN', m_('MULTIPLY', m_('MINIMUM', f, m_('SUBTRACT', 1.0, f)), period), width)
    joints = m_('MAXIMUM', joint(along, 3.0, 0.012), joint(z, 1.7, 0.012))
    # Per-panel tone from a white noise of the panel index.
    cell = N.new('ShaderNodeCombineXYZ')
    L.new(m_('FLOOR', m_('DIVIDE', along, 3.0)), cell.inputs[0])
    L.new(m_('FLOOR', m_('DIVIDE', z, 1.7)), cell.inputs[1])
    L.new(info.outputs['Random'], cell.inputs[2])
    wn = N.new('ShaderNodeTexWhiteNoise')
    wn.noise_dimensions = '3D'
    L.new(cell.outputs[0], wn.inputs['Vector'])
    tone = m_('ADD', 0.93, m_('MULTIPLY', wn.outputs['Value'], 0.12))
    base = mix(ramp.outputs['Color'], (1, 1, 1), 1.0, 'MULTIPLY')
    L.new(tone, next(s for s in base.node.inputs if s.identifier == 'B_Color'))
    base = mix(base, (0.25, 0.24, 0.23), m_('MULTIPLY', joints, 0.7))
    # Streaks: noise stretched vertically.
    mapping = N.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (3.0, 3.0, 0.25)
    L.new(tc.outputs['Object'], mapping.inputs['Vector'])
    streak = N.new('ShaderNodeTexNoise')
    streak.inputs['Scale'].default_value = 2.0
    streak.inputs['Detail'].default_value = 6.0
    L.new(mapping.outputs[0], streak.inputs['Vector'])
    base = mix(base, (0.45, 0.40, 0.36), m_('MULTIPLY', m_('MAXIMUM', m_('SUBTRACT', streak.outputs['Fac'], 0.55), 0.0), 0.8))
    # Settled regolith dust at the base.
    dust = m_('SUBTRACT', 1.0, m_('MINIMUM', m_('DIVIDE', z, 1.4), 1.0))
    base = mix(base, (0.36, 0.2, 0.11), m_('MULTIPLY', dust, 0.55))
    L.new(base, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.72
    bump = N.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.02
    L.new(m_('SUBTRACT', 1.0, joints), bump.inputs['Height'])
    L.new(bump.outputs[0], b.inputs['Normal'])
    return m


def ribbed_cladding():
    m = D.materials.get('Colony • ribbed metal cladding') or D.materials.new('Colony • ribbed metal cladding')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial')
    b = N.new('ShaderNodeBsdfPrincipled')
    L.new(b.outputs[0], out.inputs[0])
    tc = N.new('ShaderNodeTexCoord')
    info = N.new('ShaderNodeObjectInfo')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Object'], sep.inputs[0])
    add = N.new('ShaderNodeMath')
    add.operation = 'ADD'
    L.new(sep.outputs['X'], add.inputs[0])
    L.new(sep.outputs['Y'], add.inputs[1])
    wave = N.new('ShaderNodeTexWave')
    wave.wave_type = 'BANDS'
    wave.wave_profile = 'SIN'
    wave.bands_direction = 'X'
    wave.inputs['Scale'].default_value = 1.0
    comb = N.new('ShaderNodeCombineXYZ')
    scl = N.new('ShaderNodeMath')
    scl.operation = 'MULTIPLY'
    scl.inputs[1].default_value = 1.57    # Wave bands repeat every 2π/20 units → 0.2 m rib pitch
    L.new(add.outputs[0], scl.inputs[0])
    L.new(scl.outputs[0], comb.inputs[0])
    L.new(comb.outputs[0], wave.inputs['Vector'])
    bump = N.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.6
    bump.inputs['Distance'].default_value = 0.02
    L.new(wave.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs[0], b.inputs['Normal'])
    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    palette = [(0.72, 0.72, 0.70), (0.55, 0.60, 0.64), (0.66, 0.62, 0.52), (0.80, 0.80, 0.78), (0.45, 0.47, 0.48)]
    cr = ramp.color_ramp
    while len(cr.elements) < len(palette):
        cr.elements.new(0.5)
    for i, (e, c) in enumerate(zip(cr.elements, palette)):
        e.position = i / len(palette)
        e.color = (*c, 1)
    L.new(info.outputs['Random'], ramp.inputs['Fac'])
    dustmix = N.new('ShaderNodeMix')
    dustmix.data_type = 'RGBA'
    ds = {s.identifier: s for s in dustmix.inputs}
    L.new(ramp.outputs['Color'], ds['A_Color'])
    ds['B_Color'].default_value = (0.36, 0.2, 0.11, 1)
    dz = N.new('ShaderNodeMapRange')
    L.new(sep.outputs['Z'], dz.inputs['Value'])
    dz.inputs['From Min'].default_value = 0.0
    dz.inputs['From Max'].default_value = 2.0
    dz.inputs['To Min'].default_value = 0.6
    dz.inputs['To Max'].default_value = 0.0
    L.new(dz.outputs['Result'], ds['Factor_Float'])
    L.new(next(s for s in dustmix.outputs if s.identifier == 'Result_Color'), b.inputs['Base Color'])
    b.inputs['Metallic'].default_value = 0.6
    b.inputs['Roughness'].default_value = 0.42
    return m


def glazing():
    """Keep the existing BSDF node (its Emission Strength is driven by Night)."""
    m = D.materials['Colony • window glazing']
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = N['Principled BSDF']
    for n in list(N):
        if n not in (b,) and n.type != 'OUTPUT_MATERIAL':
            N.remove(n)
    info = N.new('ShaderNodeObjectInfo')
    pane = N.new('ShaderNodeAttribute')
    pane.attribute_type = 'GEOMETRY'
    pane.attribute_name = 'window_seed'
    cell = N.new('ShaderNodeCombineXYZ')
    L.new(pane.outputs['Fac'], cell.inputs[0])
    L.new(info.outputs['Random'], cell.inputs[1])
    wn = N.new('ShaderNodeTexWhiteNoise')
    wn.noise_dimensions = '3D'
    L.new(cell.outputs[0], wn.inputs['Vector'])
    sc = N.new('ShaderNodeSeparateColor')
    L.new(wn.outputs['Color'], sc.inputs[0])
    lit = N.new('ShaderNodeMath')
    lit.operation = 'LESS_THAN'
    L.new(sc.outputs['Red'], lit.inputs[0])
    lit.inputs[1].default_value = 0.68
    warm = N.new('ShaderNodeValToRGB')
    cr = warm.color_ramp
    cr.elements[0].color = (1.0, 0.62, 0.32, 1)
    cr.elements[1].color = (0.85, 0.9, 1.0, 1)
    L.new(sc.outputs['Green'], warm.inputs['Fac'])
    em = N.new('ShaderNodeMix')
    em.data_type = 'RGBA'
    em.blend_type = 'MULTIPLY'
    es = {s.identifier: s for s in em.inputs}
    es['Factor_Float'].default_value = 1.0
    L.new(warm.outputs['Color'], es['A_Color'])
    L.new(lit.outputs[0], es['B_Color'])
    L.new(next(s for s in em.outputs if s.identifier == 'Result_Color'), b.inputs['Emission Color'])
    interior = N.new('ShaderNodeValToRGB')
    ic = interior.color_ramp
    ic.elements[0].color = (0.012, 0.014, 0.018, 1)
    ic.elements[1].color = (0.06, 0.05, 0.045, 1)
    L.new(sc.outputs['Blue'], interior.inputs['Fac'])
    L.new(interior.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.03
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Specular IOR Level'].default_value = 0.55
    b.inputs['IOR'].default_value = 1.52
    return m


def main():
    mats = MATS
    mats.update({
        'facade': tinted_facade(),
        'concrete': D.materials['Perimeter foundation • cast concrete'],
        'roof': D.materials['Colony • dark roof and machinery'],
        'glass': glazing(),
        'pv': D.materials['Colony • roof photovoltaics'],
        'steel': D.materials['Colony • brushed stainless'],
        'frame': principled('Colony • anodised window frame', (0.05, 0.045, 0.04), 0.35, 0.8),
        'balcony': principled('Colony • balcony glass', (0.55, 0.62, 0.6), 0.05, 0.0),
    })
    bal = mats['balcony'].node_tree.nodes['Principled BSDF']
    bal.inputs['Transmission Weight'].default_value = 0.85
    bal.inputs['Alpha'].default_value = 1.0

    home = building('SOURCE • three storey residential', 34.0, 20.0, 3)
    towers = []
    for floors in (24, 31, 38):
        towers.append(building(f'SOURCE • residential tower {floors} storeys', 30.0, 20.0, floors, towers=True))
    # Six towers on existing home plots, spread across the residential quarter.
    homes = sorted((o for o in D.collections['YEAR 15 • Homes'].objects if o.type == 'MESH'),
                   key=lambda o: (round(o.location.y), round(o.location.x)))
    picks = [homes[int(i * (len(homes) - 1) / 5)] for i in range(6)]
    for i, ob in enumerate(picks):
        ob.data = towers[i % 3]
        ob.name = f'Residential tower • {ob.data.name.split("tower ")[1]}'
    # Halls: ribbed cladding on their wall faces.
    rib = ribbed_cladding()
    for name in ('SOURCE • long factory hall', 'SOURCE • logistics hall'):
        me = D.meshes[name]
        for i, m in enumerate(me.materials):
            if m and m.name == 'Colony • ceramic coated facade':
                me.materials[i] = rib
    out = sys.argv[sys.argv.index('--') + 1]
    print('BUILDINGS home faces', len(home.polygons), 'towers', [len(t.polygons) for t in towers],
          'tower plots', [(round(o.location.x), round(o.location.y)) for o in picks], flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('BUILDINGS SAVED', out, flush=True)


if __name__ == '__main__':
    main()
