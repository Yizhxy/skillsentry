Analyse a 3D scan file stored in binary STL format. The non-standard use of the Attribute Byte Count field is an intentional part of the encoding. Use the mesh-analysis skill for the tools to parse and process the geometry.

Calculate the mass of ALL connected components from a 3D scan. The input (`/root/scan_data.stl`) is a binary STL, but the 2-byte "Attribute Byte Count" is being used to store the **Material ID** of the object.

Steps:
1. Parse the binary STL and extract Material ID from the Attribute Byte Count field of each triangle.
2. Build a connectivity graph to identify ALL connected components by triangle adjacency.
3. For each connected component (do NOT filter — include all), determine its Material ID (from the first triangle's attribute byte).
4. Calculate the volume of each component using the signed tetrahedron volume method.
5. Look up the density for each component by referencing `/root/material_density_table.md` with its Material ID.
6. Compute mass = Volume × Density for each component, sum all masses, and save to `/root/mass_report.json`:

```json
{
 "main_part_mass": 12345.67,
 "total_mass": 15678.90,
 "component_count": 3,
 "material_id": 42
}
```

`main_part_mass` = mass of the largest component; `total_mass` = sum of all component masses.

NOTE: Correct if within **0.1% accuracy**.