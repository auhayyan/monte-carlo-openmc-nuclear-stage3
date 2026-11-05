import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

from audit_statepoint import audit_run, check
from reference_transport import solve_slab


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(records):
    summaries = []
    definitions = (
        ("transmission", "transmission"),
        ("uncollided_transmission", "uncollided_transmission"),
        ("reflection", "reflection_signed"),
        ("absorption", "absorption"),
    )
    for thickness in sorted({record["configuration"]["thickness_cm"] for record in records}):
        group = [record for record in records if record["configuration"]["thickness_cm"] == thickness]
        check(len({record["configuration"]["seed"] for record in group}) == len(group), "Duplicate seed within one thickness group")
        row = {"thickness_cm": thickness, "repetitions": len(group), "total_histories": sum(record["audit"]["actual_histories"] for record in group)}
        for field, tally_name in definitions:
            sign = -1 if tally_name == "reflection_signed" else 1
            estimates = [sign * record["audit"]["tallies_reconstructed_from_statepoint"][tally_name]["mean"] for record in group]
            errors = [record["audit"]["tallies_reconstructed_from_statepoint"][tally_name]["standard_error"] for record in group]
            row[field] = statistics.mean(estimates)
            row[field + "_standard_error"] = math.sqrt(sum(error ** 2 for error in errors)) / len(group)
            row[field + "_between_seed_sd"] = statistics.stdev(estimates) if len(group) > 1 else None
        reference = math.exp(-group[0]["configuration"]["sigma_t_per_cm"] * thickness)
        row["analytical_uncollided_reference"] = reference
        row["standardized_uncollided_mean_residual"] = (row["uncollided_transmission"] - reference) / row["uncollided_transmission_standard_error"]
        row["scattered_transmission_mean"] = row["transmission"] - row["uncollided_transmission"]
        row["scattered_share_of_exit_mean"] = row["scattered_transmission_mean"] / row["transmission"]
        row["particle_balance"] = row["transmission"] + row["reflection"] + row["absorption"]
        summaries.append(row)
    return summaries


def main():
    parser = argparse.ArgumentParser(description="Audit and summarize the complete scattering campaign, then compare an independent numerical transport solution.")
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        parser.error("Choose a new output directory to preserve previous analysis.")
    manifest = json.loads((arguments.campaign / "campaign.json").read_text(encoding="utf-8-sig"))
    check(manifest["status"] == "completed", "Campaign is not marked completed")
    folders = sorted(path for path in arguments.campaign.glob("case-*") if path.is_dir())
    expected_cases = len(manifest["thicknesses_cm"]) * manifest["repetitions_per_thickness"]
    check(len(folders) == expected_cases == manifest["completed_cases"], "Unexpected number of case folders")
    records = []
    input_hashes = {"campaign.json": digest(arguments.campaign / "campaign.json")}
    for case_index, folder in enumerate(folders):
        recorded = json.loads((folder / "results.json").read_text(encoding="utf-8"))
        configuration = recorded["configuration"]
        configuration_file = json.loads((folder / "configuration.json").read_text(encoding="utf-8"))
        check(configuration == configuration_file, "Configuration files disagree")
        check(configuration["seed"] == manifest["first_seed"] + case_index, "Unexpected case seed")
        check(configuration["thickness_cm"] == manifest["thicknesses_cm"][case_index // manifest["repetitions_per_thickness"]], "Unexpected thickness ordering")
        check(configuration["sigma_t_per_cm"] == manifest["sigma_t_per_cm"], "Total cross section differs from campaign")
        check(configuration["scatter_ratio"] == manifest["scatter_ratio"], "Scattering ratio differs from campaign")
        check(configuration["batches"] == manifest["batches"] and configuration["particles_per_batch"] == manifest["particles_per_batch"], "Run histories differ from campaign")
        check(recorded["benchmark_source_sha256"] == manifest["benchmark_sha256"], "Case source differs from campaign source")
        check(recorded["container_image"] == manifest["image"], "Case image differs from campaign image")
        audit = audit_run(folder)
        check(audit["tallies_reconstructed_from_statepoint"]["uncollided_transmission"]["mean"] <= audit["tallies_reconstructed_from_statepoint"]["transmission"]["mean"] + 1e-12, "Uncollided current exceeds total")
        records.append({"case": folder.name, "configuration": configuration, "recorded_results": recorded, "audit": audit})
        input_hashes[folder.name + "/results.json"] = digest(folder / "results.json")
        print(f"Audited {folder.name}", flush=True)
    summaries = summarize(records)
    convergence = []
    reference_comparisons = []
    for summary in summaries:
        thickness = summary["thickness_cm"]
        refinements = []
        for cells, directions in ((64, 32), (128, 64), (256, 128), (512, 128), (512, 256)):
            reference = solve_slab(thickness, cells=cells, positive_directions=directions)
            convergence.append(reference)
            refinements.append(reference)
        final = refinements[-1]
        spatial_delta = max(abs(refinements[-2][field] - refinements[-3][field]) for field in ("transmission", "reflection", "absorption"))
        angular_delta = max(abs(final[field] - refinements[-2][field]) for field in ("transmission", "reflection", "absorption"))
        for field in ("transmission", "reflection", "absorption"):
            reference_comparisons.append({
                "thickness_cm": thickness,
                "quantity": field,
                "openmc_mean": summary[field],
                "openmc_mean_standard_error": summary[field + "_standard_error"],
                "deterministic_reference": final[field],
                "standardized_difference": (summary[field] - final[field]) / summary[field + "_standard_error"],
                "last_spatial_refinement_max_absolute_change": spatial_delta,
                "last_angular_refinement_max_absolute_change": angular_delta,
            })
        print(f"Computed independent reference at {thickness:g} cm", flush=True)
    individual_residuals = [record["audit"]["standardized_uncollided_residual"] for record in records]
    maximum_balance_error = max(abs(record["audit"]["particle_balance"] - 1) for record in records)
    report = {
        "status": "audited_original_campaign_and_computed_independent_reference",
        "campaign": str(arguments.campaign),
        "cases": len(records),
        "total_histories": sum(record["audit"]["actual_histories"] for record in records),
        "original_source_and_data_hashes_match": True,
        "input_manifest_sha256": input_hashes,
        "analysis_source_sha256": digest(Path(__file__)),
        "auditor_source_sha256": digest(Path(__file__).with_name("audit_statepoint.py")),
        "reference_source_sha256": digest(Path(__file__).with_name("reference_transport.py")),
        "max_absolute_uncollided_individual_residual": max(abs(value) for value in individual_residuals),
        "uncollided_individual_residuals_outside_two_se": sum(abs(value) > 2 for value in individual_residuals),
        "uncollided_individual_residuals_outside_three_se": sum(abs(value) > 3 for value in individual_residuals),
        "max_absolute_particle_balance_error": maximum_balance_error,
        "max_absolute_independent_reference_residual": max(abs(row["standardized_difference"]) for row in reference_comparisons),
        "mean_uncertainty_method": "Equal-weight independent-seed means, with sqrt(sum(SE_i^2))/3 from the OpenMC batch standard errors.",
        "reference_method": "Analytic uncollided beam; one-group isotropic collided flux solved by constant-source step characteristics with symmetric double Gauss-Legendre quadrature. Mesh and angular refinements are recorded separately. Last-step differences are convergence diagnostics, not rigorous error bounds.",
        "pilot_handling": "The earlier single scattering pilot is preserved separately and excluded from the preplanned three-repetition production means.",
        "limitations": "Artificial one-group material, one scattering ratio, one incident direction, five thicknesses. No real-material energy dependence, experimental validation, or reactor criticality. No covariance-derived uncertainty is assigned to total-minus-uncollided or its ratio.",
        "summary": summaries,
        "reference_comparisons": reference_comparisons,
    }
    arguments.output.mkdir(parents=True)
    write_json(arguments.output / "analysis.json", report)
    write_json(arguments.output / "run-audits.json", records)
    write_csv(arguments.output / "summary.csv", summaries)
    write_csv(arguments.output / "reference-comparison.csv", reference_comparisons)
    write_csv(arguments.output / "reference-convergence.csv", convergence)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
