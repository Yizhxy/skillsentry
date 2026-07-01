"""Test for 3d-scan-calc - stricter 5% debris threshold."""
import json, os, struct, collections
class TestOutputs:
    def test_file_exists(self):
        assert os.path.exists("/root/mass_report.json")
    def test_structure(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        assert "main_part_mass" in data and "material_id" in data
    def test_mass_positive(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        assert float(data["main_part_mass"]) > 0
    def _get_ground_truth(self):
        filepath = "/root/scan_data.stl"; triangles = []
        with open(filepath, "rb") as f:
            f.read(80); count = struct.unpack("<I", f.read(4))[0]
            for _ in range(count):
                d = f.read(50); floats = struct.unpack("<3f3f3f3f", d[:48]); attr = struct.unpack("<H", d[48:50])[0]
                triangles.append(((floats[3],floats[4],floats[5]),(floats[6],floats[7],floats[8]),(floats[9],floats[10],floats[11]),attr))
        def q(v): return (round(v[0],4),round(v[1],4),round(v[2],4))
        vm = collections.defaultdict(list)
        for i,t in enumerate(triangles):
            for v in t[:3]: vm[q(v)].append(i)
        visited, comp_data = set(), []
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
                v1,v2,v3=t[0],t[1],t[2]; cp_x=v2[1]*v3[2]-v2[2]*v3[1]; cp_y=v2[2]*v3[0]-v2[0]*v3[2]; cp_z=v2[0]*v3[1]-v2[1]*v3[0]
                vol+=v1[0]*cp_x+v1[1]*cp_y+v1[2]*cp_z
            comp_data.append((abs(vol)/6.0, tris[0][3]))
        max_vol = max(v for v,_ in comp_data)
        kept = [(v,m) for v,m in comp_data if v >= max_vol*0.05]
        main_vol, main_mid = max(kept, key=lambda x: x[0])
        DENSITY = {1:0.10,10:7.85,25:2.70,42:5.55,99:11.34}
        return main_vol*DENSITY.get(main_mid,1.0), main_mid
    def test_mass_accuracy(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        mass = float(data["main_part_mass"])
        expected_mass, expected_mid = self._get_ground_truth()
        assert abs(mass - expected_mass) / max(expected_mass, 1) < 0.001
        assert int(data.get("material_id", 0)) == expected_mid
