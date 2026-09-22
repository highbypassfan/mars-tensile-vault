"""Final exterior/lighting migration; one-time operation on the year-15 share file."""
import bpy,math,random,ast,json
from pathlib import Path
from mathutils import Vector
from mathutils.noise import fractal,noise
R=Path(bpy.data.filepath).parent;s=bpy.context.scene;ctrl=bpy.data.objects['SETTLEMENT • time and district controls'];light=bpy.data.objects['LIGHTING • toggle Night sky']
t=ast.parse((R/'tools/build_year15.py').read_text(encoding='utf-8-sig'));exec(compile(ast.Module(body=[n for n in t.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ['N','Mesh','drive','toggle','material']],type_ignores=[]),'helpers','exec'))
col=bpy.data.collections['YEAR 15 • Valley terrain'];soil=bpy.data.materials['Mars • compacted ochre regolith'];stone=bpy.data.materials['Mesa • layered sedimentary stone']
ctrl['LED every L']=3;ctrl['LED every W']=3;ctrl['Night exposure']=4.;ctrl['Night sky strength']=.08;ctrl['LED brightness']=550.;ctrl['Haze density']=.000012
for key,value,lo,hi in [('Ring light power W',9000.,0,100000),('Moon fill',True,0,1),('Moon presentation boost',300.,1,2000),('Moon azimuth deg',315.,0,360),('Moon altitude deg',28.,2,85),('Show Phobos disk',True,0,1)]:
 ctrl[key]=value
 if not isinstance(value,bool):ctrl.id_properties_ui(key).update(min=lo,max=hi)
ctrl['Moon note']='Phobos-like approximate fill and illustrative 0.18-degree disk. Boost 1 is the faint reference; default 300 is presentation lighting, not calibrated Mars moonlight or an ephemeris.'
# Extend the ground to 1000 km across. The visible procedural relief covers 300 km.
floor=bpy.data.objects['Mars valley • continuous basin floor'];a=Mesh();a.box((0,0,-180),(1000000,1000000,100),soil);replacement=a.object('TEMP distant floor',None);floor.data=replacement.data;bpy.data.objects.remove(replacement)
# Expand the open valley ~5x, with mesa heights remaining at plausible landscape scales.
for o in col.objects:
 if o.name.startswith('Mesa '):
  for v in o.data.vertices:v.co.x*=5;v.co.y*=5;v.co.z*=2.3
  o.data.update()
# Smooth rolling ground starts outside the developed basin; no hills intersect pads/roads.
vv=[];ff=[];NGRID=451;extent=150000.
def terrain_z(x,y):
 r=math.hypot(x,y);blend=max(0,min(1,(r-4000)/7000));blend=blend*blend*(3-2*blend)
 broad=110+160*fractal(Vector((x/5500,y/5500,6.5)),1.,2.,4)
 small=35*fractal(Vector((x/1100,y/1100,1.2)),1.,2.,3)
 return -.09+blend*max(0,broad+small)
for j in range(NGRID):
 y=-extent+2*extent*j/(NGRID-1)
 for i in range(NGRID):
  x=-extent+2*extent*i/(NGRID-1);vv.append((x,y,terrain_z(x,y)))
for j in range(NGRID-1):
 for i in range(NGRID-1):q=j*NGRID+i;ff.append((q,q+1,q+NGRID+1,q+NGRID))
me=bpy.data.meshes.new('Mars • broad rolling valley floor');me.from_pydata(vv,[],ff);me.materials.append(soil);o=bpy.data.objects.new('Valley • gentle outer hills and continuous distant ground',me);col.objects.link(o)
for p in me.polygons:p.use_smooth=True
# Beyond the mesas, an irregular mountain chain encloses all azimuths.
rng=random.Random(202615)
for j in range(40):
 angle=j*math.tau/40;r=rng.uniform(68000,98000);cx=math.cos(angle)*r;cy=math.sin(angle)*r;rx=rng.uniform(6000,12000);ry=rng.uniform(4500,8500);h=rng.uniform(1800,4200);a=Mesh();segments=96;rings=32
 for level in range(rings):
  u=level/(rings-1);rad=1-u*.96
  for i in range(segments):
   t=i*math.tau/segments;rib=1+.12*math.sin(t*5+j)+.06*math.sin(t*11-j);x=cx+math.cos(t)*rx*rad*rib;y=cy+math.sin(t)*ry*rad*rib;z=h*(u**.7)+90*fractal(Vector((x/900,y/900,j*.4)),1,2,3)*(math.sin(u*math.pi)**.5);a.v.append((x,y,z))
 for level in range(rings-1):
  for i in range(segments):q=level*segments+i;n=level*segments+(i+1)%segments;a.f.append((q,n,n+segments,q+segments));a.mi.append(a.mat(stone))
 a.f.append(tuple((rings-1)*segments+i for i in range(segments)));a.mi.append(a.mat(stone));o=a.object(f'Distant mountains {j+1:02d} • 360 horizon',col)
 for p in o.data.polygons:p.use_smooth=True
# Lower contrast at landscape scales; procedural grain still resolves close to the camera.
b=N(soil.node_tree);p=next(n for n in b.n if n.type=='BSDF_PRINCIPLED');geo=b.node('ShaderNodeNewGeometry');n=b.noise(geo.outputs['Position'],.0007,5);r=b.node('ShaderNodeValToRGB','Kilometre-scale dust variation');r.color_ramp.elements[0].color=(.13,.051,.022,1);r.color_ramp.elements[1].color=(.25,.105,.046,1);b.set(r,0,n);old=p.inputs['Base Color'].links[0].from_socket;mix=b.node('ShaderNodeMixRGB');mix.blend_type='MIX';b.set(mix,0,.5);b.set(mix,1,old);b.set(mix,2,r.outputs[0]);b.set(p,'Base Color',mix.outputs[0])
# Extend the haze well beyond the enlarged valley, retaining a completely clear habitat cavity.
fog=bpy.data.objects['Atmosphere • valley haze with clear interior'];a=Mesh();a.box((0,0,5800),(220000,220000,12000),fog.data.materials[0]);replacement=a.object('TEMP atmosphere bounds',None);fog.data=replacement.data;bpy.data.objects.remove(replacement)
for c in bpy.data.cameras:c.clip_end=1000000
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.clip_end=1000000
# Sampled disk lights approximate the emitting ring area. Their matching LED mesh stays visible
# to camera/glossy rays, while these sources own diffuse illumination (no double energy).
lc=bpy.data.collections.new('YEAR 15 • sampled ring illumination');s.collection.children.link(lc)
surface=next(o for o in bpy.data.objects if o.name.startswith('SURFACES •'))
for iy in range(50):
 for ix in range(50):
  data=bpy.data.lights.new(f'Ring source {ix:02d}-{iy:02d}','AREA');data.shape='DISK';data.size=6.9;data.use_temperature=True
  drive(data,'temperature','k',{'k':'LED temperature K'});drive(data,'energy','p*n*on',{'p':'Ring light power W','n':(light,'Night sky'),'on':'Habitat lights'})
  drive(data,'spread','a*pi/180',{'a':(surface,'LED full beam angle deg')})
  o=bpy.data.objects.new(f'Ring light • L{ix+1:02d} W{iy+1:02d}',data);lc.objects.link(o);o.location=(-1225+ix*50,-1225+iy*50,74.88)
  expr=f'not (on and n and (({ix}-pl)%sl==0) and (({iy}-pw)%sw==0) and (not check or ({ix}+{iy})%2==0))'
  variables={'on':'Habitat lights','n':(light,'Night sky'),'pl':'LED phase L','pw':'LED phase W','sl':'LED every L','sw':'LED every W','check':'LED checkerboard'}
  drive(o,'hide_render',expr,variables);drive(o,'hide_viewport',expr,variables)
mat=bpy.data.materials['Ring • warm LED diffuser'];b=N(mat.node_tree);p=next(n for n in b.n if n.type=='BSDF_PRINCIPLED');old=p.inputs['Emission Strength'].links[0].from_socket;path=b.node('ShaderNodeLightPath','Visible LED / separately sampled illumination');visible=b.math('MAXIMUM',path.outputs['Is Camera Ray'],path.outputs['Is Glossy Ray']);b.set(p,'Emission Strength',b.math('MULTIPLY',old,visible))
# Working moon controls. Preserve the faint reference and expose an explicitly artistic boost.
moon=bpy.data.objects.get('moonlight');moon.name='MOON • Phobos fill with optional presentation boost';moon.data.angle=math.radians(.18);moon.data.color=(1,.91,.8)
drive(moon.data,'energy','p*boost*on*n',{'p':'Moon fill strength','boost':'Moon presentation boost','on':'Moon fill','n':(light,'Night sky')})
drive(moon,'rotation_euler','(90-alt)*pi/180',{'alt':'Moon altitude deg'},0);drive(moon,'rotation_euler','-az*pi/180',{'az':'Moon azimuth deg'},2);moon.rotation_euler.y=0
# Tiny illustrative disk in the environment; real Phobos is much smaller than Earth's Moon.
b=N(s.world.node_tree);out=next(n for n in b.n if n.type=='OUTPUT_WORLD');old=out.inputs['Surface'].links[0].from_socket;az=b.math('MULTIPLY',b.val('Moon azimuth deg'),math.pi/180);alt=b.math('MULTIPLY',b.val('Moon altitude deg'),math.pi/180);direction=b.xyz(b.math('MULTIPLY',b.math('SINE',az),b.math('COSINE',alt)),b.math('MULTIPLY',b.math('COSINE',az),b.math('COSINE',alt)),b.math('SINE',alt));tc=b.node('ShaderNodeTexCoord');dot=b.vec('DOT_PRODUCT',tc.outputs['Normal'],direction);disk=b.math('GREATER_THAN',dot,math.cos(math.radians(.09)));disk=b.math('MULTIPLY',disk,b.math('MULTIPLY',b.val('Show Phobos disk'),b.val('Night sky',light)));bg=b.node('ShaderNodeBackground','Illustrative Phobos disk, not an ephemeris');b.set(bg,'Color',(.62,.57,.49,1));b.set(bg,'Strength',b.math('MULTIPLY',disk,12));add=b.node('ShaderNodeAddShader');b.set(add,0,old);b.set(add,1,bg.outputs[0]);b.set(out,'Surface',add.outputs[0])
# Exterior views aimed at the lit apron; one is deliberately near the membrane.
def cam(name,loc,target,lens):
 o=bpy.data.objects.get(name) or bpy.data.objects.new(name,bpy.data.cameras.new(name))
 if not o.users_collection:s.collection.objects.link(o)
 o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();o.data.lens=lens;o.data.clip_end=1000000;return o
cam('08 • exterior spill and freight airlock',(1460,-810,7),(1200,-600,34),30)
cam('09 • night habitat from valley',(1750,-1800,110),(0,0,30),30)
# Keep the master control prominent. Archived sources stay available but out of normal view.
bpy.ops.object.select_all(action='DESELECT');ctrl.select_set(True);bpy.context.view_layer.objects.active=ctrl;s.camera=bpy.data.objects['01 • valley and landing field'];s.frame_set(1);ctrl.update_tag();bpy.context.view_layer.update()
report=json.loads((R/'docs/year15-verification.json').read_text());report.update({'ground_width_m':1000000,'rolling_terrain_width_m':300000,'mesa_radius_m':[26000,42500],'mountain_radius_m':[68000,98000],'default_active_ring_count':289,'ring_sampling':'Disk area sources at visible ring locations; mesh visible to camera/glossy rays','ring_power_W':9000,'moon_presentation_boost':300});(R/'docs/year15-verification.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True);print('ENVIRONMENT AND SAMPLED RING LIGHTS SAVED',flush=True)
