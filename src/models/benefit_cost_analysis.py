import subprocess
from dataclasses import dataclass

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
        # Run the XBeach simulation twice
        def run_xbeach(after_restoration: bool):
            """Runs the XBeach simulation using the provided simulation path."""
            if after_restoration:
                input_path = self.config["module_path"]["xbeach_paths"][1]
            else:
                input_path = self.config["module_path"]["xbeach_paths"][0]

            xbeach_exe = r"C:\\Users\\alexi\\Documents\\Mines_Paris\\Cesure\\Polynesie\\coral-restoration-bca\\src\\models\\benefits\\xbeach_module\\XBeach\\xbeach.exe"
            try:
                subprocess.run([xbeach_exe], cwd=input_path, capture_output=True)
            except FileNotFoundError:
                print(
                    "Error : xbeach.exe not in PATH, or incorrect file path furnished."
                )

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
