This parsing task targets a Three.js scene definition file. The output must correctly reflect the hierarchical structure of the 3D object. Consult the threejs skill for the recommended approach to traversing and exporting scene graphs.

Act as a nice Three.js specialist and help engineers understand a complex Three.js file that represents a 3D object. The file is located at `/root/data/object.js` and contains a single `createScene()` function that defines the 3D object.

Parse this Three.js file to find the part-level structure of the defined 3D object. Then, find each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

**Variant: Compute center of mass for each mesh**

Save all meshes as OBJ files (same structure as original), AND save a `centers.json` at `/root/output/centers.json`:

```json
{
  "PartName": {
    "MeshName": {"center": [cx, cy, cz]}
  }
}
```

Compute the geometric center (average of all vertices) for each mesh.