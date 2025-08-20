from dataclasses import dataclass

import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from matplotlib.colors import BoundaryNorm, ListedColormap
from pyproj import Transformer
from shapely.geometry import Point
from tqdm import tqdm
from xbTools.xbeachpost import XBeachModelAnalysis

from src.utils.ui import RestorationProject


@dataclass
class XBeachResultsAnalyzer:
    config: dict
    project: RestorationProject

    def analyze(self, after_restoration):
        if after_restoration:
            output_path = self.config["module_path"]["xbeach_paths"][1]
            analysis_title = "After Restoration"
        else:
            output_path = self.config["module_path"]["xbeach_paths"][0]
            analysis_title = "Before Restoration"

        # Analyze the results
        self.results = XBeachModelAnalysis(analysis_title, output_path)
        self.results.load_model_setup()

        # Compute and plot flood maps, i.e where bathymetry is positive and zs too
        zs = self.results.get_modeloutput("zs")
        zb = self.results.get_modeloutput("zb")

        zs_flood = zs[-1]
        zb_flood = zb[-1]

        # initial_sea = ~zs[0].mask ---> this also takes the initial tide, when here we only want "base" sea level, i.e where zb < 0
        sea_mask = zb[0] < 0
        land_mask = ~sea_mask

        flood_map = np.where(land_mask & (zs_flood - zb_flood > 0), 1, 0)
        flood_mask = flood_map.astype(bool)
        flood_levels = np.where(flood_mask, zs_flood - zb_flood, 0)

        # Print naive maximum water height
        max_water_level = np.max(zs_flood[flood_mask])
        print(f"Maximum water level: {max_water_level:.2f} m")

        max_water_level = np.max(zs_flood[flood_mask] - zb_flood[flood_mask])
        print(f"Maximum flood height: {max_water_level:.2f} m")

        # Coordonnées des centres de cellules
        X = self.results.grd["x"]
        Y = self.results.grd["y"]

        # Compute interesting areas
        gdf_grid = self.project.gdf_grid

        total_area = sum([polygon.area for polygon in gdf_grid.geometry]) / 10_000

        original_sea_area = self.compute_area_from_mask_and_raster(
            X, Y, sea_mask, gdf_grid
        )
        original_land_area = self.compute_area_from_mask_and_raster(
            X, Y, land_mask, gdf_grid
        )
        self.flooded_area = self.compute_area_from_mask_and_raster(
            X, Y, flood_mask, gdf_grid
        )

        print(f"Total area: {total_area:.2f} ha")
        print(f"Original sea area: {original_sea_area:.2f} ha")
        print(f"Original land area: {original_land_area:.2f} ha")
        print(f"Flooded area : {self.flooded_area:.2f} ha")

        self.plot_flood_map(flood_map, sea_mask)
        self.plot_flood_levels_satellite(X, Y, flood_levels)

    def plot_flood_map(self, flood_map, sea_mask):
        fig, ax = plt.subplots(figsize=(10, 8))

        # Fond : mer et terre
        ax.pcolormesh(
            self.results.grd["x"],
            self.results.grd["y"],
            sea_mask,
            cmap="Blues",
            shading="auto",
            alpha=0.6,
        )
        ax.pcolormesh(
            self.results.grd["x"],
            self.results.grd["y"],
            ~sea_mask,
            cmap="Greens",
            shading="auto",
            alpha=0.6,
        )

        # Flood map (zones inondées en rouge)
        flood_map_plot = np.ma.masked_where(flood_map == 0, flood_map)
        pc = ax.pcolormesh(
            self.results.grd["x"],
            self.results.grd["y"],
            flood_map_plot,
            cmap="Reds",
            shading="auto",
            alpha=0.7,
        )

        # Légende
        plt.colorbar(pc, ax=ax, label="Flooded areas")

        ax.set_title("Flood map")

        # Affichage dans Streamlit
        st.pyplot(fig)

        # Stockage du résultat
        st.session_state.results.append(
            {
                "type": "plottable",
                "data": fig,
            }
        )

    def plot_flood_levels_satellite(self, x, y, flood_levels, epsg_in=32706):
        # Définir les couleurs par palier
        colors = [
            "darkblue",  # 0
            "blue",  # 0.25
            "cyan",  # 0.5
            "green",  # 0.75
            "yellow",  # 1
            "orange",  # 1.5
            "red",  # 2
            "magenta",  # 2.5-3
        ]

        bounds = [0, 0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3]

        cmap = ListedColormap(colors)
        norm = BoundaryNorm(bounds, cmap.N)

        # 1️⃣ Convertir coordonnées grille en EPSG:4326
        transformer = Transformer.from_crs(epsg_in, 4326, always_xy=True)
        lon, lat = transformer.transform(x, y)

        # 2️⃣ Créer figure
        fig, ax = plt.subplots(figsize=(10, 8))
        masked_levels = np.ma.masked_where(flood_levels == 0, flood_levels)

        # 3️⃣ Affichage flood_map avec pcolormesh (meilleure gestion des grilles irrégulières)
        pcm = ax.pcolormesh(
            lon, lat, masked_levels, cmap=cmap, norm=norm, shading="auto", alpha=0.4
        )
        fig.colorbar(
            pcm, ax=ax, boundaries=bounds, ticks=bounds, label="Flood depth (m)"
        )

        # 4️⃣ Ajouter fond satellite (contextily attend EPSG:3857)
        gdf_bbox = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy([lon.min(), lon.max()], [lat.min(), lat.max()]),
            crs="EPSG:4326",
        ).to_crs(epsg=3857)
        xmin, ymin, xmax, ymax = gdf_bbox.total_bounds

        ctx.add_basemap(
            ax, source=ctx.providers.Esri.WorldImagery, crs="EPSG:4326", zoom=14
        )

        ax.set_aspect("equal")
        ax.set_xlim(lon.min(), lon.max())
        ax.set_ylim(lat.min(), lat.max())
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title("Flood map (satellite background)")

        st.pyplot(fig)

        st.session_state.results.append(
            {
                "type": "plottable",
                "data": fig,
            }
        )

    def compute_area_from_mask_and_raster(self, X, Y, mask, gdf):
        interest_x = X[mask]
        interest_y = Y[mask]

        # Créer un spatial index pour gdf
        sindex = gdf.sindex

        total_area = 0
        for x, y in tqdm(zip(interest_x, interest_y), desc="Computing area"):
            pt = Point(x, y)

            # Chercher seulement les géométries dont la bbox intersecte le point
            possible_matches_index = list(sindex.intersection(pt.bounds))
            possible_matches = gdf.iloc[possible_matches_index]

            # Vérifier vraiment la géométrie
            for geom in possible_matches.geometry:
                if geom.contains(pt):
                    total_area += geom.area
                    break

        return total_area / 10_000
