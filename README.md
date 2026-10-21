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

## XBeach executable

In the Docker image, the app uses the XBeach executable built at
`/opt/xbeach/src/xbeach/xbeach`. On Windows, it uses the bundled
`xbeach.exe`. To select a different executable, set `XBEACH_EXECUTABLE` to its
path. On Linux, if its shared libraries are not in the executable's expected
build location, set `XBEACH_LIBRARY_PATH` to the directory containing them.

XBeach requires a structured rectangular grid. The app therefore keeps the
complete regular grid covering the project area's extent after rotation to the
selected grid angle; for different area and grid angles, some edge cells can
extend beyond the drawn area.

## Simulation time estimates

Before a run, the app shows the structured grid size and estimates end-to-end
runtime by scaling the median runtime per grid cell from successful runs in the
current Streamlit browser session. The first successful run provides the initial
calibration. This is an order-of-magnitude estimate, not a solver guarantee:
XBeach runtime can vary with the machine and model conditions, and the restored
zone count is shown as context but is not currently part of the scaling formula.
