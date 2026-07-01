Report the **3 largest connected components** by volume. The input (`/root/scan_data.stl`) uses Attribute Byte Count as Material ID.

1. Parse the binary STL, find ALL connected components, sort by volume descending, take the top 3.
2. For each, compute mass = Volume × Density (from `/root/material_density_table.md`).
3. Save to `/root/mass_report.json`:

Save all results to the expected output paths; use the field names defined by the task specification.