Use real 2024 earthquake data and plate-boundary shapefiles. Use GeoPandas with an appropriate metric CRS for accurate distance calculations. See the geospatial-analysis skill for the exact workflow steps.

Act as a geospatial analyst with expertise in plate tectonics and earthquake analysis. Find the earthquake that occurred furthest from the Pacific plate boundary within the Pacific plate itself. Use GeoPandas projections. Save the result to `/root/answer.json` as a JSON file with these fields:

- `id`: The earthquake ID
- `place`: The earthquake location description
- `time`: The earthquake time in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
- `magnitude`: The earthquake magnitude
- `latitude`: The earthquake latitude
- `longitude`: The earthquake longitude
- `distance_km`: Largest distance to the Pacific plate boundary in kilometers (rounded to 2 decimal places)

Inputs: earthquake data in `/root/earthquakes_2024.json`; plate boundary data in `/root/PB2002_boundaries.json` and `/root/PB2002_plates.json`.
