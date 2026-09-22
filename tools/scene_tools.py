"""Repeatable inspection, variant creation and previews. Run with Blender --python.

See docs/SCENE-TOOLS.md. No operation saves over the loaded blend.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy


def json_value(value):
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    if hasattr(value, 'to_list'):
        return value.to_list()
    if hasattr(value, 'to_dict'):
        return value.to_dict()
    return str(value)


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


def report():
    scene = bpy.context.scene
    controls = {}
    for obj in scene.objects:
        if obj.type == 'EMPTY' and any(obj.name.startswith(p) for p in ('SETTLEMENT', 'SURFACES', 'LIGHTING')):
            controls[obj.name] = {
                k: {'value': json_value(obj[k]), 'ui': obj.id_properties_ui(k).as_dict()}
                for k in obj.keys() if not k.startswith('_')
                and isinstance(obj[k], (bool, int, float, str))
            }
    missing = []
    unpacked = []
    for img in bpy.data.images:
        if img.source in {'FILE', 'TILED'} and not img.packed_file and not len(img.packed_files):
            unpacked.append(img.name)
            if not Path(bpy.path.abspath(img.filepath, library=img.library)).exists():
                missing.append({'image': img.name, 'path': img.filepath})
    frames = {}
    original_frame = scene.frame_current
    try:
        for frame in (1, 120):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            rings = [o for o in scene.objects if o.type == 'LIGHT' and o.name.startswith('Ring light')]
            hidden_powered = []
            for obj in scene.objects:
                if obj.type != 'LIGHT':
                    continue
                ev = obj.evaluated_get(dg)
                if ev.data.energy > 0 and (ev.hide_render or not obj.visible_get()):
                    hidden_powered.append(obj.name)
            frames[str(frame)] = {
                'exposure': scene.view_settings.exposure,
                'active_ring_sources': sum(not o.evaluated_get(dg).hide_render and o.evaluated_get(dg).data.energy > 0 for o in rings),
                'hidden_powered_lights': hidden_powered,
            }
    finally:
        scene.frame_set(original_frame)
    warnings = []
    if missing:
        warnings.append('Missing external images')
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
        'controls': controls, 'presets': frames, 'missing_images': missing,
        'unpacked_images': unpacked, 'linked_libraries': [l.filepath for l in bpy.data.libraries],
        'warnings': warnings,
    }


def apply_changes(path, frame):
    """Validate every edit before applying any. Keyframe numeric/bool controls."""
    changes = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(changes, dict) or not changes:
        raise ValueError('Settings must be a nonempty object mapping object names to properties')
    pending = []
    for name, properties in changes.items():
        obj = resolve(name)
        if not isinstance(properties, dict):
            raise ValueError(f'{name}: expected property mapping')
        for key, value in properties.items():
            if key not in obj or key.startswith('_'):
                raise ValueError(f'{obj.name}: unknown control {key}')
            old = obj[key]
            if isinstance(old, bool):
                valid = isinstance(value, bool)
            elif isinstance(old, int):
                valid = type(value) is int
            elif isinstance(old, float):
                valid = type(value) in (float, int) and math.isfinite(value)
            else:
                valid = False
            if not valid:
                raise ValueError(f'{key}: expected {type(old).__name__} numeric/bool value')
            ui = obj.id_properties_ui(key).as_dict()
            if value < ui.get('min', -math.inf) or value > ui.get('max', math.inf):
                raise ValueError(f'{key}: value outside stored UI limits')
            data_path = '[' + json.dumps(key, ensure_ascii=False) + ']'
            if obj.animation_data and any(d.data_path == data_path for d in obj.animation_data.drivers):
                raise ValueError(f'{key}: driven property; edit its source control instead')
            pending.append((obj, key, value, data_path))
    for obj, key, value, data_path in pending:
        obj[key] = value
        obj.keyframe_insert(data_path=data_path, frame=frame)
        obj.update_tag()
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'variant', 'preview'))
    parser.add_argument('--output', required=True)
    parser.add_argument('--settings', help='JSON object mapping object names/prefixes to custom properties')
    parser.add_argument('--frame', type=int, default=1)
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
        scene.frame_set(args.frame)
        if args.settings:
            apply_changes(args.settings, args.frame)
        if args.camera:
            scene.camera = resolve(args.camera, [o for o in scene.objects if o.type == 'CAMERA'])
        if args.action == 'variant':
            if not args.settings:
                raise ValueError('variant requires --settings')
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
