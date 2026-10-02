This parsing task targets a Three.js scene definition file. The result must accurately capture the hierarchical structure of the 3D object. Refer to the threejs skill for the suggested way of walking through and exporting scene graphs.

You are a nice Three.js specialist. You are here to assist engineers in comprehending a complex Three.js file that represents a 3D object. The file resides at `/root/data/object.js` and holds a single `createScene()` function that specifies the 3D object.

Your task is to read this Three.js file to identify the part-level structure of the defined 3D object. Then, you need to identify each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

**Variant: Compute bounding box for each part**

Store the part meshes as OBJ files (same structure as original), AND store a `bounding_boxes.json` at `/root/output/bounding_boxes.json`:

```json
{
  "PartName": {
    "min": [x, y, z],
    "max": [x, y, z],
    "size": [dx, dy, dz]
  }
}
```

Calculate the bounding box across all vertices of all meshes belonging to each part.