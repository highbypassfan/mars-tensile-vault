"""Export a web (three.js) version of the daytime scene.

Run with Blender on the share file. Nothing is saved back to the blend.

  blender -b --factory-startup --disable-autoexec mars-tensile-vault.blend \
      --python tools/web_export.py -- --out <dir> [--geometry] [--bake] [--sky] [--quick]

--geometry  vault.glb: decimated, instanced models with simple PBR materials
            (lit in the browser) and terrain meshes (drawn with the baked ground).
--bake      top-down Cycles renders of the ground at 15:00 (city, near, far).
            Buildings, anchors, membrane etc. are hidden from the camera but still
            cast shadows, so their shadows and the membrane's shading are baked in.
--sky       360° day sky (world + haze) as an equirectangular image.
Also writes scene.json (bake extents, sun, cameras).
"""
import argparse
import json
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

D = bpy.data

# Bake/terrain extents (x0, y0, size) in metres.
CITY = (-1500.0, -1500.0, 3000.0)
NEAR = (-9500.0, -7000.0, 14000.0)
FAR = (-80000.0, -80000.0, 160000.0)


# ------------------------------------------------------------------ setup
def controls():
    mod = D.objects['CONTROLS • Mars vault'].modifiers['CONTROLS']
    ids = {i.name: i.identifier for i in mod.node_group.interface.items_tree if i.item_type == 'SOCKET'}
    return mod, ids


def set_control(name, value):
    mod, ids = controls()
    getattr(mod.properties.inputs, ids[name]).value = value


def set_input(ob, name, value):
    for m in ob.modifiers:
        if m.type == 'NODES' and m.node_group:
            for it in m.node_group.interface.items_tree:
                if it.item_type == 'SOCKET' and it.name == name:
                    getattr(m.properties.inputs, it.identifier).value = value


def prepare(people_fraction=0.13):
    set_control('Night', False)
    set_control('People', True)
    set_control('Viewport tether LOD', True)
    for k, v in (('Viewport tether every L', 1), ('Viewport tether every W', 1), ('Viewport tether branches', 6),
                 ('Viewport tether sides', 3), ('Viewport ring segments', 12)):
        set_control(k, v)
    set_input(membrane(), 'Clear viewport membrane', False)
    set_input(D.objects['People • residents and workers'], 'Viewport fraction', people_fraction)
    set_input(D.objects['Freight yard • stacked pallet blocks and forklifts'], 'Viewport fraction', 1.0)
    for o in D.objects:
        o.update_tag()
    bpy.context.view_layer.update()


def membrane():
    return next(o for o in D.objects if o.name.startswith('MEMBRANE'))


def cage():
    return next(o for o in D.objects if o.name.startswith('TENSILE'))


# ------------------------------------------------------------------ materials
WEB_COLORS = {  # name fragment -> (base color, roughness, metallic)
    'ceramic coated facade': ((0.72, 0.67, 0.60), 0.8, 0.0),
    'cast concrete': ((0.50, 0.48, 0.45), 0.9, 0.0),
    'dark roof': ((0.07, 0.07, 0.075), 0.7, 0.2),
    'window glazing': ((0.035, 0.04, 0.045), 0.08, 0.5),
    'roof photovoltaics': ((0.02, 0.03, 0.07), 0.2, 0.3),
    'brushed stainless': ((0.62, 0.62, 0.64), 0.35, 1.0),
    'anodised window frame': ((0.05, 0.045, 0.04), 0.35, 0.8),
    'balcony glass': ((0.45, 0.52, 0.52), 0.1, 0.3),
    'safety ochre': ((0.70, 0.45, 0.10), 0.5, 0.0),
    'ribbed metal cladding': ((0.68, 0.68, 0.66), 0.45, 0.6),
    'galvanized steel': ((0.55, 0.56, 0.57), 0.4, 1.0),
    'LED diffuser': ((0.85, 0.82, 0.75), 0.5, 0.0),
    'Anchor • steel': ((0.45, 0.46, 0.47), 0.4, 1.0),
    'cable': ((0.30, 0.30, 0.31), 0.5, 1.0),
    'Anchor • foundation': ((0.50, 0.48, 0.45), 0.9, 0.0),
    'Airlock • shell': ((0.78, 0.77, 0.74), 0.5, 0.2),
    'view port': ((0.04, 0.05, 0.06), 0.1, 0.5),
    'Pressure wall': ((0.92, 0.9, 0.86), 0.2, 0.0),
    'Live membrane': ((0.92, 0.9, 0.86), 0.2, 0.0),
    'battery container': ((0.62, 0.64, 0.64), 0.45, 0.0),
    'equipment enclosure': ((0.72, 0.72, 0.70), 0.5, 0.0),
    'transformer grey': ((0.23, 0.26, 0.27), 0.45, 0.3),
    'louvre': ((0.06, 0.06, 0.065), 0.6, 0.6),
    'chain-link': ((0.4, 0.4, 0.42), 0.5, 1.0),
    'galvanised racking': ((0.5, 0.51, 0.52), 0.45, 1.0),
    'porcelain': ((0.45, 0.2, 0.1), 0.2, 0.0),
    'dark brown compacted regolith': ((0.16, 0.09, 0.05), 0.95, 0.0),
    'white protective wrap': ((0.85, 0.85, 0.83), 0.6, 0.0),
    'Forklift • safety yellow': ((0.75, 0.48, 0.02), 0.4, 0.0),
    'bulk bag': ((0.78, 0.75, 0.68), 0.85, 0.0),
    'sintered regolith brick': ((0.26, 0.10, 0.05), 0.9, 0.0),
    'aluminium ingot': ((0.80, 0.80, 0.80), 0.32, 1.0),
    'hot-rolled steel': ((0.09, 0.085, 0.08), 0.55, 0.9),
    'galvanised pipe': ((0.55, 0.56, 0.57), 0.38, 1.0),
    'supply drums': ((0.25, 0.35, 0.45), 0.5, 0.3),
}


def web_material(src):
    """A simple Principled copy of `src` that the glTF exporter understands."""
    name = 'WEB • ' + src.name
    if name in D.materials:
        return D.materials[name]
    nt = src.node_tree if src.use_nodes else None
    bsdf = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None) if nt else None
    # Keep materials whose base colour is a plain image texture (people, rover, ships).
    if bsdf and bsdf.inputs['Base Color'].is_linked and \
            bsdf.inputs['Base Color'].links[0].from_node.bl_idname == 'ShaderNodeTexImage':
        return src
    color, rough, metal = None, 0.6, 0.0
    for key, val in WEB_COLORS.items():
        if key in src.name:
            color, rough, metal = val
            break
    if color is None:
        if bsdf and not bsdf.inputs['Base Color'].is_linked:
            color = tuple(bsdf.inputs['Base Color'].default_value[:3])
            rough = bsdf.inputs['Roughness'].default_value if not bsdf.inputs['Roughness'].is_linked else 0.6
            metal = bsdf.inputs['Metallic'].default_value if not bsdf.inputs['Metallic'].is_linked else 0.0
        else:
            color = tuple(src.diffuse_color[:3])
    m = D.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


def webify_mesh(me):
    for i, m in enumerate(me.materials):
        if m:
            me.materials[i] = web_material(m)


# ------------------------------------------------------------------ geometry helpers
WEB = None


def web_collection():
    global WEB
    if WEB is None:
        WEB = D.collections.new('WEB EXPORT')
        bpy.context.scene.collection.children.link(WEB)
    return WEB


def mesh_object(name, me, matrix=Matrix()):
    ob = D.objects.new(name, me)
    ob.matrix_world = matrix
    web_collection().objects.link(ob)
    return ob


def evaluated_copy(ob, name, dg):
    me = D.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
    me.name = name
    webify_mesh(me)
    return me


def decimate(me, ratio):
    if ratio >= 1.0:
        return me
    tmp = D.objects.new('tmp decimate', me)
    bpy.context.scene.collection.objects.link(tmp)
    mod = tmp.modifiers.new('d', 'DECIMATE')
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    out = D.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    out.name = me.name
    D.objects.remove(tmp)
    return out


def split_by_material(me, keep):
    """Return a copy of `me` with only faces whose material name contains any of `keep`."""
    bm = bmesh.new()
    bm.from_mesh(me)
    names = [m.name if m else '' for m in me.materials]
    doomed = [f for f in bm.faces if not any(k in names[f.material_index] for k in keep)]
    bmesh.ops.delete(bm, geom=doomed, context='FACES')
    out = D.meshes.new(me.name + ' part')
    bm.to_mesh(out)
    bm.free()
    for m in me.materials:
        out.materials.append(m)
    return out


def instancer(name, mesh_by_key, items):
    """GN instancer: items = [(key, matrix)], exported with EXT_mesh_gpu_instancing."""
    keys = sorted(mesh_by_key)
    pc = D.meshes.new(name + ' points')
    pc.vertices.add(len(items))
    pc.vertices.foreach_set('co', [c for _, m in items for c in m.to_translation()])
    for attr, fn in (('rot', lambda m: m.to_euler()), ('scl', lambda m: m.to_scale())):
        a = pc.attributes.new(attr, 'FLOAT_VECTOR', 'POINT')
        a.data.foreach_set('vector', [c for _, m in items for c in fn(m)])
    idx = pc.attributes.new('kind', 'INT', 'POINT')
    idx.data.foreach_set('value', [keys.index(k) for k, _ in items])
    ob = mesh_object(name, pc)
    col = D.collections.new(name + ' parts')
    for i, k in enumerate(keys):
        part = D.objects.new(f'{i:02d} {k}', mesh_by_key[k])
        col.objects.link(part)
    ng = D.node_groups.new(name + ' instancer', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    ci = N.new('GeometryNodeCollectionInfo')
    ci.inputs['Collection'].default_value = col
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    iop = N.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True

    def named(n, t):
        x = N.new('GeometryNodeInputNamedAttribute')
        x.data_type = t
        x.inputs['Name'].default_value = n
        return x.outputs['Attribute']
    m2p = N.new('GeometryNodeMeshToPoints')
    L.new(gi.outputs[0], m2p.inputs['Mesh'])
    L.new(m2p.outputs[0], iop.inputs['Points'])
    L.new(ci.outputs[0], iop.inputs['Instance'])
    L.new(named('kind', 'INT'), iop.inputs['Instance Index'])
    L.new(named('rot', 'FLOAT_VECTOR'), iop.inputs['Rotation'])
    L.new(named('scl', 'FLOAT_VECTOR'), iop.inputs['Scale'])
    L.new(iop.outputs[0], go.inputs[0])
    m = ob.modifiers.new('instances', 'NODES')
    m.node_group = ng
    return ob


def instances_of(dg, parent, mesh_filter=None, ratio=1.0):
    """(meshes by key, [(key, matrix)]) for the instances a GN object emits.

    Instance geometry may exist only inside the evaluated object, so meshes are
    copied from the evaluated instance while iterating."""
    meshes, items = {}, []
    for di in dg.object_instances:
        if di.is_instance and di.parent and di.parent.original == parent and di.object.type == 'MESH':
            data = di.object.data
            if mesh_filter is not None and not mesh_filter(data):
                continue
            key = f'{data.name} {data.as_pointer():x}'
            if key not in meshes:
                me = D.meshes.new_from_object(di.object)
                me.name = 'WEB ' + data.name
                webify_mesh(me)
                meshes[key] = me
            items.append((key, di.matrix_world.copy()))
    for key in list(meshes):
        meshes[key] = decimate(meshes[key], ratio)
    return meshes, items


# ------------------------------------------------------------------ terrain
def ground_bvh(dg, objects):
    verts, polys = [], []
    for ob in objects:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def terrain_grid(name, bvh, x0, y0, size, n, hole=None, base_z=0.0):
    step = size / n
    heights = []
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = x0 + i * step, y0 + j * step
            hit = bvh.ray_cast(Vector((x, y, 10000.0)), Vector((0, 0, -1)), 30000.0)
            heights.append(hit[0].z if hit[0] is not None else base_z)
    bm = bmesh.new()
    vs = [bm.verts.new((x0 + i * step, y0 + j * step, heights[j * (n + 1) + i]))
          for j in range(n + 1) for i in range(n + 1)]
    for j in range(n):
        for i in range(n):
            if hole:
                cx, cy = x0 + (i + 0.5) * step, y0 + (j + 0.5) * step
                if hole[0] < cx < hole[0] + hole[2] and hole[1] < cy < hole[1] + hole[2]:
                    continue
            a = j * (n + 1) + i
            bm.faces.new((vs[a], vs[a + 1], vs[a + n + 2], vs[a + n + 1]))
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    me = D.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return mesh_object(name, me)


# ------------------------------------------------------------------ geometry export
SKIP_REALIZED = (
    'CONTROLS', 'Atmosphere', 'Mars valley', 'Valley', 'Mesa', 'Grass', 'Compacted regolith', 'Concrete • walkable',
    'Freight • continuous', 'Freight • raised', 'Roads', 'Landing field', 'Interior ship foundation', 'Rock field',
    'Solar farm • east-west', 'Solar farm • access', 'Power cable', 'People', 'Freight yard', 'MEMBRANE', 'TENSILE',
    'ANCHOR BUILDER', 'Compacted yard gravel', 'ARCHIVE', 'SOURCE', 'ASSET', 'Exterior eroded', 'EXTERIOR',
    'Ring light', 'blade', 'Cargo variant', 'Aluminum pallet', 'Worker', 'Person', 'PERSON',
)
OBSERVER_PARTS = ('Person • Body', 'Person • Head', 'Person • clothing', 'Person • shoe_L', 'Person • shoe_R',
                  'Person • LeftCornea', 'Person • RightCornea')

DECIMATE = {'Starship': 0.08, 'Curiosity': 0.35, 'Heritage': 0.08, 'Homes': 0.55, 'Residential tower': 0.55}


USE_GPU = False


def set_device(scene):
    """CPU by default; --gpu renders on the GPU (HIP, then OptiX/CUDA, whichever Blender finds)."""
    scene.cycles.device = 'CPU'
    if not USE_GPU:
        return
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('HIP', 'OPTIX', 'CUDA', 'ONEAPI', 'METAL'):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == kind]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = 'GPU'
            print('RENDER DEVICE', kind, [d.name for d in gpus], flush=True)
            return
    print('RENDER DEVICE: no GPU found, using CPU', flush=True)


def bake_colors(objects, px):
    """Cycles diffuse-colour bake of each material on `objects` (as posed/tinted in the scene)
    into its own packed image; returns {material name: image}."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    set_device(scene)
    scene.cycles.samples = 4
    bk = scene.render.bake
    bk.use_pass_direct = bk.use_pass_indirect = False
    bk.use_pass_color = True
    bk.margin = 4
    bk.use_clear = True
    images, added = {}, []
    for ob in objects:
        for m in (sl.material for sl in ob.material_slots):     # object-linked slots too (the shirt)
            if not m or m.name in images:
                continue
            img = D.images.new('WEB bake ' + m.name, px, px)
            n = m.node_tree.nodes.new('ShaderNodeTexImage')
            n.image = img
            m.node_tree.nodes.active = n
            images[m.name] = img
            added.append((m, n))
    for ob in scene.objects:
        ob.select_set(False)
    for ob in objects:
        ob.hide_set(False)
        ob.select_set(True)
        uv = ob.data.uv_layers
        render_uv = next((u for u in uv if u.active_render), None)
        if render_uv:
            uv.active = render_uv
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.bake(type='DIFFUSE')
    for m, n in added:
        m.node_tree.nodes.remove(n)
    for img in images.values():
        img.pack()
    return images


def baked_material(name, img, rough=0.7):
    m = D.materials.new('WEB • ' + name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = img
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    return m


def baked_copy(ob, name, dg, images, ratio=1.0):
    """Evaluated (posed) copy of `ob` with only its render UV map and the baked materials."""
    me = D.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
    me.name = name
    keep = next((u.name for u in me.uv_layers if u.active_render), None)
    for u in [u for u in me.uv_layers if u.name != keep]:
        me.uv_layers.remove(u)
    for i, sl in enumerate(ob.material_slots):
        m = sl.material
        if not m or i >= len(me.materials):
            continue
        if m.name in images:
            me.materials[i] = baked_material(m.name, images[m.name], 0.85 if 'outfit' in m.name or 'shirt' in m.name else 0.6)
        else:
            me.materials[i] = web_material(m)
    return mesh_object(name, decimate(me, ratio), ob.matrix_world.copy())


def observer_info(dg):
    """Observer position and facing (from the corneas and the head mesh), for the viewer's start view."""
    def centre(name):
        ob = next(o for o in D.objects if o.name.startswith(name))
        me = ob.evaluated_get(dg).to_mesh()
        c = sum((ob.matrix_world @ v.co for v in me.vertices), Vector()) / len(me.vertices)
        ob.evaluated_get(dg).to_mesh_clear()
        return c
    head, eyes = centre('Person • Head'), (centre('Person • LeftCornea') + centre('Person • RightCornea')) / 2
    fwd = head - eyes        # the head mesh is face-heavy, so its centroid sits in front of the corneas
    fwd.z = 0
    feet = (centre('Person • shoe_L') + centre('Person • shoe_R')) / 2
    return {'pos': list(feet), 'forward': list(fwd.normalized())}


def export_geometry(out, quick=False):
    prepare()
    dg = bpy.context.evaluated_depsgraph_get()
    scene = bpy.context.scene
    stats = {}

    # 1. Plain objects (buildings, ships, industry, substations, fixtures): shared meshes, decimated.
    shared = {}
    count = 0
    for ob in scene.objects:
        if ob.type != 'MESH' or not ob.visible_get() or ob.hide_render:
            continue
        if ob.name.startswith(SKIP_REALIZED) or any(c.hide_render for c in ob.users_collection):
            continue
        if any(m.type == 'NODES' for m in ob.modifiers):
            continue
        if ob.name.startswith('Curiosity'):       # textured hero model: bake its layered materials
            baked_copy(ob, 'WEB ' + ob.name, dg, bake_colors([ob], 512 if quick else 1024), DECIMATE['Curiosity'])
            continue
        key = ob.data.name
        if key not in shared:
            me = ob.data.copy()
            me.name = 'WEB ' + key
            webify_mesh(me)
            ratio = next((r for k, r in DECIMATE.items() if k in ob.name), 1.0)
            shared[key] = decimate(me, ratio)
        mesh_object('WEB ' + ob.name, shared[key], ob.matrix_world.copy())
        count += 1
    stats['plain objects'] = count

    # 2. Membrane: film (decimated roof + walls), foundation, clamps; airlocks as instances.
    memb = membrane()
    full = evaluated_copy(memb, 'WEB membrane full', dg)
    roof = decimate(split_by_material(full, ['Live membrane']), 0.06 if not quick else 0.02)
    wall = split_by_material(full, ['Pressure wall'])
    base = split_by_material(full, ['clamp', 'foundation'])
    for n, me in (('WEB membrane roof', roof), ('WEB membrane wall', wall), ('WEB perimeter foundation', base)):
        me.name = n
        mesh_object(n, me)
    D.meshes.remove(full)
    alk, airlocks = instances_of(dg, memb, lambda me: len(me.polygons) > 500)
    instancer('WEB airlocks', alk, airlocks)
    stats['airlocks'] = len(airlocks)

    # 3. Anchors + rings (viewport LOD geometry), all 2,500.
    amesh, anchors = instances_of(dg, cage(), ratio=0.5)
    instancer('WEB anchors', amesh, anchors)
    stats['anchors'] = len(anchors)

    # 4. People and freight (viewport stand-ins), people decimated further.
    for obname, tag, ratio in (('People • residents and workers', 'people', 0.12),
                               ('Freight yard • stacked pallet blocks and forklifts', 'freight', 1.0)):
        meshes, items = instances_of(dg, D.objects[obname], ratio=ratio)
        if tag == 'people':      # the browser draws 2D stand-ins only: ship a token mesh per pose
            for k in meshes:
                me = D.meshes.new('WEB person token ' + str(k))
                me.from_pydata([(0, 0, 0), (0.1, 0, 0), (0, 0, 1.75)], [], [(0, 1, 2)])
                meshes[k] = me
        instancer('WEB ' + tag, meshes, items)
        stats[tag] = len(items)

    # 4b. The SpaceX-shirt observer, posed, with his materials baked to textures (shirt print included).
    parts = [o for o in scene.objects if o.type == 'MESH' and o.name.startswith(OBSERVER_PARTS)]
    images = bake_colors([o for o in parts if 'Cornea' not in o.name], 1024 if quick else 2048)
    for o in parts:
        baked_copy(o, 'WEB observer ' + o.name, dg, images)
    stats['observer parts'] = len(parts)
    with open(os.path.join(out, 'observer.json'), 'w') as f:
        json.dump(observer_info(dg), f)

    # 5. Terrain meshes (drawn in the browser with the baked ground textures).
    ground_objs = [o for o in scene.objects if o.type == 'MESH' and o.visible_get() and not o.hide_render and (
        o.name.startswith(('Mars valley', 'Valley', 'Mesa')) and not o.name.startswith('Valley basalt'))]
    t = time.time()
    bvh = ground_bvh(dg, ground_objs)
    n_near = 140 if quick else 280
    terrain_grid('WEB_TERRAIN near', bvh, NEAR[0], NEAR[1], NEAR[2], n_near, hole=None)
    terrain_grid('WEB_TERRAIN far', bvh, FAR[0], FAR[1], FAR[2], 160 if quick else 320, hole=NEAR)
    stats['terrain s'] = round(time.time() - t, 1)

    # 6. Export.
    for ob in scene.objects:
        ob.select_set(False)
    for ob in web_collection().objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(web_collection().objects))
    path = os.path.join(out, 'vault.glb')
    bpy.ops.export_scene.gltf(
        filepath=path, export_format='GLB', use_selection=True, export_apply=True,
        export_gpu_instances=True, export_gn_mesh=True, export_materials='EXPORT',
        export_image_format='JPEG', export_jpeg_quality=85,
        export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
        export_draco_position_quantization=16, export_cameras=False, export_lights=False,
        export_animations=False, export_yup=True)
    stats['glb MB'] = round(os.path.getsize(path) / 1e6, 1)
    return stats


# ------------------------------------------------------------------ bakes
CAMERA_HIDDEN = ('MEMBRANE', 'ANCHOR BUILDER', 'Homes', 'Residential tower', 'Warehouses', 'Industry',
                 'Process tanks', 'Heritage Starship', 'Crew Starship', 'Cargo Starship', 'People', 'Freight yard',
                 'Battery substation', 'Solar farm substation', 'Apron light', 'Entrance fixture', 'Curiosity',
                 'Person', 'PERSON', 'Atmosphere', 'CONTROLS', 'Solar farm • east-west')


def camera_transparent(m):
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial' and n.is_active_output)
    if not out.inputs['Surface'].is_linked:
        return
    src = out.inputs['Surface'].links[0].from_socket
    lp = nt.nodes.new('ShaderNodeLightPath')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])


def bake_setup():
    prepare(people_fraction=1.0)
    scene = bpy.context.scene
    for ob in scene.objects:
        if ob.name.startswith(CAMERA_HIDDEN) or (ob.parent and ob.parent.name.startswith('PERSON')):
            ob.visible_camera = False
            ob.visible_glossy = False
    # The browser shows only the farm substation's white enclosures, so its pad,
    # fence and gantries must not leave a baked shadow either.
    sub = next((o for o in scene.objects if o.name.startswith('Solar farm substation')), None)
    if sub:
        sub.visible_shadow = False
    atmo = D.objects.get('Atmosphere • valley haze with clear interior')
    if atmo:
        atmo.visible_camera = False      # the browser adds distance fog instead
        atmo.visible_diffuse = atmo.visible_glossy = atmo.visible_transmission = False
        atmo.visible_volume_scatter = atmo.visible_shadow = False
    # The cage also carries the prepared ground layer, so it stays camera-visible;
    # only its anchor/ring materials turn transparent to camera rays (shadows kept).
    for m in D.materials:
        if m.name.startswith(('Anchor •', 'Ring •')) and m.node_tree:
            camera_transparent(m)
    scene.render.engine = 'CYCLES'
    set_device(scene)
    scene.cycles.use_denoising = True
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 88
    scene.render.resolution_percentage = 100


def ortho_render(name, x0, y0, size, px, samples, out):
    scene = bpy.context.scene
    cam = D.objects.new('WEB bake camera', D.cameras.new('WEB bake camera'))
    scene.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = size
    cam.data.clip_start = 1.0
    cam.data.clip_end = 60000.0
    cam.location = (x0 + size / 2, y0 + size / 2, 20000.0)
    cam.rotation_euler = (0, 0, 0)
    scene.camera = cam
    scene.render.resolution_x = scene.render.resolution_y = px
    scene.cycles.samples = samples
    scene.render.filepath = os.path.join(out, name)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('BAKED', name, px, 'px', round(time.time() - t), 's', flush=True)
    D.objects.remove(cam)


def export_bakes(out, quick=False, only=None):
    bake_setup()
    s = 0.25 if quick else 1.0
    for name, ext, px, spp in (('city', CITY, 6144, 24), ('near', NEAR, 4096, 24), ('far', FAR, 4096, 16)):
        if only is None or name in only:
            ortho_render(f'ground_{name}.jpg', *ext, int(px * s), spp, out)


def export_detail(out, x0=3500.0, y0=3500.0, size=24.0, px=2048):
    """Tiling close-up ground texture: a small top-down render of open ground, high-passed
    (divided by its local mean, stored around mid-grey) and made seamless, for the browser to
    multiply over the coarse bakes near the camera."""
    import numpy as np
    bake_setup()
    # An ortho camera dices adaptive displacement at its pixel size over the whole terrain
    # (billions of micro-polygons at 1 cm/px), so dice from a perspective camera just above the patch.
    scene = bpy.context.scene
    dc = D.objects.new('WEB dicing camera', D.cameras.new('WEB dicing camera'))
    scene.collection.objects.link(dc)
    dc.location = (x0 + size / 2, y0 + size / 2, 30.0)
    scene.cycles.dicing_camera = dc
    scene.cycles.offscreen_dicing_scale = 25.0
    ortho_render('_detail_raw.jpg', x0, y0, size, px, 32, out)
    scene.cycles.dicing_camera = None
    D.objects.remove(dc)
    raw = os.path.join(out, '_detail_raw.jpg')
    img = D.images.load(raw)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(px, px, 4)[:, :, :3]
    D.images.remove(img)
    os.remove(raw)

    def blur(x, r):           # wrap-around box blur, three passes ~ gaussian
        for _ in range(3):
            for ax in (0, 1):
                c = np.cumsum(np.concatenate([x.take(range(-r, 0), ax), x, x.take(range(r), ax)], ax), ax)
                x = (c.take(range(2 * r, px + 2 * r), ax) - np.concatenate(
                    [np.zeros_like(c.take([0], ax)), c.take(range(px - 1), ax)], ax)) / (2 * r + 1)
        return x
    hp = a / np.maximum(blur(a, px // 16), 1e-4)              # local contrast per channel, ~1.0 mean, no tint
    # Seamless: cross-fade with a half-shifted copy whose wrap seam sits in the middle.
    t = np.abs(np.linspace(-1, 1, px))
    w = np.clip((1 - np.maximum(t[:, None], t[None, :])) * 4, 0, 1)[:, :, None]
    sh = np.roll(np.roll(hp, px // 2, 0), px // 2, 1)
    hp = w * hp + (1 - w) * sh
    out_img = D.images.new('WEB detail', px, px)
    rgba = np.concatenate([np.clip(hp * 0.5, 0, 1), np.ones((px, px, 1), np.float32)], 2)
    out_img.pixels = rgba.ravel()
    out_img.filepath_raw = os.path.join(out, 'ground_detail.jpg')
    out_img.file_format = 'JPEG'
    bpy.context.scene.render.image_settings.quality = 88
    out_img.save_render(out_img.filepath_raw)
    print('DETAIL', size, 'm tile', px, 'px', flush=True)


def export_sky(out, quick=False, blue=None):
    prepare()
    if blue is not None:
        set_control('Day sky blue', blue)
        D.objects['CONTROLS • Mars vault'].update_tag()
    scene = bpy.context.scene
    atmo = D.objects.get('Atmosphere • valley haze with clear interior')
    for ob in scene.objects:
        if ob != atmo:
            ob.visible_camera = False    # hide_render is driven by the district toggles
    cam = D.objects.new('WEB sky camera', D.cameras.new('WEB sky camera'))
    scene.collection.objects.link(cam)
    cam.data.type = 'PANO'
    cam.data.panorama_type = 'EQUIRECTANGULAR'
    cam.location = (0, -1800.0, 30.0)        # outside the clear cavity, so the haze reads
    cam.rotation_euler = (math.pi / 2, 0, -math.pi / 2)
    scene.camera = cam
    sun = D.objects.get('Mars_Sun')
    if sun:
        sun.hide_render = False
    scene.render.engine = 'CYCLES'
    set_device(scene)
    scene.render.resolution_x, scene.render.resolution_y = (1024, 512) if quick else (4096, 2048)
    scene.cycles.samples = 32
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 90
    scene.render.filepath = os.path.join(out, 'sky.jpg')
    bpy.ops.render.render(write_still=True)
    print('SKY done', flush=True)


def export_freight_textures(out):
    """Side and top renders of each real freight asset, for the browser's box imposters."""
    src = D.collections['ASSET • freight stacks']
    scene = D.scenes.new('WEB freight imposters')
    world = D.worlds.new('WEB imposter world')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    scene.world = world
    scene.render.engine = 'CYCLES'
    set_device(scene)
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 85
    cam = D.objects.new('WEB imposter cam', D.cameras.new('WEB imposter cam'))
    cam.data.type = 'ORTHO'
    scene.collection.objects.link(cam)
    scene.camera = cam
    done = []
    for ob in sorted(src.objects, key=lambda o: o.name):
        if ob.type != 'MESH' or not ob.name.startswith('Freight '):
            continue
        n = ob.name.split(' ')[1]
        copy = D.objects.new('WEB imposter ' + n, ob.data)
        scene.collection.objects.link(copy)
        vs = [v.co for v in ob.data.vertices]
        lo = Vector([min(v[i] for v in vs) for i in range(3)])
        hi = Vector([max(v[i] for v in vs) for i in range(3)])
        c, size = (lo + hi) / 2, hi - lo
        for view, loc, rot, w, h in (('side', (c.x, lo.y - 10, c.z), (math.pi / 2, 0, 0), size.x, size.z),
                                     ('top', (c.x, c.y, hi.z + 10), (0, 0, 0), size.x, size.y)):
            cam.location = loc
            cam.rotation_euler = rot
            cam.data.ortho_scale = max(w, h)
            scene.render.resolution_x = max(8, round(256 * w / max(w, h)))
            scene.render.resolution_y = max(8, round(256 * h / max(w, h)))
            scene.render.filepath = os.path.join(out, f'freight_{n}_{view}.jpg')
            bpy.ops.render.render(write_still=True, scene=scene.name)
        D.objects.remove(copy)
        done.append(n)
    print('FREIGHT TEXTURES', done, flush=True)


def web_viewpoints(cams):
    """The web list opens on the mesa view as '01 • valley and solar field' (no duplicate 07)."""
    mesa = next((c for c in cams if c['name'].startswith('07')), None)
    if not mesa:
        return cams
    out = []
    for c in cams:
        if c['name'].startswith('01'):
            out.append(dict(mesa, name='01 • valley and solar field'))
        elif c is not mesa:
            out.append(c)
    return out


def scene_json(out):
    scene = bpy.context.scene
    sun = D.objects['Mars_Sun']
    d = sun.matrix_world.to_3x3() @ Vector((0, 0, 1))
    cams = []
    for ob in sorted(scene.objects, key=lambda o: o.name):
        if ob.type == 'CAMERA' and ob.name[:2].isdigit():
            fwd = ob.matrix_world.to_3x3() @ Vector((0, 0, -1))
            cams.append({'name': ob.name, 'pos': list(ob.location), 'dir': list(fwd),
                         'fov': math.degrees(ob.data.angle_y)})
    cams = web_viewpoints(cams)
    solar = {'x0': -8430.0, 'x1': -2600.0, 'y0': -2915.0, 'y1': 2915.0, 'pitch': 4.9, 'seg': 40.0,
             'tilt_deg': 12.0, 'panel': 2.0, 'low': 0.18, 'track_every': 500.0, 'track_half': 26.0,
             'spine_half': 8.0, 'skid_every': 500.0}      # mirrors tools/legacy/photoreal_solar.py
    obs = os.path.join(out, 'observer.json')
    observer = json.load(open(obs)) if os.path.exists(obs) else None
    elev = math.degrees(math.asin(max(-1.0, min(1.0, d.normalized().z))))
    data = {'sun_elevation_deg': round(elev, 1), 'observer': observer, 'units': 'metres, Blender Z-up (the glb is Y-up)', 'city': CITY, 'near': NEAR, 'far': FAR, 'solar': solar,
            'sun_dir': list(d), 'exposure_ev': scene.view_settings.exposure, 'cameras': cams}
    with open(os.path.join(out, 'scene.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--geometry', action='store_true')
    ap.add_argument('--bake', action='store_true')
    ap.add_argument('--only', help='comma list of bakes: city,near,far')
    ap.add_argument('--sky', action='store_true')
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--freight', action='store_true')
    ap.add_argument('--detail', action='store_true', help='Tiling close-up ground texture')
    ap.add_argument('--sky-blue', type=float, default=0.6, help='Day sky blue used for the web sky (scene default 0.35)')
    ap.add_argument('--gpu', action='store_true', help='Render bakes on the GPU')
    ap.add_argument('--sun-hour', type=float, default=15.45,
                    help='Day solar hour for the web bakes (15.45 puts the sun ~35 deg up; scene default 15)')
    a = ap.parse_args(argv)
    global USE_GPU
    USE_GPU = a.gpu
    os.makedirs(a.out, exist_ok=True)
    set_control('Day solar hour', a.sun_hour)
    D.objects['CONTROLS • Mars vault'].update_tag()
    bpy.context.view_layer.update()
    scene_json(a.out)
    if a.geometry:
        print('GEOMETRY', export_geometry(a.out, a.quick), flush=True)
        scene_json(a.out)
    if a.bake:
        export_bakes(a.out, a.quick, a.only.split(',') if a.only else None)
    if a.sky:
        export_sky(a.out, a.quick, a.sky_blue)
    if a.freight:
        export_freight_textures(a.out)
    if a.detail:
        export_detail(a.out)


if __name__ == '__main__':
    main()
