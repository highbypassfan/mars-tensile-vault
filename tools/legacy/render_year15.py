import bpy
from pathlib import Path
r=Path(bpy.data.filepath).parent;s=bpy.context.scene;p=bpy.context.preferences.addons['cycles'].preferences
s.cycles.device='CPU'
for backend in ('OPTIX','CUDA','HIP','METAL','ONEAPI'):
 try:
  p.compute_device_type=backend;p.refresh_devices()
  if not any(d.type==backend for d in p.devices):continue
  for d in p.devices:d.use=d.type==backend
  s.cycles.device='GPU';print('RENDER DEVICE',backend,flush=True);break
 except (TypeError,RuntimeError):pass
s.cycles.samples=96;s.cycles.adaptive_threshold=.012;s.render.resolution_percentage=65
for name,frame,file in [('08 • exterior spill and freight airlock',120,'year15-exterior-night'),('02 • civic park and heritage ships',120,'year15-park-night'),('01 • valley and landing field',1,'year15-valley-day'),('02 • civic park and heritage ships',1,'year15-park-day'),('05 • cargo yard',1,'year15-cargo-day'),('06 • landing field',1,'year15-landing-day'),('09 • night habitat from valley',120,'year15-valley-night')]:
 s.camera=bpy.data.objects[name];s.frame_set(frame);s.render.filepath=str(r/'previews'/f'{file}.png');bpy.ops.render.render(write_still=True);print('FINISHED',file,flush=True)
