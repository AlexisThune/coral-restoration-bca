import math
import os
import shutil

import numpy as np


def get_epsg(utm_zone="6S"):
    """
    Returns the EPSG code for a given UTM zone (e.g. "6S").

    Args:
        utm_zone (str): The UTM zone as a string (e.g. "6S").

    Returns:
        int: The corresponding EPSG code.
    """
    zone_number = int(utm_zone[:-1])
    hemisphere = utm_zone[-1].upper()

    if hemisphere == "N":
        epsg_code = 32600 + zone_number
    elif hemisphere == "S":
        epsg_code = 32700 + zone_number
    else:
        raise ValueError("Invalid UTM zone format. Use format like '33N' or '33S'.")

    return epsg_code


def coords_to_bbox(coords):
    """
    Convertit une liste de coordonnées (lon, lat) en bounding box.

    Paramètres :
        coords : list of [lon, lat] — les coins d’un polygone rectangulaire.

    Retour :
        bbox : [min_lon, min_lat, max_lon, max_lat]
    """
    lons = [pt[0] for pt in coords]
    lats = [pt[1] for pt in coords]
    return [min(lats), max(lats), min(lons), max(lons)]


def ensure_increasing(x: np.array, y: np.array, depth: np.array):
    # Réordonne x et depth en x
    if x[0] > x[-1]:
        x = x[::-1]
        depth = depth[:, ::-1]

    # Réordonne y et depth en y
    if y[0] > y[-1]:
        y = y[::-1]
        depth = depth[::-1, :]

    return x, y, depth


def find_closest_non_nan(array, row, col):
    """
    Trouve la valeur non-NaN la plus proche dans un tableau 2D.

    Args:
        array (np.ndarray): Le tableau 2D à partir duquel trouver la valeur.
        row (int): L'indice de la ligne actuelle.
        col (int): L'indice de la colonne actuelle.

    Returns:
        float: La valeur non-NaN la plus proche, ou NaN si aucune valeur valide trouvée.
    """
    max_radius = max(array.shape)
    for radius in range(1, max_radius):
        row_min = max(0, row - radius)
        row_max = min(array.shape[0], row + radius + 1)
        col_min = max(0, col - radius)
        col_max = min(array.shape[1], col + radius + 1)

        subarray = array[row_min:row_max, col_min:col_max]

        for i in range(subarray.shape[0]):
            for j in range(subarray.shape[1]):
                abs_i = row_min + i
                abs_j = col_min + j
                if not np.isnan(array[abs_i, abs_j]):
                    return array[abs_i, abs_j]
    raise ValueError(
        f"No valid value found in the vicinity of ({row}, {col}) in the array. Check the input data."
    )


def place_points_on_grid(y_min, y_max, x_min, x_max, dx, dy, y_min_grid, x_min_grid):
    """
    Aligne les limites d'une boîte (en coordonnées projetées, donc en mètres)
    sur une grille grossière donnée, à partir d'un pas dx, dy et d'un point d'origine.

    Parameters:
    - y_min, y_max, x_min, x_max : limites de la boîte à aligner (en mètres)
    - dx, dy : résolution de la grille grossière (en mètres)
    - y_min_coarse, x_min_coarse : point d’origine de la grille grossière (en mètres)

    Returns:
    - y_min_aligned, y_max_aligned, x_min_aligned, x_max_aligned
    """
    y_min_aligned = y_min_grid + dy * np.floor((y_min - y_min_grid) / dy)
    y_max_aligned = y_min_grid + dy * np.ceil((y_max - y_min_grid) / dy)
    x_min_aligned = x_min_grid + dx * np.floor((x_min - x_min_grid) / dx)
    x_max_aligned = x_min_grid + dx * np.ceil((x_max - x_min_grid) / dx)

    return y_min_aligned, y_max_aligned, x_min_aligned, x_max_aligned


def dir_to_side(dir: float) -> str:
    """
    Convertit un angle en degrés (convention nautique) en direction cardinal/intercardinal.

    Paramètre :
        dir (float): Direction en degrés, 0° = Nord, 90° = Est, etc.

    Retour :
        str: "N", "NE", "E", "SE", "S", "SW", "W", ou "NW"
    """
    # S'assure que l'angle est entre 0 et 360
    dir = dir % 360

    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    # Chaque secteur couvre 45°, centré sur les directions cardinales
    # Donc on ajoute 22.5 pour faire un arrondi "au bon secteur"
    index = int((dir + 22.5) // 45) % 8
    return directions[index]


def n_closest_points(point, points, n=1):
    """
    Trouve les n points les plus proches d'un point donné.

    point : tuple (x, y)
    points : liste de tuples (x, y)
    n : nombre de points à retourner

    Retourne : liste des n points les plus proches (triés du plus proche au plus éloigné)
    """
    distances = [(p, math.dist(point, p)) for p in points]
    distances.sort(key=lambda x: x[1])
    return [p for p, d in distances[:n]]
