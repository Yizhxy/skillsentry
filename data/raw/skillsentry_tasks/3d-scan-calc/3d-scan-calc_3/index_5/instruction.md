You need to calculate the mass of a 3D printed part **in kilograms**. The input (`/root/scan_data.stl`) uses the Attribute Byte Count as Material ID.

1. Parse the binary STL, identify the **largest connected component**.
2. Extract Material ID, look up density in `/root/material_density_table.md`.
3. Calculate mass = Volume × Density, then convert to **kilograms** (divide by 1000).
4. Save to `/root/mass_report.json`:

Save all results to the expected output paths; use the field names defined by the task specification.