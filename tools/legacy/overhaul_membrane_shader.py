"""One-time overhaul of the roof membrane shader (Kevlar-reinforced ETFE laminate).

Root cause of the mirror-like roof: refine_night_optics.py fed the thin-sheet model
from Blender's Fresnel node. Cycles inverts the IOR on back faces, so from inside the
vault (you always see back faces) it computed a dense-to-air interface and hit total
internal reflection beyond ~45 deg incidence. The roof became a 100% mirror of the
grass and regolith. A free-standing film has air on both sides, so its reflectance is
side-independent.

This rebuild keeps the existing weld, ply-count and aramid-mask logic, and replaces
only the optical core with:
  * exact unpolarised dielectric Fresnel (s and p), computed from the geometric
    incidence angle and identical from either side
  * incoherent two-interface sheet reflectance per polarisation, 2R/(1+R)
  * Beer-Lambert absorption and haze over the refracted internal path
  * energy-conserving sum: specular transmission + diffuse (haze) transmission +
    reflection
  * aramid bundles that are partly translucent when backlit instead of opaque paint

Usage (Blender 5.2, from the repository folder):
  blender -b mars-tensile-vault.blend --factory-startup --disable-autoexec \
      --python-exit-code 1 --python tools/overhaul_membrane_shader.py
Optional after "--":  --save-as path.blend   (write elsewhere)   --no-save
Without options it backs up to renders/before-membrane-overhaul.blend, then saves in place.
"""
import bpy, sys, shutil
from pathlib import Path

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
R = Path(bpy.data.filepath).parent
ctrl = bpy.data.objects['SETTLEMENT • time and district controls']
m = bpy.data.materials['Live membrane • roof and four-ply rings']
nt = m.node_tree; nodes = nt.nodes; links = nt.links
if 'Membrane optics revision' in ctrl and ctrl['Membrane optics revision'] >= 2:
    raise RuntimeError('Membrane shader already overhauled')

# ---- controls on the settlement controller (all keyframe-safe custom props)
for k, v, lo, hi, desc in [
    ('Film IOR', 1.40, 1.30, 1.60, 'ETFE refractive index (literature ~1.40)'),
    ('Film haze per ply', ctrl.get('Film haze per ply', .025), 0, .2, 'Diffuse scatter per ply at normal incidence'),
    ('Film reflection roughness', .06, .005, .4, 'GGX roughness of the laminate reflection; higher softens pillow mirroring'),
    ('Film reflection strength', 1.0, 0, 1, 'Artistic scale on physical sheet reflectance (1 = physical)'),
    ('Aramid translucency', .35, 0, 1, 'Share of backlit transmission through the aramid bundles'),
]:
    ctrl[k] = v
    ctrl.id_properties_ui(k).update(min=lo, max=hi, description=desc)
ctrl['Membrane optics revision'] = 2

def drive_value(label, prop):
    n = nodes.new('ShaderNodeValue'); n.label = label
    fc = n.outputs[0].driver_add('default_value'); d = fc.driver; d.type = 'SCRIPTED'; d.expression = 'v'
    v = d.variables.new(); v.name = 'v'; v.targets[0].id = ctrl; v.targets[0].data_path = '["' + prop + '"]'
    return n.outputs[0]

def math(op, a, b=None, label=None, clamp=False):
    n = nodes.new('ShaderNodeMath'); n.operation = op; n.label = label or op; n.use_clamp = clamp
    for i, x in enumerate([a, b]):
        if x is None: continue
        if isinstance(x, bpy.types.NodeSocket): links.new(x, n.inputs[i])
        else: n.inputs[i].default_value = x
    return n.outputs[0]

# ---- locate existing pieces we keep
reinf = next(n for n in nodes if n.label == 'Reinforcement concentrated at welds and corners')
old_film = reinf.inputs[1].links[0].from_node
assert old_film.label == 'Angle dependent multilayer film', old_film.label
plies = nodes['MAXIMUM'].outputs[0]                          # optical ply count (welds/rings)
assert nodes['MAXIMUM'].inputs[0].links[0].from_node.name == 'MULTIPLY.007'
film_T = next(n for n in nodes if n.type == 'ATTRIBUTE' and n.attribute_name == 'Film Transmission').outputs['Fac']
geo = next(n for n in nodes if n.label == 'Two-sided sheet')
wrinkle = next(n for n in nodes if n.label == 'Subtle reflective wrinkles').outputs['Normal']
aramid = next(n for n in nodes if n.label == 'Gold aramid bundles')

before = set(n.name for n in nodes)
# Drop old drivers on nodes that will be removed (haze/roughness values are recreated below)
if nt.animation_data:
    for fc in list(nt.animation_data.drivers):
        if fc.data_path in ('nodes["Value"].outputs[0].default_value', 'nodes["Value.001"].outputs[0].default_value'):
            nt.animation_data.drivers.remove(fc)

# ---- new optical core
ior = drive_value('Film IOR', 'Film IOR')
haze_pp = drive_value('Film haze per ply', 'Film haze per ply')
rough = drive_value('Film reflection roughness', 'Film reflection roughness')
rstrength = drive_value('Film reflection strength', 'Film reflection strength')
arT = drive_value('Aramid translucency', 'Aramid translucency')

dot = nodes.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'; dot.label = 'Geometric incidence'
links.new(geo.outputs['Incoming'], dot.inputs[0]); links.new(geo.outputs['Normal'], dot.inputs[1])
c = math('MAXIMUM', math('ABSOLUTE', dot.outputs['Value']), 1e-4, 'cos θi (either side)')
c = math('MINIMUM', c, 1.0)
n2 = math('MULTIPLY', ior, ior, 'n²')
g = math('SQRT', math('ADD', math('SUBTRACT', n2, 1.0), math('MULTIPLY', c, c)), label='g = n·cos θt')
def sq_ratio(a, b, label):
    r = math('DIVIDE', math('SUBTRACT', a, b), math('ADD', a, b))
    return math('MULTIPLY', r, r, label)
Rs = sq_ratio(c, g, 'Rs single interface')
Rp = sq_ratio(math('MULTIPLY', n2, c), g, 'Rp single interface')
def sheet(Rx, label):  # incoherent two-interface slab, lossless
    return math('DIVIDE', math('MULTIPLY', Rx, 2.0), math('ADD', Rx, 1.0), label)
Rsheet = math('MULTIPLY', math('ADD', sheet(Rs, 'Rs sheet'), sheet(Rp, 'Rp sheet')), 0.5, 'Sheet reflectance (side-independent)')
cos_t = math('DIVIDE', g, ior, 'cos θt inside film')
path = math('DIVIDE', plies, math('MAXIMUM', cos_t, .05), 'Internal optical path (ply units)')
T_abs = math('POWER', film_T, path, 'Absorption (Beer-Lambert)')
haze = math('SUBTRACT', 1.0, math('POWER', math('SUBTRACT', 1.0, haze_pp), path), 'Haze fraction', clamp=True)
T_sheet = math('MULTIPLY', math('SUBTRACT', 1.0, Rsheet), T_abs, 'Transmitted energy')
T_direct = math('MULTIPLY', T_sheet, math('SUBTRACT', 1.0, haze), 'Clear transmission')
T_haze = math('MULTIPLY', T_sheet, haze, 'Hazed transmission')
refl = math('MULTIPLY', Rsheet, rstrength, 'Reflection weight')

tr = nodes.new('ShaderNodeBsdfTransparent'); tr.label = 'ETFE clear transmission'
links.new(T_direct, tr.inputs['Color'])
tint = nodes.new('ShaderNodeVectorMath'); tint.operation = 'MULTIPLY'; tint.label = 'Haze tint'
links.new(T_haze, tint.inputs[0]); tint.inputs[1].default_value = (.96, .96, .93)
tl = nodes.new('ShaderNodeBsdfTranslucent'); tl.label = 'ETFE haze scatter'
links.new(tint.outputs['Vector'], tl.inputs['Color'])
gl = nodes.new('ShaderNodeBsdfAnisotropic'); gl.label = 'ETFE sheet reflection'
gl.distribution = 'MULTI_GGX' if 'MULTI_GGX' in [e.identifier for e in gl.bl_rna.properties['distribution'].enum_items] else 'GGX'
links.new(refl, gl.inputs['Color']); links.new(rough, gl.inputs['Roughness']); links.new(wrinkle, gl.inputs['Normal'])
a1 = nodes.new('ShaderNodeAddShader'); a1.label = 'Transmission'
links.new(tr.outputs[0], a1.inputs[0]); links.new(tl.outputs[0], a1.inputs[1])
film = nodes.new('ShaderNodeAddShader'); film.label = 'Kevlar-reinforced ETFE film'
links.new(a1.outputs[0], film.inputs[0]); links.new(gl.outputs[0], film.inputs[1])
links.new(film.outputs[0], reinf.inputs[1])

# ---- aramid: fibre sheen when front-lit, warm glow when back-lit
aramid.inputs['Base Color'].default_value = (.42, .30, .09, 1)
aramid.inputs['Roughness'].default_value = .55
atl = nodes.new('ShaderNodeBsdfTranslucent'); atl.label = 'Aramid backlit transmission'
atl.inputs['Color'].default_value = (.50, .34, .08, 1)
links.new(aramid.inputs['Normal'].links[0].from_socket, atl.inputs['Normal'])
amix = nodes.new('ShaderNodeMixShader'); amix.label = 'Aramid bundle'
links.new(arT, amix.inputs[0]); links.new(aramid.outputs[0], amix.inputs[1]); links.new(atl.outputs[0], amix.inputs[2])
links.new(amix.outputs[0], reinf.inputs[2])

# ---- garbage-collect the old optical chain (anything no longer reaching the output)
out = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
keep = set(); stack = [out]
while stack:
    n = stack.pop()
    if n in keep: continue
    keep.add(n)
    for i in n.inputs:
        for l in i.links: stack.append(l.from_node)
removed = [n.name for n in nodes if n not in keep and n.type != 'FRAME' and n.name in before]
for name in removed: nodes.remove(nodes[name])
if nt.animation_data:  # drop drivers pointing at removed nodes
    for fc in list(nt.animation_data.drivers):
        if any(('nodes["%s"]' % r) in fc.data_path for r in removed): nt.animation_data.drivers.remove(fc)

# tidy layout of new nodes
x0 = max(n.location.x for n in keep if n.type != 'OUTPUT_MATERIAL') - 200
new = [n for n in nodes if n.name not in before]
for i, n in enumerate(new): n.location = (x0 - 1400 + (i % 6) * 220, -1400 - (i // 6) * 180)
fr = nodes.new('NodeFrame'); fr.label = 'ETFE optics rev 2 • side-independent Fresnel'
for n in new: n.parent = fr

ctrl['Membrane optics notes'] = ('Rev 2: exact side-independent Fresnel for a free-standing ETFE laminate '
    '(fixes back-face total internal reflection), absorption and haze on the refracted path, '
    'translucent aramid bundles. Physical approximation, not measured ETFE optical data.')
print('MEMBRANE OVERHAUL: removed', len(removed), 'old nodes, added', len(new), flush=True)

if '--no-save' in argv:
    pass
elif '--save-as' in argv:
    bpy.ops.wm.save_as_mainfile(filepath=argv[argv.index('--save-as') + 1], compress=True, copy=True)
else:
    backup = R / 'renders/before-membrane-overhaul.blend'
    if not backup.exists(): shutil.copy2(bpy.data.filepath, backup)
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True)
    print('SAVED', bpy.data.filepath, 'backup', backup, flush=True)
