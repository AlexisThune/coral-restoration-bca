from dataclasses import dataclass

import numpy as np
from scipy.interpolate import interp1d
from skimage.measure import find_contours


@dataclass
class SpatialGrid:
    target_variable: str
    values: np.ndarray
    x_values: np.ndarray
    y_values: np.ndarray
    x0: float
    y0: float
    dx: float
    dy: float
    nx: int  # nombre de points sur l'axe x de la grille
    ny: int  # nombre de points sur l'axe y de la grille

    def __post_init__(self):
        self.xlen = (self.nx - 1) * self.dx
        self.ylen = (self.ny - 1) * self.dy

    def extract_isobath_points(self, isobath_level=0.0, spacing=100.0):
        """
        Extrait des points régulièrement espacés le long d'un isobath (niveau d'altitude constant) à partir d'une grille régulière.

        Paramètres :
            Z : array 2D des profondeurs ou altitudes
            X, Y : grilles 1D des coordonnées (mêmes dimensions que Z)
            isobath_level : niveau de l'isobath (par défaut 0 m)
            spacing : distance entre les points extraits (en mètres)

        Retour :
            x_sampled, y_sampled : coordonnées des points extraits tous les `spacing` mètres
        """
        contours = find_contours(self.values, level=isobath_level)
        if not contours:
            raise ValueError("Aucun isobath trouvé à ce niveau")

        # On prend le plus long contour si plusieurs existent
        iso = max(contours, key=lambda x: x.shape[0])

        # Convertir indices en coordonnées physiques
        rows, cols = iso[:, 0], iso[:, 1]

        self.x_iso = self.x0 + cols * self.dx
        self.y_iso = self.y0 + rows * self.dy

        # Distance curviligne
        dist = np.sqrt(np.diff(self.x_iso) ** 2 + np.diff(self.y_iso) ** 2)
        curv_absc = np.concatenate([[0], np.cumsum(dist)])

        # Interpolation régulière
        s_uniform = np.arange(0, curv_absc[-1], spacing)
        fx = interp1d(curv_absc, self.x_iso)
        fy = interp1d(curv_absc, self.y_iso)

        self.x_iso_sampled = fx(s_uniform)
        self.y_iso_sampled = fy(s_uniform)

    def compute_transects_to_isobaths(
        self, interpolator, depth_min=-30, depth_max=20, max_length=10000, step=1.0
    ):
        """
        Calcule des transects perpendiculaires à une ligne (x_sampled, y_sampled),
        s'étendant jusqu'à croiser les isobathes depth_min et depth_max.

        Paramètres :
            x_sampled, y_sampled : points le long de l'isobathe 0
            interpolator : interpolateur bilinéaire (RegularGridInterpolator)
            depth_min, depth_max : seuils des isobathes à atteindre
            max_length : longueur max à balayer (en mètres, de chaque côté)
            step : résolution d'échantillonnage (en mètres)

        Retour :
            Liste de dictionnaires contenant les profils (même format que sample_transects)
        """
        transect_profiles = []

        for i in range(1, len(self.x_iso_sampled) - 1):
            # Calcul de la normale au point courant
            dx = self.x_iso_sampled[i + 1] - self.x_iso_sampled[i - 1]
            dy = self.y_iso_sampled[i + 1] - self.y_iso_sampled[i - 1]
            norm = np.sqrt(dx**2 + dy**2)
            nx, ny = -dy / norm, dx / norm

            x0, y0 = self.x_iso_sampled[i], self.y_iso_sampled[i]

            # Balayage de part et d’autre du point central1
            s_range = np.arange(-max_length, max_length + step, step)
            xs = x0 + s_range * nx
            ys = y0 + s_range * ny
            points = np.vstack([ys, xs]).T
            depths = interpolator(points)

            center_idx = (
                len(depths) // 2
            )  # index central (là où transect coupe l'isobathe 0)

            # Fonction utilitaire pour trouver le premier croisement en partant du centre
            def find_crossing(depths, isobath_dict, center_idx):
                ilim = {"min": None, "max": None}
                for search_range in [
                    range(center_idx - 1, 0, -1),
                    range(center_idx, len(depths) - 1),
                ]:
                    for isobath_name, isobath in zip(
                        isobath_dict.keys(), isobath_dict.values()
                    ):
                        for i in search_range:
                            d1, d2 = depths[i], depths[i + 1]

                            if np.isnan(d1) or np.isnan(d2):
                                continue  # ignorer les points non valides
                            # print(d1, d2, np.sign((d1 - isobath) * (d2 - isobath)))
                            if (d1 - isobath) * (d2 - isobath) < 0:
                                ilim[isobath_name] = i

                return ilim["min"], ilim["max"]

            # Croisements isobathes gauche / droite
            imin, imax = find_crossing(
                depths, {"min": depth_min, "max": depth_max}, center_idx
            )

            if imin is None or imax is None:
                continue  # on skippe si pas de croisement des deux isobathes

            imin, imax = min(imin, imax), max(imin, imax)
            # Tronquer les profils entre les deux indices
            s_trunc = s_range[imin : imax + 2]
            depths_trunc = depths[imin : imax + 2]
            xs_trunc = xs[imin : imax + 2]
            ys_trunc = ys[imin : imax + 2]

            transect_profiles.append(
                {"s": s_trunc, "x": xs_trunc, "y": ys_trunc, "depth": depths_trunc}
            )

        return transect_profiles

    def _plot_grid(self, ax, color="red", linestyle="--", label=""):
        """Helper function to plot grid lines"""

        # Lignes verticales
        for i in range(self.nx):
            ax.plot(
                [self.x0 + i * self.dx, self.x0 + i * self.dx],
                [self.y0, self.y0 + (self.ny - 1) * self.dy],
                color=color,
                linestyle=linestyle,
                linewidth=0.7,
            )

        # Lignes horizontales
        for j in range(self.ny):
            ax.plot(
                [self.x0, self.x0 + (self.nx - 1) * self.dx],
                [self.y0 + j * self.dy, self.y0 + j * self.dy],
                color=color,
                linestyle=linestyle,
                linewidth=0.7,
            )

        # Ajout du label une seule fois
        if label:
            ax.plot([], [], color=color, linestyle=linestyle, label=label)

    def _plot_isobath_0(self, ax):
        # Ligne isobathe de référence
        ax.plot(
            self.x_iso,
            self.y_iso,
            "k-",
            lw=1.5,
            label="Isobathe 0 m",
        )

    import matplotlib.cm as cm
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize

    def plot_values(self, fig, ax, cmap="viridis", savepath=None):
        """
        Affiche la grille des valeurs avec gestion des NaN (en noir),
        la grille régulière et l'isobathe 0 m.

        Paramètres :
            ax : matplotlib.axes.Axes optionnel. Si None, crée une nouvelle figure et axes.
            cmap : colormap matplotlib à utiliser (défaut 'viridis').
            savepath : chemin de fichier pour sauvegarder la figure (None = pas de sauvegarde).
        """

        # Masque les NaN dans les données
        values_masked = np.ma.masked_invalid(self.values)

        # Affichage de la carte avec pcolormesh (coordonnées des bords)
        x_edges = self.x0 + np.arange(self.nx + 1) * self.dx - self.dx / 2
        y_edges = self.y0 + np.arange(self.ny + 1) * self.dy - self.dy / 2

        pcm = ax.pcolormesh(
            x_edges,
            y_edges,
            values_masked,
            cmap=cmap,
            shading="auto",
        )

        # Ajouter la barre de couleur
        cbar = fig.colorbar(pcm, ax=ax)
        cbar.set_label(self.target_variable)

        ax.set_aspect("equal")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_title(f"Carte de {self.target_variable}")
        ax.legend(loc="best")

        # Sauvegarde si demandé
        if savepath is not None:
            fig.savefig(savepath, bbox_inches="tight", dpi=150)

        return ax
