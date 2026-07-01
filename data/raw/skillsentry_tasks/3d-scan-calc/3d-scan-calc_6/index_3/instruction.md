Compute both the **mass AND volume** of the main part. The input uses Attribute Byte Count as Material ID.

First, parse the binary STL, identify the largest connected component. Then compute volume (signed tetrahedron method) and mass = Volume × Density. Next, save to `/root/mass_report.json`:

```json
{
 "main_part_mass": 12345.67,
 "main_part_volume": 2222.33,
 "material_id": 42
}
```

NOTE: Within **0.1% accuracy**.