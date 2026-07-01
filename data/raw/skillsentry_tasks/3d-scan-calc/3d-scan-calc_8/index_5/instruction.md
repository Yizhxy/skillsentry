Report the **total number of connected components** and the main part mass. The input uses Attribute Byte Count as Material ID.

1. Parse the binary STL, find ALL connected components.
2. For the largest component (main part), compute mass.
3. Save to `/root/mass_report.json`:

Save all results to the expected output paths; use the field names defined by the task specification.