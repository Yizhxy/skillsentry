"""
Tests for Three.js mesh export task - variant 5.
"""
import os
import json
import numpy as np
from pathlib import Path


OUTPUT_DIR = Path("/root/output")
GT_DIR = Path("/root/ground_truth")
CD_THRESHOLD = 2e-4
MAX_SAMPLE_POINTS = 300


def parse_obj_vertices(filepath):
    vertices = []
    with open(filepath) as f:
        for line in f:
            if line.startswith("v "):
                parts = line.strip().split()
                if len(parts) >= 4:
                    vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return np.array(vertices, dtype=np.float32) if vertices else np.array([])


class TestThreeJSParser:
    def test_output_dir_exists(self):
        assert OUTPUT_DIR.exists(), f"Output directory {OUTPUT_DIR} not found"

    def test_centers_exist(self):
        centers_path = Path("/root/output/centers.json")
        assert centers_path.exists(), "centers.json not found"
        with open(centers_path) as f:
            data = json.load(f)
        assert len(data) > 0
        for part, meshes in data.items():
            for mesh, info in meshes.items():
                assert "center" in info and len(info["center"]) == 3

    def test_obj_files_parseable(self):
        obj_files = list(OUTPUT_DIR.rglob("*.obj"))
        assert len(obj_files) > 0, "No OBJ files found in output"
        for obj_file in obj_files[:5]:
            vertices = parse_obj_vertices(obj_file)
            if len(vertices) > 0:
                assert vertices.shape[1] == 3, f"Vertices in {obj_file.name} should have 3 coordinates"
