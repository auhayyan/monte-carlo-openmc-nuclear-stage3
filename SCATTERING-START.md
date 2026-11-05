# Running the scattering model

The completed scattering study is saved under `data/scattering-study/`. These commands make new runs and leave that dataset in place.

## One thickness

With Docker Desktop running, open PowerShell in this folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Action Scatter
```

This runs a 1 cm slab with one million histories. The total cross section is 1 per cm: scattering is 0.8 per cm and absorption is 0.2 per cm. Scattering is isotropic in one energy group, so the model does not resolve energy loss.

## Five-thickness campaign

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_campaign.ps1
```

The defaults are 0.25, 0.5, 1, 2, and 3 cm, with three seeds and one million histories per case. Each campaign saves its plan in `campaign.json`, a table in `overview.csv`, and one numbered folder per case. Keep the complete campaign, including flagged cases.

## What the tallies mean

- **Total transmission:** histories crossing the exit, including scattered histories.
- **Uncollided transmission:** exit histories with zero collisions, selected with `CollisionFilter([0])`.
- **Reflection:** histories escaping back through the entrance. The signed surface current is reversed to report a positive fraction.
- **Absorption:** histories absorbed in the slab.

The source points along the slab normal. The slab is infinite sideways, and the outer faces have vacuum boundaries. The expected uncollided fraction is `exp(-Sigma_t * thickness)`. Transmission, reflection, and absorption should sum to one within numerical precision for this analogue, nonmultiplying model.

`Review=True` marks a result that needs checking. Keep its inputs and diagnostics. Total and uncollided transmission share histories, so their errors cannot be combined as if the tallies were independent.

Each run saves its executing Python source, input XML, cross sections, configuration, statepoint, summary, and result tables. The container digest and source/data hashes identify the run environment.

References: [collision-count filter](https://docs.openmc.org/en/stable/pythonapi/generated/openmc.CollisionFilter.html), [surface-current tallies](https://docs.openmc.org/en/stable/usersguide/tallies.html), and [multigroup cross sections](https://docs.openmc.org/en/stable/pythonapi/generated/openmc.XSdata.html).
