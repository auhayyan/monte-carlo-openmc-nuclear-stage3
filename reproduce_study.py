import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys

from audit_statepoint import audit_run, check


def run_step(root, output, script, arguments):
    print(f"Running {script}", flush=True)
    with (output / (Path(script).stem + ".log")).open("w", encoding="utf-8") as stream:
        subprocess.run([sys.executable, str(root / script), *map(str, arguments)], stdout=stream, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description="Check the saved runs and rebuild the analysis, figures, and LaTeX sources without rerunning OpenMC.")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = arguments.output.resolve()
    if output.exists():
        parser.error("Choose a new output folder to preserve previous results.")
    output.mkdir(parents=True)
    absorber_folder = root / "data" / "absorber-study"
    folders = sorted(absorber_folder.glob("case-*"), key=lambda folder: int(folder.name.split("-")[-1]))
    check(len(folders) == 15, "Expected all 15 absorbing production cases")
    thicknesses = [0.25, 0.5, 1.0, 2.0, 3.0]
    image = (root / "image-lock.txt").read_text(encoding="utf-8-sig").strip()
    audits = []
    for index, folder in enumerate(folders):
        recorded = json.loads((folder / "results.json").read_text(encoding="utf-8-sig"))
        configuration = json.loads((folder / "configuration.json").read_text(encoding="utf-8-sig"))
        check(configuration == recorded["configuration"], "Absorber configuration records disagree")
        check(configuration["seed"] == 2026110401 + index, "Unexpected absorber seed order")
        check(configuration["thickness_cm"] == thicknesses[index // 3], "Unexpected absorber thickness")
        check(configuration["sigma_t_per_cm"] == configuration["sigma_a_per_cm"] == 1.0, "Unexpected absorbing cross sections")
        check(configuration["sigma_s_per_cm"] == 0.0, "Absorbing control contains scattering")
        check(configuration["batches"] == 100 and configuration["particles_per_batch"] == 10000, "Unexpected absorber histories")
        check(recorded["container_image"] == image, "Absorber container digest differs from the project lock")
        audits.append(audit_run(folder, source_override=absorber_folder / "original_source.py"))
    absorber_audits = output / "absorber-audits.json"
    absorber_audits.write_text(json.dumps(audits, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print("Audited all 15 absorbing cases", flush=True)
    study = output / "study"
    run_step(root, output, "analyze_campaign.py", ["--campaign", root / "data" / "scattering-study", "--output", study])
    run_step(root, output, "plot_study.py", ["--analysis", study / "analysis.json", "--absorber-audits", absorber_audits, "--output", study / "figures"])
    run_step(root, output, "build_report.py", ["--analysis", study / "analysis.json", "--pdf", output / "Stage3_OpenMC_Report.pdf", "--latex-output", output / "report" / "latex", "--source-only"])
    verification = {
        "status": "all_saved_production_runs_audited_and_outputs_regenerated",
        "absorbing_cases": len(audits),
        "scattering_cases": 15,
        "total_production_histories": 30000000,
        "python": platform.python_version(),
        "packages": {name: version(name) for name in ("numpy", "h5py", "matplotlib")},
        "transport_rerun": False,
        "scope": "The original OpenMC statepoints were checked. The numerical reference, figures, and LaTeX sources were regenerated.",
    }
    (output / "reproduction.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Reproduction complete: {output}", flush=True)


if __name__ == "__main__":
    main()
