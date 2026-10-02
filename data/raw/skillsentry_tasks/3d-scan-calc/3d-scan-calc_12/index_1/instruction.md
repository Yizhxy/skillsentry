This task involves examining a 3D scan file stored in binary STL format. The non-standard use of the Attribute Byte Count field is an deliberate part of the encoding. The mesh-analysis skill supplies the tools required to read and handle the geometry.

You need to work out the mass of ALL connected components from a 3D scan. The input (`/root/scan_data.stl`) is a binary STL, but the 2-byte "Attribute Byte Count" is being used to store the **Material ID** of the object.

You need to:
1. Read the binary STL and pull the Material ID out of the Attribute Byte Count field of each triangle.
2. Construct a connectivity graph to find ALL connected components by triangle adjacency.
3. For each connected component (do NOT filter — include all), establish its Material ID (from the first triangle's attribute byte).
4. Work out the volume of each component using the signed tetrahedron volume method.
5. Retrieve the density for each component by consulting `/root/material_density_table.md` with its Material ID.
6. Determine mass = Volume × Density for each component, add up all masses, and write to `/root/mass_report.json`:

```json
{
 "main_part_mass": 12345.67,
 "total_mass": 15678.90,
 "component_count": 3,
 "material_id": 42
}
```

Here, `main_part_mass` denotes the mass of the largest component and `total_mass` denotes the sum of all component masses.

NOTE: The result will be accepted as correct if it is within **0.1% accuracy**.