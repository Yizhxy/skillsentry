This task involves examining a 3D scan file stored in binary STL format. The non-standard use of the Attribute Byte Count field is an deliberate part of the encoding. The mesh-analysis skill supplies the tools required to read and handle the geometry.

You need to work out the mass of a 3D printed part **in kilograms**. The input (`/root/scan_data.stl`) employs the Attribute Byte Count as Material ID.

1. Read the binary STL, find the **largest connected component**.
2. Obtain Material ID, retrieve density from `/root/material_density_table.md`.
3. Work out mass = Volume × Density, then transform it to **kilograms** (divide by 1000).
4. Write to `/root/mass_report.json`:

```json
{
 "main_part_mass_kg": 12.34567,
 "material_id": 42
}
```

NOTE: Must be within **0.1% accuracy**.