This task involves examining a 3D scan file stored in binary STL format. The non-standard use of the Attribute Byte Count field is an deliberate part of the encoding. The mesh-analysis skill supplies the tools required to read and handle the geometry.

List the **3 largest connected components** by volume. The input (`/root/scan_data.stl`) employs Attribute Byte Count as Material ID.

1. Read the binary STL, locate ALL connected components, order by volume descending, keep the top 3.
2. For each, work out mass = Volume × Density (from `/root/material_density_table.md`).
3. Write to `/root/mass_report.json`:

```json
{
 "top3_components": [
   {"rank": 1, "volume": 12345.67, "mass": 4567.89, "material_id": 42},
   {"rank": 2, "volume": 234.56, "mass": 90.12, "material_id": 10},
   {"rank": 3, "volume": 12.34, "mass": 5.67, "material_id": 1}
 ]
}
```

NOTE: Must be within **0.1% accuracy**.