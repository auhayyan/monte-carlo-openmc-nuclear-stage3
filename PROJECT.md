# From random points to neutron transport

I started this project because I wanted to understand the physics behind nuclear reactors. I began with a problem I could check against a known answer, then moved from random points to neutron free paths and repeated collisions.

| Stage | Question | Main result | Repository |
|---|---|---|---|
| 1 | How does sample size affect error? | Repeated-run RMS-error slope -0.508, compared with the theoretical -0.5. | [Pi estimation](https://github.com/auhayyan/monte-carlo-pi-simulation-nuclear_stage1) |
| 2 | How likely is a neutron to cross a slab before its first collision? | An exponential free-path sampler reproduces the uncollided attenuation model; RMS-error slope -0.474. | [Neutron transmission](https://github.com/auhayyan/monte-carlo-neutron_transport-nuclear-stage2) |
| 3 | What happens after a neutron collides? | OpenMC separates total transmission, uncollided transmission, reflection, and absorption across 30 million production histories. | [OpenMC transport](https://github.com/auhayyan/monte-carlo-openmc-nuclear-stage3) |

Each stage includes a LaTeX report, compiled PDF, code, saved results, figures, and reproduction instructions. Stage 3 also includes a separate numerical transport solver and its refinement checks.

At 3 cm in the scattering model, mean total transmission is 0.147643 and uncollided transmission is 0.049804. About 66.3% of transmitted histories had collided. The largest difference from the numerical comparison is 2.60 standard errors and is included in the report.

The models use specified ideal coefficients. The work studies sampling error and simplified transport; it does not claim measured material performance or a reactor-criticality result. Original April records are kept with their scientific corrections. AI assistance with code, checks, figures, and writing is described in the reports.

[Download the complete portfolio and all three reports](https://github.com/auhayyan/monte-carlo-openmc-nuclear-stage3/releases/tag/v1.0.0).
