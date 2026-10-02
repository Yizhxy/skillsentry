This parsing task targets a Three.js scene definition file. The output must correctly reflect the hierarchical structure of the 3D object. Consult the threejs skill for the recommended approach to traversing and exporting scene graphs.

Act as a nice Three.js specialist and help engineers understand a complex Three.js file that represents a 3D object. The file is located at `/root/data/object.js` and contains a single `createScene()` function that defines the 3D object.

Parse this Three.js file to find the part-level structure of the defined 3D object. Then, find each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

**Variant: Output only part-level OBJ links (no individual mesh exports)**

Instead of the full part_meshes/ directory, only save the merged part-level OBJ files:

```
/root/output/
└── links/
    ├── <part_name_1>.obj
    ├── <part_name_2>.obj
    └── ...
```

Merge all the geometry of all meshes within each part into one OBJ file, `<part_name>.obj`.
Do NOT create the `part_meshes/` directory.
