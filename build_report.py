import argparse
import hashlib
import json
from pathlib import Path
import re

from latex_report import write_latex, compile_pdf


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Build the report from the checked runs and numerical reference.")
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-only", action="store_true", help="Write the LaTeX sources without compiling a PDF.")
    parser.add_argument("--compiler", help="Path to Tectonic or pdflatex; otherwise search PATH.")
    parser.add_argument("--latex-output", type=Path, default=root / "report" / "latex")
    arguments = parser.parse_args()
    data = json.loads(arguments.analysis.read_text(encoding="utf-8"))
    rows = []
    convergence = []
    for row in data["summary"]:
        values = [f"{row['thickness_cm']:g}"]
        values.extend(f"{row[field]:.6f} +/- {row[field + '_standard_error']:.6f}" for field in ("transmission", "uncollided_transmission", "reflection", "absorption"))
        rows.append("| " + " | ".join(values) + " |")
        reference = next(item for item in data["reference_comparisons"] if item["thickness_cm"] == row["thickness_cm"])
        convergence.append(f"| {row['thickness_cm']:g} | {reference['last_spatial_refinement_max_absolute_change']:.2e} | {reference['last_angular_refinement_max_absolute_change']:.2e} |")
    template_path = Path(__file__).with_name("report_template.md")
    manuscript = template_path.read_text(encoding="utf-8").replace("{{RESULTS_TABLE}}", "\n".join(rows)).replace("{{CONVERGENCE_TABLE}}", "\n".join(convergence))
    check_tokens = re.findall(r"\{\{[^}]+\}\}", manuscript)
    if check_tokens:
        raise ValueError(f"Unresolved manuscript fields: {check_tokens}")
    markdown_path = arguments.analysis.parent / "Stage3_Report.md"
    markdown_path.write_text(manuscript, encoding="utf-8", newline="\n")
    arguments.pdf.parent.mkdir(parents=True, exist_ok=True)
    latex = write_latex(manuscript, arguments.analysis.parent, arguments.latex_output, title="Neutron transmission and scattering in OpenMC", stage_label="Stage 3 | OpenMC slab transport")
    compiled = {} if arguments.source_only else compile_pdf(arguments.latex_output, arguments.pdf, compiler=arguments.compiler)
    manifest = {"analysis_sha256": hashlib.sha256(arguments.analysis.read_bytes()).hexdigest(), "template_sha256": hashlib.sha256(template_path.read_bytes()).hexdigest(), "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "latex_helper_sha256": hashlib.sha256(Path(__file__).with_name("latex_report.py").read_bytes()).hexdigest(), "latex": latex, "manuscript_sha256": hashlib.sha256(markdown_path.read_bytes()).hexdigest(), **compiled}
    (arguments.analysis.parent / "report-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"LaTeX source: {arguments.latex_output / 'main.tex'}")
    if not arguments.source_only:
        print(f"Created {arguments.pdf}")
    print(f"Editable manuscript: {markdown_path}")


if __name__ == "__main__":
    main()
