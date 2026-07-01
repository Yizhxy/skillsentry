Compute both the **mass AND volume** of the main part. The input uses Attribute Byte Count as Material ID.

1. Parse the binary STL, identify the largest connected component.
2. Compute volume (signed tetrahedron method) and mass = Volume × Density.
3. Save to `/root/mass_report.json`:

Save all results to the expected output paths; use the field names defined by the task specification.