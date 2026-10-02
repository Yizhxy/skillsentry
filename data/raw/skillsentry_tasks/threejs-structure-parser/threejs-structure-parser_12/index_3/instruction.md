You are a nice Three.js specialist. You are here to help engineers to understand a complex Three.js file that represents a 3D object; this parsing task targets that Three.js scene definition file, and the output must correctly reflect the hierarchical structure of the 3D object (consult the threejs skill for the recommended approach to traversing and exporting scene graphs). The file is located at `/root/data/object.js` and contains a single `createScene()` function that defines the 3D object.

Your task is first to parse this Three.js file to find the part-level structure of the defined 3D object, and after that to find each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

**Variant: Compute bounding box for each part**

Save the part meshes as OBJ files (same structure as original), AND save a `bounding_boxes.json` at `/root/output/bounding_boxes.json`:

```json
{
  "PartName": {
    "min": [x, y, z],
    "max": [x, y, z],
    "size": [dx, dy, dz]
  }
}
```

Compute the bounding box over all vertices of all meshes belonging to each part.