import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from src.data_loading_and_processing.bathymetry_loader import BathymetryDataLoader
from src.data_loading_and_processing.xbeach_loader import XBeachDataLoader
from src.models.benefits.xbeach_module.xbeach_analyzer import XBeachResultsAnalyzer
from src.utils.ui import RestorationProject, Scenario

xbeach_dir = Path(__file__).parent / "benefits" / "xbeach_module" / "XBeach"


def resolve_xbeach_executable():
    configured_executable = os.environ.get("XBEACH_EXECUTABLE")
    if configured_executable:
        executable = Path(configured_executable).expanduser().resolve()
    elif os.name == "nt":
        executable = xbeach_dir / "xbeach.exe"
    elif sys.platform.startswith("linux"):
        executable = Path("/opt/xbeach/src/xbeach/xbeach")
    else:
        raise OSError(f"Unsupported operating system for XBeach: {sys.platform}")

    if not executable.is_file():
        raise FileNotFoundError(
            f"XBeach executable not found at {executable}. "
            "Set XBEACH_EXECUTABLE to its path."
        )

    return executable


def build_xbeach_environment(executable):
    run_env = os.environ.copy()
    library_dir = os.environ.get("XBEACH_LIBRARY_PATH")
    if library_dir:
        library_dir = Path(library_dir).expanduser().resolve()
        if not library_dir.is_dir():
            raise FileNotFoundError(
                f"XBeach library directory not found: {library_dir}"
            )
    else:
        library_dir = (
            executable.parent.parent / "xbeachlibrary" / ".libs"
        ).resolve()

    if sys.platform.startswith("linux") and library_dir.is_dir():
        existing_library_path = run_env.get("LD_LIBRARY_PATH", "")
        run_env["LD_LIBRARY_PATH"] = os.pathsep.join(
            path for path in (str(library_dir), existing_library_path) if path
        )

    return run_env


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
        def run_xbeach(after_restoration: bool):
            """Runs the XBeach simulation using the compiled or bundled executable."""

            # Déterminer le dossier d'entrée selon le scénario
            if after_restoration:
                input_path = self.config["module_path"]["xbeach_paths"][1]
            else:
                input_path = self.config["module_path"]["xbeach_paths"][0]

            xbeach_exe = resolve_xbeach_executable()
            run_env = build_xbeach_environment(xbeach_exe)

            # Exécution
            result = subprocess.run(
                [str(xbeach_exe)],
                cwd=input_path,
                capture_output=True,
                text=True,
                env=run_env,
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
