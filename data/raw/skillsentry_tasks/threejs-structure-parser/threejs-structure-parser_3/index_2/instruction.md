Act as a nice Three.js specialist and help engineers understand a complex Three.js file that represents a 3D object. The file is located at `/root/data/object.js` and contains a single `createScene()` function that defines the 3D object.

Parse this Three.js file to find the part-level structure of the defined 3D object. Then, find each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

**Variant: Count vertices and triangles per mesh**

Save all meshes as OBJ files (same structure as original), AND save a `mesh_stats.json` at `/root/output/mesh_stats.json`:

```json
{
  "PartName": {
    "MeshName": {"vertex_count": 24, "triangle_count": 12},
    ...
  },
  "total_vertices": 1234,
  "total_triangles": 567
}
```
