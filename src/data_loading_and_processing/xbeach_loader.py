import json
import os
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from shapely.geometry import Point, Polygon
from tqdm import tqdm
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

        # Load XBeach grid files
        x = self.project.x_grid
        y = self.project.y_grid
        nrows, ncols = x.shape

        # Initialize raster grid
        friction_grid = np.full((nrows, ncols), self.default_friction, dtype=np.float32)

        # Loop over each cell and assign Manning value from polygon if available
        for i in tqdm(range(nrows), desc="Interpolating friction values"):
            for j in range(ncols):
                pt = Point(x[i, j], y[i, j])
                for _, row in gdf.iterrows():
                    if row.geometry.contains(pt):
                        friction_grid[i, j] = float(row["friction"])
                        break  # Use the first matching polygon*

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
        friction_grid = np.loadtxt(
            os.path.join(self.after_restoration_input_folder, "friction.dep")
        )

        # Load XBeach grid files
        x = self.project.x_grid
        y = self.project.y_grid
        nrows, ncols = x.shape

        # Loop over each cell and assign Manning value from polygon if available
        for i in tqdm(range(nrows), desc="Interpolating friction values"):
            for j in range(ncols):
                pt = Point(x[i, j], y[i, j])
                for _, row in gdf.iterrows():
                    if row.geometry.contains(pt):
                        friction_grid[i, j] = float(row["friction"])
                        break  # Use the first matching polygon

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

        # Load XBeach grid files
        x = self.project.x_grid
        y = self.project.y_grid
        nrows, ncols = x.shape

        # Loop over each cell and add height value from polygon if available
        for i in tqdm(range(nrows), desc="Interpolating bed depth values"):
            for j in range(ncols):
                pt = Point(x[i, j], y[i, j])
                for _, row in gdf.iterrows():
                    if row.geometry.contains(pt):
                        bed_grid[i, j] += float(row["height"])
                        break  # Use the first matching polygon

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
                "Wavemodel": "surfbeat",
                "morphology": 0,
                "bedfriction": "manning",
                "bedfricfile": "friction.dep",
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
