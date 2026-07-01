Calculate the mass using a **stricter debris filtering rule**: exclude all components smaller than **5% of the largest component's volume**. The input uses Attribute Byte Count as Material ID.

First, parse the binary STL, find all connected components. Then find the largest component volume. Next, keep only components with volume ≥ 5% of the maximum volume. After that, among kept components, take the one with the largest volume as the "main part". Subsequently, compute mass = Volume × Density. Finally, save to `/root/mass_report.json`:

```json
{
 "main_part_mass": 12345.67,
 "material_id": 42
}
```

NOTE: Within **0.1% accuracy**.