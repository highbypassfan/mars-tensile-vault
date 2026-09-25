"""One-time change (2026-09-22): procedural Martian ground and rock materials.

Rebuilds two existing materials in place (every object keeps its assignment):
- Mars • compacted ochre regolith: valley floor, hills, aprons. World-space
  dust / basalt-sand patches, wind ripples, pebbles, slope darkening.
- Mesa • layered sedimentary stone: mesas, ridges, boulders. Noise-warped
  strata, dust-mantled flat tops, cracked faces, talus tint.
All scales are in metres of world space, so nothing needs UVs.
  blender -b --factory-startup --disable-autoexec in.blend --python-exit-code 1 \
      --python tools/legacy/photoreal_terrain.py -- out.blend
"""
import sys

import bpy

D = bpy.data


class Builder:
    def __init__(self, material):
        self.nt = material.node_tree
        self.nt.nodes.clear()
        self.N, self.L = self.nt.nodes, self.nt.links
        self.x = 0

    def node(self, kind, x, y, label='', **inputs):
        n = self.N.new(kind)
        n.location = (x, y)
        n.label = label
        for k, v in inputs.items():
            n.inputs[k].default_value = v
        return n

    def link(self, a, b):
        self.L.new(a, b)

    def math(self, op, a, b, x, y, label='', clamp=False):
        n = self.node('ShaderNodeMath', x, y, label)
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        return n.outputs[0]

    def noise(self, vec, scale, detail, rough, x, y, label=''):
        n = self.node('ShaderNodeTexNoise', x, y, label)
        n.noise_dimensions = '3D'
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        self.link(vec, n.inputs['Vector'])
        return n.outputs['Fac']

    def ramp(self, fac, stops, x, y, label=''):
        n = self.node('ShaderNodeValToRGB', x, y, label)
        cr = n.color_ramp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for e, (pos, col) in zip(cr.elements, stops):
            e.position = pos
            e.color = (*col, 1.0)
        self.link(fac, n.inputs['Fac'])
        return n.outputs['Color']

    def mix(self, a, b, fac, x, y, label='', blend='MIX'):
        n = self.node('ShaderNodeMix', x, y, label)
        n.data_type = 'RGBA'
        n.blend_type = blend
        sock = {s.identifier: s for s in n.inputs}
        for key, src in (('A_Color', a), ('B_Color', b), ('Factor_Float', fac)):
            if isinstance(src, tuple):
                sock[key].default_value = (*src[:3], 1.0)
            elif isinstance(src, (int, float)):
                sock[key].default_value = src
            else:
                self.link(src, sock[key])
        return next(s for s in n.outputs if s.identifier == 'Result_Color')

    def smooth(self, value, lo, hi, x, y, label=''):
        n = self.node('ShaderNodeMapRange', x, y, label)
        n.interpolation_type = 'SMOOTHSTEP'
        self.link(value, n.inputs['Value'])
        n.inputs['From Min'].default_value = lo
        n.inputs['From Max'].default_value = hi
        return n.outputs['Result']

    def bump(self, height, strength, distance, normal, x, y, label=''):
        n = self.node('ShaderNodeBump', x, y, label)
        n.inputs['Strength'].default_value = strength
        n.inputs['Distance'].default_value = distance
        self.link(height, n.inputs['Height'])
        if normal is not None:
            self.link(normal, n.inputs['Normal'])
        return n.outputs['Normal']


def regolith():
    b = Builder(D.materials['Mars • compacted ochre regolith'])
    geo = b.node('ShaderNodeNewGeometry', -2200, 0, 'World position')
    p = geo.outputs['Position']
    slope = b.node('ShaderNodeSeparateXYZ', -2000, -600)
    b.link(geo.outputs['Normal'], slope.inputs[0])

    # Albedo: kilometre-scale dust/basalt patches, metre-scale mottling.
    big = b.noise(p, 0.0012, 4, 0.55, -1800, 400, 'Kilometre dust and basalt-sand patches')
    mid = b.noise(p, 0.035, 6, 0.6, -1800, 150, 'Tens of metres mottling')
    fine = b.noise(p, 1.6, 5, 0.65, -1800, -100, 'Grain')
    patches = b.ramp(big, [(0.28, (0.085, 0.055, 0.038)), (0.45, (0.19, 0.105, 0.058)),
                          (0.60, (0.30, 0.16, 0.085)), (0.78, (0.38, 0.205, 0.11))],
                     -1500, 400, 'Basalt sand → oxidised dust')
    mottle_mask = b.smooth(mid, 0.38, 0.68, -1500, 150)
    mottled = b.mix(patches, (0.14, 0.085, 0.052), mottle_mask, -1200, 350, 'Dark sand drifts')
    grain = b.math('ADD', b.math('MULTIPLY', fine, 0.45, -1500, -100), 0.76, -1300, -100)
    base = b.mix(mottled, (1, 1, 1), 1.0, -1000, 300, 'Grain brightness', 'MULTIPLY')
    b.link(grain, next(s for s in base.node.inputs if s.identifier == 'B_Color'))

    # Gravel. Each Voronoi cell may hold one pebble whose size,
    # shade and presence come from the cell's random colour; profile is a dome.
    def pebbles(scale, keep, y):
        vor = b.node('ShaderNodeTexVoronoi', -1900, y, f'Pebbles {1 / scale:.2f} m cells')
        vor.inputs['Scale'].default_value = scale
        vor.inputs['Randomness'].default_value = 1.0
        b.link(p, vor.inputs['Vector'])
        rnd = b.node('ShaderNodeSeparateColor', -1700, y - 150)
        b.link(vor.outputs['Color'], rnd.inputs['Color'])
        present = b.math('LESS_THAN', rnd.outputs['Red'], keep, -1500, y - 150)
        radius = b.math('ADD', b.math('MULTIPLY', rnd.outputs['Green'], 0.28, -1500, y - 300), 0.08, -1300, y - 300)
        dome = b.math('SUBTRACT', 1.0, b.math('DIVIDE', vor.outputs['Distance'], radius, -1300, y), -1100, y)
        dome = b.math('MULTIPLY', b.math('MAXIMUM', dome, 0.0, -900, y), present, -700, y)
        shade = b.ramp(rnd.outputs['Blue'], [(0.0, (0.05, 0.04, 0.035)), (0.6, (0.10, 0.07, 0.055)),
                                           (1.0, (0.17, 0.11, 0.075))], -1100, y - 250, 'Pebble colour')
        mask = b.smooth(dome, 0.0, 0.08, -500, y, 'Pebble footprint')
        return dome, mask, shade

    # Larger stones are real geometry (photoreal_rocks.py); the shader adds gravel only.
    dome2, mask2, shade2 = pebbles(6.0, 0.45, -700)
    steep = b.smooth(slope.outputs['Z'], 0.97, 0.80, -1800, -1050, 'Slope')
    color = b.mix(base, (0.10, 0.065, 0.045), b.math('MULTIPLY', steep, 0.6, -1400, -1050), -800, 250,
                  'Darker, rockier slopes')
    color = b.mix(color, shade2, mask2, -600, 250, 'Gravel')
    rock = b.math('MULTIPLY', dome2, 0.8, -300, -700, 'Gravel relief')

    # Height detail: wind ripples + pebbles + grain.
    wave = b.node('ShaderNodeTexWave', -1800, -900, 'Aeolian ripples ~0.35 m')
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Y'
    wave.inputs['Scale'].default_value = 0.45
    wave.inputs['Distortion'].default_value = 6.0
    wave.inputs['Detail'].default_value = 3.0
    b.link(p, wave.inputs['Vector'])
    ripple_zone = b.noise(p, 0.02, 2, 0.5, -1800, -1150, 'Where ripples form')
    ripples = b.math('MULTIPLY', wave.outputs['Fac'], b.smooth(ripple_zone, 0.5, 0.65, -1600, -1150), -1400, -950)
    height = b.math('ADD', b.math('MULTIPLY', ripples, 0.4, -1200, -950),
                    b.math('ADD', b.math('MULTIPLY', rock, 1.2, -1200, -700), b.math('MULTIPLY', fine, 0.25, -1200, -800), -1000, -750),
                    -800, -850, 'Surface height')
    normal = b.bump(height, 0.35, 0.06, None, -600, -700, 'Ripples, pebbles, grain')

    bsdf = b.node('ShaderNodeBsdfPrincipled', -200, 100, 'Regolith')
    b.link(color, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.93
    bsdf.inputs['Specular IOR Level'].default_value = 0.3
    b.link(normal, bsdf.inputs['Normal'])
    out = b.node('ShaderNodeOutputMaterial', 150, 100)
    b.link(bsdf.outputs[0], out.inputs['Surface'])


def mesa():
    b = Builder(D.materials['Mesa • layered sedimentary stone'])
    geo = b.node('ShaderNodeNewGeometry', -2400, 0, 'World position')
    p = geo.outputs['Position']
    sep = b.node('ShaderNodeSeparateXYZ', -2200, 300)
    b.link(p, sep.inputs[0])
    nrm = b.node('ShaderNodeSeparateXYZ', -2200, -700)
    b.link(geo.outputs['Normal'], nrm.inputs[0])

    # Strata: height, warped by large noise so beds undulate and pinch out.
    warp = b.noise(p, 0.0008, 3, 0.5, -2200, 100, 'Bed undulation')
    z = b.math('ADD', sep.outputs['Z'], b.math('MULTIPLY', warp, 180.0, -2000, 100), -1800, 250, 'Warped height')
    beds = b.math('FRACT', b.math('DIVIDE', z, 38.0, -1600, 250), None, -1400, 250, 'Bed cycle (38 m)')
    thin = b.math('FRACT', b.math('DIVIDE', z, 6.5, -1600, 450), None, -1400, 450, 'Thin laminae')
    strata = b.ramp(beds, [(0.0, (0.30, 0.13, 0.065)), (0.22, (0.40, 0.19, 0.09)), (0.35, (0.23, 0.10, 0.055)),
                          (0.55, (0.47, 0.25, 0.13)), (0.72, (0.33, 0.15, 0.075)), (0.90, (0.20, 0.085, 0.05))],
                    -1200, 250, 'Sandstone, mudstone and dark beds')
    lam = b.math('ADD', b.math('MULTIPLY', b.smooth(thin, 0.0, 0.18, -1200, 500), 0.18, -1000, 500), 0.86, -800, 500)
    layered = b.mix(strata, (1, 1, 1), 1.0, -800, 250, 'Laminae', 'MULTIPLY')
    b.link(lam, next(s for s in layered.node.inputs if s.identifier == 'B_Color'))

    # Weathering: large-scale tint shifts and cracks on faces.
    tint = b.noise(p, 0.004, 4, 0.55, -2200, -150, 'Weathering tint')
    weathered = b.mix(layered, (0.16, 0.08, 0.05), b.math('MULTIPLY', b.smooth(tint, 0.45, 0.8, -1800, -150), 0.5, -1600, -150),
                      -600, 200, 'Desert varnish')
    cracks = b.node('ShaderNodeTexVoronoi', -2200, -400, 'Joint blocks ~3 m')
    cracks.feature = 'DISTANCE_TO_EDGE'
    cracks.inputs['Scale'].default_value = 0.35
    b.link(p, cracks.inputs['Vector'])
    crack = b.smooth(cracks.outputs['Distance'], 0.05, 0.0, -2000, -400, 'Crack lines')
    rough_n = b.noise(p, 0.9, 8, 0.62, -2200, -550, 'Rock surface')

    # Dust mantle on gentle surfaces, talus tint low on slopes.
    flat = b.smooth(nrm.outputs['Z'], 0.72, 0.9, -2000, -700, 'Flat → dust covered')
    dust_n = b.noise(p, 0.02, 4, 0.5, -2000, -850, 'Dust drift')
    dust_amt = b.math('MULTIPLY', flat, b.smooth(dust_n, 0.3, 0.55, -1800, -850), -1600, -750, 'Dust mantle')
    dust = (0.40, 0.19, 0.085)
    color = b.mix(weathered, dust, dust_amt, -400, 150, 'Wind-blown dust')
    color = b.mix(color, (0.07, 0.04, 0.03), b.math('MULTIPLY', crack, 0.7, -400, -350), -200, 150, 'Shadowed joints')

    height = b.math('ADD', b.math('MULTIPLY', rough_n, 1.0, -1400, -550),
                    b.math('MULTIPLY', crack, -1.5, -1400, -400), -1200, -480, 'Rock relief')
    height = b.math('ADD', height, b.math('MULTIPLY', thin, 0.4, -1200, -300), -1000, -400)
    normal = b.bump(height, 0.55, 0.25, None, -600, -500, 'Joints, laminae, rough faces')

    bsdf = b.node('ShaderNodeBsdfPrincipled', 0, 100, 'Rock')
    b.link(color, bsdf.inputs['Base Color'])
    rough = b.math('ADD', 0.86, b.math('MULTIPLY', dust_amt, 0.1, -400, -700), -200, -700)
    b.link(rough, bsdf.inputs['Roughness'])
    bsdf.inputs['Specular IOR Level'].default_value = 0.35
    b.link(normal, bsdf.inputs['Normal'])
    out = b.node('ShaderNodeOutputMaterial', 350, 100)
    b.link(bsdf.outputs[0], out.inputs['Surface'])


def main():
    regolith()
    mesa()
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('TERRAIN SAVED', out, flush=True)


if __name__ == '__main__':
    main()
