This parsing task targets a Three.js scene definition file. The result must accurately capture the hierarchical structure of the 3D object. Refer to the threejs skill for the suggested way of walking through and exporting scene graphs.

You are a nice Three.js specialist. You are here to assist engineers in comprehending a complex Three.js file that represents a 3D object. The file resides at `/root/data/object.js` and holds a single `createScene()` function that specifies the 3D object.

Your task is to read this Three.js file to identify the part-level structure of the defined 3D object. Then, you need to identify each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

**Variant: Compute center of mass for each mesh**

Store all meshes as OBJ files (same structure as original), AND store a `centers.json` at `/root/output/centers.json`:

```json
{
  "PartName": {
    "MeshName": {"center": [cx, cy, cz]}
  }
}
```

Calculate the geometric center (mean of all vertices) for each mesh.