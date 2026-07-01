You need to work out the mass of a 3D printed part **in kilograms**. The input (`/root/scan_data.stl`) uses the Attribute Byte Count as Material ID.

1. read the binary STL, find the **largest connected component**.
2. obtain Material ID, look up density in `/root/material_density_table.md`.
3. work out mass = Volume × Density, then convert to **kilograms** (divide by 1000).
4. Save to `/root/mass_report.json`:

```json
{
 "main_part_mass_kg": 12.34567,
 "material_id": 42
}
```

NOTE: Within **0.1% accuracy**.