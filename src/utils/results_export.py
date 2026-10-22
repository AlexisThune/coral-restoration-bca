import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile


def build_results_archive(results, output_paths, metadata):
    archive_buffer = BytesIO()
    figures = []
    text_results = []

    with ZipFile(archive_buffer, "w", compression=ZIP_STORED) as archive:
        for index, result in enumerate(results, start=1):
            if result["type"] == "plottable":
                figure_path = f"figures/figure_{index}.png"
                figure_buffer = BytesIO()
                result["data"].savefig(
                    figure_buffer, format="png", dpi=160, bbox_inches="tight"
                )
                archive.writestr(figure_path, figure_buffer.getvalue())
                figures.append(figure_path)
            elif result["type"] == "writable":
                text_results.append(result["data"])

        for scenario_name, output_path in output_paths:
            scenario_dir = Path(output_path)
            if not scenario_dir.is_dir():
                raise FileNotFoundError(
                    f"Simulation output directory not found: {scenario_dir}"
                )

            scenario_files = [
                path for path in scenario_dir.rglob("*") if path.is_file()
            ]
            if not scenario_files:
                raise FileNotFoundError(
                    f"No simulation input or output files found in {scenario_dir}"
                )

            for path in scenario_files:
                archive.write(
                    path,
                    arcname=f"xbeach/{scenario_name}/{path.relative_to(scenario_dir)}",
                )

        summary = {
            "metadata": metadata,
            "results": text_results,
            "figures": figures,
            "xbeach_scenarios": [name for name, _ in output_paths],
        }
        archive.writestr(
            "summary.json",
            json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        )

    return archive_buffer.getvalue()
