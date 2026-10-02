Compute the **mass AND volume** of the main part. Input: Attribute Byte Count = Material ID.

Steps:
1. Parse the binary STL; identify the largest connected component.
2. Compute volume (signed tetrahedron method) and mass = Volume × Density.
3. Save to `/root/mass_report.json`:

```json
{
 "main_part_mass": 12345.67,
 "main_part_volume": 2222.33,
 "material_id": 42
}
```

NOTE: Within **0.1% accuracy**.
