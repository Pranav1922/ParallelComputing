# Errata found while preparing the integrated report (2026-10-17)

Every result quoted in the report was rechecked against the saved derived tables. Raw data, models, manifests,
provenance records and the acceptance reports were **not** modified; corrections are recorded here and applied in the
report and in the three working documents named below.

| # | Where | Stated | Verified value (source) | Effect |
|---|---|---|---|---|
| 1 | `docs/S02_ACCEPTANCE_REPORT.md` §B table and text; `ALGORITHM_DESIGN.md` §4.6a outcome; `EXPERIMENTAL_METHODOLOGY.md` §7.3 S02 outcome; `IMPLEMENTATION_ROADMAP.md` S02 entry | `RL` vs `HEFT`, `test_id`: 95% CI 1.0031–1.0163 | **1.00338–1.01601** (`results/derived/20261017T115054Z-s02_final-898ee9e1/s02_paired.csv`, `ratio_ci95_lo/hi`) | Transcription error. Verdict unchanged: the CI lies inside the predeclared [0.98, 1.02] "matches" band and excludes 1. Corrected in the three working documents; the acceptance report is left as written |
| 2 | `docs/S02_ACCEPTANCE_REPORT.md` §B table | `test_id` median ρ 1.0083 | **1.00767** (same file, `ratio_median`) | Transcription error; no conclusion depends on it |
| 3 | `docs/S02_ACCEPTANCE_REPORT.md` §B table | `test_ood` CI upper bound 1.0204 | **1.02017** (same file) | Transcription error; no conclusion depends on it |
| 4 | S01 GA pilot report (earlier session) | 20.6% improvement vs FCFS-EAT | 20.548% (already recorded in `DATA_SCHEMA.md` §4.1) | Previously documented |
| 5 | Integrated report §7.5 (draft) | RL vs FCFS-EAT, `test_id`: CI lower bound 0.803 | **0.802** (`s02_paired.csv`, `ratio_ci95_lo` = 0.802477) | Rounding error in the draft; corrected 2026-10-17 (compliance audit) |
| 6 | Integrated report abstract (draft) | GA ≈ 1,700× HEFT's scheduling time | **1,730×** (`docs/S01_ACCEPTANCE_REPORT.md` timing table, n = 50) | Inconsistent with the body; corrected 2026-10-17 |
| 7 | Integrated report Table 6; `docs/S03_ACCEPTANCE_REPORT.md` §B table | `ADAPTIVE` vs `SBS`, `test_id`: ratio CI 0.9991 – **1.0010** | 0.9991 – **1.0012** (`results/derived/20261017T083329Z-s03_final-b8e5be9a/s03_paired.csv`, `ratio_ci95_hi` = 1.0011992) | Rounding error. Verdict unchanged (CI includes 1; p = 0.78). Corrected in the report 2026-10-21; the acceptance report is left as written |
| 8 | Integrated report Table 5; `docs/S02_ACCEPTANCE_REPORT.md` §C.1 table | `HEFT` mean `Cmax/LB`, `test_id`: **1.181** | **1.180** (`master.csv` of all three final campaigns, `HEFT`, `test_id`, mean `Norm_Makespan` = 1.180458; `docs/S03_ACCEPTANCE_REPORT.md` already says 1.180) | Rounding error; no conclusion depends on it. `ADAPTIVE` 1.181 (1.180626) and `RL-S1` 1.181 (1.181100) are correct. Corrected in the report 2026-10-21; the acceptance report is left as written |
| 9 | Integrated report §7.8 | "about half of the threads at m = 8 ran more than 1.3× slower than calibrated (efficiency cores, no pinning)" | 38.8% (1 ms tasks), 49.0% (100 µs), 51.0% (10 µs) (`results/derived/20261018T015324Z-omp_exec_final-9c4c1f9b/thread_slowdown.csv`, `share_threads_over_1_3`); core placement was never recorded | Overstated share and an inference stated as a cause. Corrected 2026-10-21 to "39–51% (39% at 1 ms tasks)" and "consistent with … efficiency cores, an inference from task timings" |
| 10 | Integrated report §6; `cpp/README.md` | "no thread pinning (not supported on macOS)"; "No core pinning is possible on macOS" | Not tested in this project and not sourced. Verifiable fact: `OMP_PROC_BIND` is not set (`omp_env` in the M-D manifest lists only `OMP_DYNAMIC`, `OMP_MAX_ACTIVE_LEVELS`) | Unsupported claim removed 2026-10-21. The same wording remains in locked or historical files that are not edited: `configs/omp_exec_final.toml`, the `schedlab/ompexec.py` comment, `docs/CPP_OPENMP_IMPLEMENTATION_PLAN.md`, `docs/MD_ACCEPTANCE_REPORT.md` |
| 11 | Integrated report §6 | "cost × 813 iterations per µs-of-work" | `cpp/ompexec.cpp` `iters_for`: iterations = llround(cost · K), K = 813.095 × (µs per `sim_tu`) (M-D manifest `iters_per_tu`) | Imprecise formula; corrected 2026-10-21 |
| 12 | `README.md` | "No real-hardware execution was performed and no hardware speedup is claimed"; "238 tests" | Real execution exists (`results/raw/20261018T015324Z-omp_exec_final-9c4c1f9b`, 194,400 runs); 261 tests passed at the last verified run (README "Commands", 2026-10-18; `docs/MD_ACCEPTANCE_REPORT.md` §3 criterion 6) | Stale after M-D; corrected 2026-10-21. The test suite was not re-run for this correction |
| 13 | Technical note §2; `SUBMISSION_CHECKLIST.md` item 16 | Synchronization described as `NA` / not modelled without qualification | The measured replay records static-mode dependency waiting as `Synchronization_Time` (`schedlab/omp_master.py`; report Table 3) | Reconciled 2026-10-21 with report Table 3 |

Rechecked and confirmed (no discrepancy): S01 `GA` vs best heuristic, all 450 instances, mean paired improvement
1.169% (`s01_paired.csv`: 0.011694); S03 `ADAPTIVE` vs `SBS`, `test_id`, −0.0157%, Wilcoxon p = 0.777
(`s03_paired.csv`); S02 `RL` vs `HEFT`, `test_id`, mean ρ 1.00968, p = 6.80e-6 (`s02_paired.csv`); the heuristic
makespans are identical across the S01, S03 and S02 campaigns on all 2,700 (instance, heuristic) pairs.

Bibliographic discrepancies between databases (resolved in favour of the DOI registration record):
Mao et al. — Semantic Scholar year 2018 (arXiv preprint), Crossref SIGCOMM '19, August 2019 → 2019. Kerschke et al. —
Semantic Scholar 2018, Crossref Evolutionary Computation 27(1), 2019 → 2019. Uzunoglu et al. — Semantic Scholar 2024,
Crossref vol. 173, January 2025 → 2025. Jiang et al. — third author "Rui Lu" (Semantic Scholar) vs "Ruiqi Lu"
(Crossref) → Crossref.
