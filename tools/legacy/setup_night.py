"""Run in Blender with the share blend open. Sky orientation uses IAU 2009 Mars.
No third-party Python dependencies. Local +X east, +Y north, +Z up.
"""
import bpy, math, datetime, json
from pathlib import Path
from mathutils import Vector, Matrix

root = Path(bpy.data.filepath).parent
s = bpy.context.scene
ctrl = bpy.data.objects['LIGHTING • toggle Night sky']
for key,value,lo,hi in [('Day exposure EV',-.25,-10,10),('Night exposure EV',3.25,-10,15),('Night sky gain',.2,0,10)]:
    ctrl[key]=ctrl.get(key,value)
    ctrl.id_properties_ui(key).update(min=lo,max=hi)
ctrl['Sky latitude deg']=ctrl.get('Sky latitude deg',-4.59)
ctrl['Sky east longitude deg']=ctrl.get('Sky east longitude deg',137.44)
ctrl['Sky epoch UTC']=ctrl.get('Sky epoch UTC','2026-09-20T00:00:00Z')
ctrl['Sky orientation model']='IAU 2009 / pck00010; local X east, Y north'

def drive(owner,path,expression,props):
    try: owner.driver_remove(path)
    except: pass
    d=owner.driver_add(path).driver; d.expression=expression
    for name,prop in props.items():
        v=d.variables.new();v.name=name;v.targets[0].id=ctrl;v.targets[0].data_path='["'+prop+'"]'

drive(s.view_settings,'exposure','day*(1-night)+ev*night',{'day':'Day exposure EV','ev':'Night exposure EV','night':'Night sky'})
bpy.data.materials['Ring • warm LED diffuser'].cycles.emission_sampling='FRONT_BACK'
s.render.engine='CYCLES';s.cycles.diffuse_bounces=8;s.cycles.max_bounces=32
s.cycles.transmission_bounces=32;s.cycles.transparent_max_bounces=96
s.cycles.sample_clamp_indirect=0;s.cycles.use_light_tree=True

# Polynomial coefficients from NAIF pck00010. UTC -> TT using 69.184 s;
# TT approximates TDB to millisecond accuracy, ample for this visualization.
epoch=datetime.datetime.fromisoformat(ctrl['Sky epoch UTC'].replace('Z','+00:00'))
d=(epoch-datetime.datetime(2000,1,1,12,tzinfo=datetime.timezone.utc)).total_seconds()/86400+69.184/86400
t=d/36525
ra,dec,w=map(math.radians,(317.68143-.1061*t,52.88650-.0609*t,(176.630+350.89198226*d)%360))
pole=Vector((math.cos(dec)*math.cos(ra),math.cos(dec)*math.sin(ra),math.sin(dec)))
q=Vector((-math.sin(ra),math.cos(ra),0));r=pole.cross(q)
bx=math.cos(w)*q+math.sin(w)*r;by=-math.sin(w)*q+math.cos(w)*r
lat,lon=map(math.radians,(ctrl['Sky latitude deg'],ctrl['Sky east longitude deg']))
east=-math.sin(lon)*bx+math.cos(lon)*by
north=-math.sin(lat)*(math.cos(lon)*bx+math.sin(lon)*by)+math.cos(lat)*pole
up=math.cos(lat)*(math.cos(lon)*bx+math.sin(lon)*by)+math.sin(lat)*pole
matrix=Matrix((east,north,up)).transposed()
assert abs(matrix.determinant()-1)<1e-5
(root/'docs'/'sky-orientation.json').write_text(json.dumps({'epoch_utc':ctrl['Sky epoch UTC'],'latitude_deg':ctrl['Sky latitude deg'],'longitude_east_deg':ctrl['Sky east longitude deg'],'model':'IAU 2009 Mars / NAIF pck00010','local_ENU_to_J2000':[list(row) for row in matrix]},indent=2))

nt=s.world.node_tree;nodes=nt.nodes;links=nt.links
for n in list(nodes):
    if n.name.startswith('CATALOG SKY'):nodes.remove(n)
def node(kind,label):
    n=nodes.new(kind);n.name='CATALOG SKY • '+label;n.label=label;return n
def mathnode(op,a,b=None):
    n=node('ShaderNodeMath',op);n.operation=op
    for i,v in enumerate([a,b]):
        if v is None:continue
        if isinstance(v,(float,int)):n.inputs[i].default_value=v
        else:links.new(v,n.inputs[i])
    return n.outputs[0]
coord=node('ShaderNodeTexCoord','Local viewing direction')
xyz=node('ShaderNodeCombineXYZ','J2000 direction')
for i,row in enumerate(matrix):
    dot=node('ShaderNodeVectorMath','ENU to J2000 '+str(i));dot.operation='DOT_PRODUCT'
    links.new(coord.outputs['Normal'],dot.inputs[0]);dot.inputs[1].default_value=row
    links.new(dot.outputs['Value'],xyz.inputs[i])
sep=node('ShaderNodeSeparateXYZ','Celestial axes');links.new(xyz.outputs[0],sep.inputs[0])
raout=mathnode('ARCTAN2',sep.outputs['Y'],sep.outputs['X'])
u=mathnode('ADD',mathnode('MULTIPLY',raout,-1/(2*math.pi)),.5)
v=mathnode('ADD',mathnode('MULTIPLY',mathnode('ARCSINE',sep.outputs['Z']),1/math.pi),.5)
uv=node('ShaderNodeCombineXYZ','NASA RA increases left');links.new(u,uv.inputs[0]);links.new(v,uv.inputs[1])
tex=node('ShaderNodeTexImage','NASA SVS Deep Star Maps 2020')
img=bpy.data.images.get('starmap_2020_4k.exr') or bpy.data.images.load(str(root/'assets/sky/starmap_2020_4k.exr'))
img.pack();tex.image=img;tex.interpolation='Linear';links.new(uv.outputs[0],tex.inputs[0])
bg=node('ShaderNodeBackground','Catalogue night sky');links.new(tex.outputs['Color'],bg.inputs['Color'])
drive(bg.inputs['Strength'],'default_value','gain',{'gain':'Night sky gain'})
mix=nodes.get('Mix Shader');links.new(bg.outputs[0],mix.inputs[2])
for i,n in enumerate(n for n in nodes if n.name.startswith('CATALOG SKY')):n.location=(300+(i%5)*210,-400-(i//5)*220)

# Use a GPU on this workstation, retaining portable fallback in tools/render.py.
p=bpy.context.preferences.addons['cycles'].preferences
for backend in ('OPTIX','CUDA','HIP','METAL','ONEAPI'):
    try:
        p.compute_device_type=backend;p.refresh_devices()
        if not any(dev.type==backend for dev in p.devices):continue
        for dev in p.devices:dev.use=dev.type==backend
        s.cycles.device='GPU';break
    except (TypeError,RuntimeError):pass
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(root/'mars-tensile-vault.blend'))
print('NIGHT STACK SAVED',s.view_settings.exposure,flush=True)
