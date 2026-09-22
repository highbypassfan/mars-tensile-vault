"""Import the user-provided Standing Man GLB and pose it beside Curiosity."""
import bpy,math,shutil,json
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
r=Path(bpy.data.filepath).parent;s=bpy.context.scene
backup=r.parent/'tensile-cage-builder/share-before-person.blend'
if not backup.exists():shutil.copy2(bpy.data.filepath,backup)
if bpy.data.objects.get('PERSON • standing and looking skyward'):raise RuntimeError('Person already imported')
previous=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(r.parent/'standing_man.glb'));new=set(bpy.data.objects)-previous
root=next(o for o in new if o.name.startswith('Sketchfab_model'));rig=next(o for o in new if o.type=='ARMATURE')
# Keep the imported relaxed animation pose but remove time-dependent animation.
s.frame_set(1);bpy.context.view_layer.update();basis={b.name:b.matrix_basis.copy() for b in rig.pose.bones};rig.animation_data_clear()
for bone in rig.pose.bones:bone.matrix_basis=basis[bone.name]
collection=bpy.data.collections.new('STAFF • realistic skyward observer');s.collection.children.link(collection)
for o in list(new):
 if o==root or o in root.children_recursive:
  for c in list(o.users_collection):c.objects.unlink(o)
  collection.objects.link(o)
 else:bpy.data.objects.remove(o,do_unlink=True)
root.name='PERSON • standing and looking skyward';rig.name='PERSON RIG • editable head and neck pose'
root['Source']='Standing Man by zhuoyi0904, Sketchfab 8401da7cb2564fc08681836cbeff39bc';root['License']='CC BY 4.0';root['Pose']='Relaxed stance; neck + head tilted 34 degrees skyward; facing away from rover inspection camera.'
# Apply rotation in armature space so imported bone-roll conventions do not matter.
bpy.context.view_layer.update()
for name,angle in [('mixamorig:Neck_05',-12),('mixamorig:Head_06',-22)]:
 pb=rig.pose.bones[name];mat=pb.matrix.copy();pivot=mat.translation.copy();pb.matrix=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(angle),4,'X')@Matrix.Translation(-pivot)@mat;bpy.context.view_layer.update()
meshes=[o for o in collection.objects if o.type=='MESH']
def points():
 dg=bpy.context.evaluated_depsgraph_get();out=[]
 for o in meshes:
  e=o.evaluated_get(dg);me=e.to_mesh();out.extend(e.matrix_world@v.co for v in me.vertices);e.to_mesh_clear()
 return out
pts=points();height=max(v.z for v in pts)-min(v.z for v in pts);root.scale*=1.78/height;bpy.context.view_layer.update()
old=bpy.data.objects['Worker • 1.82 m including hard hat'];target=old.location.copy();cam=bpy.data.objects['Worker and Curiosity • ground material inspection'];away=target-cam.location;root.rotation_mode='QUATERNION';root.rotation_quaternion=Quaternion((0,0,1),math.atan2(away.y,away.x)+math.pi/2)@root.rotation_quaternion
bpy.context.view_layer.update();pts=points();center=Vector(((max(v.x for v in pts)+min(v.x for v in pts))/2,(max(v.y for v in pts)+min(v.y for v in pts))/2,min(v.z for v in pts)));root.location+=target-center;root.location.z-=.002
oldcol=bpy.data.collections['STAFF • clipboard inspection beside Curiosity'];oldcol.name='ARCHIVE • original placeholder worker';oldcol.hide_render=True;oldcol.hide_viewport=True
for o in meshes:
 o.name='Person • '+o.data.name
 for p in o.data.polygons:p.use_smooth=True
 for mat in o.data.materials:
  if not mat or not mat.use_nodes:continue
  for p in mat.node_tree.nodes:
   if p.type=='BSDF_PRINCIPLED' and not p.inputs['Roughness'].is_linked:p.inputs['Roughness'].default_value=.6
bpy.ops.file.pack_all();bpy.context.view_layer.update();pts=points()
report={'source':root['Source'],'license':'https://creativecommons.org/licenses/by/4.0/','mesh_objects':len(meshes),'height_m':max(v.z for v in pts)-min(v.z for v in pts),'feet_z':min(v.z for v in pts),'root_location':list(root.location),'old_placeholder_hidden':oldcol.hide_render,'all_file_images_packed':all(i.packed_file for i in bpy.data.images if i.source=='FILE')}
assert report['all_file_images_packed'];assert abs(report['height_m']-1.78)<.01
(r/'docs/person-verification.json').write_text(json.dumps(report,indent=2))
# Close camera is useful for inspecting the pose without changing the main composition.
data=bpy.data.cameras.new('Observer • pose detail');detail=bpy.data.objects.new(data.name,data);s.collection.objects.link(detail);detail.location=target+Vector((2,-3,1.8));detail.rotation_euler=(target+Vector((0,0,1.2))-detail.location).to_track_quat('-Z','Y').to_euler();data.lens=55
s.camera=cam;bpy.ops.wm.save_as_mainfile(filepath=str(r/'mars-tensile-vault.blend'));print('PERSON SAVED',report,flush=True)
p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='HIP';p.refresh_devices()
for d in p.devices:d.use=d.type=='HIP'
s.cycles.device='GPU';s.cycles.samples=96;s.cycles.adaptive_threshold=.005;s.render.resolution_percentage=65;s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='8'
light=bpy.data.objects['LIGHTING • toggle Night sky']
for night,camera,name in [(False,detail,'observer-detail'),(True,cam,'grass-night'),(False,cam,'grass-day')]:
 light['Night sky']=night;light.update_tag();s.camera=camera;s.frame_set(s.frame_current);bpy.context.view_layer.update();s.render.filepath=str(r/'previews'/f'{name}.png');bpy.ops.render.render(write_still=True)



