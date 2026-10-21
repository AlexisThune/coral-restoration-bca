from pathlib import Path
from typing import Sequence, Tuple, Union

import geopandas as gpd
from shapely.geometry import Polygon


def load_coral_for_project(
    data_path: Union[str, Path],
    project_area_coords: Sequence[Tuple[float, float]],
    project_epsg: int,
) -> gpd.GeoDataFrame:
    project_crs = f"EPSG:{project_epsg}"
    project_area = Polygon(project_area_coords)
    project_area_wgs84 = (
        gpd.GeoSeries([project_area], crs=project_crs)
        .to_crs("EPSG:4326")
        .iloc[0]
    )
    candidates = gpd.read_file(
        data_path,
        layer="coral",
        bbox=project_area_wgs84.bounds,
    )

    if candidates.crs is None:
        raise ValueError(f"Coral dataset has no CRS: {data_path}")

    candidates = candidates.to_crs(project_crs)
    return candidates.loc[candidates.intersects(project_area)].copy()
