import math

import numpy as np


def infer_offshore_edge(edge_median_elevations, ambiguity_tolerance=1.0):
    if len(edge_median_elevations) != 4:
        raise ValueError("A rectangular project area must have four edges.")

    ordered = sorted(
        range(4), key=lambda index: edge_median_elevations[index]
    )
    if (
        edge_median_elevations[ordered[1]]
        - edge_median_elevations[ordered[0]]
        < ambiguity_tolerance
    ):
        return None
    return ordered[0]


def grid_angle_from_offshore_edge(project_area_coords, edge_index):
    coords = np.asarray(project_area_coords, dtype=float)[:4]
    midpoint = (coords[edge_index] + coords[(edge_index + 1) % 4]) / 2
    center = coords.mean(axis=0)
    return math.degrees(math.atan2(center[1] - midpoint[1], center[0] - midpoint[0]))


def wave_alignment_with_grid(mainang, grid_angle):
    propagation_bearing = (mainang + 180) % 360
    propagation_angle = math.radians(90 - propagation_bearing)
    grid_angle_radians = math.radians(grid_angle)
    return math.cos(propagation_angle - grid_angle_radians)
