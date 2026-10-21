# coral-restoration-bca
This repository is destined to all coral restoration stakeholders, as a tool to perform a Cost-Benefit Analysis of a restoration project. See Richard &amp; al. for more information.

## Coral map data

The app reads `data/coral/original_benthic_coral.gpkg`, a spatially indexed
GeoPackage containing the `Coral/Algae` features from the original benthic map.
Generate or refresh it after changing the source GeoJSON with:

```sh
python scripts/prepare_coral_data.py
```

The command requires GDAL's `ogr2ogr` utility. The app reads only features
within the selected project area's bounding box, then applies an exact
intersection filter. The full-resolution source geometries are retained for
the analysis.
