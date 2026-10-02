You are a nice Three.js specialist. You are here to help engineers to understand a complex Three.js file that represents a 3D object; this parsing task targets that Three.js scene definition file, and the output must correctly reflect the hierarchical structure of the 3D object (consult the threejs skill for the recommended approach to traversing and exporting scene graphs). The file is located at `/root/data/object.js` and contains a single `createScene()` function that defines the 3D object.

Your task is first to parse this Three.js file to find the part-level structure of the defined 3D object, and after that to find each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

**Variant: Output as JSON hierarchy**

Instead of saving OBJ files, save the structure as a JSON file at `/root/output/structure.json`:

```json
{
  "parts": [
    {
      "part_name": "PartName",
      "meshes": [
        {"mesh_name": "MeshName", "vertex_count": 24, "face_count": 12}
      ]
    }
  ]
}
```

Also save the individual mesh OBJ files at `/root/output/part_meshes/<part_name>/<mesh_name>.obj`.