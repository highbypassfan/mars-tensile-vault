"""One-time change (2026-09-22): panel toggles for the photoreal additions.

Adds People, Rock field and Solar farm and power checkboxes to the Districts
section of CONTROLS • Mars vault and drives the new objects' visibility.
The freight yard keeps the existing Cargo yard toggle.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/photoreal_controls.py -- out.blend
"""
import sys

import bpy

D = bpy.data
TOGGLES = {
    'People': ('Crowd of residents and workers (shared instances)', ['YEAR 15 • People']),
    'Rock field': ('Scattered basalt cobbles and boulders outside the walls', ['YEAR 15 • Rock field']),
    'Solar farm and power': ('Solar farm, HV cable, farm and battery substations', ['YEAR 15 • Solar farm and power']),
}


def main():
    ctl = D.objects['CONTROLS • Mars vault']
    mod = ctl.modifiers['CONTROLS']
    ng = mod.node_group
    districts = next(i for i in ng.interface.items_tree if i.item_type == 'PANEL' and i.name == 'Districts')
    for name, (desc, collections) in TOGGLES.items():
        sock = ng.interface.new_socket(name, in_out='INPUT', socket_type='NodeSocketBool', parent=districts)
        sock.default_value = True
        sock.description = desc
        getattr(mod.properties.inputs, sock.identifier).value = True
        path = f'modifiers["CONTROLS"].properties.inputs.{sock.identifier}.value'
        for cname in collections:
            for ob in D.collections[cname].all_objects:
                for prop in ('hide_render', 'hide_viewport'):
                    fc = ob.driver_add(prop)
                    fc.driver.type = 'SCRIPTED'
                    var = fc.driver.variables.new()
                    var.name = 'on'
                    var.targets[0].id = ctl
                    var.targets[0].data_path = path
                    fc.driver.expression = 'not on'
                    fc.keyframe_points.clear()    # a driver F-curve must not carry keys (see fix_driver_curves.py)
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('CONTROLS SAVED', out, flush=True)


if __name__ == '__main__':
    main()
