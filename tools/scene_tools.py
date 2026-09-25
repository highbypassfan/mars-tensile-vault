"""Repeatable inspection, variant creation and previews. Run with Blender --python.

See docs/SCENE-TOOLS.md. No operation saves over the loaded blend.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy

CONTROLS = 'CONTROLS • Mars vault'
MODIFIER = 'CONTROLS'


def resolve(name, objects=None):
    objects = list(objects if objects is not None else bpy.context.scene.objects)
    exact = [o for o in objects if o.name == name]
    matches = exact or [o for o in objects if o.name.startswith(name)]
    if len(matches) != 1:
        raise ValueError(f'Expected one object for {name!r}, found {[o.name for o in matches]}')
    return matches[0]


def output_path(value, suffix):
    path = Path(value).resolve()
    if path.suffix.lower() != suffix:
        raise ValueError(f'Output must end with {suffix}')
    if path == Path(bpy.data.filepath).resolve() or path.exists():
        raise ValueError(f'Refusing to overwrite existing file: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def gpu():
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    preferences = bpy.context.preferences.addons['cycles'].preferences
    for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
        try:
            preferences.compute_device_type = backend
            preferences.refresh_devices()
            if not any(d.type == backend for d in preferences.devices):
                continue
            for device in preferences.devices:
                device.use = device.type == backend
            scene.cycles.device = 'GPU'
            return backend
        except (TypeError, RuntimeError):
            continue
    return 'CPU'


class Controls:
    """The master panel: Geometry Nodes inputs on the CONTROLS object's modifier."""

    def __init__(self):
        self.obj = bpy.data.objects[CONTROLS]
        self.mod = self.obj.modifiers[MODIFIER]
        self.sockets = {}
        self.panels = {}
        for item in self.mod.node_group.interface.items_tree:
            if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.socket_type != 'NodeSocketGeometry':
                self.sockets[item.name] = item
                self.panels[item.name] = item.parent.name if item.parent else ''

    def get(self, name):
        return getattr(self.mod.properties.inputs, self.sockets[name].identifier).value

    def set(self, name, value):
        getattr(self.mod.properties.inputs, self.sockets[name].identifier).value = value
        self.obj.update_tag()

    def validate(self, name, value):
        if name not in self.sockets:
            raise ValueError(f'Unknown control {name!r}; run inspect for the list')
        sock = self.sockets[name]
        if sock.socket_type == 'NodeSocketBool':
            ok = isinstance(value, bool)
        elif sock.socket_type == 'NodeSocketInt':
            ok = type(value) is int
        else:
            ok = type(value) in (int, float) and math.isfinite(value)
        if not ok:
            raise ValueError(f'{name}: wrong value type {type(value).__name__}')
        if sock.socket_type != 'NodeSocketBool' and not sock.min_value <= value <= sock.max_value:
            raise ValueError(f'{name}: {value} outside {sock.min_value}..{sock.max_value}')

    def describe(self):
        out = {}
        for name, sock in self.sockets.items():
            entry = {'value': self.get(name), 'description': sock.description}
            if sock.socket_type != 'NodeSocketBool':
                entry['min'], entry['max'] = sock.min_value, sock.max_value
            out.setdefault(self.panels[name], {})[name] = entry
        return out


def evaluate_state():
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    lights = [o for o in scene.objects if o.type == 'LIGHT']
    lit, hidden_powered = [], []
    for obj in lights:
        ev = obj.evaluated_get(dg)
        if ev.data.energy > 0 and not ev.hide_render:
            lit.append(obj.name)
        elif ev.data.energy > 0:
            hidden_powered.append(obj.name)
    return {'exposure': round(scene.view_settings.exposure, 4),
            'rendered_powered_lights': len(lit),
            'hidden_powered_lights': hidden_powered}


def report():
    scene = bpy.context.scene
    controls = Controls()
    missing, unpacked = [], []
    for img in bpy.data.images:
        if img.source in {'FILE', 'TILED'} and not img.packed_file and not len(img.packed_files):
            unpacked.append(img.name)
            if not Path(bpy.path.abspath(img.filepath, library=img.library)).exists():
                missing.append({'image': img.name, 'path': img.filepath})
    states = {}
    original = controls.get('Night')
    try:
        for night in (False, True):
            controls.set('Night', night)
            states['night' if night else 'day'] = evaluate_state()
    finally:
        controls.set('Night', original)
    python_drivers = 0
    owners = [*bpy.data.objects, *bpy.data.node_groups, *bpy.data.scenes, *bpy.data.lights,
              *[m.node_tree for m in bpy.data.materials if m.node_tree],
              *[w.node_tree for w in bpy.data.worlds if w.node_tree]]
    for owner in owners:
        if owner.animation_data:
            python_drivers += sum(d.driver.type == 'SCRIPTED' and not d.driver.is_simple_expression
                                  for d in owner.animation_data.drivers)
    warnings = []
    if missing:
        warnings.append('Missing external images')
    if python_drivers:
        warnings.append(f'{python_drivers} drivers need Python auto-execution')
    if bpy.data.libraries:
        warnings.append('Linked libraries must accompany the share file')
    size = Path(bpy.data.filepath).stat().st_size
    if size > 95 * 1024 * 1024:
        warnings.append('Blend is close to or above GitHub ordinary-file limit of 100 MiB')
    return {
        'blend': bpy.data.filepath, 'blender': bpy.app.version_string,
        'file_bytes': size, 'objects': len(scene.objects),
        'unique_meshes': len({o.data.name for o in scene.objects if o.type == 'MESH'}),
        'units': {'system': scene.unit_settings.system, 'scale_length': scene.unit_settings.scale_length},
        'render': {'engine': scene.render.engine, 'device': scene.cycles.device,
                   'samples': scene.cycles.samples, 'bounces': scene.cycles.max_bounces,
                   'transmission_bounces': scene.cycles.transmission_bounces,
                   'transparent_bounces': scene.cycles.transparent_max_bounces},
        'cameras': [o.name for o in scene.objects if o.type == 'CAMERA'],
        'controls': controls.describe(), 'day_night': states, 'missing_images': missing,
        'unpacked_images': unpacked, 'linked_libraries': [l.filepath for l in bpy.data.libraries],
        'warnings': warnings,
    }


def apply_changes(changes):
    """Validate every edit before applying any. Values are set directly (no keyframes)."""
    controls = Controls()
    if not isinstance(changes, dict):
        raise ValueError('Settings must be an object mapping control names to values')
    for name, value in changes.items():
        controls.validate(name, value)
    for name, value in changes.items():
        controls.set(name, value)
    bpy.context.view_layer.update()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'variant', 'preview'))
    parser.add_argument('--output', required=True)
    parser.add_argument('--settings', help='JSON file mapping control names to values')
    time = parser.add_mutually_exclusive_group()
    time.add_argument('--night', action='store_true', help='Shortcut for {"Night": true}')
    time.add_argument('--day', action='store_true', help='Shortcut for {"Night": false}')
    parser.add_argument('--camera', help='Exact camera name or unique prefix, e.g. 08')
    parser.add_argument('--samples', type=int, default=32)
    parser.add_argument('--width', type=int, default=960)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    scene = bpy.context.scene
    if args.action == 'inspect':
        target = output_path(args.output, '.json')
        target.write_text(json.dumps(report(), indent=2, ensure_ascii=False), encoding='utf-8')
    else:
        target = output_path(args.output, '.blend' if args.action == 'variant' else '.png')
        changes = json.loads(Path(args.settings).read_text(encoding='utf-8-sig')) if args.settings else {}
        if args.night or args.day:
            changes['Night'] = args.night
        if changes:
            apply_changes(changes)
        if args.camera:
            scene.camera = resolve(args.camera, [o for o in scene.objects if o.type == 'CAMERA'])
        if args.action == 'variant':
            if not changes and not args.camera:
                raise ValueError('variant needs --settings, --night/--day or --camera')
            bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=True)
        else:
            if not 1 <= args.samples <= 4096 or not 64 <= args.width <= 16384:
                raise ValueError('Samples must be 1–4096 and width 64–16384')
            backend = gpu()
            ratio = scene.render.resolution_y / scene.render.resolution_x
            scene.render.resolution_x = args.width
            scene.render.resolution_y = round(args.width * ratio)
            scene.render.resolution_percentage = 100
            scene.cycles.samples = args.samples
            scene.render.image_settings.file_format = 'PNG'
            scene.render.image_settings.color_mode = 'RGB'
            scene.render.image_settings.color_depth = '8'
            scene.render.filepath = str(target)
            print('RENDER DEVICE', backend, flush=True)
            bpy.ops.render.render(write_still=True)
    print('SCENE TOOL COMPLETE', target, flush=True)


if __name__ == '__main__':
    main()
