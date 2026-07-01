determine both the **mass AND volume** of the main part. The input uses Attribute Byte Count as Material ID.

1. read the binary STL, find the largest connected component.
2. determine volume (signed tetrahedron method) and mass = Volume × Density.
3. Save to `/root/mass_report.json`:

```json
{
 "main_part_mass": 12345.67,
 "main_part_volume": 2222.33,
 "material_id": 42
}
```

NOTE: Within **0.1% accuracy**.