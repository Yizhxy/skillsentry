This parsing task targets a Three.js scene definition file. The result must accurately capture the hierarchical structure of the 3D object. Refer to the threejs skill for the suggested way of walking through and exporting scene graphs.

You are a nice Three.js specialist. You are here to assist engineers in comprehending a complex Three.js file that represents a 3D object. The file resides at `/root/data/object.js` and holds a single `createScene()` function that specifies the 3D object.

Your task is to read this Three.js file to identify the part-level structure of the defined 3D object. Then, you need to identify each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

**Variant: Output only part-level OBJ links (no individual mesh exports)**

Rather than the full part_meshes/ directory, only store the combined part-level OBJ files:

```
/root/output/
└── links/
    ├── <part_name_1>.obj
    ├── <part_name_2>.obj
    └── ...
```

Each `<part_name>.obj` holds all the geometry of all meshes inside that part, combined into one OBJ file.
Do NOT create the `part_meshes/` directory.
