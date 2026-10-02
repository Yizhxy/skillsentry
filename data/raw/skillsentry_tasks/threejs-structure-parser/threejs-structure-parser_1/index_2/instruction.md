Act as a nice Three.js specialist and help engineers understand a complex Three.js file that represents a 3D object. The file is located at `/root/data/object.js` and contains a single `createScene()` function that defines the 3D object.

Parse this Three.js file to find the part-level structure of the defined 3D object. Then, find each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

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
