from dataclasses import dataclass

import folium
import geopandas as gpd
from folium.plugins import Draw
from shapely.affinity import rotate, translate
from shapely.geometry import Polygon

from src.utils.technical_functions import coords_to_bbox


@dataclass
class Scenario:
    discount_rate: float  # in %


@dataclass
class RestorationProject:
    start_year: int
    duration: int  # years
    location: tuple  # coordinates (lat, lon) in degrees
    oriented_rect_coords: list[tuple]  # list of coordinates (x, y) in meters
    grid_angle: float  # in degrees
    height: float  # m, can rather be computed through a function later, as an expected height, initial parameter for now
    Hm0: float  # wave specific height
    Tp: float  # wave period
    mainang: float  # main angle of wave direction, nautical degrees
    area_value: float  # value of the area in $ / m2
    zs0: float = (
        0  # initial sea level in m, includes the effects of both Sea Level Rise (SLR) and tide
    )
    epsg: int = 32706  # EPSG code for UTM zone, default is for UTM zone 50S

    def __post_init__(self):
        self.marine_aoi_bounds = self._generate_aoi_bounds(degree_margin=0.5)
        self.coastal_aoi_bounds = coords_to_bbox(self.oriented_rect_coords)
        self.gdf_grid, self.x_grid, self.y_grid = self._generate_gdf_grid(cell_size=10)
        # compute oriented_rect_coords area in ha
        self.oriented_rect_area = Polygon(self.oriented_rect_coords).area / 10_000
        print("GT area:", self.oriented_rect_area, "ha")

    def _generate_aoi_bounds(self, degree_margin=0.5):
        return (
            self.location[0] - degree_margin,
            self.location[0] + degree_margin,
            self.location[1] - degree_margin,
            self.location[1] + degree_margin,
        )

    def _generate_gdf_grid(self, cell_size):
        """to - do :
        - make sure the cells exactly match the bounds, by cutting them or enlarging the bound to have regular cells
        """
        rect_poly = Polygon(self.oriented_rect_coords)

        minx, miny, _, _ = rect_poly.bounds
        rect_local = translate(rect_poly, xoff=-minx, yoff=-miny)
        rect_axis_aligned = rotate(rect_local, -self.grid_angle, origin=(0, 0))

        nx_cells = 0  # nombre de colonnes (X)
        ny_cells = 0  # nombre de lignes (Y)

        grid_polys_local = []
        gxmin, gymin, gxmax, gymax = rect_axis_aligned.bounds
        x = gxmin

        while x < gxmax:
            nx_cells += 1
            y = gymin
            col_count = 0
            while y < gymax:
                cell = Polygon(
                    [
                        (x, y),
                        (x + cell_size, y),
                        (x + cell_size, y + cell_size),
                        (x, y + cell_size),
                    ]
                )
                if rect_axis_aligned.intersects(cell):
                    grid_polys_local.append(cell)
                    col_count += 1
                y += cell_size
            ny_cells = max(ny_cells, col_count)
            x += cell_size

        grid_polys_global = [
            translate(
                rotate(cell, self.grid_angle, origin=(0, 0)), xoff=minx, yoff=miny
            )
            for cell in grid_polys_local
        ]

        gseries = gpd.GeoSeries(grid_polys_global)
        gdf_grid = gpd.GeoDataFrame(geometry=gseries, crs=f"EPSG:{self.epsg}")

        # Get centroids for .grd files
        centroids = gdf_grid.geometry.centroid
        x_coords = centroids.x.values.reshape((nx_cells, ny_cells)).T
        y_coords = centroids.y.values.reshape((nx_cells, ny_cells)).T

        return gdf_grid, x_coords, y_coords


class InteractiveMap:
    def __init__(self, start_coords=(0, 0), start_zoom=2, width="100%", height=600):
        """Initialisation de la carte Folium."""
        self.map = folium.Map(
            location=start_coords, zoom_start=start_zoom, width=width, height=height
        )

    def add_draw_control(self):
        """Add the drawing tool Leaflet Draw."""
        Draw(
            export=True,
            filename="data.geojson",
            draw_options={
                "polyline": False,
                "rectangle": False,
                "circle": False,
                "marker": True,
                "circlemarker": False,
                "polygon": True,
            },
            edit_options={"edit": True},
        ).add_to(self.map)
