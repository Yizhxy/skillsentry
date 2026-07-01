"""Test for 3d-scan-calc - component count."""
import json, os
class TestOutputs:
    def test_file_exists(self):
        assert os.path.exists("/root/mass_report.json")
    def test_structure(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        assert "component_count" in data and "main_part_mass" in data and "material_id" in data
    def test_component_count_positive(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        assert int(data["component_count"]) >= 1

    def _get_ground_truth_mass(self):
        import struct, collections
        filepath = "/root/scan_data.stl"
        triangles = []
        with open(filepath, "rb") as f:
            f.read(80); count = struct.unpack("<I", f.read(4))[0]
            for _ in range(count):
                d = f.read(50); floats = struct.unpack("<3f3f3f3f", d[:48]); attr = struct.unpack("<H", d[48:50])[0]
                v1=(floats[3],floats[4],floats[5]); v2=(floats[6],floats[7],floats[8]); v3=(floats[9],floats[10],floats[11])
                triangles.append((v1,v2,v3,attr))
        def quantize(v): return (round(v[0],4),round(v[1],4),round(v[2],4))
        vm = collections.defaultdict(list)
        for i,t in enumerate(triangles):
            for v in t[:3]: vm[quantize(v)].append(i)
        visited, comp_data = set(), []
        for i in range(len(triangles)):
            if i in visited: continue
            comp, q = [], collections.deque([i]); visited.add(i)
            while q:
                ci = q.popleft(); comp.append(ci)
                for v in triangles[ci][:3]:
                    for ni in vm[quantize(v)]:
                        if ni not in visited: visited.add(ni); q.append(ni)
            tris = [triangles[idx] for idx in comp]
            vol = 0
            for t in tris:
                v1,v2,v3=t[0],t[1],t[2]
                cp_x=v2[1]*v3[2]-v2[2]*v3[1]; cp_y=v2[2]*v3[0]-v2[0]*v3[2]; cp_z=v2[0]*v3[1]-v2[1]*v3[0]
                vol += v1[0]*cp_x+v1[1]*cp_y+v1[2]*cp_z
            comp_data.append((abs(vol)/6.0, tris[0][3], tris))
        DENSITY = {1:0.10, 10:7.85, 25:2.70, 42:5.55, 99:11.34}
        best = max(comp_data, key=lambda x: x[0]*DENSITY.get(x[1],1.0))
        return best[0]*DENSITY.get(best[1],1.0), best[1], best[0]

    def test_main_part_mass_accuracy(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        mass = float(data["main_part_mass"])
        expected_mass, _, _ = self._get_ground_truth_mass()
        assert abs(mass - expected_mass) / max(expected_mass, 1) < 0.001
