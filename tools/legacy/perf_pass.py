"""One-time change (2026-09-24): viewport and render performance pass.

Measured before: ~280 M viewport triangles and 3.8 M instances; ~40 s render
preparation; 16,210 drivers. Changes (final renders keep full detail):
1. Delete the legacy prepared-ground pebble scatter in the cage node group:
   3.7 M hidden 5 cm stones (98% of all instances), invisible under turf/streets.
2. People: ~3k-face stand-ins in the viewport; crowd off by default.
3. Freight: box stand-ins per cargo type in the viewport.
4. Membrane: the per-bay source patch is un-subdivided once for the viewport
   (same tile everywhere, so bay edges still match).
5. Delete the 2,500 legacy sampled ring-light objects (15,000 drivers) and the
   Annular ring lighting toggle; the LED ring meshes remain the light source.
6. Rocks: ~100-face stand-ins in the viewport.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/perf_pass.py -- out.blend
"""
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gnkit  # noqa: E402

D = bpy.data
CTL = 'CONTROLS • Mars vault'


def ctl_socket(name):
    mod = D.objects[CTL].modifiers['CONTROLS']
    for it in mod.node_group.interface.items_tree:
        if it.item_type == 'SOCKET' and it.name == name:
            return mod, it
    raise KeyError(name)


# 1 ---------------------------------------------------------------- pebbles
def remove_pebbles():
    ng = [o for o in D.objects if o.name.startswith('TENSILE')][0].modifiers[0].node_group
    inst = ng.nodes['Instance on Points.004']
    doomed = {inst, inst.inputs['Points'].links[0].from_node}          # + Distribute Points on Faces
    stack = [l.from_node for l in inst.inputs['Instance'].links]       # Set Material <- Ico Sphere
    while stack:
        n = stack.pop()
        if n.bl_idname in ('GeometryNodeSetMaterial', 'GeometryNodeMeshIcoSphere') and n not in doomed:
            doomed.add(n)
            stack += [l.from_node for s in n.inputs for l in s.links]
    for n in doomed:
        ng.nodes.remove(n)
    return len(doomed)


# helpers for viewport stand-ins ----------------------------------------------
def decimated_copy(ob, col, ratio, name):
    tmp = D.objects.new('tmp decimate', ob.data.copy())
    bpy.context.scene.collection.objects.link(tmp)   # must be evaluated: stand-in collections are excluded
    mod = tmp.modifiers.new('d', 'DECIMATE')
    mod.ratio = ratio
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = D.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    me.name = name
    old = tmp.data
    D.objects.remove(tmp)
    D.meshes.remove(old)
    return gnkit.new_object(name, col, me)


def box_copy(ob, col, name):
    vs = [v.co for v in ob.data.vertices]
    lo = [min(v[i] for v in vs) for i in range(3)]
    hi = [max(v[i] for v in vs) for i in range(3)]
    bm = bmesh.new()
    geo = bmesh.ops.create_cube(bm, size=1.0)['verts']
    for v in geo:
        v.co = [lo[i] + (hi[i] - lo[i]) * (v.co[i] + 0.5) for i in range(3)]
    me = D.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    counts = {}
    for p in ob.data.polygons:
        m = ob.data.materials[p.material_index] if p.material_index < len(ob.data.materials) else None
        if m and 'Pallet' not in m.name:
            counts[m] = counts.get(m, 0) + 1
    if counts:
        me.materials.append(max(counts, key=counts.get))
    return gnkit.new_object(name, col, me)


def proxy_switch(ng, collection_name, proxy_col):
    """Swap a Collection Info's output for proxy_col when evaluating for the viewport."""
    info = next(n for n in ng.nodes if n.bl_idname == 'GeometryNodeCollectionInfo'
                and n.inputs['Collection'].default_value
                and n.inputs['Collection'].default_value.name == collection_name)
    proxy = ng.nodes.new('GeometryNodeCollectionInfo')
    proxy.transform_space = info.transform_space
    proxy.location = (info.location.x, info.location.y - 250)
    for s in ('Separate Children', 'Reset Children'):
        proxy.inputs[s].default_value = info.inputs[s].default_value
    proxy.inputs['Collection'].default_value = proxy_col
    isv = ng.nodes.new('GeometryNodeIsViewport')
    sw = ng.nodes.new('GeometryNodeSwitch')
    sw.input_type = 'GEOMETRY'
    sw.label = 'Viewport stand-ins'
    sw.location = (info.location.x + 200, info.location.y - 120)
    outs = [l.to_socket for l in info.outputs[0].links]
    ng.links.new(isv.outputs[0], sw.inputs['Switch'])
    ng.links.new(info.outputs[0], sw.inputs['False'])
    ng.links.new(proxy.outputs[0], sw.inputs['True'])
    for s in outs:
        ng.links.new(sw.outputs[0], s)


def proxies(asset_col_name, proxy_col_name, make):
    src = D.collections[asset_col_name]
    col = gnkit.collection(proxy_col_name, exclude=True)
    for ob in sorted(src.objects, key=lambda o: o.name):
        if ob.type == 'MESH':
            p = make(ob, col, ob.name.replace('•', '• viewport stand-in •', 1))
            p.location = ob.location
    return col


# 2/3/6 ------------------------------------------------------------ stand-ins
def people():
    col = proxies('ASSET • crowd poses', 'ASSET • crowd viewport stand-ins',
                  lambda ob, c, n: decimated_copy(ob, c, 0.05, n))
    proxy_switch(D.node_groups['YEAR15 • crowd scatter'], 'ASSET • crowd poses', col)
    mod, sock = ctl_socket('People')
    sock.default_value = False
    getattr(mod.properties.inputs, sock.identifier).value = False
    sock.description = 'Crowd of ~8,000 residents and workers (off by default: adds render preparation time)'
    return col


def freight():
    col = proxies('ASSET • freight stacks', 'ASSET • freight viewport stand-ins', box_copy)
    proxy_switch(D.node_groups['YEAR15 • stacked freight instances'], 'ASSET • freight stacks', col)
    return col


def rocks():
    col = proxies('ASSET • basalt rocks', 'ASSET • rock viewport stand-ins',
                  lambda ob, c, n: decimated_copy(ob, c, 0.08, n))
    proxy_switch(D.node_groups['YEAR15 • rock field scatter'], 'ASSET • basalt rocks', col)
    return col


# 4 ---------------------------------------------------------------- membrane
def membrane_lod():
    src = D.objects['SOURCE • ring-cut quad patch']
    bm = bmesh.new()
    bm.from_mesh(src.data)
    bmesh.ops.unsubdivide(bm, verts=bm.verts, iterations=1)
    me = D.meshes.new('SOURCE • ring-cut quad patch • viewport')
    bm.to_mesh(me)
    bm.free()
    for m in src.data.materials:
        me.materials.append(m)
    lod = D.objects.new('SOURCE • ring-cut quad patch • viewport', me)
    lod.matrix_world = src.matrix_world
    if src.users_collection:
        src.users_collection[0].objects.link(lod)
        lod.hide_render = True
        lod.hide_viewport = src.hide_viewport
    else:
        lod.use_fake_user = True          # stored like its source: data only, not in the scene
    ng = [o for o in D.objects if o.name.startswith('MEMBRANE')][0].modifiers[0].node_group
    info = next(n for n in ng.nodes if n.bl_idname == 'GeometryNodeObjectInfo'
                and n.inputs['Object'].default_value == src)
    sw = ng.nodes.new('GeometryNodeSwitch')
    sw.input_type = 'OBJECT'
    sw.label = 'Viewport membrane patch'
    sw.location = (info.location.x - 220, info.location.y)
    isv = ng.nodes.new('GeometryNodeIsViewport')
    isv.location = (info.location.x - 440, info.location.y)
    ng.links.new(isv.outputs[0], sw.inputs['Switch'])
    sw.inputs['False'].default_value = src
    sw.inputs['True'].default_value = lod
    ng.links.new(sw.outputs[0], info.inputs['Object'])
    return len(src.data.polygons), len(me.polygons)


# 5 ---------------------------------------------------------------- ring lights
def remove_ring_lights():
    col = D.collections['YEAR 15 • sampled ring illumination']
    obs = list(col.all_objects)
    lights = {o.data for o in obs if o.type == 'LIGHT'}
    for o in obs:
        D.objects.remove(o)
    for l in lights:
        if l.users == 0:
            D.lights.remove(l)
    for parent in [bpy.context.scene.collection] + list(D.collections):
        if col.name in parent.children:
            parent.children.unlink(col)
    D.collections.remove(col)
    # The ring shader chose between emitters with the Annular toggle; pin it to annular.
    mod, sock = ctl_socket('Annular ring lighting')
    path = f'modifiers["CONTROLS"].properties.inputs.{sock.identifier}.value'
    pinned = 0
    for owner in [*D.objects, *D.node_groups, *[m.node_tree for m in D.materials if m.node_tree],
                  *[w.node_tree for w in D.worlds], *D.lights, *D.scenes]:
        ad = owner.animation_data
        if not ad:
            continue
        for fc in list(ad.drivers):
            if any(t.data_path == path for v in fc.driver.variables for t in v.targets):
                data_path, index = fc.data_path, fc.array_index
                ad.drivers.remove(fc)
                target = owner.path_resolve(data_path.rsplit('.', 1)[0])
                attr = data_path.rsplit('.', 1)[1]
                cur = getattr(target, attr)
                if hasattr(cur, '__len__'):
                    cur[index] = 1.0
                else:
                    setattr(target, attr, type(cur)(1))
                pinned += 1
    mod.node_group.interface.remove(sock)
    return len(obs), pinned


def check_drivers():
    bad = 0
    for owner in [*D.objects, *D.node_groups, *[m.node_tree for m in D.materials if m.node_tree],
                  *[w.node_tree for w in D.worlds], *D.lights, *D.scenes]:
        if owner.animation_data:
            for fc in owner.animation_data.drivers:
                if not fc.driver.is_valid or any(t.id is None for v in fc.driver.variables for t in v.targets):
                    bad += 1
    return bad


def main():
    print('PERF pebble nodes removed', remove_pebbles(), flush=True)
    people()
    freight()
    rocks()
    print('PERF membrane patch faces render/viewport', membrane_lod(), flush=True)
    print('PERF ring lights removed / drivers pinned', remove_ring_lights(), flush=True)
    print('PERF invalid drivers', check_drivers(), flush=True)
    D.orphans_purge(do_recursive=True)
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
    print('PERF SAVED', out, flush=True)


if __name__ == '__main__':
    main()
