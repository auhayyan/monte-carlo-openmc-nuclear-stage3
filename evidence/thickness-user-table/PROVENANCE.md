# Absorbing-slab thickness study: user-reported summary

`reported_runs.csv` transcribes the fifteen numerical rows pasted by the user after executing the proposed five-thickness, three-seed campaign on the other PC. Values are preserved at the precision supplied in that table. The row order reflects its filename-based listing, not numerical thickness order.

The requested campaign used Sigma_t = Sigma_a = 1 per cm, zero scattering, 100 batches of 10,000 histories, and two threads. These settings are inferred from the supplied launch command; the individual raw `results.json` and original statepoints have not yet been received or independently checked here. No new transport histories were executed to produce this transcription or its analysis.

The per-run standard errors are the reported OpenMC batch estimates. Means across the three distinct seeds use equal weights. Assuming independent runs, the standard error of each three-run mean is sqrt(sum(SE_i^2)) / 3. Three repetitions do not precisely establish confidence-interval coverage or validate every model feature.

Original model inputs, run-level JSON, source hashes, container-image lock, and statepoints remain on the user's PC and should be retained for the final reproducibility archive.
