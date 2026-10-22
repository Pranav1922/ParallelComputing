# CS15 batch report — traceability (companion to the report)

Moved out of the report (formerly Appendix A, Table 8) on 2026-10-18 to keep the report within 12 pages. Source
artifact for every table and figure in `CS15_Integrated_Report_DRAFT.md`.

| Report element | Source artifact |
|---|---|
| Tables 1–4 | `docs/ARCHITECTURE.md`, `docs/ALGORITHM_DESIGN.md`, `docs/EXPERIMENTAL_METHODOLOGY.md`, `docs/DATA_SCHEMA.md`, `configs/*_final.toml` |
| Tables 5–7; §7.3–7.6 and §8 numbers | `results/derived/<campaign>/`: `master.csv` (Table 5, §7.6, outlier figures), `s01_paired.csv` / `s03_paired.csv` / `s02_paired.csv` (Tables 6–7; Holm from their p-values), `s01_overhead_quality.csv`, `s03_robustness.csv`, `s03_selection_by_class.csv`, `s03_ga_extension_overhead.csv`, `s02_generalization.csv`, `s02_overhead.csv`; S03 `results/raw/<campaign>/decisions.csv` |
| Figures 1–9 | `results/figures/<campaign>/<stem>.{pdf,svg}` with per-instance and plotted-summary CSVs; checks in `provenance/s0{1,2,3}_final/figure_reproducibility_check.txt` |
| Integrity, provenance, corrections | `provenance/s0{1,2,3}_final/`; `docs/report/ERRATA.md` |
| Table 8, Figure 10, §6 "Measured execution", §7.8 and the measured numbers in §2, §7.6, §7.7, §8, §9 | `results/derived/20261018T015324Z-omp_exec_final-9c4c1f9b/`: `comparisons.csv` (Table 8), `summary_by_method_m_granularity.csv`, `per_instance.csv`, `thread_slowdown.csv`, `rank_agreement_summary.csv`, `calibration_fork_join_and_threads.csv`, `master.csv`; `results/figures/20261018T015324Z-omp_exec_final-9c4c1f9b/md1_speedup_vs_threads.*`, `md2_simulator_gap.*`; report view of Figure 10 in `docs/report/word/figures/derived/` |
| C++ reproduction of accepted makespans (§2, §6) | `results/raw/20261017T161212Z-cpp_xval_heuristics-545fdfc6/` (24,300 heuristic rows), `results/raw/20261017T162329Z-rederive-21e353a7/` (10,350 re-derived runs, 17,550 accepted rows, 5,400 S03 decisions) |
| Measured-campaign design, calibration, integrity | `configs/omp_exec_final.toml`, `docs/MD_ANALYSIS_PLAN.md`, `results/raw/20261017T172332Z-omp_calibration-422f7f41/`, `docs/MD_ACCEPTANCE_REPORT.md` |
