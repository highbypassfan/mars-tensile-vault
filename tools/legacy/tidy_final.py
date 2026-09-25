import bpy,math,ast,json
from pathlib import Path
from mathutils import Vector
R=Path(bpy.data.filepath).parent;s=bpy.context.scene;ctrl=bpy.data.objects['SETTLEMENT • time and district controls'];light=bpy.data.objects['LIGHTING • toggle Night sky'];tree=ast.parse((R/'tools/build_year15.py').read_text(encoding='utf-8-sig'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ['N','Mesh','drive','toggle']],type_ignores=[]),'helpers','exec'))
ctrl['Moon presentation boost']=1000.;ctrl['Moon azimuth deg']=135.;ctrl['Airlock apron lights']=True;ctrl['Apron light power W']=1800.;ctrl.id_properties_ui('Apron light power W').update(min=0.,max=15000.)
moon=bpy.data.objects['MOON • Phobos fill with optional presentation boost'];drive(moon,'rotation_euler','(180-az)*pi/180',{'az':'Moon azimuth deg'},2)
# Genuine visible entrance fixtures provide local apron task lighting; independently toggleable.
c=bpy.data.collections.new('YEAR 15 • airlock apron fixtures');s.collection.children.link(c);steel=bpy.data.materials['Colony • brushed stainless'];report=json.loads((R/'docs/year15-verification.json').read_text())
for i,co in enumerate(report['all_airlock_positions']):
 center=Vector(co);axis=Vector((math.copysign(1,center.x),0,0)) if abs(center.x)>abs(center.y) else Vector((0,math.copysign(1,center.y),0));side=Vector((-axis.y,axis.x,0))
 for sign in [-1,1]:
  pos=center+axis*12+side*sign*3.2+Vector((0,0,6.6));a=Mesh();a.box(tuple(pos),(.45,.4,.16),steel);fixture=a.object(f'Entrance fixture {i:02d} {sign}',c);toggle(fixture,'Airlock apron lights')
  d=bpy.data.lights.new(f'Apron flood {i:02d} {sign}','AREA');d.shape='DISK';d.size=.35;d.spread=math.radians(130);d.use_temperature=True
  drive(d,'temperature','k',{'k':'LED temperature K'});drive(d,'energy','p*n*on',{'p':'Apron light power W','n':(light,'Night sky'),'on':'Airlock apron lights'})
  o=bpy.data.objects.new(d.name,d);c.objects.link(o);o.location=pos+Vector((0,0,-.13));target=pos+axis*10-Vector((0,0,6.6));o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
# Exterior spill view includes the full entrance and its lit foreground.
cam=bpy.data.objects['08 • exterior spill and freight airlock'];cam.location=(1390,-665,5);cam.rotation_euler=(Vector((1270,-610,25))-cam.location).to_track_quat('-Z','Y').to_euler()
# Tidy visible camera and control collections, leaving the editable construction geometry intact.
cc=bpy.data.collections.new('CAMERAS • 01–09 final views');s.collection.children.link(cc);ac=bpy.data.collections.new('ARCHIVE • earlier inspection cameras');s.collection.children.link(ac);controls=bpy.data.collections.new('CONTROLS • settlement and advanced settings');s.collection.children.link(controls)
for o in list(s.objects):
 dest=None
 if o.type=='CAMERA':dest=cc if o.name[:2].isdigit() else ac
 elif o.type=='EMPTY' and o.name.startswith(('SETTLEMENT','SURFACES','LIGHTING')):dest=controls
 if dest:
  for old in list(o.users_collection):old.objects.unlink(o)
  dest.objects.link(o)
# Remove only unused datablocks; native source meshes have real users or fake-user protection.
removed=bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.overlay.show_extras=False
   if area.spaces.active.region_3d:area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.object.select_all(action='DESELECT');ctrl.select_set(True);bpy.context.view_layer.objects.active=ctrl;s.frame_set(1);ctrl.update_tag();bpy.context.view_layer.update();report['moon_presentation_boost']=1000;report['apron_fixtures']=34;report['unused_datablocks_removed']=removed;(R/'docs/year15-verification.json').write_text(json.dumps(report,indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True);print('TIDIED',removed,flush=True)
