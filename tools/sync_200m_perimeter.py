"""One-time synchronization of entrance fixtures and air cavity after the roof-height update."""
import bpy, ast, math, json
from pathlib import Path
from mathutils import Vector
R=Path(bpy.data.filepath).parent;s=bpy.context.scene
ctrl=bpy.data.objects['SETTLEMENT • time and district controls'];light=bpy.data.objects['LIGHTING • toggle Night sky']
if ctrl.get('200m perimeter synchronized'):raise RuntimeError('Already synchronized')
t=ast.parse((R/'tools/build_year15.py').read_text(encoding='utf-8-sig'))
exec(compile(ast.Module(body=[n for n in t.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ['Mesh','drive','toggle']],type_ignores=[]),'helpers','exec'))
mem=next(o for o in s.objects if o.name.startswith('MEMBRANE • pressure-derived'));mm=mem.modifiers[0];mg=mm.node_group.copy()
go=next(n for n in mg.nodes if n.type=='GROUP_OUTPUT');pts=[n for n in mg.nodes if n.bl_idname=='GeometryNodeCurveToPoints'][-1]
pv=mg.nodes.new('GeometryNodePointsToVertices');mg.links.new(pts.outputs['Points'],pv.inputs['Points']);mg.links.new(pv.outputs[0],go.inputs[0])
tmp=bpy.data.objects.new('TEMP positions',bpy.data.meshes.new('temp'));s.collection.objects.link(tmp);tm=tmp.modifiers.new('positions','NODES');tm.node_group=mg
for i in mg.interface.items_tree:
 if i.item_type=='SOCKET' and i.in_out=='INPUT':
  try:getattr(tm.properties.inputs,i.identifier).value=getattr(mm.properties.inputs,i.identifier).value
  except (AttributeError,TypeError):pass
bpy.context.view_layer.update();positions=[v.co.copy() for v in tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices]
bpy.data.objects.remove(tmp,do_unlink=True);bpy.data.node_groups.remove(mg)
c=bpy.data.collections['YEAR 15 • airlock apron fixtures'];steel=bpy.data.materials['Colony • brushed stainless']
for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)
for i,center in enumerate(positions):
 axis=Vector((math.copysign(1,center.x),0,0)) if abs(center.x)>abs(center.y) else Vector((0,math.copysign(1,center.y),0))
 side=Vector((-axis.y,axis.x,0))
 for sign in [-1,1]:
  pos=center+axis*13.2+side*sign*3.2+Vector((0,0,6.6));a=Mesh();a.box(tuple(pos),(.45,.4,.16),steel)
  fixture=a.object(f'Entrance fixture {i:02d} {sign}',c);toggle(fixture,'Airlock apron lights')
  d=bpy.data.lights.new(f'Apron flood {i:02d} {sign}','AREA');d.shape='DISK';d.size=.35;d.spread=math.radians(130);d.use_temperature=True
  drive(d,'temperature','k',{'k':'LED temperature K'});drive(d,'energy','p*n*on',{'p':'Apron light power W','n':(light,'Night sky'),'on':'Airlock apron lights'})
  o=bpy.data.objects.new(f'Apron light {i:02d} {sign}',d);c.objects.link(o);o.location=pos+Vector((0,0,-.12));o.rotation_euler=(axis*.7+Vector((0,0,-1))).to_track_quat('-Z','Y').to_euler();toggle(o,'Airlock apron lights')
cage=next(o for o in s.objects if o.name.startswith('TENSILE CAGE'));cm=cage.modifiers[0]
sock=next(i for i in cm.node_group.interface.items_tree if i.item_type=='SOCKET' and i.name=='Height')
path='modifiers['+json.dumps(cm.name,ensure_ascii=False)+'].properties.inputs.'+sock.identifier+'.value'
fog=bpy.data.objects['Atmosphere • valley haze with clear interior'];changed=0
for n in fog.data.materials[0].node_tree.nodes:
 if n.type=='MATH' and n.operation=='GREATER_THAN' and not n.inputs[1].is_linked and abs(n.inputs[1].default_value-1340)<.001:
  d=n.inputs[1].driver_add('default_value').driver;d.expression='h+1265.5';v=d.variables.new();v.name='h';v.targets[0].id=cage;v.targets[0].data_path=path;changed+=1
assert changed==2
air=min([v for v in positions if v.x>1200],key=lambda v:abs(v.y+616))
roadmat=bpy.data.materials['Road • dark brown compacted regolith'];a=Mesh()
# Bridge the existing cargo aisle to the newly shifted freight entrance/trunk.
a.box(((1330+air.x-24)/2,-616.319,.02),(air.x-24-1330,18,.1),roadmat)
a.box((air.x-24,(-616.319+air.y)/2,.02),(28,abs(air.y+616.319)+28,.1),roadmat)
a.object('Freight • raised-roof airlock road connection',bpy.data.collections['YEAR 15 • Roads and plazas'])
camera=bpy.data.objects['08 • exterior spill and freight airlock'];camera.location=(air.x+62,air.y-48,5)
camera.rotation_euler=(Vector((air.x-100,air.y,35))-camera.location).to_track_quat('-Z','Y').to_euler()
ctrl['200m perimeter synchronized']=True
ctrl.update_tag();s.frame_set(s.frame_current);bpy.context.view_layer.update()
report=json.loads((R/'docs/viewport-landing-verification.json').read_text());report['all_airlock_positions']=[list(v) for v in positions];report['apron_fixtures']=2*len(positions);report['clear_air_half_extent_m']=1465.5
(R/'docs/viewport-landing-verification.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True)
print('PERIMETER SYNCHRONIZED',len(positions),'airlocks',flush=True)
