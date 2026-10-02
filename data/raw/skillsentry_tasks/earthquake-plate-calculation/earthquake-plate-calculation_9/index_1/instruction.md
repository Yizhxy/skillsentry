You are a geospatial analyst specializing in plate tectonics and earthquake analysis. I want to identify the earthquake with the LARGEST MAGNITUDE that happened within the Pacific plate in 2024. Make use of GeoPandas to work out which earthquakes lie within the Pacific plate. Write the result to `/root/answer.json` as a JSON file containing the following fields:

- `id`: The earthquake ID
- `place`: The earthquake location description
- `time`: The earthquake time in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
- `magnitude`: The earthquake magnitude
- `latitude`: The earthquake latitude
- `longitude`: The earthquake longitude
- `distance_km`: Distance to the Pacific plate boundary in kilometers (rounded to 2 decimal places)

The earthquake data is supplied in `/root/earthquakes_2024.json`. The plate boundary data is available in `/root/PB2002_boundaries.json` and `/root/PB2002_plates.json`.
