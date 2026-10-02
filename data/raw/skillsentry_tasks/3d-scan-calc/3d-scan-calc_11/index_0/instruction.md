The task at hand involves analysing a 3D scan file stored in binary STL format. The non-standard use of the Attribute Byte Count field is an intentional part of the encoding. The mesh-analysis skill provides the tools you need to parse and process the geometry.

It is required to calculate the mass of a 3D printed part and also report its volume. The input (`/root/scan_data.stl`) is a binary STL, but the 2-byte "Attribute Byte Count" at the end of each triangle record is being used to store the **Material ID** of the object.

You need to:
1. Parse the binary STL and extract Material ID from the Attribute Byte Count field of each triangle.
2. Build a connectivity graph to identify connected components by triangle adjacency.
3. Identify the **largest connected component** (main part) by filtering out scanning debris.
4. Calculate the **volume** of the main part using the signed tetrahedron volume method.
5. Look up the **density** by referencing `/root/material_density_table.md` with the Material ID.
6. Compute **mass = Volume × Density** and save to `/root/mass_report.json` in the following format:

```json
{
 "main_part_mass": 12345.67,
 "main_part_volume": 2222.33,
 "material_id": 42
}
```

NOTE: The result will be considered correct if it is within **0.1% accuracy**.