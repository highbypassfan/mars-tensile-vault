import bpy,math
from pathlib import Path
s=bpy.context.scene;r=Path(bpy.data.filepath).parent;c=bpy.data.objects['SURFACES • grass and lighting controls'];c['LED full beam angle deg']=160.;c['LED beam gain']=1.6;c['LED ambient glow fraction']=.08;c.id_properties_ui('LED ambient glow fraction').update(min=0.,max=1.);c['Grass clumps per m2']=6.
mat=bpy.data.materials['Ring • warm LED diffuser'];n=mat.node_tree.nodes;l=mat.node_tree.links;beam=next(q for q in n if q.type=='MAP_RANGE');beam.label='160 degree downward beam, soft edge';links=list(beam.outputs['Result'].links);v=n.new('ShaderNodeValue');v.label='Residual glow at all viewing angles';d=v.outputs[0].driver_add('default_value').driver;d.type='AVERAGE';t=d.variables.new();t.targets[0].id=c;t.targets[0].data_path='["LED ambient glow fraction"]';m=n.new('ShaderNodeMath');m.operation='MAXIMUM';l.new(beam.outputs['Result'],m.inputs[0]);l.new(v.outputs[0],m.inputs[1]);
for link in links:l.new(m.outputs[0],link.to_socket)
# Lift the photographic day preview while retaining the existing Mars light directions.
light=bpy.data.objects['LIGHTING • toggle Night sky'];light['Day exposure EV']=.75
c.update_tag();light.update_tag();s.frame_set(s.frame_current);bpy.ops.wm.save_as_mainfile(filepath=str(r/'mars-tensile-vault.blend'))
