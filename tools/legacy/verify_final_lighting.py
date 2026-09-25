import bpy,json,math
from pathlib import Path
R=Path(bpy.data.filepath).parent;s=bpy.context.scene;c=bpy.data.objects['SETTLEMENT • time and district controls'];moon=bpy.data.objects['MOON • Phobos fill with optional presentation boost']
for p in ['hide_render','hide_viewport']:
 try:moon.driver_remove(p)
 except:pass
setattr(moon,'hide_render',False);moon.hide_viewport=False;moon.hide_set(False)
for col in moon.users_collection:col.hide_render=False;col.hide_viewport=False
for o in bpy.data.collections['YEAR 15 • airlock apron fixtures'].objects:
 if o.type=='LIGHT':
  axis=0 if abs(o.location.x)>abs(o.location.y) else 1;o.location[axis]+=math.copysign(1.2,o.location[axis])
 else:
  center=sum((v.co for v in o.data.vertices),__import__('mathutils').Vector())/len(o.data.vertices);axis=0 if abs(center.x)>abs(center.y) else 1
  for v in o.data.vertices:v.co[axis]+=math.copysign(1.2,center[axis])
print('LIGHT CONTROL VALUES', {k:v for k,v in c.items() if 'LED' in k},flush=True)
report=json.loads((R/'docs/year15-verification.json').read_text());report['final_lighting_checks']=[]
for f in [1,120]:
 s.frame_set(f);bpy.context.view_layer.update();active=[o for o in bpy.data.collections['YEAR 15 • sampled ring illumination'].objects if not o.hide_render and o.data.energy>0]
 report['final_lighting_checks'].append({'frame':f,'active_ring_sources':len(active),'moon_hidden_render':moon.hide_render,'moon_hidden_viewport':moon.hide_get(),'moon_energy':moon.data.energy,'exposure':s.view_settings.exposure})
print('CHECKS',report['final_lighting_checks'],flush=True)
assert report['final_lighting_checks'][0]['active_ring_sources']==0
expected=sum(1 for x in range(50) for y in range(50) if (x-c['LED phase L'])%c['LED every L']==0 and (y-c['LED phase W'])%c['LED every W']==0 and (not c['LED checkerboard'] or (x+y)%2==0))
assert report['final_lighting_checks'][1]['active_ring_sources']==expected
report['default_active_ring_count']=expected
report['checkerboard_enabled']=bool(c['LED checkerboard'])
assert not moon.hide_render and not moon.hide_get() and moon.data.energy>0
assert all(i.packed_file for i in bpy.data.images if i.source=='FILE')
assert not bpy.data.libraries
text=bpy.data.texts.get('START HERE • year 15 settlement');text.clear();text.write((R/'docs/YEAR15-CONTROLS.md').read_text(encoding='utf-8'))
report['moon_visibility_fixed']=True;report['apron_fixture_header_clearance_m']=1.2;(R/'docs/year15-verification.json').write_text(json.dumps(report,indent=2));s.frame_set(1);s.camera=bpy.data.objects['01 • valley and landing field'];bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True);print('FINAL LIGHTING VERIFIED',report['final_lighting_checks'],flush=True)


