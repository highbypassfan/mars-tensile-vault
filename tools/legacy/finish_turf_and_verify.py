import bpy,json,ast
from pathlib import Path
R=Path(bpy.data.filepath).parent;s=bpy.context.scene;ctrl=bpy.data.objects['SETTLEMENT • time and district controls']
t=ast.parse((R/'tools/build_year15.py').read_text(encoding='utf-8-sig'));exec(compile(ast.Module(body=[n for n in t.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ['N','drive']],type_ignores=[]),'helper','exec'))
m=bpy.data.materials['Colony • continuous textured turf'];b=N(m.node_tree);p=next(n for n in b.n if n.type=='BSDF_PRINCIPLED');tex=next(n for n in b.n if n.type=='TEX_IMAGE' and '_diff_' in n.image.name);gray=b.node('ShaderNodeRGBToBW');b.set(gray,0,tex.outputs['Color']);r=b.node('ShaderNodeValToRGB','Living grass color with scanned fine detail');r.color_ramp.elements[0].position=.03;r.color_ramp.elements[0].color=(.018,.041,.007,1);r.color_ramp.elements[1].position=.5;r.color_ramp.elements[1].color=(.11,.22,.035,1);b.set(r,0,gray.outputs[0]);b.set(p,'Base Color',r.outputs[0])
g=bpy.data.node_groups['YEAR15 • instanced grass distance LOD'];b=N(g)
for n in list(g.nodes):
 if n.bl_idname=='GeometryNodeInstanceOnPoints':n.inputs['Scale'].default_value=(1.15,1.15,1.12)
 if n.label=='LOD 1: shared opaque blades':
  old=n.inputs['Density'].links[0].from_socket;b.set(n,'Density',b.math('MULTIPLY',old,1.35))
# Audit loaded native controls at both presets.
report=json.loads((R/'docs/year15-verification.json').read_text());report['lighting_presets']=[]
for frame in [1,120]:
 s.frame_set(frame);bpy.context.view_layer.update();l=bpy.data.objects['LIGHTING • toggle Night sky'];report['lighting_presets'].append({'frame':frame,'hour':ctrl['Local solar hour'],'night':bool(l['Night sky']),'sun_strength':bpy.data.objects['Mars_Sun'].data.energy,'exposure':s.view_settings.exposure})
assert not report['lighting_presets'][0]['night'] and report['lighting_presets'][1]['night']
assert report['lighting_presets'][1]['sun_strength']==0
report['packed_images']=all(i.packed_file for i in bpy.data.images if i.source=='FILE');assert report['packed_images']
assert not bpy.data.libraries
assert not any(i.name.startswith('Poliigon') for i in bpy.data.images)
report['invalid_object_drivers']=[(o.name,d.data_path) for o in bpy.data.objects if o.animation_data for d in o.animation_data.drivers if not d.is_valid];assert not report['invalid_object_drivers']
report['default_active_ring_count']=sum(1 for x in range(50) for y in range(50) if x%ctrl['LED every L']==0 and y%ctrl['LED every W']==0)
report['grass_extents']=[min(v.co[i] for v in bpy.data.objects['Grass • full field with three distance detail levels'].data.vertices) for i in [0,1]]+[max(v.co[i] for v in bpy.data.objects['Grass • full field with three distance detail levels'].data.vertices) for i in [0,1]]
assert max(abs(x) for x in report['grass_extents'])<1250
# Category toggles must actually update object visibility.
home=next(iter(bpy.data.collections['YEAR 15 • Homes'].objects));ctrl['Homes']=False;ctrl.update_tag();bpy.context.view_layer.update();assert home.hide_render;ctrl['Homes']=True;ctrl.update_tag();bpy.context.view_layer.update();assert not home.hide_render
report['home_toggle_verified']=True
cage=next(o for o in s.objects if o.name.startswith('TENSILE CAGE'));cm=cage.modifiers[0];socks={i.name:i for i in cm.node_group.interface.items_tree if i.item_type=='SOCKET' and i.in_out=='INPUT'}
assert getattr(cm.properties.inputs,socks['Anchors L'].identifier).value==50
assert getattr(cm.properties.inputs,socks['Anchors W'].identifier).value==50
assert getattr(cm.properties.inputs,socks['Height'].identifier).value==75
s.frame_set(1);s.camera=bpy.data.objects['02 • civic park and heritage ships'];(R/'docs/year15-verification.json').write_text(json.dumps(report,indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(R/'mars-tensile-vault.blend'),compress=True);print('AUDIT PASSED',report['lighting_presets'],flush=True)
