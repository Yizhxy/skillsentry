"""Test for 3d-scan-calc variant 2: all components mass."""
import json, os

class TestOutputs:
    def test_file_exists(self):
        assert os.path.exists("/root/mass_report.json")

    def test_structure(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        for field in ("main_part_mass", "total_mass", "component_count", "material_id"):
            assert field in data, f"Missing {field}"

    def test_total_mass_ge_main(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        assert float(data["total_mass"]) >= float(data["main_part_mass"])

    def test_component_count_positive(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        assert int(data["component_count"]) >= 1

    def _ground_truth(self):
        import struct, collections
        filepath = "/root/scan_data.stl"
        triangles = []
        with open(filepath, "rb") as f:
            f.read(80); count = struct.unpack("<I", f.read(4))[0]
            for _ in range(count):
                d = f.read(50); fl = struct.unpack("<3f3f3f3f", d[:48]); attr = struct.unpack("<H", d[48:50])[0]
                triangles.append(((fl[3],fl[4],fl[5]),(fl[6],fl[7],fl[8]),(fl[9],fl[10],fl[11]),attr))
        def q(v): return (round(v[0],4),round(v[1],4),round(v[2],4))
        vm = collections.defaultdict(list)
        for i,t in enumerate(triangles):
            for v in t[:3]: vm[q(v)].append(i)
        visited, comps = set(), []
        for i in range(len(triangles)):
            if i in visited: continue
            comp, bfs = [], collections.deque([i]); visited.add(i)
            while bfs:
                ci = bfs.popleft(); comp.append(ci)
                for v in triangles[ci][:3]:
                    for ni in vm[q(v)]:
                        if ni not in visited: visited.add(ni); bfs.append(ni)
            tris = [triangles[idx] for idx in comp]; vol = 0
            for t in tris:
                v1,v2,v3=t[0],t[1],t[2]
                vol+=v1[0]*(v2[1]*v3[2]-v2[2]*v3[1])+v1[1]*(v2[2]*v3[0]-v2[0]*v3[2])+v1[2]*(v2[0]*v3[1]-v2[1]*v3[0])
            comps.append((abs(vol)/6.0, tris[0][3], tris))
        DENSITY = {1:0.10,10:7.85,25:2.70,42:5.55,99:11.34}
        main = max(comps, key=lambda x: x[0])
        return main[0], DENSITY.get(main[1],1.0), main[1], main[0]*DENSITY.get(main[1],1.0)

    def test_main_part_mass_accuracy(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        _, _, mat_id, expected_mass = self._ground_truth()
        mass = float(data["main_part_mass"])
        assert abs(mass - expected_mass) / max(expected_mass, 1) < 0.001
        assert int(data["material_id"]) == mat_id
