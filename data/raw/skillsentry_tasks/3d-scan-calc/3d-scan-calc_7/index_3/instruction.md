You need to calculate the mass of a 3D printed part and report the material distribution across all components. The input (`/root/scan_data.stl`) is a binary STL, but the 2-byte "Attribute Byte Count" is being used to store the **Material ID**.

You need to:

First, parse the binary STL and extract Material ID from the Attribute Byte Count field of each triangle. Then build a connectivity graph to identify ALL connected components by triangle adjacency. Next, identify the **largest connected component** as the main part (filtering out debris). After that, calculate the volume of the main part using the signed tetrahedron volume method. Subsequently, look up the **density** by referencing `/root/material_density_table.md` with the Material ID. Finally, compute **mass = Volume × Density** and save to `/root/mass_report.json`:

```json
{
 "main_part_mass": 12345.67,
 "material_id": 42,
 "material_distribution": {
   "42": {"component_count": 1, "triangle_count": 5000},
   "10": {"component_count": 2, "triangle_count": 150}
 }
}
```

NOTE: The result will be considered correct if it is within **0.1% accuracy**.