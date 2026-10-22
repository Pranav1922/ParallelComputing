# CS15 compliance audit and corrections record (2026-10-17; updated 2026-10-21)

**Verdict: NOT fully compliant.** The documents have been corrected, but mandatory items that depend on the faculty,
on identifiers or on external findings are still open (§4). Every document remains marked DRAFT.

## 1. Deadline

| Source | Deadline |
|---|---|
| Manual copy in the project | 19 October 2026 |
| Confirmed by the student (2026-10-17) | **30 October 2026** ← used throughout |

The two dates disagree. The confirmed date, 30 October 2026, is used in `README.md`,
`docs/report/SUBMISSION_CHECKLIST.md` and `docs/report/word/INDEX.md`. The manual's date is recorded here only.
If faculty communications say otherwise, the faculty's date applies.

## 2. Audit findings and corrections applied (documents only)

No experiment was rerun, and no model, raw CSV, manifest, provenance record or acceptance report was changed.

| # | Audit finding | Correction | Evidence |
|---|---|---|---|
| 1 | S02 RL vs FCFS-EAT CI lower bound given as 0.803 | Changed to **0.802** (report §7.5) | `results/derived/20261017T115054Z-s02_final-898ee9e1/s02_paired.csv`: RL / FCFS-EAT / test_id `ratio_ci95_lo` = 0.802477 |
| 2 | Abstract gave "1,700×"; body and S01 report give 1,730× | Changed to **1,730×** (range "1,100–1,730×") | `docs/S01_ACCEPTANCE_REPORT.md` timing table (n = 50: ≈ 1,730×) and §conclusions |
| 3 | Parallel scheduling strategy not described | "Parallel strategy" paragraph (report §6), note §2 | Design in `docs/ALGORITHM_DESIGN.md` |
| 4 | Seeds vs timing repetitions not separated | "Repetitions and seeds" paragraph (§6); note §2 | Row counts 14,850 / 17,550 / 13,500 from `master.csv`; configs `configs/*_final.toml` |
| 5 | No scalability discussion | New §7.6 (resource count and problem size, all three sub-problems) | Values computed from `master.csv` and the paired tables of the three final campaigns |
| 6 | Overhead categories not explained | Table 3 (computation, scheduling, training, communication, synchronization, data movement, memory, energy); unmodelled quantities are `NA`, never 0 | `docs/DATA_SCHEMA.md`; raw CSV columns |
| 7 | Tables unnumbered or uncaptioned | Tables 1–8 numbered and captioned (hypotheses, modules, overheads, methodology, combined results, primary comparisons, S01 ablations, appendix); cross-references updated | DOCX caption check: Tables 1–8, Figures 1, 2a, 2b, 3–9 |
| 8 | Technical note had no references | Note §6: references [1]–[7], IEEE style; note is 2 pages in Word | Word page count |
| 9 | NP-hardness claim unsupported; no references for Wilcoxon and bootstrap | Reworded to "NP-complete in the general case [1], [2]" (wording of both sources); added [15] Wilcoxon 1945 and [16] Efron & Tibshirani 1986 | `CITATION_VERIFICATION.md` |
| 10 | GPU memory, driver and compiler flags not stated | Marked not applicable, with reasons (§6) | CPU-only PyTorch; python.org CPython; prebuilt wheels (run manifests) |
| 11 | Outlier discussion thin | §8: outlier counts, sizes and causes taken from the saved per-run decisions | `master.csv` outlier flags; S03 `results/raw/<campaign>/decisions.csv` |
| 12 | Other numerical consistency | Rechecked: no "0.803" or "1,700×" left; citations [1]–[16] in first-use order, all cited; abstract 194 words | DOCX text checks |

Literature content was also checked against full texts where they were accessible. Two sentences were corrected to
match what the full text says: Braun *et al.* [3] and READYS [9]. An unverifiable figure taken from OCR was removed. See
`CITATION_VERIFICATION.md`.

Conclusions are unchanged:
- **S01:** +1.169%, a modest gain; the GA-KEYS-EFT ablation does better.
- **S03:** −0.016%, p = 0.78, a null result.
- **S02:** better than FCFS-EAT, about 1% behind HEFT.

### Provenance re-check (2026-10-17, read-only)

Every hash in the three `provenance/s0*_final/POSTPROCESSING_PROVENANCE.json` files was recomputed against the
files on disk: S01 36, S03 48, S02 58 match (raw, derived, figure, config, model and provenance-record files). The
only differences, none rewritten:
- `report_sha256` for S01 and S03: those reports were re-worded later; the old → new hashes are in
  `provenance/s0{1,3}_final/REPORT_AMENDMENTS.md`.
- `analysis_source_sha256` for `__main__.py`, `analysis.py`, `runner.py` (S01 and S03, six entries): the current
  `schedlab/` is the S02 source (all S02 source hashes match it). The recorded S01 `__main__.py`/`runner.py` and S03
  `__main__.py`/`analysis.py`/`runner.py` are preserved byte-for-byte in each campaign's `execution_snapshot/`. The
  recorded S01 `analysis.py` (`e61379ea52…`, the post-launch τ* edit described in
  `provenance/s01_final/EXECUTION_PROVENANCE.md`) has no archived copy; `s01_paired.csv` and the Wilcoxon p-values are
  recomputed independently by `provenance/s01_final/verify_campaign.py`, which does not use `analysis.py`. The statement in that file that
  `runner` "has not changed since" was true when written; `runner.py` changed later, for S02.

### Documentation corrections (2026-10-21, after the final completion audit)

Documents only. No experiment was run, no test was re-run, and no raw CSV, derived table, figure in `results/`, model,
configuration, manifest, provenance record or acceptance report was changed. Each correction is logged in
`ERRATA.md` (items 7–13).

| # | Finding | Correction | Evidence |
|---|---|---|---|
| 13 | `README.md` said no real-hardware execution was performed | Distinguishes the simulated campaigns from the measured C++/OpenMP replay | `results/raw/20261018T015324Z-omp_exec_final-9c4c1f9b` (194,400 runs; output hashes verified 2026-10-21) |
| 14 | `README.md` gave 238 tests and 261 tests in different places | 261 at the last verified run (2026-10-18), 238 before M-A | README "Commands"; `docs/MD_ACCEPTANCE_REPORT.md` §3 criterion 6. Not re-run on 2026-10-21 |
| 15 | Report Table 6: S03 ratio CI upper bound 1.0010 | **1.0012** | `s03_paired.csv` `ratio_ci95_hi` = 1.0011992 |
| 16 | Report Table 5: HEFT `Cmax/LB` 1.181 | **1.180** | `master.csv` (all three final campaigns), HEFT `test_id` mean = 1.180458 |
| 17 | Synchronization described differently in report Table 3, note §2 and checklist item 16 | One description: `NA` in the simulation campaigns; static-mode dependency waiting measured in the replay | `schedlab/omp_master.py` (`Synchronization_Time` = `dep_wait_s` for static mode, otherwise `NA`) |
| 18 | Efficiency cores stated as the cause of the m = 8 slowdown; "about half" of the threads | "Consistent with efficiency cores; inferred from timings, placement not recorded"; "39–51% (39% at 1 ms tasks)" (report §7.8, note §3, README) | `thread_slowdown.csv` `share_threads_over_1_3` = 0.388 / 0.490 / 0.510 |
| 19 | "No thread pinning (not supported on macOS)", untested and unsourced | Replaced by the verifiable fact "no thread pinning (`OMP_PROC_BIND` unset)" (report §6, `cpp/README.md`) | M-D manifest `omp_env`. The old wording remains in locked or historical files: `configs/omp_exec_final.toml`, the `schedlab/ompexec.py` comment, `docs/CPP_OPENMP_IMPLEMENTATION_PLAN.md`, `docs/MD_ACCEPTANCE_REPORT.md` |
| 20 | Kernel formula "cost × 813 iterations per µs-of-work" | llround(cost · u · 813.1), u = µs per `sim_tu` | `cpp/ompexec.cpp` `iters_for`; manifest `iters_per_tu` |

**Deliberately not changed** (left for the student; see `INTEGRITY_AUDIT.md`):
- note §1 (individual contribution), including the overclaim "exact re-derivation of every accepted … schedule" (13 methods were re-derived; RANDOM-SELECT, ADAPTIVE-GA and GA-1000 were not);
- note §4 "What I learned", including its "efficiency cores at 8 threads" wording;
- the AI-drafted interpretive prose, the unquoted Decima phrase, the Bean patchwriting and the close paraphrases;
- the abstract's "NP-hard" versus §3.1's "NP-complete" (both terms are correct for different versions of the problem);
- the stale or rounded values in the acceptance reports (`S02_ACCEPTANCE_REPORT.md` HEFT 1.181 and CI 1.0031–1.0163; `S03_ACCEPTANCE_REPORT.md` CI 1.0010). These are left as written and corrected in `ERRATA.md`;
- design-phase documents describing the original no-hardware scope (`docs/ARCHITECTURE.md` §D2, `docs/DATA_SCHEMA.md`, `docs/VALIDATION_PLAN.md`).

**Word rebuild.** The rebuild used `python3 docs/report/build_docx.py`. Rendered with LibreOffice, the page counts are: report 12, note 3, literature review 5. The report's page starts are unchanged from the 2026-10-18 files. Abstract: 187 words. DRAFT markers and identity placeholders are present. **Re-measure in Microsoft Word** before relying on the counts.

## 3. Word verification (Microsoft Word for Mac, on scratch copies; re-measured 2026-10-18 after the C++/OpenMP integration)

| Document | Word pages | Limit | Other checks |
|---|---|---|---|
| Integrated report | **12** | 8–12 | Abstract 187 words; Tables 1–8 (Table 8 = measured comparisons; former appendix Table 8 moved to `TRACEABILITY.md`) and Figures 1–10 captioned (2a/2b, 5/6, 8/9 side by side, pairs kept on one page); references [1]–[16] in first-use order; no clipped tables or figures and no blank pages in the Word-exported PDF |
| Technical note | **3** (was 2; C++/OpenMP contribution and measured results added) | 2–3 | References [1]–[7]; Figure 9 included. Word PDF export inspected page by page (2026-10-18): a results-table row that split across pages 1–2 was fixed (rows kept whole, header kept with the first row); no clipping, no blank pages, references complete |
| Literature review | **5** (was 3; claim-check section added 2026-10-17) | companion | Citation-verification table fits the page width |

## 4. Remaining blockers (required before final export)

| Blocker | Action | Who |
|---|---|---|
| One student covering S01–S03 not approved | Ask the faculty for written approval of the one-person scope | Student → faculty |
| C++ and OpenMP confirmed as required (2026-10-17). Implemented 2026-10-17/18: C++ workload simulator reproducing every accepted heuristic and re-derived makespan exactly; OpenMP execution of the accepted schedules (194,400 measured runs; `docs/MD_ACCEPTANCE_REPORT.md`); report §5–§8 and note updated | Ask the faculty to confirm that this meets the requirement (S02 stays Python/PyTorch, as the manual lists) | Student → faculty |
| `Student_ID`, `Batch_ID` are placeholders | Set them in `configs/identity.toml`; run `analyze --final` on the three final campaigns and `python -m schedlab.omp_master` on the measured campaign; replace the placeholders in the Markdown; rebuild the Word files | Student |
| S03 objective "use findings from Batches 1–3 and 7" not met | Obtain the findings, or a faculty waiver | Student → faculty / other batches |
| Technical-note format (one combined note or three) | Confirm with the faculty | Student → faculty |
| Literature: full texts of [6], [7] (paywalled), [10] and [16] (free PDFs blocked to automated access) not read, and [5] only partially verified (published version not read); report corrections C1–C5 from the 2026-10-17 claim check applied (see `CITATION_VERIFICATION.md`) | Open [10] and [16] in a normal browser; read [6], [7] and the published [5] through library access; update the report if their text contradicts it | Student |
| Authorship and attribution (`INTEGRITY_AUDIT.md` H items) | Rewrite note §1 and §4 and the interpretive prose yourself. Quote or restate the Decima phrase and rephrase the Bean sentence. Add the disclosure the AI-use policy requires (obtain the policy first) | Student |
| Turnitin AI ≤ 10% and similarity ≤ 8% (faculty instruction) | Cannot be checked locally; needs the actual Turnitin report | Student → faculty |
| Word page counts after the 2026-10-21 rebuild | Re-measure in Microsoft Word: the report is at the 12-page limit | Student |
| Final upload to VTop by 30 October 2026 | After everything above is resolved. The manual copy says 19 October; 30 October rests on the faculty/VTop confirmation | Student |
