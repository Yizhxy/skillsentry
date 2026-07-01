Calculate the mass using a **stricter debris filtering rule**: exclude all components smaller than **5% of the largest component's volume**. The input uses Attribute Byte Count as Material ID.

1. Parse the binary STL, find all connected components.
2. Find the largest component volume.
3. Keep only components with volume ≥ 5% of the maximum volume.
4. Among kept components, take the one with the largest volume as the "main part".
5. Compute mass = Volume × Density.
6. Save to `/root/mass_report.json`:

Save all results to the expected output paths; use the field names defined by the task specification.