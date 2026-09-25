import bpy,math,json
from mathutils import Vector,Matrix
from pathlib import Path
s=bpy.context.scene;r=Path(bpy.data.filepath).parent;p=bpy.data.objects['Worker • 1.82 m including hard hat'];cam=bpy.data.objects['Worker and Curiosity • ground material inspection'];d=p.location-cam.location;p.rotation_euler.z=math.atan2(d.y,d.x)+math.pi/2
pivot=Vector((0,.005,1.48));rot=Matrix.Rotation(math.radians(-32),4,'X')
for o in p.children:
 if o.name.startswith(('Head','Nose','Eye','Ear','Hard hat')):o.matrix_basis=Matrix.Translation(pivot)@rot@Matrix.Translation(-pivot)@o.matrix_basis
p['Replacement status']='Temporary original figure, turned away and looking up. Realistic Standing Man asset located; browser blocked downloads.'
s.camera=cam;bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(r/'mars-tensile-vault.blend'))
