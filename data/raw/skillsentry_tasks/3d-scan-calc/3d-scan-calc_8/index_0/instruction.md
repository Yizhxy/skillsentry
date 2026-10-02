You are asked to report the **total number of connected components** and the main part mass. The input uses Attribute Byte Count as Material ID.

1. Parse the binary STL, find ALL connected components.
2. For the largest component (main part), compute mass.
3. Save to `/root/mass_report.json`:

```json
{
 "component_count": 3,
 "main_part_mass": 12345.67,
 "material_id": 42
}
```

NOTE: Within **0.1% accuracy**.
