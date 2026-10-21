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

## Grid orientation and wave-input checks

The app samples bathymetry along the four project-area edges and uses the
lowest median bed elevation to identify the offshore edge. If the two lowest
edge medians differ by less than 1 m, or no edge can be sampled, the user must
choose the offshore side manually. The map then shows the landward grid axis
and the wave-propagation arrow. `mainang` is shown in nautical degrees as the
direction waves come from; the arrow points in the opposite, propagation
direction.

The UI flags a zero wave height, a wave direction pointing away from the
landward grid axis, and a wave height greater than the estimated water depth
at the offshore edge. These are input-consistency warnings, not a prediction
of XBeach numerical stability.

The bundled `xbTools` postprocessor uses a Windows path separator when opening
`XBlog.txt`. The app's small adapter reads this metadata with `pathlib`, which
works on both Linux and Windows.

## Simulation time estimates

Before a run, the app shows the structured grid size and estimates end-to-end
runtime by scaling the median runtime per grid cell from successful runs in the
current Streamlit browser session. The first successful run provides the initial
calibration. This is an order-of-magnitude estimate, not a solver guarantee:
XBeach runtime can vary with the machine and model conditions, and the restored
zone count is shown as context but is not currently part of the scaling formula.
