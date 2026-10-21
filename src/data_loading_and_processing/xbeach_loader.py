import json
import os
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from affine import Affine
from rasterio.features import rasterize
from shapely.geometry import Polygon
from xbTools.xbeachtools import XBeachModelSetup

from src.utils.ui import RestorationProject


@dataclass
class XBeachDataLoader:
    config: dict
    project: RestorationProject

    def __post_init__(self):
        self.before_restoration_input_folder, self.after_restoration_input_folder = (
            self.config["module_path"]["xbeach_paths"]
        )
        self.default_friction = self.config[
            "Coral cover to friction coefficient (% to dimensionless)"
        ]["0"]

    def save_friction(self, path, friction_grid):
        with open(path, "w") as f:
            for row in friction_grid:
                f.write(" ".join(f"{val:.4f}" for val in row) + "\n")

    def rasterize_polygon_values(self, geometries, values, fill_value):
        x = self.project.x_grid
        y = self.project.y_grid
        angle = np.deg2rad(self.project.grid_angle)

        column_x = (
            x[0, 1] - x[0, 0]
            if x.shape[1] > 1
            else 10 * np.cos(angle)
        )
        column_y = (
            y[0, 1] - y[0, 0]
            if y.shape[1] > 1
            else 10 * np.sin(angle)
        )
        row_x = (
            x[1, 0] - x[0, 0]
            if x.shape[0] > 1
            else -10 * np.sin(angle)
        )
        row_y = (
            y[1, 0] - y[0, 0]
            if y.shape[0] > 1
            else 10 * np.cos(angle)
        )
        transform = Affine(
            column_x,
            row_x,
            x[0, 0] - (column_x + row_x) / 2,
            column_y,
            row_y,
            y[0, 0] - (column_y + row_y) / 2,
        )

        # Earlier polygons win when source features overlap, matching the old loop.
        shapes = (
            (geometry, value)
            for geometry, value in zip(geometries[::-1], values[::-1])
            if geometry is not None and not geometry.is_empty
        )
        return rasterize(
            shapes,
            out_shape=x.shape,
            transform=transform,
            fill=fill_value,
            dtype="float32",
        )

    def configure_friction(self, xb_setup):
        # Load the GeoJSON containing manning values
        with open(
            "src/models/benefits/xbeach_module/after_restoration/input/friction_before_restoration.geojson",
            "r",
        ) as f:
            geojson_str = f.read()
            geojson_dict = json.loads(json.loads(geojson_str))
        gdf = gpd.GeoDataFrame.from_features(geojson_dict["features"])

        # Compute original coral area
        self.project_zone = Polygon(self.project.oriented_rect_coords)
        self.original_coral_area = (
            sum(
                [
                    polygon.intersection(self.project_zone).area
                    for polygon in gdf.geometry
                ]
            )
            / 10_000
        )
        print("Original coral area :", self.original_coral_area, "ha.")

        friction_grid = self.rasterize_polygon_values(
            gdf.geometry.to_numpy(),
            gdf["friction"].to_numpy(dtype=np.float32),
            float(self.default_friction),
        )

        xb_setup.set_friction(friction_grid)

        # Save as .dep file
        before_restoration_path = os.path.join(
            self.before_restoration_input_folder, "friction.dep"
        )
        self.save_friction(before_restoration_path, friction_grid)

        after_restoration_path = os.path.join(
            self.after_restoration_input_folder, "friction.dep"
        )
        self.save_friction(after_restoration_path, friction_grid)

    def update_friction(self, xb_setup):
        # Load the GeoJSON containing manning values and the previous .dep file
        gdf = gpd.read_file(
            "src/models/benefits/xbeach_module/after_restoration/input/friction_from_restoration.geojson"
        )
        if gdf.empty:
            raise ValueError(
                "No restored coral zones found. Draw and validate at least one "
                "restoration zone before launching the simulation."
            )

        friction_grid = np.loadtxt(
            os.path.join(self.after_restoration_input_folder, "friction.dep")
        )

        restored_friction = self.rasterize_polygon_values(
            gdf.geometry.to_numpy(),
            gdf["friction"].to_numpy(dtype=np.float32),
            np.nan,
        )
        restored_cells = np.isfinite(restored_friction)
        friction_grid[restored_cells] = restored_friction[restored_cells]

        xb_setup.set_friction(friction_grid)

        # Compute restored coral area
        restored_coral_area = (
            sum(
                [
                    polygon.intersection(self.project_zone).area
                    for polygon in gdf.geometry
                ]
            )
            / 10_000
        )

        print(f"Coral area restored : {restored_coral_area} ha.")

        print(
            f"Total coral area : {restored_coral_area + self.original_coral_area} ha."
        )

        # Save as .dep file
        output_path = os.path.join(self.after_restoration_input_folder, "friction.dep")
        with open(output_path, "w") as f:
            for row in friction_grid:
                f.write(" ".join(f"{val:.4f}" for val in row) + "\n")

    def update_bed(self, xb_setup):
        # Load the GeoJSON containing manning values and the previous .dep file
        gdf = gpd.read_file(
            "src/models/benefits/xbeach_module/after_restoration/input/height_from_restoration.geojson"
        )
        bed_grid = self.project.z_grid.copy()

        bed_grid += self.rasterize_polygon_values(
            gdf.geometry.to_numpy(),
            gdf["height"].to_numpy(dtype=np.float32),
            0,
        )

        xb_setup.set_grid(
            self.project.x_grid,
            self.project.y_grid,
            bed_grid,
            posdwn=-1,
        )

    def configure_waves(self, xb_setup):
        xb_setup.set_waves(
            "jonstable",
            {
                "Hm0": [self.project.Hm0, self.project.Hm0],
                "Tp": [self.project.Tp, self.project.Tp],
                "gammajsp": [3.3, 3.3],
                "s": [20, 20],
                "mainang": [self.project.mainang, self.project.mainang],
                "duration": [3600, 3600],
                "dtbc": [1, 1],
            },
        )

    def configure_params(self, xb_setup):
        xb_setup.set_params(
            {
                "wavemodel": "surfbeat",
                "morphology": 0,
                "bedfriction": "manning",
                "bedfricfile": "friction.dep",
                "outputformat": "netcdf",
                "rugdepth": 0.02,
                "tstop": 3600,
                "tstart": 100,
                "tintg": 3100,
                "tintm": 3500,
                "tintp": 10,
                "zs0": self.project.zs0,  # constant uniform tide
                "nglobalvar": ["zs", "zb", "H"],
                "npointvar": ["zs", "zb", "H"],
                "nmeanvar": ["zs", "zb", "H"],
                "npoints": ["1 0", "6 0", "10 0", "12 0"],
            }
        )

    def load(self, after_restoration: bool):

        xb_setup = XBeachModelSetup("Test simulation")

        xb_setup.set_grid(
            self.project.x_grid,
            self.project.y_grid,
            self.project.z_grid,
            posdwn=-1,
        )

        self.configure_friction(xb_setup)

        if after_restoration:
            self.update_friction(xb_setup)
            self.update_bed(xb_setup)

        self.configure_waves(xb_setup)

        self.configure_params(xb_setup)

        if after_restoration:
            xb_setup.write_model(self.after_restoration_input_folder)
        else:
            xb_setup.write_model(self.before_restoration_input_folder)
