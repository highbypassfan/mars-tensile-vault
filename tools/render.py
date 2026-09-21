"""Render the packaged scene using an available GPU, with CPU fallback."""
import bpy
from pathlib import Path

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
preferences = bpy.context.preferences.addons['cycles'].preferences
scene.cycles.device = 'CPU'
for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
    try:
        preferences.compute_device_type = backend
        preferences.refresh_devices()
        available = [d for d in preferences.devices if d.type == backend]
        if not available:
            continue
        for device in preferences.devices:
            device.use = device.type == backend
        scene.cycles.device = 'GPU'
        print('Rendering with', backend, [d.name for d in available])
        break
    except (TypeError, RuntimeError):
        continue
root = Path(bpy.data.filepath).parent
output = root / 'renders'
output.mkdir(exist_ok=True)
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(output / 'render.png')
bpy.ops.render.render(write_still=True)
