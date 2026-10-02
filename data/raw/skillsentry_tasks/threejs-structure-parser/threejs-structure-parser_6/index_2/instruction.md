Act as a nice Three.js specialist and help engineers understand a complex Three.js file that represents a 3D object. The file is located at `/root/data/object.js` and contains a single `createScene()` function that defines the 3D object.

Parse this Three.js file to find the part-level structure of the defined 3D object. Then, find each individual mesh defined directly by primitive functions as well as the part meshes defined by THREE.Group.

**Variant: Output scene hierarchy as YAML**

Save all meshes as OBJ files (same structure as original), AND save a `hierarchy.yaml` at `/root/output/hierarchy.yaml`:

```yaml
parts:
  - name: PartName
    meshes:
      - name: MeshName
        type: BoxGeometry
      - name: OtherMesh
        type: SphereGeometry
```

Include the geometry type for each mesh (BoxGeometry, SphereGeometry, CylinderGeometry, etc.).
