from statistics import median
from typing import Mapping, Optional, Sequence


def estimate_runtime_seconds(
    grid_cells: int, completed_runs: Sequence[Mapping[str, float]]
) -> Optional[float]:
    """Scale prior end-to-end runtimes by grid size as a rough first estimate."""
    if grid_cells <= 0:
        raise ValueError("grid_cells must be positive")

    seconds_per_cell = [
        run["runtime_seconds"] / run["grid_cells"]
        for run in completed_runs
        if run.get("runtime_seconds", 0) > 0 and run.get("grid_cells", 0) > 0
    ]
    if not seconds_per_cell:
        return None

    return median(seconds_per_cell) * grid_cells


def format_runtime(seconds: float) -> str:
    total_seconds = max(0, round(seconds))
    hours, remaining_seconds = divmod(total_seconds, 3600)
    minutes, remaining_seconds = divmod(remaining_seconds, 60)

    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {remaining_seconds:02d} s"
    return f"{remaining_seconds} s"
