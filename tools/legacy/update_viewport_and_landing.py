"""One-time viewport LOD / 200 m settlement update. Refuses to run twice."""
import ast
import bpy
import json
import math
import shutil
from pathlib import Path
from mathutils import Vector

R = Path(bpy.data.filepath).parent
s = bpy.context.scene
ctrl = bpy.data.objects['SETTLEMENT • time and district controls']
if 'Viewport tether LOD' in ctrl:
    raise RuntimeError('Already updated; do not rerun this migration')
backup = R / 'renders' / 'before-viewport-landing-update.blend'
if backup.exists():
    assert backup.read_bytes() == Path(bpy.data.filepath).read_bytes(), 'Input changed since backup'
else:
    shutil.copy2(bpy.data.filepath, backup)
t = ast.parse((R/'tools/build_year15.py').read_text(encoding='utf-8-sig'))
exec(compile(ast.Module(body=[n for n in t.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in ['N','Mesh','drive','toggle']], type_ignores=[]), 'helpers', 'exec'))
cage = next(o for o in s.objects if o.name.startswith('TENSILE CAGE'))
cm = cage.modifiers[0]; cg = cm.node_group
cs = {i.name:i for i in cg.interface.items_tree if i.item_type == 'SOCKET' and i.in_out == 'INPUT'}
height_path = 'modifiers['+json.dumps(cm.name,ensure_ascii=False)+'].properties.inputs.'+cs['Height'].identifier+'.value'
assert abs(getattr(cm.properties.inputs, cs['Height'].identifier).value - 200) < .01
for k,v,lo,hi in [('Viewport tether LOD',True,0,1),('Viewport tether every L',2,1,50),('Viewport tether every W',2,1,50),('Viewport tether branches',4,3,24),('Viewport tether sides',4,3,16),('Viewport ring segments',24,12,96)]:
    ctrl[k] = v
    if not isinstance(v,bool): ctrl.id_properties_ui(k).update(min=lo,max=hi)
ctrl['Viewport LOD help'] = 'Viewport only: coarse shared anchors and every Nth row/column. Disable for full modeling detail. Final renders always use full geometry and all anchors.'

def condition(g):
    b=N(g); vp=b.node('GeometryNodeIsViewport','Automatic viewport-only LOD')
    return b, b.math('MULTIPLY',vp.outputs[0],b.val('Viewport tether LOD'))

def switch_input(b, inp, flag, low, kind='INT'):
    old = inp.links[0].from_socket if inp.is_linked else inp.default_value
    n = b.node('GeometryNodeSwitch','Viewport proxy / full render'); n.input_type=kind
    b.set(n,'Switch',flag); b.set(n,'False',old); b.set(n,'True',low); b.set(inp.node,inp.name,n.outputs[0])

b,flag=condition(cg)
anchor = next(n for n in cg.nodes if n.bl_idname=='GeometryNodeGroup' and n.node_tree.name.startswith('TV • Parametric Anchor'))
for key,control in [('Wire Count','Viewport tether branches'),('Wire Sides','Viewport tether sides'),('Cap Ring Resolution','Viewport ring segments')]:
    switch_input(b,anchor.inputs[key],flag,b.val(control))
for key in ['Show Cable Fittings','Solar Insert']:
    switch_input(b,anchor.inputs[key],flag,False,'BOOLEAN')
# Keep all grid points in renders; only thin the displayed anchor instances.
ins = cg.nodes['Instance on Points']; gi = next(n for n in cg.nodes if n.type=='GROUP_INPUT')
pos=b.node('GeometryNodeInputPosition'); xyz=b.sep(pos.outputs[0]); masks=[]
for axis,letter in enumerate(['L','W']):
    spacing=gi.outputs['Spacing '+letter]
    offset=b.math('MULTIPLY',b.math('SUBTRACT',gi.outputs['Anchors '+letter],1),.5)
    index=b.math('ROUND',b.math('ADD',b.math('DIVIDE',xyz[axis],spacing),offset))
    masks.append(b.math('LESS_THAN',b.math('FLOORED_MODULO',index,b.val('Viewport tether every '+letter)),.1))
switch_input(b,ins.inputs['Selection'],flag,b.math('MULTIPLY',*masks),'BOOLEAN')
ag=anchor.node_tree; ab,aflag=condition(ag)
for n in list(ag.nodes):
    if n.bl_idname=='GeometryNodeCurvePrimitiveCircle':
        switch_input(ab,n.inputs['Resolution'],aflag,ab.val('Viewport tether sides'))
    elif n.bl_idname=='GeometryNodeMeshCylinder' and not n.inputs['Vertices'].is_linked:
        switch_input(ab,n.inputs['Vertices'],aflag,12)

# Ring sources follow the user's editable cage elevation, rather than staying at 75m.
for o in s.objects:
    if o.type=='LIGHT' and o.name.startswith('Ring light'):
        try:o.driver_remove('location',2)
        except (TypeError,RuntimeError):pass
        d=o.driver_add('location',2).driver;d.expression='h-0.12'
        v=d.variables.new();v.name='h';v.targets[0].id=cage;v.targets[0].data_path=height_path
# Extend the existing clear-air mask to above the raised roof.
fog=bpy.data.objects['Atmosphere • valley haze with clear interior']
fog_changed=0
for n in fog.data.materials[0].node_tree.nodes:
    if n.type=='MATH' and n.operation=='GREATER_THAN' and not n.inputs[1].is_linked and abs(n.inputs[1].default_value-100)<.001:
        d=n.inputs[1].driver_add('default_value').driver;d.expression='h+30'
        v=d.variables.new();v.name='h';v.targets[0].id=cage;v.targets[0].data_path=height_path
        fog_changed+=1

concrete=bpy.data.materials['Perimeter foundation • cast concrete']
white=bpy.data.materials['Colony • ceramic coated facade']
dark=bpy.data.materials['Colony • dark roof and machinery']
glass=bpy.data.materials['Colony • window glazing']
# Replace six existing homes on their already grass-excluded footprints.
homes=bpy.data.collections['YEAR 15 • Homes']; chosen=[]
for o in sorted(homes.objects,key=lambda o:o.location.length):
    if all((o.location-p.location).length>150 for p in chosen):chosen.append(o)
    if len(chosen)==6:break
heights=[72,90,110,130,84,104]
for o,h in zip(chosen,heights):
    a=Mesh();a.box((0,0,.12),(34,20,.24),concrete)
    a.box((0,0,4),(32,18,8),white)
    a.box((0,0,(h+8)/2),(24,16,h-8),white)
    for z in range(11,h,4):
        for sign in [-1,1]:
            a.box((0,sign*8.03,z),(22,.08,2.3),glass)
            a.box((sign*12.03,0,z),(.08,14,2.3),glass)
        a.box((0,0,z+1.5),(24.3,16.3,.22),dark)
    a.box((0,0,h+.2),(24.6,16.6,.4),dark)
    tmp=a.object('TEMP tower mesh',None);o.data=tmp.data;bpy.data.objects.remove(tmp)
    o.name=f'Residential tower • {h}m';o['Height m']=h

# Shift the entire landing field 2km east; connect pad spurs through collectors to one trunk.
ships=[o for o in s.objects if 'Starship • landing pad' in o.name]
assert len(ships)==8
for o in ships:o.location.x+=2000
# Use the membrane's evaluated entrance points, not a guessed wall coordinate.
mem=next(o for o in s.objects if o.name.startswith('MEMBRANE • pressure-derived'))
mm=mem.modifiers[0]; mg=mm.node_group.copy()
go=next(n for n in mg.nodes if n.type=='GROUP_OUTPUT')
pts=[n for n in mg.nodes if n.bl_idname=='GeometryNodeCurveToPoints'][-1]
pv=mg.nodes.new('GeometryNodePointsToVertices');mg.links.new(pts.outputs['Points'],pv.inputs['Points']);mg.links.new(pv.outputs['Mesh'],go.inputs[0])
temp=bpy.data.objects.new('TEMP entrance sample',bpy.data.meshes.new('temp'));s.collection.objects.link(temp)
tm=temp.modifiers.new('sample','NODES');tm.node_group=mg
for i in mg.interface.items_tree:
    if i.item_type=='SOCKET' and i.in_out=='INPUT':
        try:getattr(tm.properties.inputs,i.identifier).value=getattr(mm.properties.inputs,i.identifier).value
        except (AttributeError,TypeError):pass
bpy.context.view_layer.update()
positions=[v.co.copy() for v in temp.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices]
entrance=min([v for v in positions if v.x>1200],key=lambda v:abs(v.y+616))
bpy.data.objects.remove(temp,do_unlink=True);bpy.data.node_groups.remove(mg)
soil=bpy.data.materials['Mars • compacted ochre regolith']
roadmat=soil.copy();roadmat.name='Road • dark brown compacted regolith'
rb=N(roadmat.node_tree);p=next(n for n in rb.n if n.type=='BSDF_PRINCIPLED')
geo=rb.node('ShaderNodeNewGeometry');r=rb.node('ShaderNodeValToRGB','Dark compacted fines')
r.color_ramp.elements[0].color=(.027,.012,.005,1);r.color_ramp.elements[1].color=(.085,.039,.016,1)
rb.set(r,0,rb.noise(geo.outputs['Position'],.12,4));rb.set(p,'Base Color',r.outputs[0]);roadmat.diffuse_color=(.065,.027,.011,1)
a=Mesh()
def road(x1,y1,x2,y2,width=24):
    assert x1==x2 or y1==y2
    a.box(((x1+x2)/2,(y1+y2)/2,.005),(abs(x2-x1)+width if x1==x2 else abs(x2-x1),abs(y2-y1)+width if y1==y2 else abs(y2-y1),.1),roadmat)
road(entrance.x-12,entrance.y,4480,entrance.y,28)
for x in sorted({round(o.location.x) for o in ships}):
    ys=[o.location.y for o in ships if abs(o.location.x-x)<1]
    collector=x+110
    road(collector,min(min(ys),entrance.y)-40,collector,max(max(ys),entrance.y)+40)
    for y in ys:road(x+48,y,collector,y,20)
for o in ships:
    x,y=o.location.x,o.location.y
    a.cyl((x,y,.02),52,.16,concrete,96);a.cyl((x,y,.11),32,.035,roadmat,96)
old=bpy.data.objects['Landing field • pads and access roads']
tmp=a.object('TEMP rebuilt landing field',None);old.data=tmp.data;bpy.data.objects.remove(tmp)
old['Road routing']='One trunk to the eastern freight airlock; three collectors with pad spurs'
# Remove the obsolete short connector to the old field, preserving all other service roads.
service=bpy.data.objects['Roads • airlock approaches and external perimeter service route']
mesh=service.data; verts=[tuple(v.co) for v in mesh.vertices];faces=[];materials=[]
for f in mesh.polygons:
    center=sum((mesh.vertices[i].co for i in f.vertices),Vector())/len(f.vertices)
    if 1380<center.x<1481 and abs(center.y+400)<1:continue
    faces.append(tuple(f.vertices));materials.append(f.material_index)
new=bpy.data.meshes.new('Service routes without obsolete landing spur');new.from_pydata(verts,[],faces)
for mat in mesh.materials:new.materials.append(mat)
for f,mi in zip(new.polygons,materials):f.material_index=mi
service.data=new
# Ground under the moved field must remain level, including interpolation between grid vertices.
terrain=bpy.data.objects['Valley • gentle outer hills and continuous distant ground']
for v in terrain.data.vertices:
    if v.co.x>=0 and v.co.x<=5334 and -2001<=v.co.y<=1334:v.co.z=-.09
terrain.data.update()
camera=bpy.data.objects['06 • landing field'];camera.location.x+=2000
# Keep the saved workspaces in Solid mode so navigation does not trace the full scene.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D' and any(k in screen.name.lower() for k in ['layout','modeling']):
            area.spaces.active.shading.type='SOLID'
ctrl.update_tag()
s.frame_set(s.frame_current)
bpy.context.view_layer.update()
print('HEIGHT DEBUG', height_path, cage.path_resolve(height_path), bpy.data.objects['Ring light • L01 W01'].location[:], flush=True)
assert abs(bpy.data.objects['Ring light • L01 W01'].evaluated_get(bpy.context.evaluated_depsgraph_get()).location.z-199.88)<.01
assert fog_changed==1, f'Expected one interior haze ceiling cutoff, found {fog_changed}'
report={'height_m':200,'towers_m':heights,'landing_shift_east_m':2000,'landing_pads':[list(o.location) for o in ships],'freight_airlock':list(entrance),'viewport_stride':[2,2],'render_grid':[50,50],'haze_cutoffs_driven':fog_changed,'rendering':'No image render requested; native geometry and driver checks used'}
(R/'docs/viewport-landing-verification.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True)
print('UPDATED',json.dumps(report),flush=True)
