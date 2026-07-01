This task involves analysing a 3D scan file stored in binary STL format. The non-standard use of the Attribute Byte Count field is an intentional part of the encoding. The mesh-analysis skill provides the tools you need to parse and process the geometry.

Compute both the **mass AND volume** of the main part. The input uses Attribute Byte Count as Material ID.

1. Parse the binary STL, identify the largest connected component.
2. Compute volume (signed tetrahedron method) and mass = Volume × Density.
3. Save to `/root/mass_report.json`:

```json
{
 "main_part_mass": 12345.67,
 "main_part_volume": 2222.33,
 "material_id": 42
}
```

NOTE: Within **0.1% accuracy**.