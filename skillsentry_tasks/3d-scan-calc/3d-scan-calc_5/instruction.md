You need to calculate the mass of a 3D printed part and also compute its surface area. The input (`/root/scan_data.stl`) is a binary STL, but the 2-byte "Attribute Byte Count" is being used to store the **Material ID**.

You need to:
1. Parse the binary STL and extract Material ID from the Attribute Byte Count field of each triangle.
2. Build a connectivity graph to identify connected components by triangle adjacency.
3. Identify the **largest connected component** (main part) by filtering out scanning debris.
4. Calculate the **volume** of the main part using the signed tetrahedron volume method. Also compute the **surface area** as the sum of triangle areas (area = 0.5 × ||(v2-v1) × (v3-v1)||).
5. Look up the **density** by referencing `/root/material_density_table.md` with the Material ID.
6. Compute **mass = Volume × Density** and save to `/root/mass_report.json`:

```json
{
 "main_part_mass": 12345.67,
 "main_part_surface_area": 23456.78,
 "material_id": 42
}
```

NOTE: The result will be considered correct if it is within **0.1% accuracy**.
