import os
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import streamlit as st

from src.data_loading_and_processing.bathymetry_loader import BathymetryDataLoader
from src.data_loading_and_processing.xbeach_loader import XBeachDataLoader
from src.models.benefits.xbeach_module.xbeach_analyzer import XBeachResultsAnalyzer
from src.utils.ui import RestorationProject, Scenario

xbeach_dir = Path(__file__).parent / "benefits" / "xbeach_module" / "XBeach"
XBEACH_PROGRESS_INTERVAL_SECONDS = 30


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

    @staticmethod
    def _report_progress(
        progress_callback: Optional[Callable[[str], None]], message: str
    ) -> None:
        if progress_callback is None:
            print(f"[simulation] {message}", flush=True)
        else:
            progress_callback(message)

    def load_data(
        self, progress_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        self._report_progress(progress_callback, "Loading and interpolating bathymetry")
        self.bathymetry_data_loader.load()

        self._report_progress(
            progress_callback, "Preparing baseline XBeach input files"
        )
        self.xbeach_data_loader.load(after_restoration=False)

        self._report_progress(
            progress_callback, "Preparing restored-scenario XBeach input files"
        )
        self.xbeach_data_loader.load(after_restoration=True)
        self._report_progress(progress_callback, "Simulation inputs are ready")

    def run(self, progress_callback: Optional[Callable[[str], None]] = None) -> None:
        def run_xbeach(after_restoration: bool):
            if after_restoration:
                input_path = self.config["module_path"]["xbeach_paths"][1]
                scenario_name = "restored scenario"
            else:
                input_path = self.config["module_path"]["xbeach_paths"][0]
                scenario_name = "baseline scenario"

            xbeach_exe = resolve_xbeach_executable()
            run_env = build_xbeach_environment(xbeach_exe)

            with subprocess.Popen(
                [str(xbeach_exe)],
                cwd=input_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=run_env,
            ) as process:
                output, _ = process.communicate()

            if process.returncode != 0:
                raise RuntimeError(
                    f"XBeach failed for the {scenario_name} "
                    f"(exit code {process.returncode}):\n{output}"
                )

            output_file = Path(input_path) / "xboutput.nc"
            if not output_file.is_file() or output_file.stat().st_size == 0:
                output_tail = "\n".join(output.splitlines()[-40:])
                raise RuntimeError(
                    f"XBeach reported success for the {scenario_name}, but did "
                    f"not create a non-empty NetCDF output file at {output_file}. "
                    "Check the XBeach build's NetCDF support and outputformat "
                    f"setting. Final solver output:\n{output_tail}"
                )

        scenarios = {
            False: "baseline scenario",
            True: "restored scenario",
        }
        self._report_progress(
            progress_callback,
            "Running baseline and restored XBeach scenarios concurrently "
            "(two solver processes)",
        )
        started_at = time.monotonic()
        failures = []
        with ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="xbeach"
        ) as executor:
            future_scenarios = {
                executor.submit(run_xbeach, after_restoration): scenario_name
                for after_restoration, scenario_name in scenarios.items()
            }
            pending = set(future_scenarios)
            while pending:
                completed, pending = wait(
                    pending,
                    timeout=XBEACH_PROGRESS_INTERVAL_SECONDS,
                    return_when=FIRST_COMPLETED,
                )
                for future in completed:
                    scenario_name = future_scenarios[future]
                    try:
                        future.result()
                    except (OSError, RuntimeError) as error:
                        failures.append((scenario_name, error))
                        self._report_progress(
                            progress_callback,
                            f"XBeach failed for the {scenario_name}: {error}",
                        )
                    else:
                        self._report_progress(
                            progress_callback,
                            f"XBeach finished for the {scenario_name}",
                        )

                if pending:
                    elapsed = time.monotonic() - started_at
                    running_scenarios = ", ".join(
                        future_scenarios[future] for future in pending
                    )
                    self._report_progress(
                        progress_callback,
                        f"XBeach is still running for {running_scenarios} "
                        f"({elapsed:.0f}s elapsed)",
                    )

        if failures:
            failure_details = "\n".join(
                f"{scenario_name}: {error}"
                for scenario_name, error in failures
            )
            raise RuntimeError(
                f"XBeach failed for {len(failures)} scenario(s):\n"
                f"{failure_details}"
            ) from failures[0][1]

        self._report_progress(progress_callback, "Analyzing baseline XBeach results")
        self.xbeach_results_analyzer.analyze(after_restoration=False)
        self.flooded_area_before = self.xbeach_results_analyzer.flooded_area

        self._report_progress(progress_callback, "Analyzing restored-scenario results")
        self.xbeach_results_analyzer.analyze(after_restoration=True)
        self.flooded_area_after = self.xbeach_results_analyzer.flooded_area

        self._report_progress(progress_callback, "Computing project benefits")
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
