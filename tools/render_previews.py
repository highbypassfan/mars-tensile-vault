"""Re-render the README preview images into previews/. Run inside Blender:

  blender -b mars-tensile-vault.blend --python tools/render_previews.py

Uses a GPU when available. Day/night comes from the Night control, not the timeline.
"""
import bpy
from pathlib import Path

root = Path(bpy.data.filepath).parent
scene = bpy.context.scene
preferences = bpy.context.preferences.addons['cycles'].preferences
scene.cycles.device = 'CPU'
for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
    try:
        preferences.compute_device_type = backend
        preferences.refresh_devices()
        if not any(d.type == backend for d in preferences.devices):
            continue
        for device in preferences.devices:
            device.use = device.type == backend
        scene.cycles.device = 'GPU'
        print('RENDER DEVICE', backend, flush=True)
        break
    except (TypeError, RuntimeError):
        pass

controls = bpy.data.objects['CONTROLS • Mars vault']
modifier = controls.modifiers['CONTROLS']
night_input = next(i.identifier for i in modifier.node_group.interface.items_tree
                   if i.item_type == 'SOCKET' and i.name == 'Night')

people = next(i.identifier for i in modifier.node_group.interface.items_tree
              if i.item_type == 'SOCKET' and i.name == 'People')
getattr(modifier.properties.inputs, people).value = True    # the crowd is off by default; show it here

scene.cycles.samples = 96
scene.cycles.adaptive_threshold = 0.012
scene.render.resolution_percentage = 65
for camera, night, file in [
        ('07 • habitat from mesa', False, 'year15-mesa-day'),
        ('02 • civic park and heritage ships', False, 'year15-park-day'),
        ('02 • civic park and heritage ships', True, 'year15-park-night'),
        ('06 • landing field', False, 'year15-landing-day'),
        ('05 • cargo yard', False, 'year15-cargo-day'),
        ('01 • valley and landing field', False, 'year15-valley-day'),
        ('09 • night habitat from valley', True, 'year15-valley-night'),
        ('08 • exterior spill and freight airlock', True, 'year15-exterior-night'),
        ('10 • solar farm and battery substation', False, 'year15-solar-farm-day'),
        ('11 • battery substation under the west wall', False, 'year15-battery-substation-day'),
        ('12 • freight yard forklift aisle', False, 'year15-freight-aisle-day'),
        ('13 • homes and residential tower', False, 'year15-towers-day'),
        ('13 • homes and residential tower', True, 'year15-towers-night')]:
    getattr(modifier.properties.inputs, night_input).value = night
    controls.update_tag()
    scene.camera = bpy.data.objects[camera]
    scene.render.filepath = str(root / 'previews' / f'{file}.png')
    bpy.ops.render.render(write_still=True)
    print('FINISHED', file, flush=True)
