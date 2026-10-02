This task involves examining a 3D scan file stored in binary STL format. The non-standard use of the Attribute Byte Count field is an deliberate part of the encoding. The mesh-analysis skill supplies the tools required to read and handle the geometry.

You need to work out the mass of a 3D printed part and also state its volume. The input (`/root/scan_data.stl`) is a binary STL, but the 2-byte "Attribute Byte Count" at the end of each triangle record is being used to store the **Material ID** of the object.

You need to:
1. Read the binary STL and pull the Material ID out of the Attribute Byte Count field of each triangle.
2. Construct a connectivity graph to find connected components by triangle adjacency.
3. Find the **largest connected component** (main part) by discarding scanning debris.
4. Work out the **volume** of the main part using the signed tetrahedron volume method.
5. Retrieve the **density** by consulting `/root/material_density_table.md` with the Material ID.
6. Determine **mass = Volume × Density** and write it to `/root/mass_report.json` in the following format:

```json
{
 "main_part_mass": 12345.67,
 "main_part_volume": 2222.33,
 "material_id": 42
}
```

NOTE: The result will be accepted as correct if it is within **0.1% accuracy**.