import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def save_figure(figure, root, name):
    figure.tight_layout(rect=(0, 0.045, 1, 1))
    figure.savefig(root / (name + ".png"), dpi=200)
    figure.savefig(root / (name + ".svg"))
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description="Create scientific figures from the audited OpenMC campaigns.")
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--absorber-audits", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        parser.error("Choose a new figure directory to preserve previous outputs.")
    data = json.loads(arguments.analysis.read_text(encoding="utf-8"))
    absorber = json.loads(arguments.absorber_audits.read_text(encoding="utf-8"))
    summaries = data["summary"]
    thicknesses = [row["thickness_cm"] for row in summaries]
    absorber_residuals = []
    for thickness in thicknesses:
        rows = [row for row in absorber if math.isclose(row["uncollided_reference"], math.exp(-thickness), rel_tol=1e-12)]
        estimates = [row["tallies_reconstructed_from_statepoint"]["transmission"]["mean"] for row in rows]
        errors = [row["tallies_reconstructed_from_statepoint"]["transmission"]["standard_error"] for row in rows]
        standard_error = math.sqrt(sum(error ** 2 for error in errors)) / len(rows)
        absorber_residuals.append((statistics.mean(estimates) - math.exp(-thickness)) / standard_error)
    arguments.output.mkdir(parents=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    colors = {"transmission": "#176b87", "uncollided_transmission": "#bf6900", "reflection": "#8e4c76", "absorption": "#547044"}
    figure, (axes, residual_axes) = plt.subplots(2, 1, figsize=(8, 6.2), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    dense = [3 * index / 300 for index in range(301)]
    axes.plot(dense, [math.exp(-value) for value in dense], linestyle="--", color="#777777", linewidth=1.5, label="Analytical zero-collision probability")
    for field, label, marker in (("transmission", "Total exit transmission", "o"), ("uncollided_transmission", "Zero-collision exit transmission", "s")):
        axes.errorbar(thicknesses, [row[field] for row in summaries], yerr=[2 * row[field + "_standard_error"] for row in summaries], fmt=marker + "-", color=colors[field], markersize=4, capsize=3, label=label)
    axes.set(yscale="log", ylabel="Probability per source neutron", title="Total and uncollided transmission")
    axes.legend(fontsize=8.5)
    axes.grid(which="both", alpha=0.2)
    residual_axes.axhspan(-2, 2, color="#176b87", alpha=0.10)
    residual_axes.axhline(0, color="#777777", linewidth=1)
    residual_axes.scatter(thicknesses, [row["standardized_uncollided_mean_residual"] for row in summaries], color=colors["transmission"], s=28, label="Scattering case: T0")
    residual_axes.scatter(thicknesses, absorber_residuals, color="#777777", marker="^", s=27, label="Absorbing control: T")
    residual_axes.set(xlabel="Slab thickness (cm)", ylabel="Residual / SE", ylim=(-3, 3))
    residual_axes.legend(fontsize=8, ncol=2, loc="lower left")
    residual_axes.grid(alpha=0.2)
    figure.text(0.5, 0.012, "Sigma_t = 1 / cm; scattering case Sigma_s = 0.8, Sigma_a = 0.2 / cm. Error bars: +/-2 combined SE.", ha="center", fontsize=8)
    save_figure(figure, arguments.output, "transmission_comparison")

    figure, axes = plt.subplots(figsize=(8, 4.8))
    for field, label, marker in (("transmission", "Transmission", "o"), ("reflection", "Reflection", "s"), ("absorption", "Absorption", "^")):
        axes.errorbar(thicknesses, [row[field] for row in summaries], yerr=[2 * row[field + "_standard_error"] for row in summaries], fmt=marker + "-", color=colors[field], markersize=4, capsize=3, label="OpenMC " + label)
        references = [row for row in data["reference_comparisons"] if row["quantity"] == field]
        axes.plot([row["thickness_cm"] for row in references], [row["deterministic_reference"] for row in references], "--", color=colors[field], alpha=0.65)
    axes.set(xlabel="Slab thickness (cm)", ylabel="Probability per source neutron", ylim=(0, 1), title="Particle fates in the ideal scattering slab")
    axes.legend(fontsize=9)
    axes.grid(alpha=0.2)
    figure.text(0.5, 0.012, "Points: three-seed OpenMC means +/-2 combined SE. Dashed lines: independent numerical references at the same thicknesses.", ha="center", fontsize=7.8)
    save_figure(figure, arguments.output, "particle_fates")

    figure, axes = plt.subplots(figsize=(8, 4.8))
    axes.axhspan(-2, 2, color="#176b87", alpha=0.10, label="Pointwise +/-2-SE reference band")
    axes.axhline(0, color="#777777", linewidth=1)
    for field, label, marker in (("transmission", "Transmission", "o"), ("reflection", "Reflection", "s"), ("absorption", "Absorption", "^")):
        references = [row for row in data["reference_comparisons"] if row["quantity"] == field]
        axes.plot([row["thickness_cm"] for row in references], [row["standardized_difference"] for row in references], marker, color=colors[field], markersize=5, label=label)
    axes.set(xlabel="Slab thickness (cm)", ylabel="(OpenMC mean - numerical reference) / SE", ylim=(-3.3, 3.3), title="OpenMC compared with the numerical solution")
    axes.legend(fontsize=8.5, ncol=2)
    axes.grid(alpha=0.2)
    figure.text(0.5, 0.012, "The T and R means at 2 cm differ by +2.43 and -2.60 SE. Outcomes are correlated through particle balance.", ha="center", fontsize=8)
    save_figure(figure, arguments.output, "reference_residuals")
    manifest = {
        "analysis_sha256": hashlib.sha256(arguments.analysis.read_bytes()).hexdigest(),
        "absorber_audits_sha256": hashlib.sha256(arguments.absorber_audits.read_bytes()).hexdigest(),
        "plot_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "matplotlib_version": matplotlib.__version__,
        "figures_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(arguments.output.iterdir()) if path.suffix in (".png", ".svg")},
    }
    (arguments.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Saved three figures to {arguments.output}")


if __name__ == "__main__":
    main()
