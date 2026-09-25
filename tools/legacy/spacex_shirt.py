"""One-time change (2026-09-24): SpaceX four-leaf-clover T-shirt for the observer.

Only the embedded observer (PERSON RIG) changes; the crowd keeps its varied
shirts. A logo image (green four-leaf clover with the white SpaceX wordmark) is
rendered once from a scratch Workbench scene and packed. The wordmark is the
SVG from Wikimedia Commons (File:SpaceX_logo_black.svg), passed as the second
argument and not committed. The
observer's clothing gets its own copy of the outfit material: the light shirt
area of the texture turns black (fold shading kept) and the logo is projected
onto the back from an empty aligned with the torso.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/spacex_shirt.py -- out.blend SpaceX_logo_black.svg
"""
import math
import os
import sys
import tempfile

import bpy
from mathutils import Matrix, Vector

D = bpy.data
RIG = 'PERSON RIG • editable head and neck pose'
GREEN = (0.03, 0.30, 0.06, 1.0)
WHITE = (0.92, 0.92, 0.92, 1.0)


# ---------------------------------------------------------------- logo image
def flat_material(name, color):
    m = D.materials.new(name)
    m.diffuse_color = color
    return m


def wordmark_from_svg(svg_path, scene, white, width=1.18, y=0.0):
    """Official SpaceX wordmark (Wikimedia Commons SVG), recoloured white and centred."""
    import addon_utils
    addon_utils.enable('io_curve_svg', default_set=False)
    before = set(D.objects)
    bpy.ops.import_curve.svg(filepath=svg_path)
    new = [o for o in D.objects if o not in before and o.type == 'CURVE']
    for col in {c for o in new for c in o.users_collection}:
        for o in new:
            if o.name in col.objects:
                col.objects.unlink(o)
        if not col.objects and not col.children:
            D.collections.remove(col)
    xs = [(o.matrix_world @ Vector(c)).x for o in new for c in o.bound_box]
    ys = [(o.matrix_world @ Vector(c)).y for o in new for c in o.bound_box]
    scale = width / (max(xs) - min(xs))
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    for o in new:
        o.data.materials.clear()
        o.data.materials.append(white)
        o.matrix_world = (Matrix.Translation((-cx * scale, -cy * scale + y, 0.05)) @ Matrix.Scale(scale, 4)
                          @ o.matrix_world)
        scene.collection.objects.link(o)


def drawn_wordmark(add, white):
    """Fallback when the SVG is not available: text plus a drawn swoosh."""
    txt = D.curves.new('tmp text', 'FONT')
    txt.body = 'SPACEX'
    for path in (r'C:\Windows\Fontsahnschrift.ttf', r'C:\Windows\Fontsrialbd.ttf'):
        if os.path.exists(path):
            txt.font = D.fonts.load(path)
            break
    txt.align_x, txt.align_y = 'CENTER', 'CENTER'
    txt.size = 0.27
    txt.space_character = 1.12
    t = add(D.objects.new('tmp text', txt), white, 0.05)
    t.scale.x = 1.25


def logo_image(svg_path=None, size=1024):
    scene = D.scenes.new('tmp • logo render')
    green, white = flat_material('tmp green', GREEN), flat_material('tmp white', WHITE)

    def add(ob, mat, z=0.0):
        ob.data.materials.append(mat)
        ob.location.z += z
        scene.collection.objects.link(ob)
        return ob

    def circle(center, r, mat, z=0.0):
        me = D.meshes.new('tmp circle')
        n = 64
        verts = [(center[0] + r * math.cos(2 * math.pi * i / n), center[1] + r * math.sin(2 * math.pi * i / n), 0)
                 for i in range(n)]
        me.from_pydata(verts, [], [list(range(n))])
        return add(D.objects.new('tmp circle', me), mat, z)

    def poly(points, mat, z=0.0):
        me = D.meshes.new('tmp poly')
        me.from_pydata([(x, y, 0) for x, y in points], [], [list(range(len(points)))])
        return add(D.objects.new('tmp poly', me), mat, z)

    # Four heart-shaped leaves, points meeting at the centre, slightly turned.
    # Each heart: two round lobes plus a triangle down to its tip at the centre.
    r = 0.185
    for k in range(4):
        rot = Matrix.Rotation(math.radians(12 + 90 * k), 2)
        lobes = [Vector((side * 0.15, 0.45)) for side in (-1, 1)]
        for c in lobes:
            circle(tuple(rot @ c), r, green)
        tip = Vector((0.0, 0.04))
        wing = [Vector((-0.315, 0.38)), Vector((0.0, 0.50)), Vector((0.315, 0.38))]
        poly([tuple(rot @ p) for p in [tip, wing[2], wing[1], wing[0]]], green)
    circle((0.0, 0.0), 0.13, green)                     # leaves meet solidly at the centre
    # Stem curving to the lower right.
    stem = D.curves.new('tmp stem', 'CURVE')
    stem.dimensions = '2D'
    spline = stem.splines.new('BEZIER')
    spline.bezier_points.add(1)
    for bp, co, h1, h2 in ((spline.bezier_points[0], (0.02, -0.02), (-0.05, 0.05), (0.06, -0.25)),
                           (spline.bezier_points[1], (0.36, -0.88), (0.2, -0.62), (0.42, -0.98))):
        bp.co = (*co, 0)
        bp.handle_left = (*h1, 0)
        bp.handle_right = (*h2, 0)
    stem.bevel_depth = 0.0
    stem.extrude = 0.0
    stem.offset = 0.0
    stem.fill_mode = 'BOTH'
    stem.bevel_mode = 'ROUND'
    stem.bevel_depth = 0.045
    add(D.objects.new('tmp stem', stem), green)
    if svg_path and os.path.exists(svg_path):
        wordmark_from_svg(svg_path, scene, white)
    else:
        drawn_wordmark(add, white)

    cam = D.objects.new('tmp cam', D.cameras.new('tmp cam'))
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 2.0
    cam.location = (0, 0, 5)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'FLAT'
    scene.display.shading.color_type = 'MATERIAL'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    path = os.path.join(tempfile.gettempdir(), 'spacex_clover_logo.png')
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=scene.name)
    for ob in list(scene.collection.objects):
        data = ob.data
        D.objects.remove(ob)
        if data and data.users == 0:
            (D.meshes if isinstance(data, bpy.types.Mesh) else D.curves if isinstance(data, bpy.types.Curve)
             else D.cameras).remove(data)
    D.scenes.remove(scene)
    for m in (green, white):
        D.materials.remove(m)
    img = D.images.load(path)
    img.name = 'SpaceX clover shirt logo'
    img.pack()
    img.filepath = ''
    return img


# ---------------------------------------------------------------- projector
def projector():
    rig = D.objects[RIG]
    M = rig.matrix_world

    def w(bone):
        return M @ rig.pose.bones['mixamorig:' + bone].head
    fwd = (w('LeftToeBase_058') - w('LeftFoot_057')) + (w('RightToeBase_063') - w('RightFoot_062'))
    fwd.z = 0
    fwd.normalize()
    back = -fwd
    right_seen_from_behind = Vector((fwd.y, -fwd.x, 0))
    centre = (w('Spine1_03') + w('Spine2_04')) / 2
    centre.z += 0.04
    empty = D.objects.new('PERSON • shirt logo projector', None)
    empty.empty_display_type = 'PLAIN_AXES'
    empty.empty_display_size = 0.2
    rot = Matrix((right_seen_from_behind, Vector((0, 0, 1)), back)).transposed().to_4x4()
    empty.matrix_world = Matrix.Translation(centre) @ rot
    rig.users_collection[0].objects.link(empty)
    # Keep it with the figure if the rig is moved.
    world = empty.matrix_world.copy()
    empty.parent = rig
    empty.matrix_world = world
    empty.hide_render = True
    return empty, back


# ---------------------------------------------------------------- material
def shirt_material(image, empty, back):
    src = D.materials['outfit_map']
    m = src.copy()
    m.name = 'Observer • black SpaceX T-shirt'
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = next(n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    # The diffuse texture is the image node that does not feed the normal map.
    images = [n for n in N if n.bl_idname == 'ShaderNodeTexImage']
    tex = next(n for n in images if not any(l.to_node.bl_idname == 'ShaderNodeNormalMap' for l in n.outputs['Color'].links))

    def node(kind, **inputs):
        n = N.new(kind)
        for k, v in inputs.items():
            n.inputs[k].default_value = v
        return n

    def mixc(a, b, fac, blend='MIX'):
        n = N.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = blend
        s = {x.identifier: x for x in n.inputs}
        for key, v in (('A_Color', a), ('B_Color', b), ('Factor_Float', fac)):
            if isinstance(v, (tuple, list)):
                s[key].default_value = v
            elif isinstance(v, (int, float)):
                s[key].default_value = v
            else:
                L.new(v, s[key])
        return next(x for x in n.outputs if x.identifier == 'Result_Color')

    lum = N.new('ShaderNodeRGBToBW')
    L.new(tex.outputs['Color'], lum.inputs[0])
    shirt = node('ShaderNodeMapRange', **{'From Min': 0.28, 'From Max': 0.42})
    shirt.interpolation_type = 'SMOOTHSTEP'
    L.new(lum.outputs[0], shirt.inputs['Value'])
    black = mixc(tex.outputs['Color'], (0.035, 0.035, 0.04, 1.0), 1.0, 'MULTIPLY')
    # Projected logo on the back.
    tc = N.new('ShaderNodeTexCoord')
    tc.object = empty
    mp = N.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1 / 0.52, 1 / 0.52, 1.0)     # logo image spans 0.52 m on the back
    mp.inputs['Location'].default_value = (0.5, 0.5, 0.0)
    mp.vector_type = 'POINT'
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    logo = N.new('ShaderNodeTexImage')
    logo.image = image
    logo.extension = 'CLIP'
    L.new(mp.outputs[0], logo.inputs['Vector'])
    geo = N.new('ShaderNodeNewGeometry')
    facing = N.new('ShaderNodeVectorMath')
    facing.operation = 'DOT_PRODUCT'
    L.new(geo.outputs['Normal'], facing.inputs[0])
    facing.inputs[1].default_value = back
    on_back = node('ShaderNodeMapRange', **{'From Min': 0.15, 'From Max': 0.45})
    L.new(facing.outputs['Value'], on_back.inputs['Value'])
    mask = N.new('ShaderNodeMath')
    mask.operation = 'MULTIPLY'
    L.new(logo.outputs['Alpha'], mask.inputs[0])
    L.new(on_back.outputs['Result'], mask.inputs[1])
    printed = mixc(black, logo.outputs['Color'], mask.outputs[0])
    shirt_col = mixc(tex.outputs['Color'], printed, shirt.outputs['Result'])
    L.new(shirt_col, bsdf.inputs['Base Color'])
    # Screen-printed ink is a little smoother than the cotton.
    rough = N.new('ShaderNodeMapRange')
    L.new(mask.outputs[0], rough.inputs['Value'])
    rough.inputs['To Min'].default_value = 0.85
    rough.inputs['To Max'].default_value = 0.6
    L.new(rough.outputs['Result'], bsdf.inputs['Roughness'])
    return m


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    image = logo_image(args[1] if len(args) > 1 else None)
    empty, back = projector()
    mat = shirt_material(image, empty, back)
    body = D.objects['Person • clothing_outfit_map_0']
    for slot in body.material_slots:
        if slot.material and slot.material.name == 'outfit_map':
            slot.link = 'OBJECT'
            slot.material = mat
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
    print('SHIRT SAVED', out, flush=True)


if __name__ == '__main__':
    main()
