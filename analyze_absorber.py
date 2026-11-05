import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


def summarize(records):
    summaries = []
    for thickness in sorted({float(row["thickness_cm"]) for row in records}):
        group = [row for row in records if float(row["thickness_cm"]) == thickness]
        seeds = [row["seed"] for row in group]
        if len(set(seeds)) != len(seeds):
            raise ValueError("Repeated seeds at one thickness cannot be treated as independent repetitions.")
        estimates = [float(row["transmission"]) for row in group]
        errors = [float(row["standard_error"]) for row in group]
        if any(not math.isfinite(value) or value <= 0 for value in errors):
            raise ValueError("Each run must have a finite positive reported standard error.")
        reference = math.exp(-thickness)
        if any(not math.isclose(float(row["analytical_reference"]), reference, rel_tol=1e-12, abs_tol=1e-14) for row in group):
            raise ValueError("The table does not match the specified Sigma_t = 1 per cm reference.")
        mean = statistics.mean(estimates)
        combined_error = math.sqrt(sum(error ** 2 for error in errors)) / len(group)
        summaries.append({
            "thickness_cm": thickness,
            "repetitions": len(group),
            "mean_transmission": mean,
            "combined_standard_error": combined_error,
            "analytical_reference": reference,
            "standardized_mean_residual": (mean - reference) / combined_error,
            "sample_sd_across_runs": statistics.stdev(estimates) if len(group) > 1 else None,
        })
    return summaries


def main():
    parser = argparse.ArgumentParser(description="Analyze the user-reported ideal absorbing-slab thickness table.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        parser.error("Choose a new output directory to preserve previous analysis.")
    with arguments.input.open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream))
    if not records:
        parser.error("The input table has no observations.")
    summaries = summarize(records)
    arguments.output.mkdir(parents=True)
    with (arguments.output / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    maximum_residual = max(abs((float(row["transmission"]) - float(row["analytical_reference"])) / float(row["standard_error"])) for row in records)
    maximum_balance_error = max(abs(float(row["particle_balance"]) - 1) for row in records)
    diagnostics = {
        "source": "Pasted summary table only. Use reproduce_study.py to check the original statepoints.",
        "input_sha256": hashlib.sha256(arguments.input.read_bytes()).hexdigest(),
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "observations": len(records),
        "max_absolute_individual_standardized_residual": maximum_residual,
        "max_absolute_particle_balance_error": maximum_balance_error,
        "mean_uncertainty_method": "Equal-weight means of independent seeded runs; SE(mean) = sqrt(sum(SE_i^2)) / repetitions.",
        "limitations": "Single ideal absorbing model, five thicknesses, and three repetitions per thickness; no verification of scattering, energy dependence, or real materials. Agreement does not independently validate physical cross sections.",
    }
    (arguments.output / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    figure, (axes, residual_axes) = plt.subplots(2, 1, figsize=(8, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    dense = [3 * index / 300 for index in range(301)]
    axes.plot(dense, [math.exp(-value) for value in dense], color="#bf6900", linewidth=2, label="Analytical uncollided transmission")
    axes.scatter([float(row["thickness_cm"]) for row in records], [float(row["transmission"]) for row in records], color="#72828c", s=22, alpha=0.55, label="Individual seeded runs")
    axes.errorbar([row["thickness_cm"] for row in summaries], [row["mean_transmission"] for row in summaries], yerr=[2 * row["combined_standard_error"] for row in summaries], fmt="o", color="#176b87", markersize=5, capsize=4, label="Three-run mean +/- 2 combined SE")
    axes.set(yscale="log", ylabel="Transmission per source neutron", title="OpenMC absorbing-slab verification")
    axes.legend(fontsize=9)
    axes.grid(which="both", alpha=0.2)
    residual_axes.axhspan(-2, 2, color="#176b87", alpha=0.12)
    residual_axes.axhline(0, color="#777777", linewidth=1)
    residual_axes.scatter([row["thickness_cm"] for row in summaries], [row["standardized_mean_residual"] for row in summaries], color="#176b87", s=30)
    residual_axes.set(xlabel="Slab thickness (cm), total cross section = 1 / cm", ylabel="Mean residual / SE", ylim=(-3, 3))
    residual_axes.grid(alpha=0.2)
    figure.text(0.5, 0.012, "Source: user-reported summary; 3 seeded runs per thickness. Error bars are pointwise.", ha="center", fontsize=9)
    figure.tight_layout(rect=(0, 0.035, 1, 1))
    figure.savefig(arguments.output / "absorber_verification.png", dpi=200)
    figure.savefig(arguments.output / "absorber_verification.svg")
    plt.close(figure)
    print(json.dumps({"summary": summaries, "diagnostics": diagnostics}, indent=2))


if __name__ == "__main__":
    main()
