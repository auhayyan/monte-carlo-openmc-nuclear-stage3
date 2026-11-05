# First scattering run: original-file review

The user executed this ideal one-group slab calculation on the Docker-enabled PC. The original files became available through the shared OneDrive workspace and were copied here byte-for-byte. The console log was supplied in the chat.

The independent HDF5 reader checked the archived Python source hash, model/cross-section hashes, original statepoint hash, seed, batch count, histories per batch, serialized filter references, and actual cross sections. It reconstructed tally means and standard errors directly from the statepoint sums and squared sums. These reproduce the recorded JSON results. See `audit.json`.

| Quantity | Observed mean | Reported batch standard error |
|---|---:|---:|
| Total transmission | 0.540863 | 0.000426346 |
| Uncollided transmission | 0.366922 | 0.000451830 |
| Reflection | 0.210826 | 0.000381323 |
| Absorption | 0.248311 | 0.000399512 |

The actual library has total cross section 1 per cm, scattering 0.8 per cm, and absorption approximately 0.2 per cm. The statepoint confirms 100 batches of 10,000 histories, seed 20261104, and one million histories total.

The uncollided reference is exp(-1) = 0.3678794412. Its observed standardized residual is approximately -2.119. This misses a two-standard-error band but remains a plausible individual fluctuation; it must be retained in subsequent statistical assessment rather than selectively repeated for better agreement.

Total exit transmission exceeds the zero-collision component by 0.173941 per source neutron. Approximately 32.16% of the transmitted component consists of histories with at least one collision. No uncertainty for this difference or ratio is inferred by treating the correlated tallies as independent.

Transmission + reflection + absorption is 1.0000000000000002. The XML defines unique filter IDs, with the exit-surface filter correctly shared between total and uncollided tallies. The console warning arose from construction of two equal exit filters and their deduplication. Future model construction shares the object explicitly; none of this run's source or physics outputs has been modified.

This audit does not independently rerun transport or experimentally validate the assumed scattering model. The single energy group does not resolve neutron slowing-down, and the coefficients do not represent a verified real material.
