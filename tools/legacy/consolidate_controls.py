"""One-time migration (2026-09-22): merge every scene control into one panel.

Run in background Blender on the pre-consolidation blend and save to a NEW file:
  blender -b --factory-startup --disable-autoexec old.blend --python-exit-code 1 \
      --python tools/legacy/consolidate_controls.py -- new.blend

What it does
- Creates CONTROLS • Mars vault, an empty mesh whose Geometry Nodes modifier is
  the single, sectioned control panel (Modifier tab). Every driver that read the
  old SETTLEMENT / LIGHTING / SURFACES empties is retargeted to it.
- Replaces the keyframed solar hour (frame 1 = day, frame 120 = night) with a
  single Night checkbox. Nothing in the scene depends on the timeline any more.
- Moves the membrane foundation custom properties onto the membrane modifier
  itself (they were only mirrored there by drivers) and hides mirrored inputs.
- Freezes the retired cage-grass inputs, deletes the duplicate .001 empties and
  the retired exterior-dust object.
- Rewrites Python-only driver expressions (%) as simple fmod() expressions,
  so no driver needs script auto-execution.
- Adds a faint blue Mars sky tint/aureole and a procedural distant-mountain
  horizon to the world, both controlled from the panel.
Not repeatable: it expects the old control objects to exist.
"""
import sys

import bpy

D = bpy.data
CTL_NAME = 'CONTROLS • Mars vault'
MOD = 'CONTROLS'


def one(prefix):
    found = [o for o in D.objects if o.name == prefix] or [o for o in D.objects if o.name.startswith(prefix)]
    if len(found) != 1:
        raise RuntimeError(f'Expected one object for {prefix!r}: {[o.name for o in found]}')
    return found[0]


SET = D.objects['SETTLEMENT • time and district controls']
SET1 = D.objects.get('SETTLEMENT • time and district controls.001')
LIT = D.objects['LIGHTING • toggle Night sky']
LIT1 = D.objects.get('LIGHTING • toggle Night sky.001')
SURF = D.objects['SURFACES • grass and lighting controls']
DUST = D.objects.get('EXTERIOR DUST • toggle render or Dust Storm')
MEMB = one('MEMBRANE • pressure-derived panels')
CAGE = one('TENSILE CAGE')
SUN = D.objects['Mars_Sun']
WORLD = D.worlds['Mars • dusty afternoon']

# (panel, open, [(name, source object, source key or default value, kind, description)])
# kind: bool | int | float | factor | dist
S = SET
SPEC = [
    ('Time of day', True, [
        ('Night', None, False, 'bool', 'THE day/night switch. Off = daytime at Day solar hour; on = night: stars, ring LEDs, apron floods, lit windows, night exposure'),
        ('Day solar hour', S, 15.0, 'float', 'Sun position in daytime, 0–24 local solar time (12 = noon). Sunlight fades to zero at 06:00 and 18:00'),
        ('Sun strength', S, 'Sun strength', 'float', None),
        ('Day sky strength', S, 'Day sky strength', 'float', None),
        ('Day exposure', S, 'Day exposure', 'float', 'Photographic exposure (EV) used when Night is off'),
        ('Night exposure', S, 'Night exposure', 'float', 'Photographic exposure (EV) used when Night is on'),
    ]),
    ('Sky and atmosphere', False, [
        ('Day sky blue', None, 0.35, 'factor', 'Faint blue in the daytime sky: bluish zenith and the blue aureole Mars shows around the Sun. 0 = pure butterscotch'),
        ('Skybox mountains', None, True, 'bool', 'Procedural mountain silhouettes on the far horizon, beyond the modelled mesas'),
        ('Skybox mountain height deg', None, 4.2, 'float', 'Tallest skybox peak, in degrees above the horizon'),
        ('Skybox mountain haze', None, 0.5, 'factor', 'How far the skybox mountains fade into the sky colour (1 = invisible)'),
        ('Night sky strength', S, 'Night sky strength', 'float', None),
        ('Star foreground gain', S, 'Star foreground gain', 'float', None),
        ('Milky Way gain', S, 'Milky Way gain', 'float', None),
        ('Exterior haze', S, 'Exterior haze', 'bool', None),
        ('Haze density', S, 'Haze density', 'float', None),
        ('Dust storm', S, 'Dust storm', 'bool', None),
    ]),
    ('Moon (Phobos)', False, [
        ('Moon fill', S, 'Moon fill', 'bool', None),
        ('Moon fill strength', S, 'Moon fill strength', 'float', None),
        ('Moon presentation boost', S, 'Moon presentation boost', 'float', 'Artistic multiplier so the exterior reads at night. 1 = faint physical reference'),
        ('Moon azimuth deg', S, 'Moon azimuth deg', 'float', None),
        ('Moon altitude deg', S, 'Moon altitude deg', 'float', None),
        ('Show Phobos disk', S, 'Show Phobos disk', 'bool', None),
    ]),
    ('Habitat lights (night)', False, [
        ('Habitat lights', S, 'Habitat lights', 'bool', None),
        ('LED brightness', S, 'LED brightness', 'float', 'Visible glow of the ring LED strips (also sets the cage LED Strength)'),
        ('Ring light power W', S, 'Ring light power W', 'float', 'Illumination per active ring'),
        ('LED temperature K', S, 'LED temperature K', 'float', None),
        ('LED every L', S, 'LED every L', 'int', 'Light every Nth ring along L'),
        ('LED every W', S, 'LED every W', 'int', 'Light every Nth ring along W'),
        ('LED phase L', S, 'LED phase L', 'int', None),
        ('LED phase W', S, 'LED phase W', 'int', None),
        ('LED checkerboard', S, 'LED checkerboard', 'bool', 'Additionally keep only alternating L+W parity'),
        ('LED beam angle deg', SURF, 'LED full beam angle deg', 'float', 'Total downward cone width of the ring emission'),
        ('LED beam gain', SURF, 'LED beam gain', 'float', None),
        ('LED ambient glow fraction', SURF, 'LED ambient glow fraction', 'factor', 'Faint emission outside the beam'),
        ('Ring mesh illumination gain', S, 'Ring mesh illumination gain', 'float', None),
        ('Annular ring lighting', S, 'Annular ring lighting', 'bool', 'On: the LED ring meshes emit the light. Off: older sampled disk lights'),
        ('Airlock apron lights', S, 'Airlock apron lights', 'bool', None),
        ('Apron light power W', S, 'Apron light power W', 'float', None),
    ]),
    ('Districts', False, [
        ('Homes', S, 'Homes', 'bool', None),
        ('Warehouses', S, 'Warehouses', 'bool', None),
        ('Industry and tanks', S, 'Industry and tanks', 'bool', None),
        ('Cargo yard', S, 'Cargo yard', 'bool', None),
        ('Starships', S, 'Starships', 'bool', None),
        ('Grass areas', S, 'Grass areas', 'bool', None),
    ]),
    ('Grass detail', False, [
        ('Near grass distance m', S, 'Near grass distance m', 'dist', 'Dense 96-blade clumps out to this distance from the render camera'),
        ('Mid grass distance m', S, 'Mid grass distance m', 'dist', None),
        ('Far grass distance m', S, 'Far grass distance m', 'dist', 'Beyond this only the textured turf surface remains'),
        ('Grass density multiplier', S, 'Grass density multiplier', 'float', None),
    ]),
    ('Membrane optics', False, [
        ('Film IOR', S, 'Film IOR', 'float', None),
        ('Film haze per ply', S, 'Film haze per ply', 'float', None),
        ('Film reflection roughness', S, 'Film reflection roughness', 'float', None),
        ('Film reflection strength', S, 'Film reflection strength', 'float', None),
        ('Aramid translucency', S, 'Aramid translucency', 'factor', 'Translucency of the Kevlar reinforcement bundles'),
    ]),
    ('Viewport performance', False, [
        ('Viewport tether LOD', S, 'Viewport tether LOD', 'bool', 'Coarse anchors in the viewport only; final renders always use full detail'),
        ('Viewport tether every L', S, 'Viewport tether every L', 'int', None),
        ('Viewport tether every W', S, 'Viewport tether every W', 'int', None),
        ('Viewport tether branches', S, 'Viewport tether branches', 'int', None),
        ('Viewport tether sides', S, 'Viewport tether sides', 'int', None),
        ('Viewport ring segments', S, 'Viewport ring segments', 'int', None),
    ]),
]
SOCKET = {'bool': 'NodeSocketBool', 'int': 'NodeSocketInt', 'float': 'NodeSocketFloat',
          'factor': 'NodeSocketFloat', 'dist': 'NodeSocketFloat'}


def all_anim_owners():
    for coll in (D.objects, D.node_groups, D.scenes, D.lights, D.cameras, D.meshes):
        yield from coll
    for coll in (D.materials, D.worlds, D.lights):
        for idb in coll:
            if getattr(idb, 'node_tree', None):
                yield idb.node_tree


def all_drivers():
    for owner in all_anim_owners():
        ad = owner.animation_data
        if ad:
            for fc in ad.drivers:
                yield owner, fc


# ---------------------------------------------------------------- control panel
def build_controls():
    ng = D.node_groups.new(CTL_NAME, 'GeometryNodeTree')
    ng.use_fake_user = False
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
    go.location.x = 300
    ng.links.new(gi.outputs[0], go.inputs[0])
    ng.description = 'Mars tensile vault master controls. Inputs are read by drivers; the group itself passes geometry through.'
    values, idents = {}, {}
    for panel_name, is_open, items in SPEC:
        panel = ng.interface.new_panel(panel_name, default_closed=not is_open)
        for name, src, key, kind, desc in items:
            sock = ng.interface.new_socket(name, in_out='INPUT', socket_type=SOCKET[kind], parent=panel)
            if src is not None and isinstance(key, str):
                value = src[key]
                ui = src.id_properties_ui(key).as_dict()
            else:
                value, ui = key, {}
            if kind == 'bool':
                value = bool(value)
            elif kind == 'int':
                value = int(value)
            else:
                value = float(value)
            if kind == 'factor':
                sock.subtype = 'FACTOR'
                sock.min_value, sock.max_value = 0.0, 1.0
            elif kind == 'dist':
                sock.subtype = 'DISTANCE'
            if kind in ('int', 'float', 'dist') and ui:
                lo = ui.get('min', ui.get('soft_min'))
                hi = ui.get('max', ui.get('soft_max'))
                if lo is not None:
                    sock.min_value = lo
                if hi is not None:
                    sock.max_value = hi
            if name == 'Day solar hour':
                sock.min_value, sock.max_value = 0.0, 24.0
            if name == 'Skybox mountain height deg':
                sock.min_value, sock.max_value = 0.0, 10.0
            if kind != 'bool' and hasattr(sock, 'structure_type'):
                sock.structure_type = 'SINGLE'
            sock.default_value = value
            sock.description = desc or ui.get('description', '') or ''
            values[name] = value
            idents[name] = sock.identifier
    mesh = D.meshes.new(CTL_NAME)
    ctl = D.objects.new(CTL_NAME, mesh)
    coll = SET.users_collection[0]
    coll.objects.link(ctl)
    coll.name = 'CONTROLS'
    ctl.hide_render = True
    mod = ctl.modifiers.new(MOD, 'NODES')
    mod.node_group = ng
    mod.show_expanded = True
    for name, value in values.items():
        getattr(mod.properties.inputs, idents[name]).value = value
    return ctl, idents


def path(idents, name):
    return f'modifiers["{MOD}"].properties.inputs.{idents[name]}.value'


# -------------------------------------------------------------------- drivers
def retarget(ctl, idents):
    mapping = {}
    for _, items in ((p, i) for p, _, i in SPEC):
        for name, src, key, kind, _ in items:
            if src is not None and isinstance(key, str):
                mapping[(src.name, f'["{key}"]')] = name
    mapping[(SET.name, '["Local solar hour"]')] = 'Day solar hour'
    mapping[(LIT.name, '["Night sky"]')] = 'Night'
    mapping[(LIT.name, '["Night sky gain"]')] = 'Night sky strength'
    mapping[(LIT.name, '["Day exposure EV"]')] = 'Day exposure'
    mapping[(LIT.name, '["Night exposure EV"]')] = 'Night exposure'
    if SET1:
        for key in SET1.keys():
            if (SET.name, f'["{key}"]') in mapping:
                mapping[(SET1.name, f'["{key}"]')] = mapping[(SET.name, f'["{key}"]')]
    count = 0
    for owner, fc in all_drivers():
        if owner in (LIT, LIT1, SET, SET1, SURF, DUST):
            continue
        for var in fc.driver.variables:
            for t in var.targets:
                if t.id is None:
                    continue
                new = mapping.get((t.id.name, t.data_path))
                if new:
                    t.id = ctl
                    t.data_path = path(idents, new)
                    count += 1
    return count


def simple_expressions():
    """Python's % made 5,000 ring-light drivers need script auto-run; fmod does not."""
    import re
    fixed = 0
    for _, fc in all_drivers():
        drv = fc.driver
        if drv.type == 'SCRIPTED' and not drv.is_simple_expression and '%' in drv.expression:
            drv.expression = re.sub(r'\(([^()]*)\)%(\w+)',
                                    lambda m: f'fmod({m.group(1)},{m.group(2)})', drv.expression)
            fixed += drv.is_simple_expression
    return fixed


def sun_drivers(ctl, idents):
    """Sun follows Day solar hour and is switched off by Night."""
    fc = SUN.data.animation_data.drivers.find('energy')
    drv = fc.driver
    n = drv.variables.new()
    n.name = 'n'
    n.targets[0].id = ctl
    n.targets[0].data_path = path(idents, 'Night')
    drv.expression = 'strength*max(0,cos((h-12)*pi/12))*(1-n)'


def memb_to_modifier():
    """Foundation props lived on MEMB and were copied into its modifier by drivers."""
    mod = next(m for m in MEMB.modifiers if m.type == 'NODES' and m.name.startswith('LIVE'))
    moved = {}
    for fc in list(MEMB.animation_data.drivers):
        var = fc.driver.variables[0]
        t = var.targets[0]
        if t.id == MEMB and t.data_path.startswith('["'):
            prop_path = t.data_path
            socket_path = fc.data_path
            value = MEMB[prop_path[2:-2]]
            MEMB.driver_remove(socket_path, fc.array_index)
            MEMB.path_resolve(socket_path.rsplit('.value', 1)[0]).value = value
            moved[prop_path] = socket_path
    for owner, fc in all_drivers():
        for var in fc.driver.variables:
            for t in var.targets:
                if t.id == MEMB and t.data_path in moved:
                    t.data_path = moved[t.data_path]
    for key in list(MEMB.keys()):
        if not key.startswith('_') and key != 'cycles':
            del MEMB[key]
    # Hide inputs that simply mirror the cage; leave foundation inputs visible.
    mirrored = {fc.data_path.split('.inputs.')[1].split('.')[0] for fc in MEMB.animation_data.drivers
                if '.inputs.' in fc.data_path}
    for item in mod.node_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.identifier in mirrored:
            item.hide_in_modifier = True
    return mod, len(moved)


def clear_membrane_to_modifier(mod):
    """'Clear modeling membrane' was a SURFACES prop feeding a Value node."""
    ng = mod.node_group
    ad = ng.animation_data
    for fc in list(ad.drivers):
        t = fc.driver.variables[0].targets[0]
        if t.id == SURF and t.data_path == '["Clear modeling membrane"]':
            node_name = fc.data_path.split('"')[1]
            value = bool(SURF['Clear modeling membrane'])
            node = ng.nodes[node_name]
            sock = ng.interface.new_socket('Clear viewport membrane', in_out='INPUT', socket_type='NodeSocketBool')
            sock.description = 'Viewport-only: show membrane faces nearly transparent in Material Preview. Final renders are unaffected'
            sock.default_value = value
            gi = ng.nodes.new('NodeGroupInput')
            gi.location = node.location
            for link in list(node.outputs[0].links):
                ng.links.new(gi.outputs[sock.identifier], link.to_socket)
            ad.drivers.remove(fc)
            ng.nodes.remove(node)
            getattr(mod.properties.inputs, sock.identifier).value = value
            return True
    return False


def freeze_cage():
    """Retired cage grass inputs were driven by SURFACES; LED Strength stays driven."""
    mod = CAGE.modifiers['PARAMETERS • edit here']
    hidden = []
    for fc in list(CAGE.animation_data.drivers):
        t = fc.driver.variables[0].targets[0]
        if t.id == SURF:
            data_path = fc.data_path
            socket = CAGE.path_resolve(data_path.rsplit('.value', 1)[0])
            value = socket.value
            CAGE.driver_remove(data_path, fc.array_index)
            socket.value = value
            hidden.append(data_path.split('.inputs.')[1].split('.')[0])
    hidden += ['Socket_120', 'Socket_15']  # LED Strength (driven by LED brightness); unused Pressure/Bulge
    for item in mod.node_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.identifier in hidden:
            item.hide_in_modifier = True
        if item.item_type == 'PANEL' and item.name.startswith('07'):
            item.name = '07 • Legacy cargo and bulldozer (off)'
        if item.item_type == 'PANEL' and item.name.startswith('08'):
            item.name = '08 • Legacy terrain and base modules (off)'
    return hidden


# ------------------------------------------------------------------------ sky
def drive(socket_owner_tree, data_path, expr, variables):
    fc = socket_owner_tree.driver_add(data_path)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    for name, idb, dpath in variables:
        v = drv.variables.new()
        v.name = name
        v.targets[0].id = idb
        v.targets[0].data_path = dpath
    drv.expression = expr
    return fc


def build_sky(ctl, idents):
    nt = WORLD.node_tree
    N, L = nt.nodes, nt.links
    ctl_var = lambda name, var: (var, ctl, path(idents, name))

    def node(kind, x, y, label='', **inputs):
        n = N.new(kind)
        n.location = (x, y)
        n.label = label
        for k, v in inputs.items():
            n.inputs[k].default_value = v
        return n

    def value(label, x, y, name):
        n = node('ShaderNodeValue', x, y, label)
        drive(nt, f'nodes["{n.name}"].outputs[0].default_value', 'v', [ctl_var(name, 'v')])
        return n.outputs[0]

    def math(op, a, b, x, y, label='', clamp=False):
        n = node('ShaderNodeMath', x, y, label)
        n.operation = op
        n.use_clamp = clamp
        for i, src in enumerate((a, b)):
            if isinstance(src, (int, float)):
                n.inputs[i].default_value = src
            elif src is not None:
                L.new(src, n.inputs[i])
        return n.outputs[0]

    def mix(a, b, fac, x, y, label='', blend='MIX'):
        n = node('ShaderNodeMix', x, y, label)
        n.data_type = 'RGBA'
        n.blend_type = blend
        n.clamp_result = False
        sock = {s.identifier: s for s in n.inputs}
        for key, src in (('A_Color', a), ('B_Color', b), ('Factor_Float', fac)):
            if isinstance(src, (int, float, tuple)):
                sock[key].default_value = src
            else:
                L.new(src, sock[key])
        return next(s for s in n.outputs if s.identifier == 'Result_Color')

    X = -1400
    coord = node('ShaderNodeTexCoord', X - 200, 1200)
    # In a world shader, Normal points back toward the camera; negate it.
    view = node('ShaderNodeVectorMath', X, 1200, 'View direction')
    view.operation = 'SCALE'
    view.inputs['Scale'].default_value = -1.0
    L.new(coord.outputs['Normal'], view.inputs[0])
    view_dir = view.outputs['Vector']
    sep = node('ShaderNodeSeparateXYZ', X + 200, 1200)
    L.new(view_dir, sep.inputs[0])
    z = sep.outputs['Z']

    # ---- blue: bluish zenith and a blue aureole around the Sun (Mars forward scattering)
    blue = value('Day sky blue', X, 1000, 'Day sky blue')
    sun_dir = node('ShaderNodeCombineXYZ', X + 200, 900, 'Direction to Sun (driven by Mars_Sun)')
    rot = [(c, SUN, f'rotation_euler[{i}]') for i, c in enumerate('abc')]
    exprs = ('cos(a)*sin(b)*cos(c)+sin(a)*sin(c)', 'cos(a)*sin(b)*sin(c)-sin(a)*cos(c)', 'cos(a)*cos(b)')
    for i, e in enumerate(exprs):
        drive(nt, f'nodes["{sun_dir.name}"].inputs[{i}].default_value', e, rot)
    dot = node('ShaderNodeVectorMath', X + 400, 900, 'cos(angle to Sun)')
    dot.operation = 'DOT_PRODUCT'
    L.new(view_dir, dot.inputs[0])
    L.new(sun_dir.outputs[0], dot.inputs[1])
    near_sun = math('MAXIMUM', dot.outputs['Value'], 0.0, X + 600, 900)
    aureole = math('POWER', near_sun, 12.0, X + 800, 900, 'Aureole falloff')
    zen = math('MAXIMUM', z, 0.0, X + 400, 1100)
    zen = math('POWER', zen, 0.8, X + 600, 1100, 'Zenith weight')
    ramp = N['Color Ramp']
    base = ramp.outputs['Color']
    zen_fac = math('MULTIPLY', zen, blue, X + 800, 1100)
    zen_fac = math('MULTIPLY', zen_fac, 0.45, X + 1000, 1100, 'Zenith tint amount')
    tinted = mix(base, (0.27, 0.30, 0.36, 1.0), zen_fac, X + 1200, 1100, 'Bluish zenith')
    aur_fac = math('MULTIPLY', aureole, blue, X + 1000, 900)
    aur_fac = math('MULTIPLY', aur_fac, 0.8, X + 1200, 900, 'Aureole amount')
    sky = mix(tinted, (0.36, 0.48, 0.70, 1.0), aur_fac, X + 1400, 1000, 'Blue aureole round the Sun')

    # ---- skybox mountains: two seamless noise ridgelines on the horizon
    flat = node('ShaderNodeCombineXYZ', X + 400, 700)
    L.new(sep.outputs['X'], flat.inputs[0])
    L.new(sep.outputs['Y'], flat.inputs[1])
    norm = node('ShaderNodeVectorMath', X + 600, 700, 'Azimuth on unit circle')
    norm.operation = 'NORMALIZE'
    L.new(flat.outputs[0], norm.inputs[0])
    height = value('Skybox mountain height deg', X, 600, 'Skybox mountain height deg')
    height = math('MULTIPLY', height, 0.0174533, X + 200, 600, 'deg to rad')
    haze = value('Skybox mountain haze', X, 400, 'Skybox mountain haze')
    enabled = value('Skybox mountains', X, 300, 'Skybox mountains')

    def ridge(y, scale, seed, amp, base_frac, label):
        off = node('ShaderNodeVectorMath', X + 800, y, label)
        off.operation = 'ADD'
        L.new(norm.outputs[0], off.inputs[0])
        off.inputs[1].default_value = (seed, seed * 1.7, seed * 0.3)
        noise = node('ShaderNodeTexNoise', X + 1000, y, label + ' noise')
        noise.noise_dimensions = '3D'
        noise.inputs['Scale'].default_value = scale
        noise.inputs['Detail'].default_value = 9.0
        noise.inputs['Roughness'].default_value = 0.58
        noise.inputs['Lacunarity'].default_value = 2.1
        L.new(off.outputs[0], noise.inputs['Vector'])
        shape = node('ShaderNodeMapRange', X + 1200, y, label + ' profile')
        shape.clamp = True
        L.new(noise.outputs['Fac'], shape.inputs['Value'])
        shape.inputs['From Min'].default_value = 0.32
        shape.inputs['From Max'].default_value = 0.72
        shape.inputs['To Min'].default_value = base_frac
        shape.inputs['To Max'].default_value = 1.0
        top = math('MULTIPLY', shape.outputs['Result'], height, X + 1400, y)
        top = math('MULTIPLY', top, amp, X + 1600, y, label + ' crest (rad)')
        # 1 below the crest, 0 above; ~0.02° soft edge
        edge = math('SUBTRACT', top, z, X + 1800, y)
        return math('MULTIPLY', edge, 3000.0, X + 2000, y, label + ' mask', clamp=True)

    far = ridge(700, 2.2, 11.0, 1.0, 0.18, 'Far range')
    near = ridge(450, 4.5, 37.0, 0.55, 0.05, 'Near range')
    far = math('MULTIPLY', far, enabled, X + 2200, 700)
    near = math('MULTIPLY', near, enabled, X + 2200, 450)
    either = math('MAXIMUM', far, near, X + 2400, 600, 'Mountain mask')

    rock = (0.40, 0.23, 0.14, 1.0)
    keep = math('SUBTRACT', 1.0, haze, X + 1400, 300)
    keep_near = math('MULTIPLY', keep, 1.6, X + 1600, 300, clamp=True)
    far_col = mix(sky, rock, keep, X + 2400, 900, 'Far range colour (hazy)')
    near_col = mix(sky, rock, keep_near, X + 2600, 900, 'Near range colour')
    day = mix(sky, far_col, far, X + 2800, 1000, 'Sky + far range')
    day = mix(day, near_col, near, X + 3000, 1000, 'Sky + both ranges')
    L.new(day, N['Background'].inputs['Color'])

    # Night: the ranges block the stars as a dark silhouette.
    stars = N['Vector Math.003'].outputs['Vector']
    night = mix(stars, (0.0, 0.0, 0.0, 1.0), either, X + 3000, 400, 'Stars behind mountain silhouette')
    L.new(night, N['CATALOG SKY • Catalogue night sky'].inputs['Color'])


def build_haze_blue(ctl, idents):
    """Mars' blue aureole comes from the dust itself: fine particles scatter blue
    light in a narrow forward lobe. Divert part of the exterior haze density into
    a bluish, strongly forward-scattering component (it also reddens what it
    transmits). Needed because the haze volume, not the world, forms most of the
    visible sky, especially with Dust storm on."""
    nt = D.materials['YEAR15 • exterior-only dust'].node_tree
    N, L = nt.nodes, nt.links
    pv = N['Principled Volume']
    out = N['Material Output']
    density = pv.inputs['Density'].links[0].from_socket

    def math(op, x, y, label=''):
        n = N.new('ShaderNodeMath')
        n.operation = op
        n.label = label
        n.location = (x, y)
        return n

    blue = N.new('ShaderNodeValue')
    blue.label = 'Day sky blue'
    blue.location = (pv.location.x - 800, pv.location.y - 400)
    drive(nt, f'nodes["{blue.name}"].outputs[0].default_value', 'v', [('v', ctl, path(idents, 'Day sky blue'))])
    share = math('MULTIPLY', blue.location.x + 200, blue.location.y, 'Share of dust in blue forward lobe')
    share.inputs[1].default_value = 0.4
    L.new(blue.outputs[0], share.inputs[0])
    keep = math('SUBTRACT', share.location.x + 200, share.location.y + 150)
    keep.inputs[0].default_value = 1.0
    L.new(share.outputs[0], keep.inputs[1])
    main_d = math('MULTIPLY', keep.location.x + 200, keep.location.y, 'Ordinary dust density')
    L.new(density, main_d.inputs[0])
    L.new(keep.outputs[0], main_d.inputs[1])
    L.new(main_d.outputs[0], pv.inputs['Density'])
    blue_d = math('MULTIPLY', share.location.x + 400, share.location.y - 150, 'Blue lobe density')
    L.new(density, blue_d.inputs[0])
    L.new(share.outputs[0], blue_d.inputs[1])
    scatter = N.new('ShaderNodeVolumeScatter')
    scatter.label = 'Blue forward-scattering dust (aureole)'
    scatter.location = (pv.location.x, pv.location.y - 450)
    scatter.inputs['Color'].default_value = (0.42, 0.58, 0.92, 1.0)
    scatter.inputs['Anisotropy'].default_value = 0.88
    L.new(blue_d.outputs[0], scatter.inputs['Density'])
    add = N.new('ShaderNodeAddShader')
    add.location = (out.location.x - 200, out.location.y - 200)
    L.new(pv.outputs['Volume'], add.inputs[0])
    L.new(scatter.outputs['Volume'], add.inputs[1])
    L.new(add.outputs[0], out.inputs['Volume'])


# ----------------------------------------------------------------- cleanup
def delete_old():
    doomed = [o for o in (SET, SET1, LIT, LIT1, SURF, DUST) if o]
    names = {o.name for o in doomed}
    retired = {s.material.node_tree for s in DUST.material_slots if s.material} if DUST else set()
    for owner, fc in all_drivers():
        if owner in doomed or owner in retired:
            continue
        for var in fc.driver.variables:
            for t in var.targets:
                if t.id is not None and t.id.name in names:
                    raise RuntimeError(f'{owner.name} {fc.data_path} still reads {t.id.name} {t.data_path}')
    for o in D.objects:
        if o.parent in doomed:
            raise RuntimeError(f'{o.name} is parented to a control object')
    dust_coll = DUST.users_collection[0] if DUST else None
    for o in doomed:
        D.objects.remove(o)
    if dust_coll and not dust_coll.objects and not dust_coll.children:
        D.collections.remove(dust_coll)
    return sorted(names)


def texts():
    for name in ('CONTROLS', 'GRASS AND SURFACE CONTROLS', 'START HERE', 'START HERE • year 15 settlement'):
        if name in D.texts:
            D.texts.remove(D.texts[name])
    t = D.texts.new('START HERE')
    t.write(
        'MARS TENSILE VAULT — START HERE\n\n'
        'Select "CONTROLS • Mars vault" (Outliner, CONTROLS collection) and open the Modifier tab (wrench).\n'
        'Everything about the look of the scene is there, in collapsible sections:\n'
        '  Time of day  — the Night checkbox switches day <-> night. The timeline is not used.\n'
        '  Sky and atmosphere, Moon, Habitat lights, Districts, Grass detail, Membrane optics, Viewport performance.\n\n'
        'Structure (geometry) has its own panels because it is expensive to re-evaluate:\n'
        '  TENSILE CAGE ... > Modifier "PARAMETERS • edit here"  — grid, spacing, height, anchors, cables.\n'
        '  MEMBRANE ...     > Modifier "LIVE • follows original cage controls" — concrete pad, clamps, Kevlar, airlocks.\n\n'
        'Cameras 01–09 are the presentation views. See README.md and docs/CONTROLS.md.\n')


def main():
    out = sys.argv[sys.argv.index('--') + 1]
    scene = bpy.context.scene
    simple_before = sum(1 for _, fc in all_drivers() if fc.driver.type == 'SCRIPTED' and not fc.driver.is_simple_expression)
    ctl, idents = build_controls()
    n = retarget(ctl, idents)
    sun_drivers(ctl, idents)
    simple_expressions()
    mod, moved = memb_to_modifier()
    cleared = clear_membrane_to_modifier(mod)
    hidden = freeze_cage()
    build_sky(ctl, idents)
    build_haze_blue(ctl, idents)
    removed = delete_old()
    texts()
    if CAGE.animation_data and CAGE.animation_data.action and not any(
            cb.fcurves for layer in CAGE.animation_data.action.layers for st in layer.strips for cb in st.channelbags):
        CAGE.animation_data.action = None  # empty leftover action
    scene.frame_set(1)
    for o in scene.objects:
        o.select_set(False)
    ctl.select_set(True)
    bpy.context.view_layer.objects.active = ctl
    for screen in D.screens:
        for area in screen.areas:
            if area.type == 'PROPERTIES':
                for space in area.spaces:
                    if space.type == 'PROPERTIES':
                        try:
                            space.context = 'MODIFIER'
                        except TypeError:
                            pass
    simple_after = sum(1 for _, fc in all_drivers() if fc.driver.type == 'SCRIPTED' and not fc.driver.is_simple_expression)
    D.orphans_purge(do_recursive=True)
    print('MIGRATION retargeted', n, 'moved membrane props', moved, 'clear membrane', cleared,
          'frozen/hidden cage', hidden, 'removed', removed,
          'python-only drivers before/after', simple_before, simple_after, flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    print('MIGRATION SAVED', out, flush=True)


main()
