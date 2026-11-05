import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


def analytical_transmission(thickness, sigma):
    if not math.isfinite(thickness) or thickness <= 0:
        raise ValueError("Thickness must be positive and finite.")
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("The cross section must be positive and finite.")
    return math.exp(-sigma * thickness)


def arguments_from(command_line=None):
    parser = argparse.ArgumentParser(description="First OpenMC verification: normally incident transmission through a purely absorbing slab.")
    parser.add_argument("--thickness", type=float, default=1.0)
    parser.add_argument("--sigma", type=float, default=1.0)
    parser.add_argument("--batches", type=int, default=50)
    parser.add_argument("--particles", type=int, default=2000)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261104)
    parser.add_argument("--output", type=Path, default=Path("runs/first-benchmark"))
    parser.add_argument("--plan", action="store_true", help="Print the configuration and analytical reference without running OpenMC.")
    arguments = parser.parse_args(command_line)
    try:
        analytical_transmission(arguments.thickness, arguments.sigma)
    except ValueError as error:
        parser.error(str(error))
    if arguments.batches < 30 or arguments.particles < 1 or arguments.threads < 1:
        parser.error("Use at least 30 batches, a positive particle count, and a positive thread count.")
    if not 1 <= arguments.seed < 2 ** 63:
        parser.error("Seed must be an integer between 1 and 2^63 - 1.")
    return arguments


def build_model(openmc, numpy, arguments, output):
    groups = openmc.mgxs.EnergyGroups([0.0, 20.0e6])
    data = openmc.XSdata("ideal_absorber", groups)
    data.order = 0
    data.set_total([arguments.sigma])
    data.set_absorption([arguments.sigma])
    data.set_scatter_matrix(numpy.zeros((1, 1, 1)))
    library = openmc.MGXSLibrary(groups)
    library.add_xsdata(data)
    library.export_to_hdf5(output / "mgxs.h5")

    absorber = openmc.Material(name="Ideal purely absorbing material")
    absorber.add_macroscopic("ideal_absorber")
    absorber.set_density("macro", 1.0)
    absorber.temperature = 294.0
    materials = openmc.Materials([absorber])
    materials.cross_sections = str((output / "mgxs.h5").resolve())

    left = openmc.XPlane(x0=-1.0, boundary_type="vacuum")
    entrance = openmc.XPlane(x0=0.0)
    right = openmc.XPlane(x0=arguments.thickness, boundary_type="vacuum")
    upstream = openmc.Cell(name="Upstream void", region=+left & -entrance)
    slab = openmc.Cell(name="Absorber slab", fill=absorber, region=+entrance & -right)
    geometry = openmc.Geometry([upstream, slab])

    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((-0.5, 0.0, 0.0))
    source.angle = openmc.stats.Monodirectional((1.0, 0.0, 0.0))
    source.energy = openmc.stats.Discrete([1.0e6], [1.0])
    settings = openmc.Settings()
    settings.run_mode = "fixed source"
    settings.energy_mode = "multi-group"
    settings.survival_biasing = False
    settings.batches = arguments.batches
    settings.particles = arguments.particles
    settings.seed = arguments.seed
    settings.source = source

    transmission = openmc.Tally(name="transmission")
    transmission.filters = [openmc.SurfaceFilter(right)]
    transmission.scores = ["current"]
    reflection = openmc.Tally(name="reflection_signed")
    reflection.filters = [openmc.SurfaceFilter(left)]
    reflection.scores = ["current"]
    absorption = openmc.Tally(name="absorption")
    absorption.filters = [openmc.CellFilter(slab)]
    absorption.scores = ["absorption"]
    absorption.estimator = "analog"
    return openmc.Model(
        geometry=geometry,
        materials=materials,
        settings=settings,
        tallies=openmc.Tallies([transmission, reflection, absorption]),
    )


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(command_line=None):
    arguments = arguments_from(command_line)
    reference = analytical_transmission(arguments.thickness, arguments.sigma)
    configuration = {
        "thickness_cm": arguments.thickness,
        "sigma_t_per_cm": arguments.sigma,
        "sigma_a_per_cm": arguments.sigma,
        "sigma_s_per_cm": 0.0,
        "temperature_K": 294.0,
        "incident_energy_eV": 1.0e6,
        "batches": arguments.batches,
        "particles_per_batch": arguments.particles,
        "histories": arguments.batches * arguments.particles,
        "seed": arguments.seed,
        "threads": arguments.threads,
        "analytical_transmission": reference,
        "observable": "Exit current per source neutron; total and zero-collision transmission coincide in this purely absorbing model.",
    }
    if arguments.plan:
        print(json.dumps({"status": "plan_only_no_transport_results", "configuration": configuration}, indent=2, allow_nan=False))
        return
    if arguments.output.exists():
        raise SystemExit("Output already exists. Choose a new --output directory to preserve previous results.")
    try:
        import numpy
        import openmc
    except ImportError as error:
        raise SystemExit(f"OpenMC and NumPy must be available inside the Docker image. Use run.ps1. Details: {error}") from None
    version = subprocess.run(["openmc", "--version"], capture_output=True, text=True, check=True)
    output = arguments.output.resolve()
    output.mkdir(parents=True)
    (output / "configuration.json").write_text(json.dumps(configuration, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    model = build_model(openmc, numpy, arguments, output)
    started = time.perf_counter()
    statepoint_path = model.run(cwd=output, threads=arguments.threads)
    elapsed = time.perf_counter() - started
    with openmc.StatePoint(statepoint_path) as statepoint:
        transmission = statepoint.get_tally(name="transmission")
        reflection = statepoint.get_tally(name="reflection_signed")
        absorption = statepoint.get_tally(name="absorption")
        estimate = transmission.mean.item()
        standard_error = transmission.std_dev.item()
        reflected = -reflection.mean.item()
        absorbed = absorption.mean.item()
    residual = (estimate - reference) / standard_error if standard_error > 0 else None
    balance_error = abs(estimate + reflected + absorbed - 1.0)
    results = {
        "status": "transport_completed",
        "configuration": configuration,
        "transmission": estimate,
        "transmission_standard_error": standard_error,
        "reflection": reflected,
        "absorption": absorbed,
        "particle_balance": estimate + reflected + absorbed,
        "balance_absolute_error": balance_error,
        "standardized_transmission_residual": residual,
        "review_needed": balance_error > 1e-8 or residual is None or abs(residual) > 3,
        "elapsed_seconds": elapsed,
        "openmc_python_version": openmc.__version__,
        "openmc_executable_version": version.stdout.strip(),
        "numpy_version": numpy.__version__,
        "python_version": sys.version,
        "platform": platform.platform(),
        "container_image": os.environ.get("OPENMC_STARTER_IMAGE", "not_recorded"),
        "benchmark_source_sha256": file_hash(Path(__file__)),
        "statepoint_filename": Path(statepoint_path).name,
        "input_sha256": {path.name: file_hash(path) for path in sorted(output.iterdir()) if path.suffix in (".xml", ".h5") and not path.name.startswith(("statepoint", "summary"))},
        "statepoint_sha256": file_hash(Path(statepoint_path)),
        "limitations": "An ideal one-group software verification benchmark, not a water/graphite calculation or experimental validation. Standard errors are OpenMC batch estimates, not 95% confidence limits. A residual beyond three standard errors needs investigation, not selective rerunning.",
    }
    (output / "results.json").write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    with (output / "results.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = ("transmission", "transmission_standard_error", "reflection", "absorption", "particle_balance", "standardized_transmission_residual")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({field: results[field] for field in fields})
    print(f"\nOpenMC transmission: {estimate:.8f}")
    print(f"Standard error:       {standard_error:.8f}")
    print(f"Analytical reference: {reference:.8f}")
    print(f"Particle balance:     {results['particle_balance']:.8f}")
    print(f"Saved actual outputs: {output}")
    if results["review_needed"]:
        print("REVIEW NEEDED: preserve this run and inspect its diagnostics before drawing conclusions.")
    if balance_error > 1e-8:
        raise SystemExit("Particle balance failed for this nonmultiplying analogue benchmark. Preserve the run for diagnosis.")


if __name__ == "__main__":
    main()
