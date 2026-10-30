import json
import math
import os
import random
import struct
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "static" / "models"
CATALOG_PATH = MODELS_DIR / "catalog.json"

WEB_ASSETS = {
    # Aircraft models from CesiumGS and BabylonJS
    "cesium_air.glb": {
        "url": "https://raw.githubusercontent.com/CesiumGS/cesium/main/Apps/SampleData/models/CesiumAir/Cesium_Air.glb",
        "category": "aircraft",
        "label": "Cesium Air Twin-Turboprop",
        "target_size": 18.0,
        "heading_offset_deg": 0.0,
    },
    "aerobatic_plane.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/aerobatic_plane.glb",
        "category": "aircraft",
        "label": "Extra 300 Aerobatic Stunt Plane",
        "target_size": 12.5,
        "heading_offset_deg": -90.0,
    },
    "seagulf.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/seagulf.glb",
        "category": "aircraft",
        "label": "Seagull Bush Cruiser",
        "target_size": 15.0,
        "heading_offset_deg": -90.0,
    },
    # Web Trees from BabylonJS villagePack & graveYardPack
    "web_tree_1.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/tree1/tree1.glb",
        "category": "tree",
        "subtype": "conifer",
        "label": "Web Woodland Spruce (Type 1)",
        "target_size": 18.0,
    },
    "web_tree_2.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/tree2/tree2.glb",
        "category": "tree",
        "subtype": "deciduous",
        "label": "Web Meadow Canopy Tree (Type 2)",
        "target_size": 16.0,
    },
    "web_tree_3.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/tree3/tree3.glb",
        "category": "tree",
        "subtype": "conifer",
        "label": "Web Alpine Fir (Type 3)",
        "target_size": 21.0,
    },
    "web_tree_4.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/tree4/tree4.glb",
        "category": "tree",
        "subtype": "deciduous",
        "label": "Web Broadleaf Tree (Type 4)",
        "target_size": 15.0,
    },
    "web_gnarled_1.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/graveYardPack/tree1/tree1.glb",
        "category": "tree",
        "subtype": "ancient",
        "label": "Web Ancient Gnarled Oak",
        "target_size": 14.0,
    },
    "web_gnarled_2.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/graveYardPack/tree2/tree2.glb",
        "category": "tree",
        "subtype": "ancient",
        "label": "Web Twisted Deadwood Tree",
        "target_size": 13.0,
    },
    # Web Bushes & Understory Shrubs
    "web_bush_1.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/bush1/bush1.glb",
        "category": "bush",
        "subtype": "shrub",
        "label": "Web Hedgerow Bush 1",
        "target_size": 2.8,
    },
    "web_bush_2.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/bush2/bush2.glb",
        "category": "bush",
        "subtype": "shrub",
        "label": "Web Berry Shrub 2",
        "target_size": 2.4,
    },
    "web_bush_3.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/bush3/bush3.glb",
        "category": "bush",
        "subtype": "shrub",
        "label": "Web Low Thicket 3",
        "target_size": 2.2,
    },
    "web_bush_4.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/bush4/bush4.glb",
        "category": "bush",
        "subtype": "shrub",
        "label": "Web Dense Foliage Bush 4",
        "target_size": 3.0,
    },
    "web_bush_5.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/bush5/bush5.glb",
        "category": "bush",
        "subtype": "shrub",
        "label": "Web Wild Scrub 5",
        "target_size": 2.5,
    },
    "grass_tuft.glb": {
        "url": "https://raw.githubusercontent.com/VictorZakharov/dark-strands/main/assets/models/eztree/grass.glb",
        "category": "bush",
        "subtype": "grass",
        "label": "MIT-Licensed Meadow Grass Tuft",
        "target_size": 0.8,
    },
    # Web Rocks & Forestry Structures
    "web_rocks_1.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/rocks1/rocks1.glb",
        "category": "rock",
        "subtype": "boulder",
        "label": "Web Granite Outcrop 1",
        "target_size": 4.5,
    },
    "web_rocks_2.glb": {
        "url": "https://raw.githubusercontent.com/BabylonJS/Assets/master/meshes/villagePack/rocks2/rocks2.glb",
        "category": "rock",
        "subtype": "boulder",
        "label": "Web Mossy Boulder 2",
        "target_size": 3.8,
    },
    "wood_tower.glb": {
        "url": "https://raw.githubusercontent.com/CesiumGS/cesium/main/Apps/SampleData/models/WoodTower/Wood_Tower.glb",
        "category": "structure",
        "subtype": "lookout",
        "label": "Forestry Fire Lookout Tower",
        "target_size": 22.0,
    },
    "flamingo.glb": {
        "url": "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/Flamingo.glb",
        "category": "wildlife",
        "subtype": "bird",
        "label": "Soaring Flamingo",
        "target_size": 2.5,
    },
    "parrot.glb": {
        "url": "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/Parrot.glb",
        "category": "wildlife",
        "subtype": "bird",
        "label": "Canopy Macaw Parrot",
        "target_size": 1.8,
    },
}


class GLBBuilder:
    """Pure-Python binary glTF 2.0 (.glb) multi-material 3D mesh builder."""

    def __init__(self):
        self.materials = []
        self.primitives = []

    def add_material(self, name, rgba, metallic=0.05, roughness=0.85, emissive=None):
        idx = len(self.materials)
        mat = {
            "name": name,
            "pbrMetallicRoughness": {
                "baseColorFactor": [float(c) for c in rgba],
                "metallicFactor": float(metallic),
                "roughnessFactor": float(roughness),
            },
            "doubleSided": True,
        }
        if emissive:
            mat["emissiveFactor"] = [float(c) for c in emissive]
        self.materials.append(mat)
        return idx

    def add_cone_frustum(
        self, mat_idx, base_center, top_center, r_bottom, r_top, segments=10, cap_top=False, cap_bottom=False
    ):
        bx, by, bz = base_center
        tx, ty, tz = top_center
        dx, dy, dz = tx - bx, ty - by, tz - bz
        height = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-4

        ux, uy, uz = dx / height, dy / height, dz / height
        if abs(uy) < 0.9:
            rx, ry, rz = uz, 0.0, -ux
        else:
            rx, ry, rz = 1.0, 0.0, 0.0
        rlen = math.sqrt(rx * rx + ry * ry + rz * rz) or 1.0
        rx, ry, rz = rx / rlen, ry / rlen, rz / rlen
        fx = uy * rz - uz * ry
        fy = uz * rx - ux * rz
        fz = ux * ry - uy * rx

        positions = []
        normals = []
        indices = []

        slope = (r_bottom - r_top) / height
        for i in range(segments + 1):
            theta = (2.0 * math.pi * i) / segments
            ct, st = math.cos(theta), math.sin(theta)
            ox = rx * ct + fx * st
            oy = ry * ct + fy * st
            oz = rz * ct + fz * st

            nx = ox + ux * slope
            ny = oy + uy * slope
            nz = oz + uz * slope
            nlen = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx, ny, nz = nx / nlen, ny / nlen, nz / nlen

            positions.append((bx + ox * r_bottom, by + oy * r_bottom, bz + oz * r_bottom))
            normals.append((nx, ny, nz))
            positions.append((tx + ox * r_top, ty + oy * r_top, tz + oz * r_top))
            normals.append((nx, ny, nz))

        for i in range(segments):
            i0 = i * 2
            i1 = i0 + 1
            i2 = i0 + 2
            i3 = i0 + 3
            indices.extend([i0, i2, i1, i1, i2, i3])

        self._append_mesh(mat_idx, positions, normals, indices)

    def add_icosphere(self, mat_idx, center, radius_xyz, subdivisions=1, jitter=0.0, seed=42):
        cx, cy, cz = center
        rx, ry, rz = radius_xyz
        rng = random.Random(seed)

        t = (1.0 + math.sqrt(5.0)) / 2.0
        raw_verts = [
            (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
            (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
            (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1),
        ]
        verts = []
        for vx, vy, vz in raw_verts:
            l = math.sqrt(vx * vx + vy * vy + vz * vz)
            verts.append([vx / l, vy / l, vz / l])

        faces = [
            (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
            (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
            (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
            (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
        ]

        midpoint_cache = {}

        def get_midpoint(i1, i2):
            key = (min(i1, i2), max(i1, i2))
            if key in midpoint_cache:
                return midpoint_cache[key]
            v1, v2 = verts[i1], verts[i2]
            mx, my, mz = (v1[0] + v2[0]) * 0.5, (v1[1] + v2[1]) * 0.5, (v1[2] + v2[2]) * 0.5
            ml = math.sqrt(mx * mx + my * my + mz * mz) or 1.0
            verts.append([mx / ml, my / ml, mz / ml])
            idx = len(verts) - 1
            midpoint_cache[key] = idx
            return idx

        for _ in range(subdivisions):
            new_faces = []
            for f0, f1, f2 in faces:
                a = get_midpoint(f0, f1)
                b = get_midpoint(f1, f2)
                c = get_midpoint(f2, f0)
                new_faces.extend([(f0, a, c), (f1, b, a), (f2, c, b), (a, b, c)])
            faces = new_faces

        positions = []
        normals = []
        for vx, vy, vz in verts:
            scale = 1.0 + (rng.uniform(-jitter, jitter) if jitter > 0 else 0.0)
            px = cx + vx * rx * scale
            py = cy + vy * ry * scale
            pz = cz + vz * rz * scale
            positions.append((px, py, pz))
            normals.append((vx, vy, vz))

        indices = []
        for f0, f1, f2 in faces:
            indices.extend([f0, f1, f2])

        self._append_mesh(mat_idx, positions, normals, indices)

    def add_box(self, mat_idx, center, size_xyz):
        cx, cy, cz = center
        sx, sy, sz = size_xyz[0] * 0.5, size_xyz[1] * 0.5, size_xyz[2] * 0.5
        faces_data = [
            ((0, 0, 1), [(-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]),
            ((0, 0, -1), [(sx, -sy, -sz), (-sx, -sy, -sz), (-sx, sy, -sz), (sx, sy, -sz)]),
            ((1, 0, 0), [(sx, -sy, sz), (sx, -sy, -sz), (sx, sy, -sz), (sx, sy, sz)]),
            ((-1, 0, 0), [(-sx, -sy, -sz), (-sx, -sy, sz), (-sx, sy, sz), (-sx, sy, -sz)]),
            ((0, 1, 0), [(-sx, sy, sz), (sx, sy, sz), (sx, sy, -sz), (-sx, sy, -sz)]),
            ((0, -1, 0), [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz), (-sx, -sy, sz)]),
        ]
        positions = []
        normals = []
        indices = []
        for norm, corners in faces_data:
            base = len(positions)
            for ox, oy, oz in corners:
                positions.append((cx + ox, cy + oy, cz + oz))
                normals.append(norm)
            indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
        self._append_mesh(mat_idx, positions, normals, indices)

    def _append_mesh(self, mat_idx, positions, normals, indices):
        for prim in self.primitives:
            if prim[0] == mat_idx:
                v_offset = len(prim[1])
                prim[1].extend(positions)
                prim[2].extend(normals)
                prim[3].extend([idx + v_offset for idx in indices])
                return
        self.primitives.append([mat_idx, list(positions), list(normals), list(indices)])

    def save_glb(self, filepath):
        buffer_views = []
        accessors = []
        gltf_primitives = []
        bin_chunks = bytearray()

        def align4(ba):
            rem = len(ba) % 4
            if rem:
                ba.extend(b"\x00" * (4 - rem))

        for mat_idx, positions, normals, indices in self.primitives:
            if not positions or not indices:
                continue

            pos_offset = len(bin_chunks)
            min_p = [min(p[i] for p in positions) for i in range(3)]
            max_p = [max(p[i] for p in positions) for i in range(3)]
            for px, py, pz in positions:
                bin_chunks.extend(struct.pack("<fff", px, py, pz))
            pos_len = len(bin_chunks) - pos_offset
            align4(bin_chunks)

            bv_pos = len(buffer_views)
            buffer_views.append({
                "buffer": 0,
                "byteOffset": pos_offset,
                "byteLength": pos_len,
                "target": 34962,
            })
            acc_pos = len(accessors)
            accessors.append({
                "bufferView": bv_pos,
                "byteOffset": 0,
                "componentType": 5126,
                "count": len(positions),
                "type": "VEC3",
                "min": min_p,
                "max": max_p,
            })

            norm_offset = len(bin_chunks)
            for nx, ny, nz in normals:
                bin_chunks.extend(struct.pack("<fff", nx, ny, nz))
            norm_len = len(bin_chunks) - norm_offset
            align4(bin_chunks)

            bv_norm = len(buffer_views)
            buffer_views.append({
                "buffer": 0,
                "byteOffset": norm_offset,
                "byteLength": norm_len,
                "target": 34962,
            })
            acc_norm = len(accessors)
            accessors.append({
                "bufferView": bv_norm,
                "byteOffset": 0,
                "componentType": 5126,
                "count": len(normals),
                "type": "VEC3",
            })

            idx_offset = len(bin_chunks)
            for idx in indices:
                bin_chunks.extend(struct.pack("<H", idx))
            idx_len = len(bin_chunks) - idx_offset
            align4(bin_chunks)

            bv_idx = len(buffer_views)
            buffer_views.append({
                "buffer": 0,
                "byteOffset": idx_offset,
                "byteLength": idx_len,
                "target": 34963,
            })
            acc_idx = len(accessors)
            accessors.append({
                "bufferView": bv_idx,
                "byteOffset": 0,
                "componentType": 5123,
                "count": len(indices),
                "type": "SCALAR",
            })

            gltf_primitives.append({
                "attributes": {"POSITION": acc_pos, "NORMAL": acc_norm},
                "indices": acc_idx,
                "material": mat_idx,
            })

        gltf = {
            "asset": {"version": "2.0", "generator": "CalebCLI-CesiumFlightSim-GLBBuilder"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": "RootNode"}],
            "meshes": [{"name": "ProceduralMesh", "primitives": gltf_primitives}],
            "materials": self.materials,
            "buffers": [{"byteLength": len(bin_chunks)}],
            "bufferViews": buffer_views,
            "accessors": accessors,
        }

        json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
        json_pad = (4 - (len(json_bytes) % 4)) % 4
        json_bytes += b" " * json_pad

        total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_chunks)
        with open(filepath, "wb") as f:
            f.write(struct.pack("<III", 0x46546C67, 2, total_len))
            f.write(struct.pack("<II", len(json_bytes), 0x4E4F534A))
            f.write(json_bytes)
            f.write(struct.pack("<II", len(bin_chunks), 0x004E4942))
            f.write(bin_chunks)


def build_procedural_models():
    """Creates custom botanical foliage species and a custom jet fighter as .glb files."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    generated = {}

    # 1. Alpine Ponderosa Pine (pine_tall.glb)
    b = GLBBuilder()
    bark = b.add_material("PineBark", [0.32, 0.20, 0.12, 1.0], roughness=0.92)
    needle_dark = b.add_material("PineNeedleDark", [0.09, 0.28, 0.13, 1.0], roughness=0.8)
    needle_mid = b.add_material("PineNeedleMid", [0.14, 0.38, 0.17, 1.0], roughness=0.78)
    needle_tip = b.add_material("PineNeedleTip", [0.20, 0.46, 0.21, 1.0], roughness=0.75)
    b.add_cone_frustum(bark, (0, 0, 0), (0, 18.0, 0), 0.75, 0.12, segments=10)
    tiers = [
        (3.2, 8.5, 4.4, needle_dark),
        (6.0, 11.5, 3.8, needle_dark),
        (9.0, 14.5, 3.2, needle_mid),
        (12.0, 17.2, 2.5, needle_mid),
        (15.0, 20.0, 1.7, needle_tip),
        (17.5, 22.0, 0.9, needle_tip),
    ]
    for y0, y1, rad, mat in tiers:
        b.add_cone_frustum(mat, (0, y0, 0), (0, y1, 0), rad, 0.08, segments=12)
    b.save_glb(MODELS_DIR / "pine_tall.glb")
    generated["pine_tall.glb"] = {
        "category": "tree",
        "subtype": "conifer",
        "label": "Alpine Ponderosa Pine",
        "target_size": 22.0,
        "source": "procedural",
    }

    # 2. Giant Coastal Redwood (giant_redwood.glb)
    b = GLBBuilder()
    red_bark = b.add_material("RedwoodBark", [0.42, 0.18, 0.11, 1.0], roughness=0.95)
    red_foliage = b.add_material("RedwoodNeedles", [0.11, 0.33, 0.15, 1.0], roughness=0.82)
    b.add_cone_frustum(red_bark, (0, 0, 0), (0, 46.0, 0), 2.2, 0.35, segments=12)
    for i in range(9):
        y_base = 16.0 + i * 3.5
        rad = 6.2 - i * 0.52
        b.add_cone_frustum(red_foliage, (0, y_base, 0), (0, y_base + 5.5, 0), rad, 0.3, segments=12)
    b.save_glb(MODELS_DIR / "giant_redwood.glb")
    generated["giant_redwood.glb"] = {
        "category": "tree",
        "subtype": "conifer",
        "label": "Giant Coastal Sequoia",
        "target_size": 48.0,
        "source": "procedural",
    }

    # 3. Broadleaf Valley Oak (oak_broadleaf.glb)
    b = GLBBuilder()
    oak_bark = b.add_material("OakBark", [0.28, 0.21, 0.15, 1.0], roughness=0.92)
    oak_leaf1 = b.add_material("OakLeaf1", [0.18, 0.44, 0.14, 1.0], roughness=0.82)
    oak_leaf2 = b.add_material("OakLeaf2", [0.25, 0.52, 0.18, 1.0], roughness=0.78)
    b.add_cone_frustum(oak_bark, (0, 0, 0), (0, 6.5, 0), 0.95, 0.55, segments=10)
    branches = [
        ((0, 5.2, 0), (3.2, 9.5, 1.5), 0.38, 0.16),
        ((0, 5.5, 0), (-3.0, 9.2, 1.8), 0.36, 0.15),
        ((0, 5.0, 0), (0.8, 9.8, -3.2), 0.35, 0.15),
        ((0, 5.8, 0), (-1.5, 10.5, -2.0), 0.32, 0.14),
    ]
    for p0, p1, r0, r1 in branches:
        b.add_cone_frustum(oak_bark, p0, p1, r0, r1, segments=8)
    lobes = [
        ((0, 11.8, 0), (4.8, 3.8, 4.8), oak_leaf2, 10),
        ((3.4, 10.0, 1.6), (3.4, 2.8, 3.4), oak_leaf1, 20),
        ((-3.2, 9.8, 1.9), (3.5, 2.9, 3.2), oak_leaf1, 30),
        ((1.0, 10.2, -3.2), (3.4, 2.8, 3.4), oak_leaf2, 40),
        ((-2.0, 10.8, -2.2), (3.2, 2.7, 3.2), oak_leaf1, 50),
    ]
    for center, rads, mat, seed in lobes:
        b.add_icosphere(mat, center, rads, subdivisions=2, jitter=0.14, seed=seed)
    b.save_glb(MODELS_DIR / "oak_broadleaf.glb")
    generated["oak_broadleaf.glb"] = {
        "category": "tree",
        "subtype": "deciduous",
        "label": "Broadleaf Valley Oak",
        "target_size": 16.0,
        "source": "procedural",
    }

    # 4. Silver Paper Birch Grove Cluster (birch_cluster.glb)
    b = GLBBuilder()
    birch_bark = b.add_material("BirchBark", [0.88, 0.86, 0.82, 1.0], roughness=0.75)
    birch_leaf = b.add_material("BirchLeaf", [0.42, 0.66, 0.20, 1.0], roughness=0.76)
    stems = [
        ((0, 0, 0), (0.8, 13.5, 0.4), 0.28),
        ((-0.7, 0, 0.5), (-1.8, 11.8, 1.2), 0.24),
        ((0.6, 0, -0.6), (1.9, 12.2, -1.4), 0.25),
    ]
    for idx_s, (p0, p1, r0) in enumerate(stems):
        b.add_cone_frustum(birch_bark, p0, p1, r0, 0.06, segments=8)
        b.add_icosphere(
            birch_leaf,
            (p1[0], p1[1] - 1.5, p1[2]),
            (2.4, 3.5, 2.4),
            subdivisions=2,
            jitter=0.15,
            seed=100 + idx_s,
        )
    b.save_glb(MODELS_DIR / "birch_cluster.glb")
    generated["birch_cluster.glb"] = {
        "category": "tree",
        "subtype": "deciduous",
        "label": "Silver Paper Birch Cluster",
        "target_size": 15.0,
        "source": "procedural",
    }

    # 5. Autumn Sugar Maple (autumn_maple.glb)
    b = GLBBuilder()
    maple_bark = b.add_material("MapleBark", [0.26, 0.19, 0.15, 1.0], roughness=0.9)
    maple_red = b.add_material("MapleCrimson", [0.78, 0.21, 0.12, 1.0], roughness=0.78)
    maple_gold = b.add_material("MapleAmber", [0.90, 0.48, 0.12, 1.0], roughness=0.76)
    b.add_cone_frustum(maple_bark, (0, 0, 0), (0, 8.0, 0), 0.72, 0.28, segments=10)
    b.add_icosphere(maple_red, (0, 10.5, 0), (4.2, 4.6, 4.2), subdivisions=2, jitter=0.16, seed=77)
    b.add_icosphere(maple_gold, (2.2, 9.2, 1.5), (2.8, 3.0, 2.8), subdivisions=2, jitter=0.14, seed=78)
    b.add_icosphere(maple_gold, (-2.1, 9.5, -1.6), (2.9, 3.1, 2.9), subdivisions=2, jitter=0.14, seed=79)
    b.save_glb(MODELS_DIR / "autumn_maple.glb")
    generated["autumn_maple.glb"] = {
        "category": "tree",
        "subtype": "autumn",
        "label": "Crimson Autumn Sugar Maple",
        "target_size": 16.0,
        "source": "procedural",
    }

    # 6. Riparian Weeping Willow (weeping_willow.glb)
    b = GLBBuilder()
    willow_bark = b.add_material("WillowBark", [0.30, 0.25, 0.18, 1.0], roughness=0.9)
    willow_leaf = b.add_material("WillowFrond", [0.32, 0.58, 0.24, 1.0], roughness=0.8)
    b.add_cone_frustum(willow_bark, (0, 0, 0), (0, 7.5, 0), 0.9, 0.4, segments=10)
    b.add_icosphere(willow_leaf, (0, 9.5, 0), (4.8, 2.8, 4.8), subdivisions=2, jitter=0.12, seed=88)
    for i in range(10):
        ang = (2.0 * math.pi * i) / 10.0
        rx, rz = math.cos(ang) * 3.4, math.sin(ang) * 3.4
        b.add_icosphere(willow_leaf, (rx, 5.8, rz), (1.1, 4.2, 1.1), subdivisions=1, jitter=0.1, seed=90 + i)
    b.save_glb(MODELS_DIR / "weeping_willow.glb")
    generated["weeping_willow.glb"] = {
        "category": "tree",
        "subtype": "riparian",
        "label": "Weeping River Willow",
        "target_size": 14.5,
        "source": "procedural",
    }

    # 7. Tropical Coconut Palm (palm_tropical.glb)
    b = GLBBuilder()
    palm_trunk = b.add_material("PalmTrunk", [0.44, 0.34, 0.24, 1.0], roughness=0.88)
    palm_frond = b.add_material("PalmFrond", [0.18, 0.52, 0.16, 1.0], roughness=0.72)
    pts = [(0, 0, 0), (0.4, 3.5, 0.1), (1.0, 7.0, 0.3), (1.4, 10.5, 0.4), (1.6, 13.5, 0.4)]
    for i in range(len(pts) - 1):
        b.add_cone_frustum(palm_trunk, pts[i], pts[i + 1], 0.48 - i * 0.06, 0.42 - i * 0.06, segments=8)
    top = pts[-1]
    for i in range(9):
        ang = (2.0 * math.pi * i) / 9.0
        dx, dz = math.cos(ang), math.sin(ang)
        mid = (top[0] + dx * 2.4, top[1] + 0.6, top[2] + dz * 2.4)
        tip = (top[0] + dx * 4.5, top[1] - 1.2, top[2] + dz * 4.5)
        b.add_cone_frustum(palm_frond, top, mid, 0.45, 0.65, segments=6)
        b.add_cone_frustum(palm_frond, mid, tip, 0.65, 0.05, segments=6)
    b.save_glb(MODELS_DIR / "palm_tropical.glb")
    generated["palm_tropical.glb"] = {
        "category": "tree",
        "subtype": "tropical",
        "label": "Coastal Coconut Palm",
        "target_size": 15.0,
        "source": "procedural",
    }

    # 8. Forest Floor Fern & Wildflower Cluster (fern_cluster.glb)
    b = GLBBuilder()
    fern_green = b.add_material("FernGreen", [0.16, 0.48, 0.18, 1.0], roughness=0.75)
    flower_pink = b.add_material("WildflowerPink", [0.88, 0.32, 0.58, 1.0], roughness=0.65)
    flower_yellow = b.add_material("WildflowerGold", [0.95, 0.80, 0.18, 1.0], roughness=0.65)
    for i in range(12):
        ang = (2.0 * math.pi * i) / 12.0
        dx, dz = math.cos(ang), math.sin(ang)
        b.add_cone_frustum(
            fern_green,
            (0, 0.1, 0),
            (dx * 1.6, 0.85 + (i % 3) * 0.2, dz * 1.6),
            0.28,
            0.03,
            segments=6,
        )
    for i in range(6):
        ang = (2.0 * math.pi * i) / 6.0 + 0.3
        mat = flower_pink if i % 2 == 0 else flower_yellow
        b.add_icosphere(
            mat,
            (math.cos(ang) * 0.8, 0.95, math.sin(ang) * 0.8),
            (0.24, 0.24, 0.24),
            subdivisions=1,
            seed=200 + i,
        )
    b.save_glb(MODELS_DIR / "fern_cluster.glb")
    generated["fern_cluster.glb"] = {
        "category": "bush",
        "subtype": "fern",
        "label": "Forest Fern & Wildflower Cluster",
        "target_size": 2.4,
        "source": "procedural",
    }

    # 9. Supersonic Twin-Tail Delta Jet (supersonic_jet.glb)
    b = GLBBuilder()
    fuselage_mat = b.add_material("AirframeTitanium", [0.82, 0.85, 0.89, 1.0], metallic=0.65, roughness=0.32)
    wing_accent = b.add_material("NavyAccent", [0.12, 0.24, 0.48, 1.0], metallic=0.45, roughness=0.4)
    canopy_glass = b.add_material("CanopyGoldGlass", [0.18, 0.55, 0.78, 0.95], metallic=0.85, roughness=0.12)
    afterburner = b.add_material(
        "AfterburnerGlow", [1.0, 0.45, 0.1, 1.0], metallic=0.1, roughness=0.3, emissive=[0.95, 0.35, 0.05]
    )
    b.add_cone_frustum(fuselage_mat, (-7.5, 0, 0), (3.5, 0, 0), 1.15, 0.95, segments=12)
    b.add_cone_frustum(fuselage_mat, (3.5, 0, 0), (9.5, -0.1, 0), 0.95, 0.05, segments=12)
    b.add_icosphere(canopy_glass, (2.6, 0.72, 0), (2.6, 0.62, 0.68), subdivisions=2)
    b.add_box(fuselage_mat, (-1.2, -0.05, 0), (4.8, 0.16, 12.8))
    b.add_box(wing_accent, (-2.0, 0.0, 0), (2.2, 0.18, 13.4))
    b.add_box(wing_accent, (-6.4, 0.0, 0), (2.2, 0.14, 5.6))
    b.add_cone_frustum(wing_accent, (-6.2, 0.2, 1.2), (-7.4, 2.5, 1.6), 0.85, 0.35, segments=6)
    b.add_cone_frustum(wing_accent, (-6.2, 0.2, -1.2), (-7.4, 2.5, -1.6), 0.85, 0.35, segments=6)
    b.add_cone_frustum(afterburner, (-8.2, 0, 0.48), (-7.4, 0, 0.48), 0.38, 0.48, segments=10)
    b.add_cone_frustum(afterburner, (-8.2, 0, -0.48), (-7.4, 0, -0.48), 0.38, 0.48, segments=10)
    b.save_glb(MODELS_DIR / "supersonic_jet.glb")
    generated["supersonic_jet.glb"] = {
        "category": "aircraft",
        "label": "F-22X Supersonic Interceptor",
        "target_size": 18.0,
        "heading_offset_deg": 0.0,
        "source": "procedural",
    }

    return generated


def _node_local_scale(node):
    if "scale" in node and len(node["scale"]) == 3:
        return [abs(float(x)) for x in node["scale"]]
    if "matrix" in node and len(node["matrix"]) == 16:
        m = node["matrix"]
        sx = math.sqrt(m[0] * m[0] + m[1] * m[1] + m[2] * m[2])
        sy = math.sqrt(m[4] * m[4] + m[5] * m[5] + m[6] * m[6])
        sz = math.sqrt(m[8] * m[8] + m[9] * m[9] + m[10] * m[10])
        return [sx, sy, sz]
    return [1.0, 1.0, 1.0]


def inspect_glb_bounds(filepath):
    """Computes effective world-space bounding box span (accounting for glTF node hierarchy scales)."""
    try:
        data = Path(filepath).read_bytes()
        if len(data) < 20:
            return 1.0
        magic, version, length = struct.unpack("<III", data[:12])
        if magic != 0x46546C67:
            return 1.0
        chunk_len, chunk_type = struct.unpack("<II", data[12:20])
        j = json.loads(data[20 : 20 + chunk_len].decode("utf-8"))

        nodes = j.get("nodes", [])
        meshes = j.get("meshes", [])
        accessors = j.get("accessors", [])

        # Traverse scene graph to accumulate scale per mesh
        mesh_scales = {}

        def dfs(node_idx, acc_scale):
            if node_idx < 0 or node_idx >= len(nodes):
                return
            nd = nodes[node_idx]
            ls = _node_local_scale(nd)
            cur = [acc_scale[0] * ls[0], acc_scale[1] * ls[1], acc_scale[2] * ls[2]]
            if "mesh" in nd:
                m_idx = nd["mesh"]
                mesh_scales[m_idx] = cur
            for ch in nd.get("children", []):
                dfs(ch, cur)

        scenes = j.get("scenes", [])
        root_nodes = scenes[0].get("nodes", list(range(len(nodes)))) if scenes else list(range(len(nodes)))
        for rn in root_nodes:
            dfs(rn, [1.0, 1.0, 1.0])

        spans = []
        for m_idx, mesh in enumerate(meshes):
            sc = mesh_scales.get(m_idx, [1.0, 1.0, 1.0])
            for prim in mesh.get("primitives", []):
                pos_acc_idx = prim.get("attributes", {}).get("POSITION")
                if pos_acc_idx is not None and pos_acc_idx < len(accessors):
                    acc = accessors[pos_acc_idx]
                    if "min" in acc and "max" in acc and len(acc["min"]) == 3:
                        mn, mx = acc["min"], acc["max"]
                        span = max((mx[i] - mn[i]) * sc[i] for i in range(3))
                        if span > 0:
                            spans.append(span)

        if not spans:
            for acc in accessors:
                if acc.get("type") == "VEC3" and "min" in acc and "max" in acc:
                    mn, mx = acc["min"], acc["max"]
                    span = max(mx[i] - mn[i] for i in range(3))
                    if span > 0:
                        spans.append(span)

        return max(spans) if spans else 1.0
    except Exception:
        return 1.0


def ensure_all_models():
    """Downloads web .glb models, builds procedural .glb models, and writes catalog.json."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    catalog = {"aircraft": [], "foliage": [], "structures": [], "wildlife": []}

    proc_meta = build_procedural_models()
    all_meta = {}
    all_meta.update(proc_meta)

    for filename, info in WEB_ASSETS.items():
        dest = MODELS_DIR / filename
        if not dest.exists() or dest.stat().st_size < 100:
            try:
                req = urllib.request.Request(info["url"], headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content = resp.read()
                dest.write_bytes(content)
                print(f"[Downloaded Web Model] {filename} ({len(content):,} bytes)")
            except Exception as exc:
                print(f"[Warning] Failed to download {filename}: {exc}")
                continue
        entry = dict(info)
        entry["source"] = "web"
        all_meta[filename] = entry

    for filename, info in all_meta.items():
        fpath = MODELS_DIR / filename
        if not fpath.exists():
            continue
        native_span = inspect_glb_bounds(fpath)
        target_size = float(info.get("target_size", 15.0))
        recommended_scale = round(target_size / max(native_span, 0.001), 5)

        record = {
            "id": filename.replace(".glb", ""),
            "filename": filename,
            "url": f"/static/models/{filename}",
            "origin_url": info.get("url", "procedural://local-glb"),
            "source": info.get("source", "web"),
            "category": info["category"],
            "subtype": info.get("subtype", info["category"]),
            "label": info["label"],
            "target_size_m": target_size,
            "native_span": round(native_span, 4),
            "base_scale": recommended_scale,
            "heading_offset_deg": info.get("heading_offset_deg", 0.0),
        }

        if info["category"] == "aircraft":
            catalog["aircraft"].append(record)
        elif info["category"] in ("tree", "bush", "rock"):
            catalog["foliage"].append(record)
        elif info["category"] == "structure":
            catalog["structures"].append(record)
        elif info["category"] == "wildlife":
            catalog["wildlife"].append(record)

    CATALOG_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    return catalog


def generate_foliage_ecosystem(center_lat, center_lon, radius_m=2800.0, count=420, biome="mixed", seed=None):
    """Generates a natural multi-species 3D forest ecosystem around (center_lat, center_lon)."""
    if not CATALOG_PATH.exists():
        catalog = ensure_all_models()
    else:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    rng = random.Random(seed if seed is not None else int((center_lat * 1000 + center_lon * 1000) * 100))
    foliage_list = catalog.get("foliage", [])
    if not foliage_list:
        return {"instances": [], "summary": {}}

    trees_conifer = [m for m in foliage_list if m["category"] == "tree" and m["subtype"] == "conifer"]
    trees_decid = [m for m in foliage_list if m["category"] == "tree" and m["subtype"] in ("deciduous", "autumn")]
    trees_special = [m for m in foliage_list if m["category"] == "tree" and m["subtype"] in ("riparian", "tropical", "ancient")]
    bushes = [m for m in foliage_list if m["category"] == "bush"]
    rocks = [m for m in foliage_list if m["category"] == "rock"]

    all_trees = trees_conifer + trees_decid + trees_special
    if not all_trees:
        all_trees = foliage_list

    num_groves = max(6, count // 35)
    groves = []
    for _ in range(num_groves):
        dist = rng.uniform(140.0, radius_m * 0.92)
        ang = rng.uniform(0, 2 * math.pi)
        groves.append((dist * math.cos(ang), dist * math.sin(ang), rng.uniform(90.0, 260.0)))

    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * max(0.2, math.cos(math.radians(center_lat)))

    instances = []
    species_counts = {}

    for i in range(count):
        if rng.random() < 0.78 and groves:
            gx, gy, g_spread = rng.choice(groves)
            ox = gx + rng.gauss(0, g_spread * 0.45)
            oy = gy + rng.gauss(0, g_spread * 0.45)
        else:
            r = radius_m * math.sqrt(rng.random())
            theta = rng.uniform(0, 2 * math.pi)
            ox, oy = r * math.cos(theta), r * math.sin(theta)

        # Keep runway clearing near spawn point
        if abs(ox) < 55.0 and abs(oy) < 240.0:
            ox += 110.0 if ox >= 0 else -110.0

        roll = rng.random()
        if roll < 0.64:
            if biome == "alpine" and trees_conifer:
                pool = trees_conifer
            elif biome == "autumn" and trees_decid:
                pool = trees_decid
            elif biome == "tropical" and trees_special:
                pool = trees_special + trees_decid
            else:
                pool = all_trees
        elif roll < 0.90 and bushes:
            pool = bushes
        elif rocks:
            pool = rocks
        else:
            pool = all_trees

        model = rng.choice(pool)
        scale_jitter = rng.uniform(0.78, 1.35)
        lat = center_lat + (oy / meters_per_deg_lat)
        lon = center_lon + (ox / meters_per_deg_lon)

        species_counts[model["label"]] = species_counts.get(model["label"], 0) + 1
        instances.append({
            "id": f"fol_{i}",
            "model_id": model["id"],
            "url": model["url"],
            "label": model["label"],
            "category": model["category"],
            "source": model["source"],
            "lat": round(lat, 7),
            "lon": round(lon, 7),
            "scale": round(model["base_scale"] * scale_jitter, 5),
            "height_m": round(model["target_size_m"] * scale_jitter, 1),
            "heading_deg": round(rng.uniform(0, 360), 1),
        })

    for idx_t, st in enumerate(catalog.get("structures", [])):
        for t_i in range(2):
            ang = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(450.0, radius_m * 0.7)
            lat = center_lat + (dist * math.sin(ang)) / meters_per_deg_lat
            lon = center_lon + (dist * math.cos(ang)) / meters_per_deg_lon
            instances.append({
                "id": f"tower_{idx_t}_{t_i}",
                "model_id": st["id"],
                "url": st["url"],
                "label": st["label"],
                "category": "structure",
                "source": st["source"],
                "lat": round(lat, 7),
                "lon": round(lon, 7),
                "scale": st["base_scale"],
                "height_m": st["target_size_m"],
                "heading_deg": round(rng.uniform(0, 360), 1),
            })

    return {
        "center": {"lat": center_lat, "lon": center_lon},
        "radius_m": radius_m,
        "biome": biome,
        "total_instances": len(instances),
        "species_breakdown": species_counts,
        "instances": instances,
    }


if __name__ == "__main__":
    cat = ensure_all_models()
    for group, items in cat.items():
        print(f"=== {group.upper()} ===")
        for it in items:
            print(f"  {it['filename']:22s} | span={it['native_span']:8.3f}m | scale={it['base_scale']:8.4f} | target={it['target_size_m']}m")
