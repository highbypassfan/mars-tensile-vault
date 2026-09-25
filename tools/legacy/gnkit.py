"""Small helpers for building Geometry Nodes trees from Python (Blender 5.2).

Used by the photoreal_* one-time scripts in this folder.
"""
import bpy


def enabled(sockets, name):
    """First enabled socket with this name or identifier (type-dependent sockets share names)."""
    for s in sockets:
        if s.enabled and (s.name == name or s.identifier == name):
            return s
    raise KeyError(name)


class Tree:
    def __init__(self, name, inputs=()):
        self.ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        self.ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        self.ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        self.N, self.L = self.ng.nodes, self.ng.links
        self.gin = self.N.new('NodeGroupInput')
        self.gout = self.N.new('NodeGroupOutput')
        self.col = 0
        for name, kind, default in inputs:
            sock = self.ng.interface.new_socket(name, in_out='INPUT', socket_type=kind)
            sock.default_value = default
            if hasattr(sock, 'structure_type') and kind != 'NodeSocketObject':
                try:
                    sock.structure_type = 'SINGLE'
                except TypeError:
                    pass

    def inp(self, name):
        return enabled(self.gin.outputs, name)

    def node(self, kind, label='', **props):
        n = self.N.new(kind)
        n.label = label
        self.col += 1
        n.location = ((self.col % 40) * 220, -(self.col // 40) * 300)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.L.new(a, b)

    def set(self, node, name, value):
        """Link a socket or set a default on an input found by name."""
        sock = enabled(node.inputs, name)
        if isinstance(value, bpy.types.NodeSocket):
            self.L.new(value, sock)
        elif value is not None:
            sock.default_value = value
        return sock

    def out(self, node, name=None):
        return enabled(node.outputs, name) if name else next(s for s in node.outputs if s.enabled)

    def make(self, kind, label='', props=None, **inputs):
        n = self.node(kind, label, **(props or {}))
        for k, v in inputs.items():
            self.set(n, k.replace('_', ' '), v)
        return n

    # --- field helpers -------------------------------------------------------
    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.L.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.L.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        if scale is not None:
            self.set(n, 'Scale', scale)
        return self.out(n, 'Value' if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else 'Vector')

    def xyz(self, vec):
        n = self.node('ShaderNodeSeparateXYZ')
        self.L.new(vec, n.inputs[0])
        return n.outputs['X'], n.outputs['Y'], n.outputs['Z']

    def combine(self, x=0.0, y=0.0, z=0.0):
        n = self.node('ShaderNodeCombineXYZ')
        for i, v in enumerate((x, y, z)):
            if isinstance(v, bpy.types.NodeSocket):
                self.L.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]

    def random(self, kind, lo, hi, seed, id_field=None):
        n = self.node('FunctionNodeRandomValue', data_type=kind)
        self.set(n, 'Min', lo)
        self.set(n, 'Max', hi)
        self.set(n, 'Seed', seed)
        if id_field is not None:
            self.set(n, 'ID', id_field)
        return self.out(n, 'Value')

    def position(self):
        return self.out(self.node('GeometryNodeInputPosition'))

    def index(self):
        return self.out(self.node('GeometryNodeInputIndex'))

    def named(self, name, kind='FLOAT'):
        n = self.node('GeometryNodeInputNamedAttribute', data_type=kind)
        self.set(n, 'Name', name)
        return self.out(n, 'Attribute')

    def obj(self, ob, relative=True):
        n = self.node('GeometryNodeObjectInfo', transform_space='RELATIVE' if relative else 'ORIGINAL')
        self.set(n, 'Object', ob)
        return self.out(n, 'Geometry')

    def join(self, *geos):
        n = self.node('GeometryNodeJoinGeometry')
        for g in reversed(geos):
            self.L.new(g, n.inputs[0])
        return n.outputs[0]

    def finish(self, geo):
        self.L.new(geo, self.gout.inputs[0])
        return self.ng


def modifier(ob, tree, name):
    m = ob.modifiers.new(name, 'NODES')
    m.node_group = tree
    return m


def set_input(mod, name, value):
    for item in mod.node_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == name:
            getattr(mod.properties.inputs, item.identifier).value = value
            return
    raise KeyError(name)


def new_object(name, collection, mesh=None):
    me = mesh or bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def collection(name, parent=None, exclude=False):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if col.name not in parent.children:
        parent.children.link(col)
    if exclude:
        def find(layer):
            if layer.collection == col:
                return layer
            for child in layer.children:
                hit = find(child)
                if hit:
                    return hit
        lc = find(bpy.context.view_layer.layer_collection)
        if lc:
            lc.exclude = True
    return col
