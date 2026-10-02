"""Test for 3d-scan-calc - top 3 components."""
import json, os
class TestOutputs:
    def test_file_exists(self):
        assert os.path.exists("/root/mass_report.json")
    def test_structure(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        assert "top3_components" in data
        comps = data["top3_components"]
        assert isinstance(comps, list) and 1 <= len(comps) <= 3
    def test_components_have_required_fields(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        for c in data["top3_components"]:
            for f in ("rank", "volume", "mass", "material_id"): assert f in c
    def test_ranked_by_volume(self):
        with open("/root/mass_report.json") as f: data = json.load(f)
        comps = data["top3_components"]
        if len(comps) >= 2:
            assert float(comps[0]["volume"]) >= float(comps[1]["volume"])
