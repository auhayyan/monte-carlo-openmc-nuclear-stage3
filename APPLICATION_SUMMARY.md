# Project description

I developed a three-stage computational project to understand Monte Carlo methods and neutron transport. I began by estimating pi and measuring how sampling error changed with sample size. I then wrote a free-path model for uncollided neutron transmission and extended the study to repeated collisions in OpenMC. The final stage used 30 million histories across absorbing and scattering slabs, with three seeds per thickness. I checked saved inputs and tally statistics and compared the results with a separate numerical transport calculation. The project includes reproducible code, data, figures, and three LaTeX reports. It taught me to distinguish a close numerical answer from a result supported by uncertainty estimates and verification.

## Supporting facts

- Stage 1: 30 runs at each of four sample sizes; saved counts, seeds, timings, and uncertainty estimates.
- Stage 2: 31 thickness points and 30 runs at each of five convergence sample sizes.
- Stage 3: 30 production cases, one million histories each, with original OpenMC statepoints and source records.
- All three reports explain assumptions and limitations. These are project reports, not peer-reviewed journal publications.
- The OpenMC model uses artificial one-group coefficients and isotropic scattering. It does not resolve real-material energy dependence or reactor criticality.
- AI tools assisted with code, statistical checks, the numerical comparison, figures, and writing. I ran the OpenMC campaigns.

[Code, reports, and complete portfolio](https://github.com/auhayyan/monte-carlo-openmc-nuclear-stage3/releases/tag/v1.0.0).
