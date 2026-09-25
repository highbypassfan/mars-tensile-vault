"""One-time change (2026-09-22): carry the welded wall seams around the corners.

The wall is tiled from welded panels. Straight walls already had vertical seams
on the anchor rows and horizontal seams every Spacing W of profile arc length,
but each rounded corner was a single panel. Now:
- horizontal seams continue around the corner (same GroundArc rule);
- vertical corner seams fan radially from the corner anchor, evenly spaced in
  angle, so every seam line points into that anchor. Their count keeps the
  panel width at the ground close to Spacing L; panels taper toward the top.
The node group stores the wall's outer ground reach (WallGroundReach); the
shader derives the seam count from it, so it follows cage edits.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/corner_seams.py -- out.blend
"""
import sys

import bpy

D = bpy.data
HALF_PI = 1.5707963267948966


def geometry_nodes():
    ng = D.node_groups['TV • Pressure-derived panels and continuous foundation']
    N, L = ng.nodes, ng.links
    last = next(n for n in N if n.bl_idname == 'GeometryNodeStoreNamedAttribute'
                and n.inputs['Name'].default_value == 'GroundStrip')
    out_links = [(l.to_socket) for l in last.outputs[0].links]
    x0, y0 = last.location

    def node(kind, dx, dy, **props):
        n = N.new(kind)
        n.location = (x0 + dx, y0 + dy)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def named(name, dy):
        n = node('GeometryNodeInputNamedAttribute', 150, dy, data_type='FLOAT_VECTOR' if name == 'WallLocal' else 'FLOAT')
        n.inputs['Name'].default_value = name
        return n.outputs['Attribute']

    def stat(field, dy):
        n = node('GeometryNodeAttributeStatistic', 500, dy, data_type='FLOAT', domain='POINT')
        L.new(last.outputs[0], n.inputs['Geometry'])
        L.new(field, n.inputs['Attribute'])
        return n.outputs['Max']

    def op_node(op, a, b, dx, dy):
        n = node('ShaderNodeMath', dx, dy, operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    sep = node('ShaderNodeSeparateXYZ', 300, -200)
    L.new(named('WallLocal', -200), sep.inputs[0])
    reach = stat(op_node('ABSOLUTE', sep.outputs['X'], None, 350, -300), -300)   # outer ground edge of wall
    store = node('GeometryNodeStoreNamedAttribute', 900, 0, data_type='FLOAT', domain='POINT')
    store.label = 'WallGroundReach'
    store.inputs['Name'].default_value = 'WallGroundReach'
    L.new(last.outputs[0], store.inputs['Geometry'])
    L.new(reach, store.inputs['Value'])
    for sock in out_links:
        L.new(store.outputs[0], sock)


def shader():
    nt = D.materials['Pressure wall • aligned bays and single-piece corners'].node_tree
    N, L = nt.nodes, nt.links

    # Existing seam distances: old_v = straight seams plus the two corner boundaries,
    # straight_v = straight seams only, old_h = horizontal seams (+1e4 inside corners).
    old_v = next(n for n in N if n.bl_idname == 'ShaderNodeMath' and n.operation == 'ADD'
                 and n.inputs[0].is_linked and n.inputs[0].links[0].from_node.name == 'MINIMUM.003'
                 and n.inputs[1].is_linked and n.inputs[1].links[0].from_node.name == 'MULTIPLY.006')
    straight_v = next(n for n in N if n.bl_idname == 'ShaderNodeMath' and n.operation == 'ADD'
                      and {l.from_node.name for s in n.inputs[:2] for l in s.links} == {'MULTIPLY.004', 'MULTIPLY.005'})
    old_h = N['ADD.004']
    straight_h = old_h.inputs[0].links[0].from_socket          # distance to nearest horizontal seam
    x0, y0 = old_v.location.x, old_v.location.y + 900

    def node(kind, dx, dy, label=''):
        n = N.new(kind)
        n.location = (x0 + dx, y0 + dy)
        n.label = label
        return n

    def attr(name, dx, dy):
        n = node('ShaderNodeAttribute', dx, dy, name)
        n.attribute_name = name
        return n

    def m(op, a, b, dx, dy, label=''):
        n = node('ShaderNodeMath', dx, dy, label)
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    local = node('ShaderNodeSeparateXYZ', -1400, 0, 'Wall position')
    L.new(attr('WallLocal', -1600, 0).outputs['Vector'], local.inputs[0])
    dx = m('SUBTRACT', m('ABSOLUTE', local.outputs['X'], None, -1200, 60),
           m('MULTIPLY', attr('AnchorSpanX', -1600, -150).outputs['Fac'], 0.5, -1200, -80), -1000, 40, 'From corner anchor X')
    dy = m('SUBTRACT', m('ABSOLUTE', local.outputs['Y'], None, -1200, -200),
           m('MULTIPLY', attr('AnchorSpanY', -1600, -300).outputs['Fac'], 0.5, -1200, -340), -1000, -220, 'From corner anchor Y')
    fan = m('MULTIPLY', m('GREATER_THAN', dx, 0.0, -800, 60), m('GREATER_THAN', dy, 0.0, -800, -120), -600, 0,
            'Corner fan region')
    angle = m('ARCTAN2', dy, dx, -800, -300, 'Angle about corner anchor')
    # Seam count: keep corner panels about Spacing L wide at the ground.
    ground_radius = m('SUBTRACT', attr('WallGroundReach', -1400, -700).outputs['Fac'],
                      m('MULTIPLY', attr('AnchorSpanX', -1400, -850).outputs['Fac'], 0.5, -1200, -850), -1000, -750)
    count = m('DIVIDE', m('MULTIPLY', ground_radius, HALF_PI, -900, -750),
              attr('Spacing L', -1400, -1000).outputs['Fac'], -800, -800)
    count = m('MAXIMUM', m('ROUND', count, None, -700, -800), 1.0, -600, -800, 'Corner seam count')
    step = m('DIVIDE', HALF_PI, count, -800, -450, 'Seam angle step')
    t = m('DIVIDE', angle, step, -600, -350)
    frac = m('FRACT', t, None, -400, -350)
    nearest = m('MINIMUM', frac, m('SUBTRACT', 1.0, frac, -300, -450), -200, -380)
    radius = m('SQRT', m('ADD', m('MULTIPLY', dx, dx, -600, -550), m('MULTIPLY', dy, dy, -600, -650), -400, -600),
               None, -200, -600, 'Plan distance from anchor')
    fan_v = m('MULTIPLY', m('MULTIPLY', nearest, step, 0, -400), radius, 200, -450, 'Distance to radial corner seam')
    new_v = m('ADD', straight_v.outputs[0],
              m('MULTIPLY', m('SUBTRACT', fan_v, straight_v.outputs[0], 400, -300), fan, 600, -200), 800, -100,
              'Vertical seam distance, corners fanned into anchor')
    for link in list(old_v.outputs[0].links):
        L.new(new_v, link.to_socket)
    for link in list(old_h.outputs[0].links):
        L.new(straight_h, link.to_socket)                      # horizontal seams continue round corners
    nt.nodes.remove(old_h)  # its only role was to disable corner horizontal seams
    return new_v


def main():
    geometry_nodes()
    shader()
    mat = D.materials['Pressure wall • aligned bays and single-piece corners']
    mat.name = 'Pressure wall • welded bays with fanned corners'
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('CORNER SEAMS SAVED', out, flush=True)


if __name__ == '__main__':
    main()
