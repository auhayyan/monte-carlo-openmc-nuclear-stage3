import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import h5py


def check(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_run(folder, source_override=None):
    recorded = json.loads((folder / "results.json").read_text(encoding="utf-8-sig"))
    configuration = recorded["configuration"]
    source_path = folder / "benchmark_source.py"
    if not source_path.exists():
        check(source_override is not None, "No archived source or explicit original-source file was supplied")
        source_path = Path(source_override)
    check(digest(source_path) == recorded["benchmark_source_sha256"], "Original source hash mismatch")
    for filename, expected in recorded["input_sha256"].items():
        check(digest(folder / filename) == expected, f"Input hash mismatch: {filename}")
    statepoint_path = folder / recorded["statepoint_filename"]
    check(digest(statepoint_path) == recorded["statepoint_sha256"], "Statepoint hash mismatch")
    model = ET.parse(folder / "model.xml").getroot()
    filters = model.findall("./tallies/filter")
    filter_map = {item.get("id"): item for item in filters}
    check(len(filter_map) == len(filters), "Duplicate filter IDs in serialized model")
    tally_definitions = {item.get("name"): item for item in model.findall("./tallies/tally")}
    for tally in tally_definitions.values():
        check(all(filter_id in filter_map for filter_id in tally.findtext("filters").split()), "Unknown filter reference in model")
    direct_uncollided = "uncollided_transmission" in tally_definitions
    if direct_uncollided:
        uncollided_filters = [filter_map[filter_id] for filter_id in tally_definitions["uncollided_transmission"].findtext("filters").split()]
        check(any(item.get("type") == "collision" and item.findtext("bins").strip() == "0" for item in uncollided_filters), "Uncollided tally does not select collision count zero")
    else:
        check(configuration["sigma_s_per_cm"] == 0, "A scattering case is missing its uncollided tally")
    materials = model.findall("./materials/material")
    check(len(materials) == 1, "Auditor expects one homogeneous material")
    material_name = materials[0].find("macroscopic").get("name")
    density = materials[0].find("density")
    check(density.get("units") == "macro" and float(density.get("value")) == 1, "Unexpected macroscopic cross-section multiplier")
    surfaces = {item.get("id"): item for item in model.findall("./geometry/surface")}
    total_filters = [filter_map[filter_id] for filter_id in tally_definitions["transmission"].findtext("filters").split()]
    check(len(total_filters) == 1 and total_filters[0].get("type") == "surface", "Unexpected total-transmission filters")
    exit_surface = surfaces[total_filters[0].findtext("bins").strip()]
    check(exit_surface.get("type") == "x-plane" and exit_surface.get("boundary") == "vacuum", "Exit is not the expected vacuum x-plane")
    check(math.isclose(float(exit_surface.get("coeffs")), configuration["thickness_cm"], abs_tol=1e-14), "Exit position differs from slab thickness")
    if direct_uncollided:
        check(any(item.get("type") == "surface" and item.findtext("bins") == total_filters[0].findtext("bins") for item in uncollided_filters), "Total and uncollided tallies use different exit surfaces")
    check(model.findtext("./settings/run_mode") == "fixed source", "Unexpected run mode")
    check(model.findtext("./settings/energy_mode") == "multi-group", "Unexpected energy mode")
    check(model.findtext("./settings/survival_biasing") == "false", "Auditor expects analogue transport without survival biasing")
    check(model.find("./settings/source/angle").get("reference_uvw") == "1.0 0.0 0.0", "Unexpected incident source direction")
    coefficients = {}
    with h5py.File(folder / "mgxs.h5", "r") as library:
        material = library[material_name + "/294K"]
        for name, dataset in (("total", "total"), ("absorption", "absorption"), ("scattering", "scatter_data/scatter_matrix")):
            coefficients[name] = float(material[dataset][()].item())
    check(math.isclose(coefficients["total"], configuration["sigma_t_per_cm"], abs_tol=1e-14), "Total cross section differs from configuration")
    check(math.isclose(coefficients["absorption"], configuration["sigma_a_per_cm"], abs_tol=1e-14), "Absorption cross section differs from configuration")
    check(math.isclose(coefficients["scattering"], configuration["sigma_s_per_cm"], abs_tol=1e-14), "Scattering cross section differs from configuration")
    check(math.isclose(coefficients["total"], coefficients["absorption"] + coefficients["scattering"], abs_tol=1e-14), "Cross-section balance failed")
    tallies = {}
    with h5py.File(statepoint_path, "r") as statepoint:
        check(statepoint.attrs["filetype"].decode() == "statepoint", "Unexpected HDF5 file type")
        check(int(statepoint["n_batches"][()]) == configuration["batches"], "Batch count mismatch")
        check(int(statepoint["n_particles"][()]) == configuration["particles_per_batch"], "Particles per batch mismatch")
        check(int(statepoint["seed"][()]) == configuration["seed"], "Seed mismatch")
        for name, group in statepoint["tallies"].items():
            if not name.startswith("tally "):
                continue
            tally_name = group["name"][()].decode()
            realizations = int(group["n_realizations"][()])
            statistics = group["results"][()]
            check(statistics.shape == (1, 1, 2), "Reader expects single-bin tally sums and squared sums")
            mean = float(statistics[0, 0, 0]) / realizations
            variance = (float(statistics[0, 0, 1]) / realizations - mean ** 2) / (realizations - 1)
            tallies[tally_name] = {"mean": mean, "standard_error": math.sqrt(max(variance, 0.0)), "realizations": realizations}
    comparisons = [
        ("transmission", "transmission", "transmission_standard_error", 1),
        ("reflection_signed", "reflection", "reflection_standard_error", -1),
        ("absorption", "absorption", "absorption_standard_error", 1),
    ]
    if direct_uncollided:
        comparisons.append(("uncollided_transmission", "uncollided_transmission", "uncollided_transmission_standard_error", 1))
    else:
        tallies["uncollided_transmission"] = dict(tallies["transmission"])
    for tally_name, mean_field, error_field, sign in comparisons:
        check(math.isclose(sign * tallies[tally_name]["mean"], recorded[mean_field], rel_tol=1e-12, abs_tol=1e-14), f"Statepoint mean mismatch: {mean_field}")
        if error_field in recorded:
            check(math.isclose(tallies[tally_name]["standard_error"], recorded[error_field], rel_tol=1e-9, abs_tol=1e-13), f"Statepoint standard error mismatch: {error_field}")
    transmission = tallies["transmission"]["mean"]
    uncollided = tallies["uncollided_transmission"]["mean"]
    reflection = -tallies["reflection_signed"]["mean"]
    absorption = tallies["absorption"]["mean"]
    reference = math.exp(-configuration["sigma_t_per_cm"] * configuration["thickness_cm"])
    return {
        "status": "original_inputs_and_statepoint_checked",
        "run_folder": str(folder),
        "source_file_checked": str(source_path),
        "uncollided_tally_direct": direct_uncollided,
        "hashes_match": True,
        "serialized_filter_references_valid": True,
        "actual_cross_sections_per_cm": coefficients,
        "actual_histories": configuration["batches"] * configuration["particles_per_batch"],
        "tallies_reconstructed_from_statepoint": tallies,
        "particle_balance": transmission + reflection + absorption,
        "uncollided_reference": reference,
        "standardized_uncollided_residual": (uncollided - reference) / tallies["uncollided_transmission"]["standard_error"],
        "scattered_transmission_mean": transmission - uncollided,
        "scattered_share_of_exit_transmission": (transmission - uncollided) / transmission,
        "limitations": "This checks the saved run's inputs, filters, statistics and bookkeeping. It is not an independent rerun of transport or an experimental validation. No covariance-based uncertainty for the total-minus-uncollided difference is inferred.",
    }


def main():
    parser = argparse.ArgumentParser(description="Check a single-bin OpenMC slab run directly from its saved HDF5 statepoint and model.")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        parser.error("Choose a new audit output filename to preserve earlier checks.")
    result = audit_run(arguments.run)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
