You need to calculate the mass of ALL connected components from a 3D scan. The input (`/root/scan_data.stl`) is a binary STL, but the 2-byte "Attribute Byte Count" is being used to store the **Material ID** of the object.

You need to:
1. Parse the binary STL and extract Material ID from the Attribute Byte Count field of each triangle.
2. Build a connectivity graph to identify ALL connected components by triangle adjacency.
3. For each connected component (do NOT filter — include all), determine its Material ID (from the first triangle's attribute byte).
4. Calculate the volume of each component using the signed tetrahedron volume method.
5. Look up the density for each component by referencing `/root/material_density_table.md` with its Material ID.
6. Compute mass = Volume × Density for each component, sum all masses, and save to `/root/mass_report.json`:

Save all results to the expected output paths; use the field names defined by the task specification.