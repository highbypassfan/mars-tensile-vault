"""One-time year-15 settlement migration. Run against the backed-up share blend.
Native drivers and Geometry Nodes work after saving without script auto-execution.
"""
import bpy, math, random, json
from pathlib import Path
from mathutils import Vector
from mathutils.noise import noise_vector
R=Path(bpy.data.filepath).parent
s=bpy.context.scene
if bpy.data.objects.get('SETTLEMENT • time and district controls'):raise RuntimeError('Already migrated')
cage=next(o for o in s.objects if o.name.startswith('TENSILE CAGE'))
cm=cage.modifiers[0];cg=cm.node_group
cs={i.name:i for i in cg.interface.items_tree if i.item_type=='SOCKET' and i.in_out=='INPUT'}
def cv(k,v):getattr(cm.properties.inputs,cs[k].identifier).value=v
def byprefix(prefix):return next(o for o in bpy.data.objects if o.name.startswith(prefix))
mem=byprefix('MEMBRANE • pressure-derived')
surface=byprefix('SURFACES •');light=bpy.data.objects['LIGHTING • toggle Night sky']
ctrl=bpy.data.objects.new('SETTLEMENT • time and district controls',None);s.collection.objects.link(ctrl)
ctrl.empty_display_size=12
props=[('Local solar hour',15.,0,24),('Sun strength',3.,0,10),('Day sky strength',.28,0,3),('Night sky strength',.12,0,2),('Day exposure',0.,-5,8),('Night exposure',3.5,-5,12),('LED brightness',260.,0,2000),('LED temperature K',3500.,1800,10000),('LED every L',1,1,50),('LED every W',1,1,50),('LED phase L',0,0,49),('LED phase W',0,0,49),('LED checkerboard',False,0,1),('Habitat lights',True,0,1),('Grass areas',True,0,1),('Homes',True,0,1),('Warehouses',True,0,1),('Industry and tanks',True,0,1),('Cargo yard',True,0,1),('Starships',True,0,1),('Exterior haze',True,0,1),('Dust storm',False,0,1),('Haze density',.000035,0,.0005),('Moon fill',False,0,1),('Moon fill strength',.00003,0,.002),('Near grass distance m',150.,20,600),('Mid grass distance m',600.,100,2000),('Far grass distance m',3500.,500,6000),('Grass density multiplier',1.,0,3)]
for k,v,lo,hi in props:
 ctrl[k]=v
 if not isinstance(v,bool):ctrl.id_properties_ui(k).update(min=lo,max=hi)
ctrl['Notes']='15:00 day / 22:00 night. Solar-hour art control, not an ephemeris. Districts and roads are an editable 50x50 masterplan; cage remains parametric.'
def drive(owner,path,expr,variables,index=None):
 try:owner.driver_remove(path) if index is None else owner.driver_remove(path,index)
 except:pass
 d=(owner.driver_add(path) if index is None else owner.driver_add(path,index)).driver;d.type='SCRIPTED';d.expression=expr
 for name,spec in variables.items():
  obj,prop=spec if isinstance(spec,tuple) else (ctrl,spec)
  v=d.variables.new();v.name=name;v.targets[0].id=obj;v.targets[0].data_path='["'+prop+'"]'
 return d
def toggle(o,k):
 drive(o,'hide_render','not on',{'on':k});drive(o,'hide_viewport','not on',{'on':k})
class N:
 def __init__(self,t):self.t=t;self.n=t.nodes;self.l=t.links
 def node(self,typ,label=''):
  n=self.n.new(typ);n.label=label;return n
 def set(self,n,k,v):
  if isinstance(v,bpy.types.NodeSocket):self.l.new(v,n.inputs[k])
  else:n.inputs[k].default_value=v
 def math(self,op,a,b=None):
  n=self.node('ShaderNodeMath',op);n.operation=op;self.set(n,0,a)
  if b is not None:self.set(n,1,b)
  return n.outputs[0]
 def val(self,k,obj=ctrl):
  n=self.node('ShaderNodeValue',k);drive(n.outputs[0],'default_value','v',{'v':(obj,k)});return n.outputs[0]
 def vec(self,op,a,b):
  n=self.node('ShaderNodeVectorMath');n.operation=op;self.set(n,0,a);self.set(n,1,b);return n.outputs['Value' if op in ['DISTANCE','DOT_PRODUCT'] else 'Vector']
 def xyz(self,x=0,y=0,z=0):
  n=self.node('ShaderNodeCombineXYZ');self.set(n,0,x);self.set(n,1,y);self.set(n,2,z);return n.outputs[0]
 def sep(self,v):
  n=self.node('ShaderNodeSeparateXYZ');self.set(n,0,v);return n.outputs
 def noise(self,vec,scale,detail=3):
  n=self.node('ShaderNodeTexNoise');self.set(n,'Vector',vec);self.set(n,'Scale',scale);self.set(n,'Detail',detail);return n.outputs['Fac']
def material(name,color,metal=0,rough=.6):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True;m.node_tree.nodes.clear();b=N(m.node_tree);p=b.node('ShaderNodeBsdfPrincipled');b.set(p,'Base Color',(*color,1));b.set(p,'Metallic',metal);b.set(p,'Roughness',rough);o=b.node('ShaderNodeOutputMaterial');b.set(o,'Surface',p.outputs[0]);m.diffuse_color=(*color,1);return m,b,p
def rough_surface(name,kind):
 colors={'concrete':((.16,.15,.13),(.42,.4,.36)), 'soil':((.055,.023,.012),(.29,.115,.05)), 'stone':((.09,.038,.018),(.31,.16,.085))}
 lo,hi=colors[kind];m,b,p=material(name,hi);geo=b.node('ShaderNodeNewGeometry');v=geo.outputs['Position'];base=b.noise(v,.35 if kind=='stone' else 1.8,5);grain=b.noise(v,34 if kind!='concrete' else 65,3)
 r=b.node('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(*lo,1);r.color_ramp.elements[1].color=(*hi,1);b.set(r,0,base);b.set(p,'Base Color',r.outputs[0]);b.set(p,'Roughness',b.math('ADD',.65,b.math('MULTIPLY',grain,.3)))
 bump=b.node('ShaderNodeBump','Aggregate relief in metres');b.set(bump,'Height',grain);b.set(bump,'Distance',.022 if kind=='concrete' else .06);b.set(bump,'Strength',.65)
 pores=b.node('ShaderNodeTexVoronoi','Fine pores and grain');b.set(pores,'Vector',v);b.set(pores,'Scale',240 if kind=='concrete' else 130)
 micro=b.node('ShaderNodeBump','Fine pore relief');b.set(micro,'Height',pores.outputs['Distance']);b.set(micro,'Distance',.0017 if kind=='concrete' else .003);b.set(micro,'Strength',.5);b.set(micro,'Normal',bump.outputs[0]);b.set(p,'Normal',micro.outputs[0]);return m
for m in list(bpy.data.materials):
 if any(k in m.name.lower() for k in ['foundation','concrete','mineral composite']):rough_surface(m.name,'concrete')
 for_kind='stone' if 'Mesa' in m.name or 'basalt' in m.name else 'soil'
 if any(k in m.name for k in ['prepared regolith','compacted ochre','Mesa •','scattered basalt']):rough_surface(m.name,for_kind)
concrete=bpy.data.materials['Perimeter foundation • cast concrete'];soil=bpy.data.materials['Mars • compacted ochre regolith'];stone=bpy.data.materials['Mesa • layered sedimentary stone']
white,_,_=material('Colony • ceramic coated facade',(.59,.57,.51),.12,.5)
dark,_,_=material('Colony • dark roof and machinery',(.045,.065,.075),.6,.4)
steel,_,_=material('Colony • brushed stainless',(.36,.4,.43),.88,.29)
solar,_,_=material('Colony • roof photovoltaics',(.012,.025,.039),.5,.28)
ochre,_,_=material('Colony • safety ochre',(.5,.22,.04),.2,.48)
glass,b,p=material('Colony • window glazing',(.07,.12,.14),.3,.2)
b.set(p,'Emission Color',(1,.66,.32,1));drive(p.inputs['Emission Strength'],'default_value','0.45*n',{'n':(light,'Night sky')})
# Replace coarse cable relief with nested helical strands and individual wire scoring.
m=bpy.data.materials['Anchor • twisted steel cable'];m.node_tree.nodes.clear();b=N(m.node_tree);M=b.math
def at(name,vec=False):
 n=b.node('ShaderNodeAttribute');n.attribute_name=name;return n.outputs['Vector' if vec else 'Fac']
x,y,z=b.sep(at('CableRadial',True));theta=M('ARCTAN2',y,x);travel=at('CableTravel');lay=M('MAXIMUM',at('CableLay'),.02);phase=M('SUBTRACT',theta,M('MULTIPLY',M('DIVIDE',travel,lay),math.tau));strand=M('COSINE',M('MULTIPLY',phase,6));fine=M('COSINE',M('ADD',M('MULTIPLY',phase,114),M('MULTIPLY',travel,180)))
p=b.node('ShaderNodeBsdfPrincipled');b.set(p,'Base Color',(.3,.33,.35,1));b.set(p,'Metallic',.95);b.set(p,'Roughness',M('ADD',.23,M('MULTIPLY',fine,.045)))
bm=b.node('ShaderNodeBump','Six gently rounded strand bundles');b.set(bm,'Height',strand);b.set(bm,'Distance',M('MULTIPLY',at('CableRelief'),.3));b.set(bm,'Strength',.65)
bm2=b.node('ShaderNodeBump','Individual helical steel wires');b.set(bm2,'Normal',bm.outputs[0]);b.set(bm2,'Height',fine);b.set(bm2,'Distance',.00045);b.set(bm2,'Strength',.6);b.set(p,'Normal',bm2.outputs[0]);out=b.node('ShaderNodeOutputMaterial');b.set(out,'Surface',p.outputs[0])
# Expand the original native cage, preserving the accepted pressure-derived roof.
for k,v in [('Anchors L',50),('Anchors W',50),('Height',75.),('Show Mars Terrain',False),('Show Base Modules',False),('Show Cargo',False),('LED Strength',260.),('Airlock Spacing',650.)]:cv(k,v)
drive(getattr(cm.properties.inputs,cs['LED Strength'].identifier),'value','v',{'v':'LED brightness'})
# Disable the earlier short-range grass scatter; the settlement supplies correctly masked turf.
for n in cg.nodes:
 if n.label=='Shared blades, never realized':
  for link in list(n.outputs[0].links):cg.links.remove(link)
for c in s.collection.children:
 if c.name.startswith(('EXTERIOR •','ATMOSPHERE •')):c.hide_render=True;c.hide_viewport=True
# One solar-hour control owns day/night, exposure, sun and all lamps.
drive(light,'["Night sky"]','max(0,min(1,0.5-8*cos((h-12)*pi/12)))',{'h':'Local solar hour'})
drive(light,'["Night sky gain"]','v',{'v':'Night sky strength'})
drive(light,'["Day exposure EV"]','v',{'v':'Day exposure'});drive(light,'["Night exposure EV"]','v',{'v':'Night exposure'})
sun=bpy.data.objects['Mars_Sun'];sun.data.angle=math.radians(.35);sun.data.color=(1,.88,.76)
drive(sun.data,'energy','strength*max(0,cos((h-12)*pi/12))',{'h':'Local solar hour','strength':'Sun strength'})
drive(sun,'rotation_euler','(h-12)*pi/12',{'h':'Local solar hour'},0)
sun.rotation_euler[1]=math.radians(22);sun.rotation_euler[2]=math.radians(-28)
soft=bpy.data.objects.get('Soft sun')
if soft:soft.hide_render=True;soft.hide_viewport=True
moon=bpy.data.objects.get('moonlight')
if moon:
 moon.data.color=(1,.91,.78);moon.data.angle=math.radians(.18)
 drive(moon.data,'energy','on*power*night',{'on':'Moon fill','power':'Moon fill strength','night':(light,'Night sky')});moon['note']='Optional approximate Phobos fill. Not ephemeris-driven or absolute radiometric calibration; disabled by default.'
world=N(s.world.node_tree);bg=s.world.node_tree.nodes.get('Background');drive(bg.inputs['Strength'],'default_value','v',{'v':'Day sky strength'})
# Ring selection evaluated in world metres: independent L/W stride, phase, checkerboard.
m=bpy.data.materials['Ring • warm LED diffuser'];b=N(m.node_tree);p=next(n for n in b.n if n.type=='BSDF_PRINCIPLED');old=p.inputs['Emission Strength'].links[0].from_socket
geo=b.node('ShaderNodeNewGeometry');x,y,z=b.sep(geo.outputs['Position']);ix=b.math('ROUND',b.math('DIVIDE',b.math('ADD',x,1225),50));iy=b.math('ROUND',b.math('DIVIDE',b.math('ADD',y,1225),50))
lx=b.math('LESS_THAN',b.math('PINGPONG',b.math('SUBTRACT',ix,b.val('LED phase L')),b.val('LED every L')),.1)
ly=b.math('LESS_THAN',b.math('PINGPONG',b.math('SUBTRACT',iy,b.val('LED phase W')),b.val('LED every W')),.1)
# Floored modulo rather than pingpong: every N rows really means N, not 2N.
for n in [lx.node.inputs[0].links[0].from_node,ly.node.inputs[0].links[0].from_node]:n.operation='FLOORED_MODULO'
checker=b.math('SUBTRACT',1,b.math('MULTIPLY',b.val('LED checkerboard'),b.math('FLOORED_MODULO',b.math('ADD',ix,iy),2)))
mask=b.math('MULTIPLY',b.math('MULTIPLY',lx,ly),checker);mask=b.math('MULTIPLY',mask,b.math('MULTIPLY',b.val('Habitat lights'),b.val('Night sky',light)));b.set(p,'Emission Strength',b.math('MULTIPLY',old,mask))
black=b.node('ShaderNodeBlackbody','LED color temperature');b.set(black,'Temperature',b.val('LED temperature K'));b.set(p,'Emission Color',black.outputs[0])
print('MATERIALS AND CONTROLS READY',flush=True)
# Lightweight editable architectural assets. Shared mesh data, no realized duplicates.
cols={}
for key in ['Homes','Warehouses','Industry and tanks','Cargo yard','Starships','Roads and plazas','Valley terrain','Grass areas']:
 c=bpy.data.collections.new('YEAR 15 • '+key);s.collection.children.link(c);cols[key]=c
class Mesh:
 def __init__(self):self.v=[];self.f=[];self.mi=[];self.mats=[]
 def mat(self,m):
  if m not in self.mats:self.mats.append(m)
  return self.mats.index(m)
 def box(self,c,d,m):
  x,y,z=c;a,bb,h=[q*.5 for q in d];i=len(self.v);self.v.extend([(x+sx*a,y+sy*bb,z+sz*h) for sx,sy,sz in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]])
  for face in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.f.append(tuple(i+j for j in face));self.mi.append(self.mat(m))
 def cyl(self,c,r,h,m,n=32):
  i=len(self.v);x,y,z=c
  for zz in [-h/2,h/2]:
   for j in range(n):self.v.append((x+r*math.cos(j*math.tau/n),y+r*math.sin(j*math.tau/n),z+zz))
  self.f.extend([tuple(i+j for j in reversed(range(n))),tuple(i+n+j for j in range(n))]);self.mi.extend([self.mat(m)]*2)
  for j in range(n):k=(j+1)%n;self.f.append((i+j,i+k,i+n+k,i+n+j));self.mi.append(self.mat(m))
 def object(self,name,col,bevel=0):
  me=bpy.data.meshes.new(name);me.from_pydata(self.v,[],self.f);me.update()
  for m in self.mats:me.materials.append(m)
  for f,mi in zip(me.polygons,self.mi):f.material_index=mi
  o=bpy.data.objects.new(name,me)
  if col:col.objects.link(o)
  else:o.use_fake_user=True
  if bevel:
   mod=o.modifiers.new('Small manufactured edge radii','BEVEL');mod.width=bevel;mod.segments=2
  return o
def instance(src,name,loc,key,angle=0):
 o=bpy.data.objects.new(name,src.data);cols[key].objects.link(o);o.location=loc;o.rotation_euler.z=angle
 if key in ctrl:toggle(o,key)
 return o
excluded=[]
def exclude(x,y,wx,wy):excluded.append((x-wx/2-2,x+wx/2+2,y-wy/2-2,y+wy/2+2))
def building(name,w,d,h,residential=False):
 a=Mesh();a.box((0,0,h/2),(w,d,h),white);a.box((0,0,.1),(w+2,d+2,.2),concrete);a.box((0,0,h+.18),(w+.5,d+.5,.36),dark)
 if residential:
  for z in range(2,int(h),3):
   for x in range(-int(w/2)+2,int(w/2),4):
    for sy in [-1,1]:a.box((x,sy*(d/2+.03),z),(2.2,.06,1.4),glass)
  a.box((0,-d/2-.06,1.3),(2.2,.15,2.6),dark)
 else:
  for y in range(-int(d/2)+4,int(d/2),12):
   for sx in [-1,1]:
    a.box((sx*(w/2+.05),y,3),(.13,7,5.8),dark);a.box((sx*(w/2+.1),y,6.4),(.2,7,.2),ochre)
  for y in range(-int(d/2)+3,int(d/2),5):a.box((0,y,h+.4),(w+1,.13,.25),steel)
 for x in [-w*.28,w*.28]:a.box((x,0,h+.5),(w*.3,d*.72,.15),solar)
 for y in [-d*.3,d*.3]:a.box((0,y,h+.8),(2.8,3.5,1.2),steel)
 return a.object(name,None)
home=building('SOURCE • three storey residential',32,18,10,True);warehouse=building('SOURCE • long factory hall',36,136,18);short=building('SOURCE • logistics hall',36,86,12)
count={'Homes':0,'Warehouses':0,'Industry and tanks':0}
for x in range(-1100,1150,50):
 for y in range(-1100,1150,50):
  # 200m street grid, axial civic park, landing monuments and the cargo quadrant.
  if x%200==0 or y%200==0 or abs(x)<120 or abs(y)<120:continue
  if x<-500 and y<-500:continue
  if y>150:
   if y%200!=100:continue
   src=warehouse;key='Warehouses';d=136
  elif x>150:
   src=home;key='Homes';d=18
  else:
   if y%200!=100:continue
   src=short;key='Warehouses';d=86
  instance(src,f'{key} • block {x} {y}',(x,y,0),key);exclude(x,y,36,d);count[key]+=1
# Tanks / industrial processing modules in the north-eastern service quarter.
a=Mesh();a.box((0,0,.2),(36,36,.4),concrete)
for x in [-8,8]:
 for y in [-8,8]:
  a.cyl((x,y,8),5.5,16,steel,32);a.cyl((x,y,16.2),5.8,.4,white,32)
  for z in [3,7,11,15]:a.cyl((x,y,z),5.65,.18,dark,32)
a.box((0,0,1),(2,35,1.2),steel);tank=a.object('SOURCE • four tank utility block',None)
for x in [950,1050,1150]:
 for y in [250,450,650,850,1050]:
  # replace any hall in this cell to avoid overlaps
  for o in list(cols['Warehouses'].objects):
   if abs(o.location.x-x)<1 and abs(o.location.y-y)<75:bpy.data.objects.remove(o,do_unlink=True)
  instance(tank,'Process tanks • water oxygen methane',(x,y,0),'Industry and tanks');exclude(x,y,40,40);count['Industry and tanks']+=1
a=Mesh();a.box((0,0,.2),(36,86,.4),concrete)
for y in [-28,-10,10,28]:
 a.box((0,y,4),(24,12,8),dark)
 for x in [-8,0,8]:a.cyl((x,y,9),2.5,3,steel,24)
 a.box((0,y,11),(32,1,1),ochre)
machine=a.object('SOURCE • industrial compressor train',None)
for x in [-1050,-950,-850,-750,-650]:
 instance(machine,'Industry • atmospheric processing',(x,150,0),'Industry and tanks');exclude(x,150,40,90)
# Road grid lies between anchor lines; concrete sidewalks flank the residential streets.
a=Mesh();walk=Mesh()
for t in range(-1200,1201,200):
 a.box((t,0,-.02),(16,2600,.06),soil);a.box((0,t,-.019),(2600,16,.06),soil)
 for sg in [-1,1]:
  walk.box((t+sg*10,0,.03),(3,2500,.1),concrete);walk.box((0,t+sg*10,.031),(2500,3,.1),concrete)
a.box((-850,-850,-.018),(660,660,.06),soil);exclude(-850,-850,665,665)
a.object('Compacted regolith • streets and cargo apron',cols['Roads and plazas']);walk.object('Concrete • walkable street network',cols['Roads and plazas'])
# Reuse the existing aluminum pallets and wrapped cargo as a shared source collection.
cargo_col=bpy.data.collections.get('ASSET • Mars cargo on aluminum pallets')
if cargo_col:
 for row in range(13):
  for column in range(14):
   o=bpy.data.objects.new(f'Cargo cluster {row:02d}-{column:02d}',None);o.instance_type='COLLECTION';o.instance_collection=cargo_col;cols['Cargo yard'].objects.link(o);o.location=(-1130+column*40,-1130+row*42,0);toggle(o,'Cargo yard')
# Import crew and cargo ships without boosters, flames or launch animations.
ship_report=[]
with bpy.data.libraries.load(str(R.parent/'mars_assets/Space X Starship and Super Heavy crew  cargo.blend'),link=False) as (a,bb):bb.collections=['Starship Crew','Starship Cargo']
ship_sources=[]
for col in bb.collections:
 s.collection.children.link(col)
bpy.context.view_layer.update()
dg=bpy.context.evaluated_depsgraph_get()
for col in bb.collections:
 root=next(o for o in col.objects if o.name.startswith('Starship') and o.type=='MESH');center=root.matrix_world.translation.copy();a=Mesh()
 for o in col.all_objects:
  par=o;flame=False
  while par:
   if 'Flame' in par.name:flame=True
   par=par.parent
  if flame or o.type!='MESH':continue
  ev=o.evaluated_get(dg);me=ev.to_mesh();offset=len(a.v);a.v.extend([tuple(o.matrix_world@v.co-center) for v in me.vertices])
  for face in me.polygons:
   a.f.append(tuple(offset+i for i in face.vertices));mat=me.materials[face.material_index] if me.materials else steel;a.mi.append(a.mat(mat.original if mat else steel))
  ev.to_mesh_clear()
 zmin=min(v[2] for v in a.v);zmax=max(v[2] for v in a.v);a.v=[(x,y,z-zmin) for x,y,z in a.v];src=a.object('SOURCE • landed '+col.name,None);ship_sources.append(src);ship_report.append({'name':col.name,'height_m':zmax-zmin,'vertices':len(a.v)})
 s.collection.children.unlink(col)
for i,(x,y) in enumerate([(-100,0),(100,0),(0,150)]):
 instance(ship_sources[i%2],'Heritage Starship • habitat built around ship',(x,y,.12),'Starships',i*.6);exclude(x,y,38,38)
 a=Mesh();a.cyl((x,y,0),20,.22,concrete,64);a.object('Interior ship foundation',cols['Roads and plazas'])
# Landing field 350-1000m beyond east membrane, with visible regolith access roads.
landing=[];a=Mesh()
for i,(x,y) in enumerate([(1750,-800),(2050,-800),(2350,-800),(1750,-400),(2050,-400),(2350,-400),(1750,0),(2050,0)]):
 instance(ship_sources[i%2],('Crew' if i%2==0 else 'Cargo')+f' Starship • landing pad {i+1}',(x,y,.2),'Starships',i*.7)
 a.cyl((x,y,.02),52,.16,concrete,96);a.cyl((x,y,.11),32,.035,soil,96);a.box(((1350+x)/2,y,-.015),(x-1350,18,.09),soil);landing.append((x,y))
a.box((1480,-400,-.015),(20,1250,.09),soil);a.object('Landing field • pads and access roads',cols['Roads and plazas'])
print('DISTRICTS AND SHIPS',count,ship_report,flush=True)
# A 360-degree open valley: level settlement basin and distant stratified mesa escarpments.
rng=random.Random(915)
a=Mesh();a.box((0,0,-.45),(32000,32000,.7),soil);a.object('Mars valley • continuous basin floor',cols['Valley terrain'])
for j in range(36):
 ang=j*math.tau/36;r=rng.uniform(5200,8500);cx=math.cos(ang)*r;cy=math.sin(ang)*r;rx=rng.uniform(700,1800);ry=rng.uniform(550,1400);h=rng.uniform(250,650)
 a=Mesh();n=96;levels=[(0,1.55),(.17,1.22),(.63,1.02),(.68,.92),(.95,.76),(1,.71)]
 for z,f in levels:
  for k in range(n):
   t=k*math.tau/n;pert=1+.07*math.sin(7*t+j)+.035*math.sin(17*t-j);a.v.append((cx+rx*f*math.cos(t)*pert,cy+ry*f*math.sin(t)*pert,h*z+5*math.sin(5*t+j)))
 for lev in range(len(levels)-1):
  for k in range(n):q=lev*n+k;kn=lev*n+(k+1)%n;a.f.append((q,kn,kn+n,q+n));a.mi.append(a.mat(stone))
 a.f.append(tuple((len(levels)-1)*n+k for k in range(n)));a.mi.append(a.mat(stone));a.object(f'Mesa {j+1:02d} • eroded layered escarpment',cols['Valley terrain'])
# Grass surface at grade, clipped conservatively inside roof edge (over 75m from outer clamp).
# 5m cells exclude occupied blocks and roads; metre-scale footing clearance is done in GN.
grassmat,b,p=material('Colony • continuous textured turf',(.05,.13,.02),0,.9)
geo=b.node('ShaderNodeNewGeometry');v=geo.outputs['Position'];n=b.noise(v,.55,5);r=b.node('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.022,.05,.008,1);r.color_ramp.elements[1].color=(.115,.235,.043,1);b.set(r,0,n);b.set(p,'Base Color',r.outputs[0]);fine=b.noise(v,95,2);bm=b.node('ShaderNodeBump');b.set(bm,'Height',fine);b.set(bm,'Distance',.022);b.set(bm,'Strength',.7);b.set(p,'Normal',bm.outputs[0])
verts=[];faces=[]
# spatial hash makes the 250000-cell exclusion pass cheap
bins={}
for rect in excluded:
 x0,x1,y0,y1=rect
 for xx in range(math.floor(x0/100),math.floor(x1/100)+1):
  for yy in range(math.floor(y0/100),math.floor(y1/100)+1):bins.setdefault((xx,yy),[]).append(rect)
for x in range(-1240,1240,5):
 for y in range(-1240,1240,5):
  xx=x+2.5;yy=y+2.5
  if min(abs((xx+100)%200-100),abs((yy+100)%200-100))<14:continue
  if any(x0-3<xx<x1+3 and y0-3<yy<y1+3 for x0,x1,y0,y1 in bins.get((math.floor(xx/100),math.floor(yy/100)),[])):continue
  # anchors at +-25, +-75... leave enough clearance for the entire clump radius
  if math.hypot((xx+1250)%50-25,(yy+1250)%50-25)<4.5:continue
  i=len(verts);verts.extend([(x,y,.005),(x+5,y,.005),(x+5,y+5,.005),(x,y+5,.005)]);faces.append((i,i+1,i+2,i+3))
me=bpy.data.meshes.new('Turf occupancy • clipped to occupied settlement');me.from_pydata(verts,[],faces);me.materials.append(grassmat);grass=bpy.data.objects.new('Grass • full field with three distance detail levels',me);cols['Grass areas'].objects.link(grass);toggle(grass,'Grass areas')
g=bpy.data.node_groups.new('YEAR15 • instanced grass distance LOD','GeometryNodeTree');g.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');g.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');b=N(g);gi=b.node('NodeGroupInput');go=b.node('NodeGroupOutput');join=b.node('GeometryNodeJoinGeometry');b.set(join,0,gi.outputs[0]);b.set(go,0,join.outputs[0]);mod=grass.modifiers.new('Grass density and camera distance','NODES');mod.node_group=g
pos=b.node('GeometryNodeInputPosition');cam=b.node('GeometryNodeInputActiveCamera');ci=b.node('GeometryNodeObjectInfo');b.set(ci,'Object',cam.outputs[0]);dist=b.vec('DISTANCE',pos.outputs[0],ci.outputs['Location']);vp=b.node('GeometryNodeIsViewport');vf=b.math('SUBTRACT',1,b.math('MULTIPLY',vp.outputs[0],.985))
near=b.val('Near grass distance m');mid=b.val('Mid grass distance m');far=b.val('Far grass distance m')
source=bpy.data.objects['SOURCE • shared grass clump'];sources=[source]
# Far clumps use only 12 or 4 bent blades, opaque geometry to avoid stacked alpha costs.
for num in [12,4]:
 vv=[];ff=[]
 for j in range(num):
  angle=j*2.39996;xx=math.cos(angle)*.24;yy=math.sin(angle)*.24;h=.12+(j%3)*.018;w=.012 if num==12 else .024;k=len(vv);vv.extend([(xx-w,yy,0),(xx+w,yy,0),(xx+.025,yy+.04,h)]);ff.append((k,k+1,k+2))
 mm=bpy.data.meshes.new(f'Grass distant {num} blade clump');mm.from_pydata(vv,[],ff);mm.materials.append(bpy.data.materials['Grass • varied translucent blades']);o=bpy.data.objects.new(f'SOURCE • {num} blade LOD',mm);o.use_fake_user=True;sources.append(o)
for i,(lo,hi,density,src) in enumerate([(0,near,1.6,sources[0]),(near,mid,.32,sources[1]),(mid,far,.06,sources[2])]):
 sel=b.math('MULTIPLY',b.math('GREATER_THAN',dist,lo),b.math('LESS_THAN',dist,hi));scatter=b.node('GeometryNodeDistributePointsOnFaces',f'LOD {i+1}: shared opaque blades');b.set(scatter,'Mesh',gi.outputs[0]);b.set(scatter,'Density',b.math('MULTIPLY',sel,b.math('MULTIPLY',density,b.math('MULTIPLY',vf,b.val('Grass density multiplier')))));b.set(scatter,'Seed',97+i);info=b.node('GeometryNodeObjectInfo');b.set(info,'Object',src);ins=b.node('GeometryNodeInstanceOnPoints');b.set(ins,'Points',scatter.outputs['Points']);b.set(ins,'Instance',info.outputs['Geometry']);b.set(join,0,ins.outputs[0])
print('GRASS SURFACE',len(faces),'cells',flush=True)
# Exterior-only atmospheric scattering; zero density throughout the enclosing habitat prism.
a=Mesh();a.box((0,0,800),(26000,26000,1800),soil);fog=a.object('Atmosphere • valley haze with clear interior',cols['Valley terrain']);fog.display_type='WIRE';toggle(fog,'Exterior haze');mat=bpy.data.materials.new('YEAR15 • exterior-only dust');mat.use_nodes=True;mat.node_tree.nodes.clear();b=N(mat.node_tree);geo=b.node('ShaderNodeNewGeometry');x,y,z=b.sep(geo.outputs['Position']);outside=b.math('MAXIMUM',b.math('GREATER_THAN',b.math('ABSOLUTE',x),1340),b.math('GREATER_THAN',b.math('ABSOLUTE',y),1340));outside=b.math('MAXIMUM',outside,b.math('GREATER_THAN',z,100));density=b.math('MULTIPLY',outside,b.math('MULTIPLY',b.val('Haze density'),b.math('ADD',1,b.math('MULTIPLY',b.val('Dust storm'),12))));density=b.math('MULTIPLY',density,b.math('EXPONENT',b.math('MULTIPLY',b.math('MAXIMUM',z,0),-1/900)));vol=b.node('ShaderNodeVolumePrincipled');b.set(vol,'Color',(.63,.46,.32,1));b.set(vol,'Density',density);b.set(vol,'Anisotropy',.3);out=b.node('ShaderNodeOutputMaterial');b.set(out,'Volume',vol.outputs['Volume']);fog.data.materials.clear();fog.data.materials.append(mat)
# Useful views, with day/night timeline markers that also select cameras.
def camera(name,loc,target,lens):
 c=bpy.data.objects.new(name,bpy.data.cameras.new(name));s.collection.objects.link(c);c.location=loc;c.rotation_euler=(Vector(target)-c.location).to_track_quat('-Z','Y').to_euler();c.data.lens=lens;c.data.clip_end=40000;c.data.clip_start=.1;return c
cams=[]
for row in [('01 • valley and landing field',(3400,-3600,1400),(0,0,50),42),('02 • civic park and heritage ships',(175,-180,2.1),(0,30,27),24),('03 • residential boulevard',(430,-420,3),(650,-650,9),35),('04 • industrial district',(-520,180,35),(-600,670,20),35),('05 • cargo yard',(-790,-1190,6),(-850,-800,7),35),('06 • landing field',(1830,-1050,12),(1980,-350,25),32),('07 • habitat from mesa',(4200,-3100,300),(0,0,35),52)]:cams.append(camera(*row))
s.camera=cams[1]
for frame,hour,label in [(1,15.,'DAY • afternoon'),(120,22.,'NIGHT • illuminated settlement')]:
 ctrl['Local solar hour']=hour;ctrl.keyframe_insert(data_path='["Local solar hour"]',frame=frame);s.timeline_markers.new(label,frame=frame)
s.frame_start=1;s.frame_end=120;s.frame_set(1)
# Keyframes make frame 1 / 120 standard, portable day/night presets; slider is editable.
s.render.engine='CYCLES';s.cycles.samples=256;s.cycles.use_denoising=True;s.cycles.adaptive_threshold=.008;s.cycles.max_bounces=32;s.cycles.diffuse_bounces=8;s.cycles.transmission_bounces=32;s.cycles.transparent_max_bounces=96;s.cycles.use_light_tree=True;s.cycles.sample_clamp_indirect=0;s.cycles.volume_bounces=2
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='8';s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='HIP';prefs.refresh_devices()
for d in prefs.devices:d.use=d.type=='HIP'
s.cycles.device='GPU'
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.clip_end=40000
bpy.ops.object.select_all(action='DESELECT');ctrl.select_set(True);bpy.context.view_layer.objects.active=ctrl
for img in bpy.data.images:
 if img.source=='FILE' and not img.packed_file:
  try:img.pack()
  except:pass
report={'grid':[50,50],'spacing_m':50,'ring_height_m':75,'district_counts':count,'ships':ship_report,'landing_pads':landing,'grass_cells':len(faces),'grass_max_extent_m':1240,'clamp_min_extent_m':1332.5,'sky':'Packed NASA 4k catalogue retained; high resolution deferred','notes':'Art-directed year-15 concept. Roof is pressure-derived, not structural certification. Starships sourced from user file; provenance not supplied.'}
(R/'docs/year15-verification.json').write_text(json.dumps(report,indent=2))
text=bpy.data.texts.new('START HERE • year 15 settlement');text.write(ctrl['Notes']+'\nFrame 1: day. Frame 120: night. Select SETTLEMENT controls > Object Custom Properties. Cameras 01–07 cover the full masterplan. Grass uses 3 instanced LOD tiers; no realized blades. Concrete, soil and steel cable are procedural.\n')
bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True)
print('YEAR15 SAVED',flush=True)

