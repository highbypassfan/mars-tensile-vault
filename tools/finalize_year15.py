import bpy,math,ast,json
from pathlib import Path
from mathutils import Vector
R=Path(bpy.data.filepath).parent;s=bpy.context.scene;ctrl=bpy.data.objects['SETTLEMENT • time and district controls']
tree=ast.parse((R/'tools/build_year15.py').read_text(encoding='utf-8-sig'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ['N','Mesh','drive','toggle','material']],type_ignores=[]),'helpers','exec'))
soil=bpy.data.materials['Mars • compacted ochre regolith'];stone=bpy.data.materials['Mesa • layered sedimentary stone'];concrete=bpy.data.materials['Perimeter foundation • cast concrete']
# Quarter-turn the editable districts to put freight beside the eastern landing field.
for key in ['Homes','Warehouses','Industry and tanks']:
 for o in bpy.data.collections['YEAR 15 • '+key].objects:
  x,y=o.location.x,o.location.y;o.location.x=-y;o.location.y=x;o.rotation_euler.z+=math.pi/2
for name in ['Grass • full field with three distance detail levels','Cargo yard • instanced wrapped loads and barrels','Compacted regolith • streets and cargo apron']:
 o=bpy.data.objects[name]
 for v in o.data.vertices:x,y=v.co.x,v.co.y;v.co.x=-y;v.co.y=x
 o.data.update()
# Keep thermal tiles black. Orient one preserved ship side-on to show its steel/heatshield split.
ships=[o for o in bpy.data.collections['YEAR 15 • Starships'].objects if o.name.startswith('Heritage')]
ships[0].rotation_euler.z+=math.pi*.65;ships[1].rotation_euler.z+=math.pi*.3
# Source actual vehicle-airlock positions from native geometry, so roads meet doors precisely.
mem=next(o for o in s.objects if o.name.startswith('MEMBRANE • pressure-derived'));mm=mem.modifiers[0];mg=mm.node_group.copy();go=next(n for n in mg.nodes if n.type=='GROUP_OUTPUT');pts=[n for n in mg.nodes if n.bl_idname=='GeometryNodeCurveToPoints'][-1];pv=mg.nodes.new('GeometryNodePointsToVertices');mg.links.new(pts.outputs['Points'],pv.inputs['Points']);mg.links.new(pv.outputs['Mesh'],go.inputs[0]);temp=bpy.data.objects.new('TEMP airlocks',bpy.data.meshes.new('temp'));s.collection.objects.link(temp);tm=temp.modifiers.new('positions','NODES');tm.node_group=mg
for i in mg.interface.items_tree:
 if i.item_type=='SOCKET' and i.in_out=='INPUT':
  try:getattr(tm.properties.inputs,i.identifier).value=getattr(mm.properties.inputs,i.identifier).value
  except:pass
bpy.context.view_layer.update();positions=[v.co.copy() for v in temp.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices];bpy.data.objects.remove(temp,do_unlink=True);bpy.data.node_groups.remove(mg)
east=sorted([v for v in positions if v.x>1300 and -1250<v.y<-450],key=lambda v:v.y)
road=Mesh()
for v in east:road.box(((480+v.x+30)/2,v.y,.035),(v.x+30-480,18,.07),soil)
road.object('Freight • continuous cargo aisles aligned to east airlocks',bpy.data.collections['YEAR 15 • Roads and plazas'])
# Remove grass and pallet points in those through aisles.
o=bpy.data.objects['Cargo yard • instanced wrapped loads and barrels'];coords=[tuple(v.co) for v in o.data.vertices if not any(abs(v.co.y-a.y)<13 for a in east)];me=bpy.data.meshes.new('Freight clear aisles and pallet coordinates');me.from_pydata(coords,[],[]);o.data=me
o=bpy.data.objects['Grass • full field with three distance detail levels'];old=o.data;vv=[];ff=[]
for p in old.polygons:
 center=sum((old.vertices[i].co for i in p.vertices),Vector())/len(p.vertices)
 if center.x>477 and any(abs(center.y-a.y)<13 for a in east):continue
 off=len(vv);vv.extend(tuple(old.vertices[i].co) for i in p.vertices);ff.append(tuple(off+i for i in range(len(p.vertices))))
me=bpy.data.meshes.new('Turf • districts and aligned freight exclusions');me.from_pydata(vv,[],ff)
for m in old.materials:me.materials.append(m)
o.data=me
# Exact point-domain footing exclusions include clump radius, not just the cell centroid.
g=o.modifiers[0].node_group;b=N(g);pos=b.node('GeometryNodeInputPosition');x,y,z=b.sep(pos.outputs[0]);dx=b.math('SUBTRACT',b.math('FLOORED_MODULO',b.math('ADD',x,1250),50),25);dy=b.math('SUBTRACT',b.math('FLOORED_MODULO',b.math('ADD',y,1250),50),25);remove=b.math('LESS_THAN',b.math('ADD',b.math('MULTIPLY',dx,dx),b.math('MULTIPLY',dy,dy)),2.1**2)
for n in list(g.nodes):
 if n.bl_idname=='GeometryNodeInstanceOnPoints':
  src=n.inputs['Points'].links[0].from_socket;delete=b.node('GeometryNodeDeleteGeometry','Footing clearance including blade spread');delete.domain='POINT';b.set(delete,'Geometry',src);b.set(delete,'Selection',remove);b.set(n,'Points',delete.outputs[0])
# CC0 grass maps allow the share file itself to remain publicly redistributable.
mat=bpy.data.materials['Colony • continuous textured turf']
for n in mat.node_tree.nodes:
 if n.type=='TEX_IMAGE' and n.image and n.image.name.startswith('Poliigon'):
  suffix='diff' if 'BaseColor' in n.image.name else 'rough' if 'Roughness' in n.image.name else 'nor_gl';im=bpy.data.images.load(str(R/'assets/surfaces'/f'leafy_grass_{suffix}_2k.jpg'),check_existing=True);im.colorspace_settings.name='sRGB' if suffix=='diff' else 'Non-Color';im.pack();n.image=im
for im in list(bpy.data.images):
 if im.name.startswith('Poliigon'):bpy.data.images.remove(im)
for n in mat.node_tree.nodes:
 if n.type=='NORMAL_MAP':n.inputs['Strength'].default_value=.55
 if n.type=='HUE_SAT':n.inputs['Value'].default_value=.85
# Subtle sedimentary strata rather than high-contrast contour stripes.
for n in stone.node_tree.nodes:
 if n.type=='VALTORGB':
  n.color_ramp.elements[0].color=(.15,.075,.035,1);n.color_ramp.elements[-1].color=(.235,.119,.06,1)
# Adjust view targets to the moved districts.
views={'03 • residential boulevard':((420,420,3),(750,650,10)), '04 • industrial district':((-180,-520,35),(-670,-600,20)), '05 • cargo yard':((1180,-1150,7),(950,-650,8))}
for name,(loc,target) in views.items():
 c=bpy.data.objects[name];c.location=loc;c.rotation_euler=(Vector(target)-c.location).to_track_quat('-Z','Y').to_euler()
# Change the hour by slider or timeline; two explicitly labelled keyframes avoid hidden modes.
ctrl['Notes']='Frame 1 = 15:00 day; frame 120 = 22:00 night. Hour can be changed in Custom Properties; keyframe it to persist while scrubbing. Road/building masterplan is fixed at 50x50 columns. Resize cage independently with care.'
s.camera=bpy.data.objects['02 • civic park and heritage ships'];s.frame_set(1);ctrl.update_tag();bpy.context.view_layer.update()
report=json.loads((R/'docs/year15-verification.json').read_text());report['cargo_side']='southeast, on east landing-field side';report['cargo_airlocks']=[list(v) for v in east];report['cargo_clusters']=len(coords);report['all_airlock_positions']=[list(v) for v in positions];report['notes']='Concept masterplan; not structural or flight-safety certification. Starships: Anyll Markevich / BlendSwap 27853, CC0. Turf: Poly Haven Leafy Grass, CC0.';(R/'docs/year15-verification.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True);print('FREIGHT ALIGNED',[(v.x,v.y) for v in east],flush=True)
