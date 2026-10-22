# Word export (generated 2026-10-17) — DRAFTS, not submission-ready

Built by `python3 docs/report/build_docx.py` from the Markdown sources in `docs/report/` (which are unchanged and
authoritative). A4, 2 cm margins, Calibri 10.5 pt body, numbered pages. Page counts below were measured in
**Microsoft Word for Mac** (on scratch copies), last on 2026-10-18 after the C++/OpenMP integration. Rebuilt 2026-10-21 after documentation corrections
(`../ERRATA.md` items 7–13); LibreOffice render gives the same counts, Microsoft Word re-measurement pending.

**Deadline (confirmed): 30 October 2026** (the manual copy says 19 October 2026; see `../COMPLIANCE_AUDIT.md`).
Not ready for upload: the blockers are listed in `../COMPLIANCE_AUDIT.md` §4.

| File | Pages (Microsoft Word) | Source |
|---|---|---|
| `CS15_Integrated_Report_DRAFT.docx` | 12 (manual: 8–12) | `CS15_Integrated_Report_DRAFT.md`; abstract 187 words (manual: 150–200); Tables 1–8, Figures 1–10, references [1]–[16]; traceability of every table and figure in `../TRACEABILITY.md` |
| `CS15_Individual_Technical_Note_DRAFT.docx` | 3 (manual: 2–3) | `CS15_Individual_Technical_Note_DRAFT.md` + Figure 9; references [1]–[7] |
| `CS15_Literature_Review_DRAFT.docx` | 5 (companion; includes the 2026-10-17 claim check) | report §3.2–3.3, §10 and `CITATION_VERIFICATION.md` |

Hashes of these files: `DOCUMENT_HASHES.json` (separate from the execution and campaign provenance).

- `figures/figNN_*.png` — embedded images: 2400-px renderings of the accepted PDFs in `results/figures/<campaign>/`,
  except Figure 1 (below).
- `figures/source/<fig>/` — the accepted editable sources for each figure: PDF, SVG, plotted-summary CSV and
  per-instance/per-run CSV, copied unchanged.
- `figures/derived/fig01_S01_makespan_vs_size_report.*` — the report's Figure 1: a readable view of the accepted S01
  G1 restricted to the 4 in-distribution classes × m ∈ {2, 4, 8} and 6 methods, drawn directly from the saved
  plotted-summary CSV (subset saved as `fig01_S01_makespan_vs_size_report_subset.csv`); no values recomputed.
- `figures/derived/fig10_MD_measured_execution_report.*` — the report's Figure 10, drawn from the saved plotted CSVs
  `md1_speedup_vs_threads.csv` and `md2_simulator_gap.csv` of the measured campaign
  `results/figures/20261018T015324Z-omp_exec_final-9c4c1f9b/`; no values recomputed.
- `tables/<campaign>__*.csv` — the derived tables the report quotes (Table 8: `omp_exec_final__comparisons.csv`; Table 6: `*_paired.csv`; Table 7:
  `s01_final__s01_paired.csv`). Table 5 is computed from `results/derived/<campaign>/master.csv` (not copied: size).

Placeholders kept: `[STUDENT_ID — PENDING CONFIRMATION]`, `[BATCH_ID — PENDING CONFIRMATION]`.
