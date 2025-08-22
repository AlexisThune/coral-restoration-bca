from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely.geometry as sg
import streamlit as st
import xarray as xr
from rasterio.features import shapes
from scipy.interpolate import griddata

from src.data_loading_and_processing.spatial_grid import SpatialGrid
from src.utils.technical_functions import ensure_increasing, place_points_on_grid
from src.utils.ui import RestorationProject


@dataclass
class BathymetryDataLoader:
    config: dict
    project: RestorationProject

    def __post_init__(self):
        self.grids = {}
        self.module_input_path = Path(
            self.config["module_path"]["bathymetry_input_path"]
        )

    def load_bathy_data(self):
        # Load the main bathymetry data
        lat_min, lat_max, lon_min, lon_max = self.project.marine_aoi_bounds

        with xr.open_dataset(self.module_input_path) as ds:
            bathy = ds["Band1"]
            bathy = bathy.rio.write_crs(ds["crs"].attrs["spatial_ref"])

        bathy_bounded = bathy.rio.clip_box(
            minx=lon_min, miny=lat_min, maxx=lon_max, maxy=lat_max
        )

        bathy_bounded_and_projected = bathy_bounded.rio.reproject(
            dst_crs=self.project.epsg, resampling=1
        )

        res_x = abs(
            bathy_bounded_and_projected["x"][1].values
            - bathy_bounded_and_projected["x"][0].values
        )
        res_y = abs(
            bathy_bounded_and_projected["y"][1].values
            - bathy_bounded_and_projected["y"][0].values
        )

        y_min_grid, x_min_grid = (
            bathy_bounded_and_projected["y"].min().values,
            bathy_bounded_and_projected["x"].min().values,
        )

        # Define grid boundaries
        y_min, y_max, x_min, x_max = self.project.coastal_aoi_bounds

        y_min_a, y_max_a, x_min_a, x_max_a = place_points_on_grid(
            y_min,
            y_max,
            x_min,
            x_max,
            dx=res_x,
            dy=res_y,
            y_min_grid=y_min_grid,
            x_min_grid=x_min_grid,
        )

        grid = bathy_bounded_and_projected.rio.clip_box(
            minx=x_min_a,
            miny=y_min_a,
            maxx=x_max_a,
            maxy=y_max_a,
        )

        # Make values order to be ascending
        x_ordered, y_ordered, depth_ordered = ensure_increasing(
            grid["x"].values,
            grid["y"].values,
            grid.values,
        )

        self.grids["transect_bathy"] = SpatialGrid(
            target_variable="bathymetry",
            values=depth_ordered,
            x_values=x_ordered,
            y_values=y_ordered,
            x0=grid["x"].min().values,
            y0=grid["y"].min().values,
            dx=res_x,
            dy=res_y,
            nx=len(grid["x"].values),
            ny=len(grid["y"].values),
        )

        # Conversion du DataArray en numpy
        mask = ~np.isnan(grid.values)
        shapes_gen = shapes(grid.values, mask=mask, transform=grid.rio.transform())

        # Créer un GeoDataFrame
        records = []
        for geom, value in shapes_gen:
            records.append({"geometry": sg.shape(geom), "bathymetry": float(value)})

        self.gdf_bathy = gpd.GeoDataFrame(records, crs=f"EPSG:{self.project.epsg}")

    def build_bathy_grid(self):
        xy_bathy = np.vstack(
            [self.gdf_bathy.geometry.centroid.x, self.gdf_bathy.geometry.centroid.y]
        ).T
        values_bathy = self.gdf_bathy["bathymetry"].values

        # Coordonnées points du grid projet
        xy_project = np.vstack(
            [
                self.project.x_grid.flatten(),
                self.project.y_grid.flatten(),
            ]
        ).T

        # Interpolation avec méthode 'linear' (bilinéaire)
        bathy_interp = griddata(
            points=xy_bathy, values=values_bathy, xi=xy_project, method="linear"
        )

        # Option fallback : là où linéaire donne NaN (en bordure), on peut tenter 'nearest'
        mask_nan = np.isnan(bathy_interp)
        if mask_nan.any():
            bathy_interp[mask_nan] = griddata(
                xy_bathy, values_bathy, xy_project[mask_nan], method="nearest"
            )

        # Ajouter la colonne dans gdf projet
        self.project.gdf_grid = self.project.gdf_grid.assign(bathy_interp=bathy_interp)

        # Save as an array
        nrows, ncols = self.project.y_grid.shape  # shape 2D
        self.project.z_grid = bathy_interp.reshape((nrows, ncols))

    def load(self):
        with st.spinner("Loading bathymetry data..."):
            self.load_bathy_data()
            self.build_bathy_grid()
        st.success("Bathymetry data loaded successfully.")
