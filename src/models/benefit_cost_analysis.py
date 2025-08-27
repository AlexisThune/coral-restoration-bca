import os
import platform
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from src.data_loading_and_processing.bathymetry_loader import BathymetryDataLoader
from src.data_loading_and_processing.xbeach_loader import XBeachDataLoader
from src.models.benefits.xbeach_module.xbeach_analyzer import XBeachResultsAnalyzer
from src.utils.ui import RestorationProject, Scenario


@dataclass
class CoralRestorationBCA:
    config: dict
    scenario: Scenario
    restoration_project: RestorationProject

    def __post_init__(self):
        self.bathymetry_data_loader = BathymetryDataLoader(
            self.config, self.restoration_project
        )

        self.xbeach_data_loader = XBeachDataLoader(
            self.config,
            self.restoration_project,
        )

        self.xbeach_results_analyzer = XBeachResultsAnalyzer(
            self.config, self.restoration_project
        )

    def load_data(self):
        self.bathymetry_data_loader.load()
        self.xbeach_data_loader.load(after_restoration=False)
        self.xbeach_data_loader.load(after_restoration=True)

    def run(self):

        # Répertoire contenant XBeach et les DLL
        xbeach_dir = Path(__file__).parent / "benefits" / "xbeach_module" / "XBeach"

        # Donne les droits d'exécution à tous les fichiers du dossier
        for fname in os.listdir(xbeach_dir):
            fpath = os.path.join(xbeach_dir, fname)
            if os.path.isfile(fpath):
                file_stat = os.stat(fpath)
                os.chmod(fpath, file_stat.st_mode | stat.S_IXUSR)

        def run_xbeach(after_restoration: bool):
            """Runs the XBeach simulation using the compiled or bundled executable."""

            # Déterminer le dossier d'entrée selon le scénario
            if after_restoration:
                input_path = self.config["module_path"]["xbeach_paths"][1]
            else:
                input_path = self.config["module_path"]["xbeach_paths"][0]

            # 1. Vérifier si on est sous Streamlit Cloud (Linux)
            if not platform.processor():
                # Binaire compilé fournir avec le projet
                xbeach_exe = (
                    Path(__file__).parent
                    / "benefits"
                    / "xbeach_module"
                    / "XBeach"
                    / "xbeach"
                )

            # 2. If not that means we are running the program in local
            else:
                # fallback Windows : exe fourni avec le projet
                if os.name == "nt":
                    xbeach_exe = (
                        Path(__file__).parent
                        / "benefits"
                        / "xbeach_module"
                        / "XBeach"
                        / "xbeach.exe"
                    )

            # Vérifier si le binaire existe
            if not xbeach_exe.exists():
                raise FileNotFoundError(
                    f"❌ Impossible de trouver XBeach à {xbeach_exe}.\n"
                    "Assurez-vous de l'avoir compilé (Cloud/Linux) ou fourni (Windows)."
                )

            # Exécution
            result = subprocess.run(
                [str(xbeach_exe)], cwd=input_path, capture_output=True, text=True
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"XBeach a échoué (code {result.returncode}) :\n{result.stderr}"
                )

            return result.stdout

        st.write("Running XBeach simulation...")
        print("Running XBeach simulation...")
        run_xbeach(after_restoration=False)
        run_xbeach(after_restoration=True)

        st.write("Analyzing XBeach results...")
        print("Analyzing XBeach results...")
        self.xbeach_results_analyzer.analyze(after_restoration=False)
        self.flooded_area_before = self.xbeach_results_analyzer.flooded_area
        self.xbeach_results_analyzer.analyze(after_restoration=True)
        self.flooded_area_after = self.xbeach_results_analyzer.flooded_area

        st.write("Computing benefits...")
        self.compute_benefits()

    def compute_benefits(self):
        self.benefits = (
            (self.flooded_area_after - self.flooded_area_before)
            * self.restoration_project.area_value
            * 10_000
        )  # conversion back to m2

        st.write("Benefits:", self.benefits, "$", ":sunglasses:")
        benefits_str = "Benefits:" + f"{self.benefits:.0f}" + "$" + ":sunglasses:"
        st.session_state.results.append(
            {
                "type": "writable",
                "data": {
                    "benefits": benefits_str,
                },
            }
        )
