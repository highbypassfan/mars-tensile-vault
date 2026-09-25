import bpy,math,random,ast,json
from pathlib import Path
from mathutils import Vector
from mathutils.noise import noise,fractal
R=Path(bpy.data.filepath).parent;s=bpy.context.scene;ctrl=bpy.data.objects['SETTLEMENT • time and district controls'];light=bpy.data.objects['LIGHTING • toggle Night sky']
tree=ast.parse((R/'tools/build_year15.py').read_text(encoding='utf-8-sig'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ['N','Mesh','drive','toggle','material']],type_ignores=[]),'helpers','exec'))
concrete=bpy.data.materials['Perimeter foundation • cast concrete'];soil=bpy.data.materials['Mars • compacted ochre regolith'];stone=bpy.data.materials['Mesa • layered sedimentary stone'];steel=bpy.data.materials['Colony • brushed stainless'];dark=bpy.data.materials['Colony • dark roof and machinery']
ctrl['Day exposure']=.9;ctrl['Day sky strength']=.45;ctrl['Sun strength']=4.;ctrl['Night exposure']=3.;ctrl['LED every L']=2;ctrl['LED every W']=2;ctrl['LED brightness']=420.;ctrl['LED temperature K']=3900.
# Replace old imported renderer-dependent steel groups with native Cycles procedural steel.
for name in ['Steel','Steel Smooth','Steel.001','Steel (cargo)','Material.012']:
 if name not in bpy.data.materials:continue
 m,b,p=material(name,(.52,.57,.59),.9,.3);geo=b.node('ShaderNodeNewGeometry');coord=b.vec('MULTIPLY',geo.outputs['Position'],(100,100,6));n=b.noise(coord,8,2);bm=b.node('ShaderNodeBump','Fine brushed stainless sheet');b.set(bm,'Height',n);b.set(bm,'Distance',.00025);b.set(bm,'Strength',.35);b.set(p,'Normal',bm.outputs[0]);b.set(p,'Roughness',b.math('ADD',.26,b.math('MULTIPLY',n,.16)))
for name in ['Hex','Black','Padding']:
 if name in bpy.data.materials:
  m,b,p=material(name,(.025,.028,.032),.05,.74);geo=b.node('ShaderNodeNewGeometry');n=b.noise(geo.outputs['Position'],120,2);bm=b.node('ShaderNodeBump');b.set(bm,'Height',n);b.set(bm,'Distance',.0006);b.set(p,'Normal',bm.outputs[0])
if 'Window' in bpy.data.materials:
 m,b,p=material('Window',(.035,.07,.09),.4,.17)
# Restore smooth normals lost when baking the source meshes, keeping original material assignments.
for name in ['SOURCE • landed Starship Crew','SOURCE • landed Starship Cargo']:
 o=bpy.data.objects[name]
 for f in o.data.polygons:f.use_smooth=True
# Rebuild each mesa with many irregular erosion contours, not a handful of straight bands.
col=bpy.data.collections['YEAR 15 • Valley terrain'];rng=random.Random(915)
for o in list(col.objects):
 if o.name.startswith('Mesa '):bpy.data.objects.remove(o,do_unlink=True)
for j in range(36):
 ang=j*math.tau/36;r=rng.uniform(5200,8500);cx=math.cos(ang)*r;cy=math.sin(ang)*r;rx=rng.uniform(700,1800);ry=rng.uniform(550,1400);h=rng.uniform(250,650);a=Mesh();n=192;levels=65
 for lev in range(levels):
  t=lev/(levels-1)
  # apron, steep wall, rounded cap and a flat top
  f=1.62-.4*math.sqrt(t)-.43*t-.06*math.tanh((t-.77)*22)
  for k in range(n):
   an=k*math.tau/n;rad=1+.055*math.sin(7*an+j)+.032*math.sin(17*an-j)+.025*noise(Vector((math.cos(an)*5,math.sin(an)*5,t*4+j)))
   x=cx+rx*f*math.cos(an)*rad;y=cy+ry*f*math.sin(an)*rad
   relief=10*fractal(Vector((x*.015,y*.015,t*4)),1,2,4)+2.3*noise(Vector((x*.15,y*.15,t*8)))
   a.v.append((x,y,h*t+relief))
 for lev in range(levels-1):
  for k in range(n):q=lev*n+k;kn=lev*n+(k+1)%n;a.f.append((q,kn,kn+n,q+n));a.mi.append(a.mat(stone))
 a.f.append(tuple((levels-1)*n+k for k in range(n)));a.mi.append(a.mat(stone));o=a.object(f'Mesa {j+1:02d} • erosion contours',col)
 for f in o.data.polygons:f.use_smooth=True
# Layered sandstone color uses world elevation with warped strata and fine surface relief.
b=N(stone.node_tree);p=next(n for n in b.n if n.type=='BSDF_PRINCIPLED');geo=b.node('ShaderNodeNewGeometry');v=geo.outputs['Position'];x,y,z=b.sep(v);warp=b.noise(v,.006,4);phase=b.math('ADD',b.math('MULTIPLY',z,.52),b.math('MULTIPLY',warp,6));band=b.math('MULTIPLY_ADD',b.math('SINE',phase),.5)
# MULTIPLY_ADD third input is the additive offset.
band.node.inputs[2].default_value=.5
r=b.node('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.1,.044,.022,1);r.color_ramp.elements[1].color=(.3,.16,.08,1);b.set(r,0,band);b.set(p,'Base Color',r.outputs[0])
# Provided grass maps stay local and packed; concrete, soil and cable remain fully procedural.
mat=bpy.data.materials['Colony • continuous textured turf'];b=N(mat.node_tree);p=next(n for n in b.n if n.type=='BSDF_PRINCIPLED');geo=b.node('ShaderNodeNewGeometry');v=b.vec('MULTIPLY',geo.outputs['Position'],(.22,.22,.22));folder=R.parent/'mars_assets/Poliigon_GrassPatchyGround_4585/2K'
for suffix,target in [('BaseColor','Base Color'),('Roughness','Roughness')]:
 im=bpy.data.images.load(str(folder/f'Poliigon_GrassPatchyGround_4585_{suffix}.jpg'),check_existing=True);im.colorspace_settings.name='sRGB' if suffix=='BaseColor' else 'Non-Color';im.pack();tex=b.node('ShaderNodeTexImage',suffix+' turf / 4.5m repeat');tex.image=im;b.set(tex,'Vector',v)
 if suffix=='BaseColor':
  hue=b.node('ShaderNodeHueSaturation');b.set(hue,'Color',tex.outputs['Color']);b.set(hue,'Saturation',.85);b.set(hue,'Value',.65);b.set(p,target,hue.outputs[0])
 else:b.set(p,target,tex.outputs['Color'])
im=bpy.data.images.load(str(folder/'Poliigon_GrassPatchyGround_4585_Normal.png'),check_existing=True);im.colorspace_settings.name='Non-Color';im.pack();tex=b.node('ShaderNodeTexImage','Turf normal map');tex.image=im;b.set(tex,'Vector',v);normal=b.node('ShaderNodeNormalMap');normal.space='WORLD';b.set(normal,'Color',tex.outputs['Color']);b.set(normal,'Strength',.65);b.set(p,'Normal',normal.outputs[0])
# Denser close grass overlaps clumps; keep the distant mesh cheap.
g=bpy.data.node_groups['YEAR15 • instanced grass distance LOD']
for n in g.nodes:
 if n.label=='LOD 1: shared opaque blades':
  # multiply the existing native density by 2, without disturbing distance masking
  b=N(g);old=n.inputs['Density'].links[0].from_socket;b.set(n,'Density',b.math('MULTIPLY',old,2.2))
# Make a dense instanced cargo yard; keep truck aisles and column footprints clear.
c=bpy.data.collections['YEAR 15 • Cargo yard']
for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)
points=[]
for i in range(60):
 for j in range(60):
  x=-1130+i*9.5;y=-1130+j*9.5
  if min(abs((x+100)%200-100),abs((y+100)%200-100))<13:continue
  if math.hypot((x+1250)%50-25,(y+1250)%50-25)<5:continue
  points.append((x,y,0))
me=bpy.data.meshes.new('Cargo yard • pallet cluster positions');me.from_pydata(points,[],[]);o=bpy.data.objects.new('Cargo yard • instanced wrapped loads and barrels',me);c.objects.link(o);toggle(o,'Cargo yard')
g=bpy.data.node_groups.new('YEAR15 • dense cargo placement','GeometryNodeTree');g.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');g.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');b=N(g);gi=b.node('NodeGroupInput');go=b.node('NodeGroupOutput');info=b.node('GeometryNodeCollectionInfo');info.inputs['Collection'].default_value=bpy.data.collections['ASSET • Mars cargo on aluminum pallets'];ins=b.node('GeometryNodeInstanceOnPoints');b.set(ins,'Points',gi.outputs[0]);b.set(ins,'Instance',info.outputs['Instances']);b.set(go,0,ins.outputs[0]);mod=o.modifiers.new('Shared cargo • no realized duplicates','NODES');mod.node_group=g
# Obtain actual airlock locations from a temporary copy of its live Geometry Nodes graph.
mem=next(o for o in s.objects if o.name.startswith('MEMBRANE • pressure-derived'));mm=mem.modifiers[0];mg=mm.node_group.copy();go=next(n for n in mg.nodes if n.type=='GROUP_OUTPUT');airinfo=next(n for n in mg.nodes if n.bl_idname=='GeometryNodeCollectionInfo' and n.inputs['Collection'].default_value and 'vehicle airlock' in n.inputs['Collection'].default_value.name)
# The final Curve to Points node drives the vehicle chamber instance positions.
pts=[n for n in mg.nodes if n.bl_idname=='GeometryNodeCurveToPoints'][-1];pv=mg.nodes.new('GeometryNodePointsToVertices');mg.links.new(pts.outputs['Points'],pv.inputs['Points']);mg.links.new(pv.outputs['Mesh'],go.inputs[0]);temp=bpy.data.objects.new('TEMP • airlock positions',bpy.data.meshes.new('temporary'));s.collection.objects.link(temp);mod=temp.modifiers.new('Extract live airlock points','NODES');mod.node_group=mg
for item in mg.interface.items_tree:
 if item.item_type=='SOCKET' and item.in_out=='INPUT':
  try:getattr(mod.properties.inputs,item.identifier).value=getattr(mm.properties.inputs,item.identifier).value
  except:pass
bpy.context.view_layer.update();ev=temp.evaluated_get(bpy.context.evaluated_depsgraph_get());airpoints=[v.co.copy() for v in ev.data.vertices];bpy.data.objects.remove(temp,do_unlink=True);bpy.data.node_groups.remove(mg)
roads=Mesh()
def road(a,b,width):
 a=Vector(a);b=Vector(b);d=b-a;normal=Vector((-d.y,d.x,0)).normalized()*width/2;idx=len(roads.v);roads.v.extend([tuple(a+normal),tuple(b+normal),tuple(b-normal),tuple(a-normal)]);roads.f.append((idx,idx+1,idx+2,idx+3));roads.mi.append(roads.mat(soil))
for v in airpoints:
 # Connect each entrance to the nearest peripheral street with a compacted service road.
 x,y=v.x,v.y
 if abs(x)>abs(y):
  sg=1 if x>0 else -1;road((sg*1200,y,.04),(x+sg*38,y,.04),16)
  # external ring road joins the landing-field spur
 else:
  sg=1 if y>0 else -1;road((x,sg*1200,.04),(x,y+sg*38,.04),16)
for a,bb in [((-1380,-1380),(1380,-1380)),((1380,-1380),(1380,1380)),((1380,1380),(-1380,1380)),((-1380,1380),(-1380,-1380))]:road((*a,.025),(*bb,.025),18)
for v in airpoints:
 if abs(v.x)>abs(v.y):road((v.x+math.copysign(20,v.x),v.y,.04),(math.copysign(1380,v.x),v.y,.04),16)
 else:road((v.x,v.y+math.copysign(20,v.y),.04),(v.x,math.copysign(1380,v.y),.04),16)
road((1380,-400,.04),(1480,-400,.04),18);roads.object('Roads • airlock approaches and external perimeter service route',bpy.data.collections['YEAR 15 • Roads and plazas'])
# Deterministic rocks and talus outside the settlement and beyond landing pad clearance.
rng=random.Random(912);a=Mesh();n=12
for z,r in [(0,1),(.6,.9),(1,.35)]:
 for i in range(n):a.v.append((math.cos(i*math.tau/n)*r,math.sin(i*math.tau/n)*r,z))
for lev in range(2):
 for i in range(n):j=(i+1)%n;a.f.append((lev*n+i,lev*n+j,(lev+1)*n+j,(lev+1)*n+i));a.mi.append(a.mat(stone))
a.f.append(tuple(24+i for i in range(n)));a.mi.append(a.mat(stone));src=a.object('SOURCE • eroded basalt boulder',None)
for i in range(900):
 x=rng.uniform(-6000,6000);y=rng.uniform(-6000,6000)
 if abs(x)<2600 and abs(y)<1500:continue
 ob=bpy.data.objects.new(f'Valley basalt {i:04d}',src.data);col.objects.link(ob);ob.location=(x,y,-.15);scale=rng.uniform(.4,4);ob.scale=(scale,scale*rng.uniform(.7,1.4),scale*.6);ob.rotation_euler.z=rng.random()*math.tau
report=json.loads((R/'docs/year15-verification.json').read_text());report['airlock_road_connections']=len(airpoints);report['cargo_clusters']=len(points);report['district_counts']={k:len(bpy.data.collections['YEAR 15 • '+k].objects) for k in ['Homes','Warehouses','Industry and tanks']};(R/'docs/year15-verification.json').write_text(json.dumps(report,indent=2))
ctrl.update_tag();s.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True);print('POLISHED',len(airpoints),'AIRLOCKS',len(points),'CARGO CLUSTERS',flush=True)
