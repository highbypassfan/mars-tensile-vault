"""One-time migration from the pre-grass share revision; do not rerun on an upgraded file."""
import bpy,math,random,shutil,json
from pathlib import Path
from mathutils import Vector
R=Path(bpy.data.filepath).parent
if bpy.data.objects.get('SURFACES • grass and lighting controls'):raise RuntimeError('Surface stack already exists; use its native controls.')
backup=R.parent/'tensile-cage-builder/share-before-grass.blend'
if not backup.exists():shutil.copy2(bpy.data.filepath,backup)
s=bpy.context.scene;cage=bpy.data.objects['TENSILE CAGE • select and edit modifier'];mod=cage.modifiers[0];g=mod.node_group;gi=next(n for n in g.nodes if n.type=='GROUP_INPUT')
mem=bpy.data.objects['MEMBRANE • pressure-derived panels and perimeter foundation']
ctrl=bpy.data.objects.get('SURFACES • grass and lighting controls')
if not ctrl:
 ctrl=bpy.data.objects.new('SURFACES • grass and lighting controls',None);s.collection.objects.link(ctrl);ctrl.empty_display_type='PLAIN_AXES';ctrl.empty_display_size=2
for key,value,lo,hi in [('Grass field',True,0,1),('Grass blade height m',.14,.025,.6),('Grass clumps per m2',3.0,0,12),('Grass detail distance m',65.0,5,200),('Viewport grass fraction',.12,0,1),('Concrete relief m',.008,0,.04),('Soil relief m',.025,0,.15),('LED full beam angle deg',45.0,10,160),('LED beam gain',5.0,.1,30),('Clear modeling membrane',True,0,1)]:
 ctrl[key]=value
 if not isinstance(value,bool):ctrl.id_properties_ui(key).update(min=lo,max=hi)
ctrl['Notes']='Grass changes the surface material at the existing datum. Shared blade clumps fade to textured turf with distance from the active render camera. LED angle is total cone width.'
def driver(owner,path,prop):
 d=owner.driver_add(path).driver;d.type='AVERAGE';v=d.variables.new();v.name='control';v.targets[0].id=ctrl;v.targets[0].data_path='["'+prop+'"]'
def addprop(group,owner,key,typ,value):
 i=group.interface.new_socket(name=key,in_out='INPUT',socket_type=typ);i.default_value=value
 driver(getattr(owner.properties.inputs,i.identifier),'value',key);return i
for key,typ in [('Grass field','NodeSocketBool'),('Grass blade height m','NodeSocketFloat'),('Grass clumps per m2','NodeSocketFloat'),('Grass detail distance m','NodeSocketFloat'),('Viewport grass fraction','NodeSocketFloat')]:addprop(g,mod,key,typ,ctrl[key])
class Nodes:
 def __init__(self,tree):self.t=tree;self.n=tree.nodes;self.l=tree.links
 def node(self,kind,label=''):
  n=self.n.new(kind);n.label=label;return n
 def set(self,n,k,v):
  if isinstance(v,bpy.types.NodeSocket):self.l.new(v,n.inputs[k])
  else:n.inputs[k].default_value=v
 def math(self,op,a,b=None):
  n=self.node('ShaderNodeMath',op);n.operation=op;self.set(n,0,a)
  if b is not None:self.set(n,1,b)
  return n.outputs[0]
 def xyz(self,x,y,z):
  n=self.node('ShaderNodeCombineXYZ')
  for k,v in enumerate([x,y,z]):self.set(n,k,v)
  return n.outputs[0]
 def sep(self,v):
  n=self.node('ShaderNodeSeparateXYZ');self.set(n,0,v);return n.outputs
 def vec(self,op,a,b):
  n=self.node('ShaderNodeVectorMath');n.operation=op;self.set(n,0,a);self.set(n,1,b);return n.outputs['Value' if op in ['DISTANCE','DOT_PRODUCT'] else 'Vector']
 def val(self,key):
  n=self.node('ShaderNodeValue',key);driver(n.outputs[0],'default_value',key);return n.outputs[0]
 def mat(self,geo,mat,sel=True):
  n=self.node('GeometryNodeSetMaterial');self.set(n,'Geometry',geo);self.set(n,'Selection',sel);self.set(n,'Material',mat);return n.outputs[0]
 def join(self,*geos):
  n=self.node('GeometryNodeJoinGeometry')
  for geo in geos:self.set(n,0,geo)
  return n.outputs[0]
# Texture maps are physically scaled in world coordinates, including procedural instances.
def pbr_texture(name,asset,scale,relief,soil=False):
 mat=bpy.data.materials[name];mat.use_nodes=True;mat.node_tree.nodes.clear();b=Nodes(mat.node_tree);M=b.math
 geo=b.node('ShaderNodeNewGeometry');coords=b.vec('MULTIPLY',geo.outputs['Position'],(scale,scale,scale))
 maps={}
 for kind in ['diff','rough','disp']:
  file=R/'assets/surfaces'/f'{asset}_{kind}_2k.jpg';img=bpy.data.images.load(str(file),check_existing=True);img.colorspace_settings.name='sRGB' if kind=='diff' else 'Non-Color';img.pack()
  n=b.node('ShaderNodeTexImage',kind+' / metre-scale triplanar');n.image=img;n.projection='BOX';n.projection_blend=.22;b.set(n,'Vector',coords);maps[kind]=n.outputs['Color']
 p=b.node('ShaderNodeBsdfPrincipled');b.set(p,'Roughness',M('MAXIMUM',maps['rough'],.72 if soil else .62))
 color=maps['diff']
 if soil:
  gray=b.node('ShaderNodeRGBToBW');b.set(gray,0,color);r=b.node('ShaderNodeValToRGB');r.color_ramp.elements[0].position=.015;r.color_ramp.elements[0].color=(.055,.019,.007,1);r.color_ramp.elements[1].position=.45;r.color_ramp.elements[1].color=(.34,.13,.045,1);b.set(r,0,gray.outputs[0]);color=r.outputs[0]
 b.set(p,'Base Color',color)
 bump=b.node('ShaderNodeBump','Scanned surface height');b.set(bump,'Height',maps['disp']);b.set(bump,'Distance',b.val(relief));b.set(bump,'Strength',.7)
 fine=b.node('ShaderNodeTexNoise','Fine mineral grain');b.set(fine,'Vector',geo.outputs['Position']);b.set(fine,'Scale',160 if soil else 230);b.set(fine,'Detail',2)
 micro=b.node('ShaderNodeBump','Submillimetre grain');b.set(micro,'Normal',bump.outputs['Normal']);b.set(micro,'Height',fine.outputs['Fac']);b.set(micro,'Distance',.0012 if soil else .0008);b.set(micro,'Strength',.32);b.set(p,'Normal',micro.outputs[0])
 out=b.node('ShaderNodeOutputMaterial');b.set(out,'Surface',p.outputs[0]);mat.diffuse_color=(.24,.09,.035,1) if soil else (.35,.33,.29,1)
 return mat
concretes=[m.name for m in bpy.data.materials if any(k in m.name.lower() for k in ['foundation','concrete','mineral composite'])]
for name in concretes:pbr_texture(name,'concrete',.5,'Concrete relief m')
for name in ['Ground • prepared regolith layer','Mars • compacted ochre regolith','Mesa • layered sedimentary stone','Regolith • scattered basalt grains']:
 pbr_texture(name,'aerial_ground_rock',.12 if 'Mesa' in name else .25,'Soil relief m',True)
# Turf uses multiscale shading far away, actual shared leaves nearby.
turf=bpy.data.materials.new('Grass • living turf and soil');turf.use_nodes=True;turf.node_tree.nodes.clear();b=Nodes(turf.node_tree)
geo=b.node('ShaderNodeNewGeometry');noise=b.node('ShaderNodeTexNoise');b.set(noise,'Vector',geo.outputs['Position']);b.set(noise,'Scale',.7);b.set(noise,'Detail',4)
r=b.node('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.015,.032,.005,1);r.color_ramp.elements[1].color=(.085,.19,.025,1);b.set(r,0,noise.outputs['Fac'])
p=b.node('ShaderNodeBsdfPrincipled');b.set(p,'Base Color',r.outputs[0]);b.set(p,'Roughness',.92)
fine=b.node('ShaderNodeTexNoise');b.set(fine,'Vector',geo.outputs['Position']);b.set(fine,'Scale',170);b.set(fine,'Detail',2)
bump=b.node('ShaderNodeBump');b.set(bump,'Height',fine.outputs['Fac']);b.set(bump,'Distance',.012);b.set(bump,'Strength',.55);b.set(p,'Normal',bump.outputs[0]);out=b.node('ShaderNodeOutputMaterial');b.set(out,'Surface',p.outputs[0]);turf.diffuse_color=(.06,.16,.02,1)
# Material switch on existing ground, never a second hovering ground plane.
ground=bpy.data.materials['Ground • prepared regolith layer'];b=Nodes(ground.node_tree);out=next(n for n in b.n if n.type=='OUTPUT_MATERIAL');base=out.inputs['Surface'].links[0].from_socket
# Copy turf nodes into a group for a compact material blend.
sg=bpy.data.node_groups.new('TV • distant grass surface','ShaderNodeTree');sg.interface.new_socket(name='Surface',in_out='OUTPUT',socket_type='NodeSocketShader');cop={}
for n in turf.node_tree.nodes:
 if n.type=='OUTPUT_MATERIAL':continue
 nn=sg.nodes.new(n.bl_idname);cop[n]=nn
 if n.type=='VALTORGB':
  for a,bb in zip(n.color_ramp.elements,nn.color_ramp.elements):bb.position=a.position;bb.color=a.color
 for a,bb in zip(n.inputs,nn.inputs):
  if hasattr(a,'default_value'):
   try:bb.default_value=a.default_value
   except:pass
for l in turf.node_tree.links:
 if l.to_node in cop:sg.links.new(cop[l.from_node].outputs[l.from_socket.name],cop[l.to_node].inputs[l.to_socket.name])
go=sg.nodes.new('NodeGroupOutput');sg.links.new(cop[p].outputs[0],go.inputs[0])
group=b.node('ShaderNodeGroup');group.node_tree=sg;at=b.node('ShaderNodeAttribute');at.attribute_name='Habitat grass mask';mix=b.node('ShaderNodeMixShader');b.set(mix,0,b.math('MULTIPLY',at.outputs['Fac'],b.val('Grass field')));b.set(mix,1,base);b.set(mix,2,group.outputs[0]);b.set(out,'Surface',mix.outputs[0])
# Mask follows the live footprint and leaves the concrete pad and footing bases clear.
b=Nodes(g);M=b.math;C=lambda k:gi.outputs[k];pos=b.node('GeometryNodeInputPosition');x,y,z=b.sep(pos.outputs[0]);hx=M('MULTIPLY',C('Anchors L'),M('MULTIPLY',C('Spacing L'),.5));hy=M('MULTIPLY',C('Anchors W'),M('MULTIPLY',C('Spacing W'),.5))
def membrane_value(prop):
 n=b.node('ShaderNodeValue',prop);d=n.outputs[0].driver_add('default_value').driver;d.type='AVERAGE';v=d.variables.new();v.name='membrane';v.targets[0].id=mem;v.targets[0].data_path='["'+prop+'"]';return n.outputs[0]
# Actual roof rise is exposed on membrane custom properties; inspect GN driver source.
mm=mem.modifiers[0];mi={i.name:i for i in mm.node_group.interface.items_tree if i.item_type=='SOCKET' and i.in_out=='INPUT'}
def memsocket(key):
 n=b.node('ShaderNodeValue',key);d=n.outputs[0].driver_add('default_value').driver;d.type='AVERAGE';v=d.variables.new();v.targets[0].id=mem;v.targets[0].data_path=f'modifiers["{mm.name}"].properties.inputs.{mi[key].identifier}.value';return n.outputs[0]
radius=M('SUBTRACT',M('ADD',C('Height'),M('MULTIPLY',memsocket('Roof rise m'),.7)),M('ADD',memsocket('Concrete pad height m'),M('MULTIPLY',memsocket('Clamp band height m'),.5)))
rr=M('ADD',C('Corner Radius'),M('SUBTRACT',radius,M('MULTIPLY',memsocket('Concrete pad width m'),.5)))
qx=M('SUBTRACT',M('ABSOLUTE',x),M('SUBTRACT',hx,C('Corner Radius')));qy=M('SUBTRACT',M('ABSOLUTE',y),M('SUBTRACT',hy,C('Corner Radius')))
sdf=M('SUBTRACT',M('ADD',M('SQRT',M('ADD',M('POWER',M('MAXIMUM',qx,0),2),M('POWER',M('MAXIMUM',qy,0),2))),M('MINIMUM',M('MAXIMUM',qx,qy),0)),rr)
inside=M('MULTIPLY',M('LESS_THAN',sdf,-.2),M('GREATER_THAN',z,-.012))
spanx=M('MULTIPLY',M('SUBTRACT',C('Anchors L'),1),C('Spacing L'));spany=M('MULTIPLY',M('SUBTRACT',C('Anchors W'),1),C('Spacing W'))
dx=M('SUBTRACT',M('MULTIPLY',M('FRACT',M('ADD',M('DIVIDE',M('ADD',x,M('MULTIPLY',spanx,.5)),C('Spacing L')),.5)),C('Spacing L')),M('MULTIPLY',C('Spacing L'),.5))
dy=M('SUBTRACT',M('MULTIPLY',M('FRACT',M('ADD',M('DIVIDE',M('ADD',y,M('MULTIPLY',spany,.5)),C('Spacing W')),.5)),C('Spacing W')),M('MULTIPLY',C('Spacing W'),.5))
dist=M('SQRT',M('ADD',M('POWER',dx,2),M('POWER',dy,2)));clear=M('GREATER_THAN',dist,M('ADD',M('MULTIPLY',C('Base Diameter'),.5),.2));mask=M('MULTIPLY',inside,clear)
sm=g.nodes['Set Material.004'];old=sm.inputs['Geometry'].links[0].from_socket;store=b.node('GeometryNodeStoreNamedAttribute','Grass surface mask at existing grade');store.data_type='FLOAT';store.domain='POINT';b.set(store,'Name','Habitat grass mask');b.set(store,'Value',mask);b.set(store,'Geometry',old);b.set(sm,'Geometry',store.outputs[0])
# Shared clump mesh, 96 curved blades. No Realize Instances node.
blade=bpy.data.materials.new('Grass • varied translucent blades');blade.use_nodes=True;blade.node_tree.nodes.clear();bb=Nodes(blade.node_tree);a=bb.node('ShaderNodeAttribute');a.attribute_name='Blade tone';r=bb.node('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.016,.044,.004,1);r.color_ramp.elements[1].color=(.17,.31,.035,1);bb.set(r,0,a.outputs['Fac']);p=bb.node('ShaderNodeBsdfPrincipled');bb.set(p,'Base Color',r.outputs[0]);bb.set(p,'Roughness',.66);bb.set(p,'Subsurface Weight',.06);bb.set(p,'Subsurface Radius',(.15,.3,.05));out=bb.node('ShaderNodeOutputMaterial');bb.set(out,'Surface',p.outputs[0]);blade.diffuse_color=(.065,.18,.02,1)
rng=random.Random(583);vv=[];ff=[];tones=[]
for j in range(96):
 xx=rng.uniform(-.36,.36);yy=rng.uniform(-.36,.36);h=rng.uniform(.07,.18);width=rng.uniform(.004,.011);angle=rng.random()*math.tau;lean=rng.uniform(.012,.065);ux,uy=math.cos(angle),math.sin(angle);vx,vy=-uy,ux;tone=rng.random();offset=len(vv)
 for t,wid in [(0,1),(.42,.8),(.78,.45),(1,0)]:
  for sign in [-1,1]:vv.append((xx+ux*lean*t*t+sign*vx*width*wid,yy+uy*lean*t*t+sign*vy*width*wid,h*t-.001));tones.append(tone)
 for k in range(3):a0=offset+k*2;ff.append((a0,a0+1,a0+3,a0+2))
mesh=bpy.data.meshes.new('96 shared curved grass blades');mesh.from_pydata(vv,[],ff);mesh.materials.append(blade);attr=mesh.attributes.new('Blade tone','FLOAT','POINT')
for a,v in zip(attr.data,tones):a.value=v
for f in mesh.polygons:f.use_smooth=True
source=bpy.data.objects.new('SOURCE • shared grass clump',mesh);source.use_fake_user=True
info=b.node('GeometryNodeObjectInfo');b.set(info,'Object',source)
cam=b.node('GeometryNodeInputActiveCamera');ci=b.node('GeometryNodeObjectInfo');ci.transform_space='ORIGINAL';b.set(ci,'Object',cam.outputs[0]);cp=b.vec('SUBTRACT',ci.outputs['Location'],b.xyz(C('Habitat X'),C('Habitat Y'),C('Ground Elevation')))
rotate=b.node('ShaderNodeVectorRotate');rotate.rotation_type='AXIS_ANGLE';b.set(rotate,'Vector',cp);b.set(rotate,'Axis',(0,0,1));b.set(rotate,'Angle',M('MULTIPLY',C('Habitat Rotation'),-math.pi/180));local=b.vec('DIVIDE',rotate.outputs[0],b.xyz(C('Scale L'),C('Scale W'),C('Scale Z')))
distance=b.vec('DISTANCE',pos.outputs[0],local);fade=M('MINIMUM',M('MAXIMUM',M('DIVIDE',M('SUBTRACT',C('Grass detail distance m'),distance),20),0),1);view=b.node('GeometryNodeIsViewport');vf=M('SUBTRACT',1,M('MULTIPLY',view.outputs[0],M('SUBTRACT',1,C('Viewport grass fraction'))));density=M('MULTIPLY',M('MULTIPLY',M('MULTIPLY',C('Grass clumps per m2'),fade),vf),M('MULTIPLY',mask,C('Grass field')))
scatter=b.node('GeometryNodeDistributePointsOnFaces','Camera-distance grass LOD');scatter.distribute_method='RANDOM';b.set(scatter,'Mesh',g.nodes['Extrude Mesh.002'].inputs['Mesh'].links[0].from_socket);b.set(scatter,'Density',density);b.set(scatter,'Seed',43)
rand=b.node('FunctionNodeRandomValue');rand.data_type='FLOAT';b.set(rand,'Min',0);b.set(rand,'Max',math.tau);inst=b.node('GeometryNodeInstanceOnPoints','Shared blades, never realized');b.set(inst,'Points',scatter.outputs['Points']);b.set(inst,'Instance',info.outputs['Geometry']);b.set(inst,'Rotation',b.xyz(0,0,rand.outputs['Value']));b.set(inst,'Scale',b.xyz(1,1,M('DIVIDE',C('Grass blade height m'),.14)))
join=g.nodes['Transform Geometry.005'].inputs['Geometry'].links[0].from_node;b.set(join,0,inst.outputs[0])
# Directional emission from the actual LED arc geometry, with a soft cone edge.
mat=bpy.data.materials['Ring • warm LED diffuser'];b=Nodes(mat.node_tree);p=next(n for n in b.n if n.type=='BSDF_PRINCIPLED');old=p.inputs['Emission Strength'].links[0].from_socket
geo=b.node('ShaderNodeNewGeometry');dot=b.vec('DOT_PRODUCT',geo.outputs['Incoming'],(0,0,-1));half=b.math('MULTIPLY',b.val('LED full beam angle deg'),math.pi/360);outer=b.math('COSINE',half);inner=b.math('COSINE',b.math('MULTIPLY',half,.85));r=b.node('ShaderNodeMapRange','45 degree total downward beam');r.interpolation_type='SMOOTHSTEP';r.clamp=True;b.set(r,'Value',dot);b.set(r,'From Min',outer);b.set(r,'From Max',inner);b.set(p,'Emission Strength',b.math('MULTIPLY',old,b.math('MULTIPLY',r.outputs['Result'],b.val('LED beam gain'))));mat.cycles.emission_sampling='FRONT_BACK'
# Transparent preview material only on film faces; concrete and steel stay solid.
preview=bpy.data.materials.new('Membrane • clear modeling preview');preview.use_nodes=True;preview.node_tree.nodes.clear();b=Nodes(preview.node_tree);tr=b.node('ShaderNodeBsdfTransparent');pp=b.node('ShaderNodeBsdfPrincipled');b.set(pp,'Base Color',(.35,.65,.8,1));b.set(pp,'Roughness',.22);mix=b.node('ShaderNodeMixShader');b.set(mix,0,.055);b.set(mix,1,tr.outputs[0]);b.set(mix,2,pp.outputs[0]);out=b.node('ShaderNodeOutputMaterial');b.set(out,'Surface',mix.outputs[0]);preview.diffuse_color=(.35,.65,.8,.055)
mg=mem.modifiers[0].node_group;b=Nodes(mg);out=next(n for n in mg.nodes if n.type=='GROUP_OUTPUT');old=out.inputs[0].links[0].from_socket;view=b.node('GeometryNodeIsViewport');sel=0
for name in ['Live membrane • roof and four-ply rings','Pressure wall • aligned bays and single-piece corners']:
 n=b.node('GeometryNodeMaterialSelection');b.set(n,'Material',bpy.data.materials[name]);sel=b.math('MAXIMUM',sel,n.outputs[0])
on=b.node('ShaderNodeValue');driver(on.outputs[0],'default_value','Clear modeling membrane');sel=b.math('MULTIPLY',sel,b.math('MULTIPLY',view.outputs[0],on.outputs[0]));b.set(out,0,b.mat(old,preview,sel))
for screen in bpy.data.screens:
 if any(k in screen.name.lower() for k in ['layout','modeling']):
  for area in screen.areas:
   if area.type=='VIEW_3D':area.spaces.active.shading.type='MATERIAL';area.spaces.active.shading.use_scene_world=False;area.spaces.active.shading.use_scene_lights=False
# Store user-facing instructions in the blend too.
text=bpy.data.texts.new('GRASS AND SURFACE CONTROLS');text.write(ctrl['Notes']+'\nSelect SURFACES • grass and lighting controls > Object Properties > Custom Properties. Grass field toggles the living surface and blades. Concrete and soil relief are bump distances in metres. Clear modeling membrane affects material-preview viewports only.\n')
s.render.engine='CYCLES';s.cycles.samples=128;s.cycles.adaptive_threshold=.005
bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'));print('SURFACE STACK SAVED',concretes,flush=True)

