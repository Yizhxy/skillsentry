This task involves analysing a 3D scan file stored in binary STL format. The non-standard use of the Attribute Byte Count field is an intentional part of the encoding. The mesh-analysis skill provides the tools you need to parse and process the geometry.

You need to calculate the mass of a 3D printed part **in kilograms**. The input (`/root/scan_data.stl`) uses the Attribute Byte Count as Material ID.

First, parse the binary STL and identify the **largest connected component**. Then, extract the Material ID and look up its density in `/root/material_density_table.md`. Next, calculate mass = Volume × Density, then convert to **kilograms** (divide by 1000). Finally, save to `/root/mass_report.json`:

```json
{
 "main_part_mass_kg": 12.34567,
 "material_id": 42
}
```

NOTE: Within **0.1% accuracy**.