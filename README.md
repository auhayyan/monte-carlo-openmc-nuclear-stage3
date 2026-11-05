# Neutron transmission and scattering in OpenMC - Stage 3

Stage 2 stopped at the first collision. Here I wanted to follow what happens next. A neutron can be absorbed, scatter back through the entrance, or scatter and still reach the other side.

I used OpenMC to compare a purely absorbing slab with an ideal scattering slab. Both have a total cross section of 1 per cm. In the scattering slab, 0.8 per cm is scattering and 0.2 per cm is absorption. The model uses one energy group and isotropic scattering.

## What I ran

Each model has five thicknesses: 0.25, 0.5, 1, 2, and 3 cm. I ran three seeds per thickness, with one million histories per run. That gives 30 million production histories across both models.

All original inputs, cross sections, statepoints, and source records are saved under [data/](data/). A separate numerical solver checks the scattering results using a different transport method. Its spatial and angular refinements are saved with the analysis.

## What I found

At 3 cm, total transmission was `0.147643 +/- 0.000207 SE`. Uncollided transmission was `0.049804 +/- 0.000131 SE`, close to `exp(-3)`. About 66.3% of the transmitted histories had collided at least once.

This is where the first-collision model becomes incomplete: the exponential still describes the uncollided beam, but some scattered neutrons also reach the exit. Since total cross section is fixed here, the comparison replaces some absorption with scattering.

The largest difference from the separate numerical solution was 2.60 standard errors, for reflection at 2 cm. That result is included. The model uses artificial cross sections and does not resolve energy loss, real-material shielding, or reactor criticality.

## Report and results

- [Report](report/Stage3_OpenMC_Report.pdf), [LaTeX source](report/latex/main.tex), and [editable text](results/study/Stage3_Report.md).
- [Summary table](results/study/summary.csv), [figures](results/study/figures/), and [reference comparison](results/study/reference-comparison.csv).
- [Original absorbing runs](data/absorber-study/) and [original scattering runs](data/scattering-study/).

All 30 statepoints were checked against their saved inputs and source hashes. The tally means and standard errors were recalculated from the saved sums. The 18 code checks cover configuration, uncertainty calculations, and the separate numerical solver.

I ran the OpenMC campaigns. AI tools helped with code, data checks, the numerical comparison, figures, and writing. Earlier setup records and the single scattering pilot are kept under `evidence/`, outside the production averages.

## Reproduce the analysis

Use Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-analysis.txt
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe reproduce_study.py --output results-reproduced
```

This checks the saved runs and rebuilds the numerical comparison, figures, and LaTeX sources. Choose a new output folder each time. It does not start new OpenMC histories.

The report is written in LaTeX. Compile `report/latex/main.tex` in Overleaf or with a local TeX installation. To regenerate and compile the published report, run `python build_report.py --analysis results/study/analysis.json --pdf report/Stage3_OpenMC_Report.pdf` with Tectonic or pdfLaTeX installed.

## Run OpenMC

Keep Docker Desktop running with Linux containers, then open PowerShell in this folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Action Check
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Action Scatter
```

The default run is a 1 cm absorber with 100,000 histories. `Scatter` runs the 1 cm scattering model with one million histories. [SCATTERING-START.md](SCATTERING-START.md) explains the full thickness campaign and tallies.

The launcher uses the container digest in `image-lock.txt` and writes each new run to its own folder under `runs/`. The production runs used OpenMC 0.16.0. Their original sources are archived with the data; later launcher changes do not alter those saved runs.

## Project stages

[Stage 1](https://github.com/auhayyan/monte-carlo-pi-simulation-nuclear_stage1) started with geometric sampling and uncertainty. [Stage 2](https://github.com/auhayyan/monte-carlo-neutron_transport-nuclear-stage2) moved to neutron free paths. This stage adds repeated collisions, scattering, and absorption in OpenMC.

See [PROJECT.md](PROJECT.md) for the complete project and [the release](https://github.com/auhayyan/monte-carlo-openmc-nuclear-stage3/releases/tag/v1.0.0) for the three reports, LaTeX sources, and complete portfolio download.

References: [OpenMC tallies](https://docs.openmc.org/en/stable/usersguide/tallies.html), [multigroup data](https://docs.openmc.org/en/stable/pythonapi/generated/openmc.XSdata.html), and [Docker setup](https://docs.openmc.org/en/stable/quickinstall.html).
