import argparse
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "data/coral/original_benthic_map.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/coral/original_benthic_coral.gpkg"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an indexed GeoPackage containing coral/algae features."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "ogr2ogr",
            "-f",
            "GPKG",
            "-overwrite",
            "-nln",
            "coral",
            "-where",
            "class = 'Coral/Algae'",
            "-lco",
            "SPATIAL_INDEX=YES",
            str(args.output),
            str(args.source),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
