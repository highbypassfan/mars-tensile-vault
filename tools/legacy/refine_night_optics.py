"""One-time star-map and thin-film/night-lighting refinement."""
import bpy,ast,math,json,shutil
from pathlib import Path
R=Path(bpy.data.filepath).parent;s=bpy.context.scene
ctrl=bpy.data.objects['SETTLEMENT • time and district controls']
if 'Annular ring lighting' in ctrl:raise RuntimeError('Already refined')
backup=R/'renders/before-night-optics.blend'
if backup.exists():assert backup.read_bytes()==Path(bpy.data.filepath).read_bytes()
else:shutil.copy2(bpy.data.filepath,backup)
t=ast.parse((R/'tools/build_year15.py').read_text(encoding='utf-8-sig'))
exec(compile(ast.Module(body=[n for n in t.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ['N','drive']],type_ignores=[]),'helpers','exec'))
for k,v,lo,hi in [('Annular ring lighting',True,0,1),('Ring mesh illumination gain',1.,0,5),('Star foreground gain',.55,0,4),('Milky Way gain',.32,0,4),('Film haze per ply',.025,0,.2),('Film reflection roughness',.035,.005,.25)]:
 ctrl[k]=v
 if not isinstance(v,bool):ctrl.id_properties_ui(k).update(min=lo,max=hi)
# NASA's full-sphere catalogue orientation remains unchanged. Keep the bright stars
# at 16k while the extended faint background only needs 4k.
wb=N(s.world.node_tree);tex=next(n for n in wb.n if n.type=='TEX_IMAGE' and n.image and n.image.name=='starmap_2020_4k.exr')
old=tex.image
for name in ['hiptyc_2020_16k.exr','milkyway_2020_4k.exr']:
 assert (R/'assets/sky'/name).is_file()
stars=bpy.data.images.load(str(R/'assets/sky/hiptyc_2020_16k.exr'),check_existing=True)
stars.filepath='//assets/sky/hiptyc_2020_16k.exr';tex.image=stars;tex.interpolation='Linear';tex.extension='REPEAT'
tex.label='NASA Hipparcos/Tycho bright stars • 16k'
milky=bpy.data.images.load(str(R/'assets/sky/milkyway_2020_4k.exr'),check_existing=True);milky.filepath='//assets/sky/milkyway_2020_4k.exr'
mt=wb.node('ShaderNodeTexImage','NASA Milky Way • 4k extended background');mt.image=milky;mt.interpolation='Linear';wb.set(mt,'Vector',tex.inputs['Vector'].links[0].from_socket)
star_scale=wb.node('ShaderNodeVectorMath','Star radiance');star_scale.operation='SCALE';wb.set(star_scale,0,tex.outputs['Color']);wb.set(star_scale,'Scale',wb.val('Star foreground gain'))
mw_scale=wb.node('ShaderNodeVectorMath','Milky Way radiance');mw_scale.operation='SCALE';wb.set(mw_scale,0,mt.outputs['Color']);wb.set(mw_scale,'Scale',wb.val('Milky Way gain'))
bg=next(n for n in wb.n if n.label=='Catalogue night sky');wb.set(bg,'Color',wb.vec('ADD',star_scale.outputs[0],mw_scale.outputs[0]))
if old.users==0:bpy.data.images.remove(old)
s.cycles.filter_width=1.0
# A welded laminate does not add an independent air/polymer reflection at every ply.
# Use the effective two-interface thin-sheet Fresnel result, plus the actual optical
# path *inside* the film (Snell), instead of 1/cos(external angle) blowing up at grazing.
m=bpy.data.materials['Live membrane • roof and four-ply rings'];b=N(m.node_tree);M=b.math
geo=m.node_tree.nodes['Two-sided sheet'];normal=m.node_tree.nodes['Subtle reflective wrinkles'].outputs['Normal']
cosine=M('MINIMUM',1,M('ABSOLUTE',b.vec('DOT_PRODUCT',geo.outputs['Incoming'],normal)))
inside_cos=M('SQRT',M('SUBTRACT',1,M('DIVIDE',M('SUBTRACT',1,M('MULTIPLY',cosine,cosine)),1.4**2)))
b.set(m.node_tree.nodes['DIVIDE.011'],1,inside_cos)
f=b.node('ShaderNodeFresnel','ETFE interface • IOR 1.4');b.set(f,'IOR',1.4);b.set(f,'Normal',normal)
effective=M('DIVIDE',M('MULTIPLY',2,f.outputs[0]),M('ADD',1,f.outputs[0]))
b.set(m.node_tree.nodes['Angle dependent multilayer film'],0,effective)
ply=m.node_tree.nodes['MAXIMUM'].outputs[0]
haze=M('SUBTRACT',1,M('POWER',M('SUBTRACT',1,b.val('Film haze per ply')),M('DIVIDE',ply,inside_cos)))
b.set(m.node_tree.nodes['Accumulated ply haze'],0,haze)
b.set(m.node_tree.nodes['Stacked thin-sheet reflections'],'Roughness',b.val('Film reflection roughness'))
# Illuminate from the actual narrow segmented emitter geometry, not a filled disk
# crossing through the cable fan. Retain the original area-source setup as a toggle.
led=bpy.data.materials['Ring • warm LED diffuser'];b=N(led.node_tree);M=b.math
p=next(n for n in b.n if n.type=='BSDF_PRINCIPLED')
last=p.inputs['Emission Strength'].links[0].from_node
assert last.operation=='MULTIPLY'
pre=last.inputs[0].links[0].from_socket
visibility=last.inputs[1].links[0].from_socket
cage=next(o for o in s.objects if o.name.startswith('TENSILE CAGE'));cm=cage.modifiers[0]
def cage_value(name):
 sock=next(i for i in cm.node_group.interface.items_tree if i.item_type=='SOCKET' and i.in_out=='INPUT' and i.name==name)
 n=b.node('ShaderNodeValue',name);d=n.outputs[0].driver_add('default_value').driver;d.expression='v';v=d.variables.new();v.name='v';v.targets[0].id=cage;v.targets[0].data_path='modifiers['+json.dumps(cm.name,ensure_ascii=False)+'].properties.inputs.'+sock.identifier+'.value';return n.outputs[0]
# Approximate emitting half-torus area; gain allows artistic correction of the
# existing angular mask. This is not calibrated photometric power.
area=M('MULTIPLY',math.pi**2*.5,M('MULTIPLY',cage_value('Cap Diameter'),cage_value('LED Strip Diameter')))
radiance=M('DIVIDE',b.val('Ring light power W'),M('MAXIMUM',M('MULTIPLY',math.pi,area),.001))
ratio=M('DIVIDE',M('MULTIPLY',radiance,b.val('Ring mesh illumination gain')),M('MAXIMUM',b.val('LED brightness'),.001))
factor=M('ADD',visibility,M('MULTIPLY',M('SUBTRACT',1,visibility),M('MULTIPLY',b.val('Annular ring lighting'),ratio)))
b.set(p,'Emission Strength',M('MULTIPLY',pre,factor));led.cycles.emission_sampling='FRONT_BACK'
for o in s.objects:
 if o.type!='LIGHT' or not o.name.startswith('Ring light'):continue
 for owner,path in [(o.data,'energy'),(o,'hide_render'),(o,'hide_viewport')]:
  fc=next(f for f in owner.animation_data.drivers if f.data_path==path);d=fc.driver;oldexpr=d.expression
  v=d.variables.new();v.name='annular';v.targets[0].id=ctrl;v.targets[0].data_path='["Annular ring lighting"]'
  d.expression=('('+oldexpr+')*(1-annular)') if path=='energy' else '(('+oldexpr+') or annular)'
ctrl['Night optics notes']='16k bright-star layer plus separate Milky Way. Annular mode uses the actual LED mesh, avoiding the filled-disk cable hotspot. Some reflected illumination on steel near lights remains physically expected. Ring power is an approximate radiance conversion, not IES photometry.'
ctrl.update_tag();s.frame_set(s.frame_current);bpy.context.view_layer.update()
assert tuple(stars.size)==(16384,8192)
assert all(Path(bpy.path.abspath(im.filepath)).exists() for im in [stars,milky])
bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True)
print('NIGHT OPTICS SAVED',flush=True)
