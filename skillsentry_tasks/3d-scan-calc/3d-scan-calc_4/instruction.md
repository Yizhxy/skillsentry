Report the **3 largest connected components** by volume. The input (`/root/scan_data.stl`) uses Attribute Byte Count as Material ID.

1. Parse the binary STL, find ALL connected components, sort by volume descending, take the top 3.
2. For each, compute mass = Volume × Density (from `/root/material_density_table.md`).
3. Save to `/root/mass_report.json`:

```json
{
 "top3_components": [
   {"rank": 1, "volume": 12345.67, "mass": 4567.89, "material_id": 42},
   {"rank": 2, "volume": 234.56, "mass": 90.12, "material_id": 10},
   {"rank": 3, "volume": 12.34, "mass": 5.67, "material_id": 1}
 ]
}
```

NOTE: Within **0.1% accuracy**.
