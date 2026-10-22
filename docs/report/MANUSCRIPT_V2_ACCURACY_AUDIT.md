# Accuracy audit of `manuscript_v2.docx` (claim ledger)

Audit date 2026-10-21. Read-only: no manuscript, data, model, configuration or provenance file was changed. This file is the only file created.

## Document audited

| Item | Value |
|---|---|
| File | `docs/report/word/manuscript_v2.docx` (2,448,971 bytes, saved 2026-10-21 21:24) |
| SHA-256 | `a668cb8d089b478cff7640d61f776cea229988193bb38c1d542f9df008ef4083` |
| Word metadata | Microsoft Office Word, revision 68, TotalTime 41 min, Pages 13, Words 7,090; core.xml created by python-docx, last modified by "Pranav Kumar" 2026-10-21 15:53Z |
| Markdown source | `docs/report/CS15_Integrated_Report_DRAFT.md` (sha256 `6c84c600…`), differs substantially in wording |
| Earlier Word version | `CS15_Integrated_Report_DRAFT.docx` no longer present; Word lock file `~$15_Integrated_Report_DRAFT.docx` remains |
| Version control | Not a Git repository (`git status`: not a git repository) |
| Footnotes / equations | footnotes.xml and endnotes.xml contain only separators; no OMML equations |

## Scores

Claims reviewed: **243** — Correct 180, Partially correct 46, Incorrect 8, Unsupported 8, Not assessable 1 (sum 243).

| Measure | Formula | Value |
|---|---|---|
| A. Strict verified-correct | C / (C+P+I) = 180/234 | **76.9%** |
| B. Conservative weighted (rubric estimate) | (C + 0.5·P) / (C+P+I) = (180 + 23)/234 | **86.8%** |
| C. Evidence coverage | (C+P+I) / total = 234/243 | **96.3%** |
| Sensitivity: only claims verified directly in this audit or against bibliographic metadata (level D/S, n = 188) | same formulas | strict 80.3%, weighted 88.3% |

Errors by severity (Partially correct, Incorrect, Unsupported): critical 3, major 4, moderate 12, minor 43. Severity-weighted error points (critical 4, major 3, moderate 2, minor 1): 91. This is an additional view only; it does not replace A–C.

**Limitations of the scores.** Claims differ in importance; the unit of a claim is a judgement (one entry per independent assertion; a table row whose cells are all correct is one claim, and any wrong cell is split out as its own claim, which lowers rather than raises the score). Evidence level is recorded per claim: **D** recomputed or inspected directly in this audit; **S** Semantic Scholar bibliographic record or TL;DR (not an abstract); **R** repository record only (acceptance reports, `CITATION_VERIFICATION.md`), not re-derived here. No full text of any cited paper was read in this audit. Grammar and style were not scored except where wording changes the meaning. Assignment compliance (below) is not part of the accuracy score.

## Most serious errors

| Rank | ID | Section | Claim | Status | Severity | Evidence |
|---|---|---|---|---|---|---|
| 1 | D2 | §7.4 | 'ADAPTIVE outperformed SBS (HEFT) on just 18 out of 360' | Incorrect | critical | s03_paired.csv: better 6 / tie 342 / worse 12 |
| 2 | V11 | §8 | 'Seeded approaches will never beat their seeds' | Incorrect | critical | s01_paired.csv GA vs HEFT 338/112/0 (GA beats its seed HEFT on 338) |
| 3 | X3 | §7.8 | 'the GA scheduling was 1.6% faster than HEFT's scheduling' | Incorrect | critical | comparisons.csv M1 = measured execution of the schedules; GA scheduling time is ~10³× HEFT's (s01_overhead_quality.csv) |
| 4 | AB2 | Abstract | 'AI schedulers usually outperform list heuristics' | Unsupported | major | s02_paired.csv (RL vs HEFT rho 1.0097); s03_paired.csv (ADAPTIVE vs SBS null); §3.2 sources report gains only in specific settings |
| 5 | S8 | §7.3 | 'for this budget, GA does not need population and crossover' | Incorrect | major | s01_paired.csv GA vs HILL-CLIMB CI 0.13–0.42% (excludes 0) |
| 6 | TB1 | Title block | Student ID(s): 'Pranav Kumar(23BCE0358)' | Unsupported | major | configs/identity.toml (STUDENT_ID_UNCONFIRMED); all four master.csv Student_ID = STUDENT_ID_UNCONFIRMED |
| 7 | Z7 | §7.7 | 'hill climbing with the same seed values performed equally' | Incorrect | major | s01_paired.csv GA vs HILL-CLIMB +0.27% (CI 0.13–0.42), 190/98/162 |
| 8 | AB11 | Abstract | C++ simulator reproduced makespans for '41,850 accepted jobs' exactly | Partially correct | moderate | cpp_xval manifest accepted_rows_compared 24,300; rederive manifest accepted_rows_compared 17,550, reproduced 10,350/10,350 |
| 9 | AB13 | Abstract | 'the OpenMP task was 19% slower than a statically scheduled HEFT job' | Partially correct | moderate | comparisons.csv M3 1.1879 |
| 10 | AB7 | Abstract | GA 'ran up to ~1,100 - 1,730 times slower than HEFT' | Partially correct | moderate | s01_overhead_quality.csv time_ratio_vs_HEFT_median 1,734 (n=50) … ~1,100 (n=400) |
| 11 | D4 | §7.4 | 'the gap narrowed by −0.03 (95% CI −0.30, 0.19)' | Partially correct | moderate | s03_paired.csv gap_closed −0.029 [−0.299, 0.185] |
| 12 | D9 | §7.4 | 'total time for SBS is about 0.5 ms' | Incorrect | moderate | S03 master.csv median call: HEFT 0.37 ms, ADAPTIVE 0.54 ms |
| 13 | E22 | §6 Table 3 | Training time of S02 policies AND S03 selectors recorded in model.json 'measured' block | Partially correct | moderate | s02_rl_seed*/model.json measured.train_time_s present; s03_selector_v1/model.json has no measured/timing field |
| 14 | G1 | §3.3 | 'In all reviewed literature' AI schedulers are benchmarked in isolation… | Unsupported | moderate | §3.2 itself reports [3],[13] comparing against heuristics |
| 15 | L16 | §3.2 | [6]'s approach is 'never worse than the seeds' (attribute of the algorithm) | Unsupported | moderate | CITATION_VERIFICATION [6]: abstract says nothing of this |
| 16 | L27 | §3.2 | Rice [11]: choose the algorithm 'expected to solve it optimally' | Incorrect | moderate | CITATION_VERIFICATION [11] (metadata only) and [12] full text: choose the algorithm expected to perform best |
| 17 | L4 | §3.2 | HEFT/CPOP 'devised for obtaining near-optimal schedules at a low cost' | Partially correct | moderate | S2 TL;DR [2]: 'high performance and fast scheduling time'; CITATION_VERIFICATION [2] |
| 18 | L8 | §3.2 | Min-min 'took less time to generate near optimal solutions' | Partially correct | moderate | CITATION_VERIFICATION [3]: Min-min close to the best at very small execution time |
| 19 | X11 | §7.8 | 'consistent with efficiency cores; observed from timing, not placement' | Partially correct | moderate | M-D manifest: no placement recorded; omp_analysis.py note 'no pinning' |

## Unsupported and not-assessable statements

| ID | Section | Claim | Status | Why |
|---|---|---|---|---|
| TB1 | Title block | Student ID(s): 'Pranav Kumar(23BCE0358)' | Unsupported | Identifier not confirmed anywhere in the repository; contradicts the CSV exports |
| AB2 | Abstract | 'AI schedulers usually outperform list heuristics' | Unsupported | Unsupported generalisation; this study's own primary results contradict it for strong heuristics |
| M5 | §3.1 | On heterogeneous platforms processor allocation is 'as important as' task order | Unsupported | No evidence or citation given |
| L15 | §3.2 | Reviewed abstracts report no equal-budget random-search / hill-climbing controls | Not assessable | Not re-verifiable here |
| L16 | §3.2 | [6]'s approach is 'never worse than the seeds' (attribute of the algorithm) | Unsupported | Statement attributed to [6] without support (rewording of the original argument) |
| G1 | §3.3 | 'In all reviewed literature' AI schedulers are benchmarked in isolation… | Unsupported | Over-broad universal claim |
| G2 | §3.3 | Four questions are not answered together in the reviewed work | Unsupported | Gap claim about the literature, only scoped to 13 papers |
| S12 | §7.3 | Its advantage is a smaller search space that is easier to search at 6,000 evaluations | Unsupported | Plausible explanation, not tested |
| Y2 | §7.6 | Efficiency falls 'because of the restricted parallelism of the DAGs' | Unsupported | Explanation not tested (no DAG-width analysis cited) |

## Section summary

| Section | Claims | Correct | Partial | Incorrect | Unsupported | Not assessable |
|---|---|---|---|---|---|---|
| Title block | 1 | 0 | 0 | 0 | 1 | 0 |
| Abstract | 15 | 7 | 7 | 0 | 1 | 0 |
| §3.1 | 5 | 3 | 1 | 0 | 1 | 0 |
| §3.2 | 37 | 23 | 10 | 2 | 1 | 1 |
| §3.3 | 4 | 1 | 1 | 0 | 2 | 0 |
| §4 | 5 | 5 | 0 | 0 | 0 | 0 |
| §5 | 12 | 12 | 0 | 0 | 0 | 0 |
| §6 | 29 | 25 | 4 | 0 | 0 | 0 |
| §7.1 | 14 | 11 | 3 | 0 | 0 | 0 |
| §7.2 | 6 | 6 | 0 | 0 | 0 | 0 |
| §7.3 | 18 | 13 | 3 | 1 | 1 | 0 |
| §7.4 | 15 | 9 | 4 | 2 | 0 | 0 |
| §7.5 | 10 | 8 | 2 | 0 | 0 | 0 |
| §7.6 | 11 | 7 | 3 | 0 | 1 | 0 |
| §7.7 | 10 | 6 | 3 | 1 | 0 | 0 |
| §7.8 | 15 | 10 | 4 | 1 | 0 | 0 |
| §8 | 14 | 12 | 1 | 1 | 0 | 0 |
| §9 | 6 | 6 | 0 | 0 | 0 | 0 |
| §10 | 16 | 16 | 0 | 0 | 0 | 0 |

## Recheck of previously reported issues

| Earlier finding | Current status in manuscript_v2.docx |
|---|---|
| §7.4 ADAPTIVE differed on 18 (better 6, worse 12) | D2 Incorrect (text says 'outperformed on 18'); D3, numbers 6/12 correct |
| §7.4 gap_closed interpretation; ~0.54 ms call time | D4 Partially correct ('narrowed by −0.03'); D9 Incorrect (0.5 ms attributed to SBS; HEFT is 0.37 ms, ADAPTIVE 0.54 ms) |
| §7.8 GA schedule execution vs scheduler time | X3 Incorrect (critical) |
| §8 seeded approaches 'never beat' seeds | V11 Incorrect (critical) |
| §7.3/§7.7 GA vs hill climbing; population/crossover | S7 numbers Correct; S8 Incorrect; Z7 Incorrect; conflicts with §9 (W1) |
| §4 definition of sim_tu and 100 sim_tu mean work | Absent from the Word document (omission, not scored); sim_tu is used later in §5, §6 and Table 3 undefined |
| Abstract: rows, generalisation, selector, OpenMP runtime, GA overhead | AB11 Partially (jobs vs rows); AB2 Unsupported; AB8 Correct (ungrammatical); AB13 Partially; AB7 Partially |
| §7.6 TRY-ALL headroom at m = 8 | Y4 Partially (0.09 → 0.08; recomputed 0.0849%) |
| Table 3 S03 training time in model.json | E22 Partially (S02 recorded; S03 not) |
| Citations: Topcuoglu, Braun, Sulaiman, Mao, READYS, Zhadan, Rice, Kerschke, Uzunoglu | L4 P, L8 P, L16 U, L17 P, L19 P, L21 P, L23 C (abstract level), L25 P, L27 I, L29 P, L33 P |
| Evaluation methodology | L35 Correct (design); L36 Incorrect (causal logic); L37 Partially (percentile attributed to [16]) |
| S03 CI 0.9991–1.0012 | T6b Correct |
| HEFT mean Cmax/LB 1.180 | T5c Correct (1.180458) |
| M-D speedups, OpenMP runtime, core placement, lost hardware records | AB12 P, AB13 P, AB14 C, X8 C, X9 C, X11 P (placement labelled 'observed'), V3 P, V4 C |
| Real-hardware implications | Replay is measured execution of a synthetic compute kernel on one host; the manuscript labels it so in §6/§8. 'proved' (AB12) and §3.3 (iv) 'real performance gains' overstate what a synthetic kernel shows |

## Internal consistency (not scored)

- §7.7 says hill climbing 'performed equally'; §7.3 numbers and §9 say 'nearly as good'.
- The Word document no longer matches its Markdown source; `build_docx.py` would regenerate the older draft. `DOCUMENT_HASHES.json` and `word/INDEX.md` reference the missing `CS15_Integrated_Report_DRAFT.docx`.
- Student ID shown in the title block is not in `configs/identity.toml` or any CSV; Batch ID is still a placeholder.
- The technical note DOCX still describes the efficiency-core inference correctly ('inferred'), while §7.8 now says 'observed'.
- sim_tu is used undefined after its definition was removed from §4.

## Assignment compliance (separate from accuracy)

| Requirement (manual) | Status |
|---|---|
| Batch report 8–12 pages (p.2) | Not met: Word metadata Pages = 13; LibreOffice render 13 |
| Abstract 150–200 words (p.16 §2) | Not met: 214 words |
| Sections 1–10 incl. limitations, ≥3 future directions (p.16–17) | Present |
| Student_ID / Batch_ID in CSV rows (p.17) | Not met: placeholders in all CSVs; Batch ID placeholder in document |
| S03 'use findings from Batches 1–3 and 7' (p.16) | Not met (stated in §8) |
| Faculty approval of scope/tooling (p.1) | No evidence in repository |
| DRAFT status | DRAFT banner, header and Status row removed although approvals and identifiers are unresolved |
| Deadline | Manual states 19 October 2026; working deadline 30 October 2026 rests on faculty/VTop confirmation |

## Prioritized correction checklist (not applied)

1. **D2** (critical, §7.4): 'chose differently on 18 (better 6, worse 12)'
2. **V11** (critical, §8): 'cannot be worse than their seeds'
3. **X3** (critical, §7.8): 'GA schedules executed 1.6% faster than HEFT schedules'
4. **AB2** (major, Abstract): Restrict to 'are reported to outperform … in some settings'
5. **S8** (major, §7.3): 'add little at this budget'
6. **TB1** (major, Title block): Confirm the ID, then set identity.toml and run the final export so documents and CSVs agree
7. **Z7** (major, §7.7): 'nearly as well'
8. **AB11** (moderate, Abstract): Replace 'jobs' with 'accepted result rows'
9. **AB13** (moderate, Abstract): Name the OpenMP task runtime vs the static HEFT schedule
10. **AB7** (moderate, Abstract): Say 'needed ~1,100–1,730× HEFT's scheduling time'
11. **D4** (moderate, §7.4): 'gap closed −0.03; CI includes 0'
12. **D9** (moderate, §7.4): Attribute 0.5 ms to ADAPTIVE
13. **E22** (moderate, §6 Table 3): Remove S03 or state 'not recorded'
14. **G1** (moderate, §3.3): 'Most reviewed work'
15. **L16** (moderate, §3.2): Restore the original reasoning or remove
16. **L27** (moderate, §3.2): 'expected to perform best'; cite [12] for the definition
17. **L4** (moderate, §3.2): Use 'good schedules at low scheduling cost'
18. **L8** (moderate, §3.2): 'came close to the best result at very small execution time'
19. **X11** (moderate, §7.8): 'inferred from timings; placement not recorded'
20. **AB12** (minor, Abstract): 'showed'
21. **AB15** (minor, Abstract): Add 'on these workloads'
22. **AB3** (minor, Abstract): Describe the action as a (ready task, processor) pair
23. **AB5** (minor, Abstract): Qualify ('predeclared tests; S01 population chosen post hoc, all reported')
24. **D11** (minor, §7.4): Reword
25. **D13** (minor, §7.4): 'improved the mean by 0.10% (not resolved)'
26. **D7** (minor, §7.4): 'H3b held'
27. **E10** (minor, §6): 'asserted'
28. **E11** (minor, §6): 'once per seed'
29. **E8** (minor, §6): 'so that … are not distorted'
30. **G2** (minor, §3.3): Scope to 'the reviewed work'
31. **G3** (minor, §3.3): Name the controls
32. **L17** (minor, §3.2): 'algorithm running time'
33. **L19** (minor, §3.2): Use 'job completion time'
34. **L21** (minor, §3.2): 'at low duration noise'
35. **L24** (minor, §3.2): Correct term
36. **L25** (minor, §3.2): Reword
37. **L29** (minor, §3.2): 'reference points'
38. **L33** (minor, §3.2): Keep 'over the worst compared method'
39. **L36** (minor, §3.2 Eval. methodology): Rewrite the sentence
40. **L37** (minor, §3.2 Eval. methodology): 'bootstrap CIs (percentile method) [16]'
41. **M1** (minor, §3.1): Restate: performance is bounded by the schedule
42. **M5** (minor, §3.1): Cite or soften
43. **R6** (minor, §7.5): 'worsened'
44. **R8** (minor, §7.5): 'relies substantially on'
45. **S12** (minor, §7.3): Mark as a hypothesis
46. **S15** (minor, §7.3): Name HEFT
47. **S4** (minor, §7.3): 'unseeded'
48. **S6** (minor, §7.3): 'costs measured wall-clock time'
49. **T5i** (minor, §7.1 Table 5): 3.513
50. **T5j** (minor, §7.1 Table 5): 0.814
51. **T5l** (minor, §7.1 Table 5): 0.820
52. **V3** (minor, §8): 'likely reflect'
53. **X10** (minor, §7.8): 'more than 1.3×'
54. **X2** (minor, §7.8): 'median CV'
55. **X6** (minor, §7.8): 'vanished (0.999)'
56. **Y2** (minor, §7.6): Support or mark as likely explanation
57. **Y3** (minor, §7.6): 'best heuristic'
58. **Y4** (minor, §7.6): 0.08%
59. **Y8** (minor, §7.6): 1.013
60. **Z2** (minor, §7.7): Reword
61. **Z5** (minor, §7.7): 'consistent with'
62. **Z6** (minor, §7.7): Restore terms

## Remaining uncertainties and missing material

- No full text of any reference was read in this audit; citation-content claims at level R rely on `CITATION_VERIFICATION.md` (full text: [1],[4],[8],[12],[13]; partial: [2],[3],[5],[9]; abstract only: [6],[7],[10],[16]; metadata only: [11],[14],[15]).
- Semantic Scholar returned bibliographic records and machine TL;DRs, not abstracts; [15] was not found there.
- Figure images were not visually re-inspected; captions were checked against the source files.
- The test suite was not re-run; validation claims rest on saved verification results.
- M-D host records at start/end and the exact power string are irrecoverable (manifest RECONSTRUCTED).
- Turnitin AI-writing and similarity scores cannot be established by this audit.

## Claim ledger

Status: C Correct, P Partially correct, I Incorrect, U Unsupported, N Not assessable. Level: D direct, S bibliographic record, R repository record.

| ID | Section | Claim | Category | Status | Level | Evidence | Finding | Severity | Recommended action |
|---|---|---|---|---|---|---|---|---|---|
| TB1 | Title block | Student ID(s): 'Pranav Kumar(23BCE0358)' | I Consistency | U | D | configs/identity.toml (STUDENT_ID_UNCONFIRMED); all four master.csv Student_ID = STUDENT_ID_UNCONFIRMED | Identifier not confirmed anywhere in the repository; contradicts the CSV exports | major | Confirm the ID, then set identity.toml and run the final export so documents and CSVs agree |
| AB1 | Abstract | DAG scheduling on heterogeneous processors is NP-hard | C Technical | C | R | CITATION_VERIFICATION [1] full text: 'in general an NP-complete problem' (decision version) | Consistent with [1],[2] | — | — |
| AB2 | Abstract | 'AI schedulers usually outperform list heuristics' | G Conclusion | U | D | s02_paired.csv (RL vs HEFT rho 1.0097); s03_paired.csv (ADAPTIVE vs SBS null); §3.2 sources report gains only in specific settings | Unsupported generalisation; this study's own primary results contradict it for strong heuristics | major | Restrict to 'are reported to outperform … in some settings' |
| AB3 | Abstract | Three schedulers: seeded GA; REINFORCE policy 'choosing processors for ready tasks'; decision tree over six heuristics | C Technical | P | D | schedlab/rl.py docstring (action = (ready task, processor) pair); ga.py; adaptive.py | RL chooses the task AND the processor, not only processors | minor | Describe the action as a (ready task, processor) pair |
| AB4 | Abstract | One simulator, same synthetic workloads; compared with FCFS and HEFT on 360 test and 90 novel workloads | B Experimental | C | D | runs.csv split counts (test_id 360, test_ood 90 instances) in all three campaigns | — | — | — |
| AB5 | Abstract | 'using predetermined tests and Holm's correction' | D Statistical | P | R | S01_ACCEPTANCE_REPORT §B.2: S01 analysis population not predeclared | Test and Holm family predeclared; S01 population was not | minor | Qualify ('predeclared tests; S01 population chosen post hoc, all reported') |
| AB6 | Abstract | GA 1.17% lower makespan than per-instance best heuristic, p = 6.2e-52 | A Numerical | C | D | s01_paired.csv all/GA/BEST-HEURISTIC improvement_mean 0.011694, wilcoxon_p 6.25e-52 | Simulated makespan (stated earlier in abstract only as 'simulator') | — | — |
| AB7 | Abstract | GA 'ran up to ~1,100 - 1,730 times slower than HEFT' | A Numerical | P | D | s01_overhead_quality.csv time_ratio_vs_HEFT_median 1,734 (n=50) … ~1,100 (n=400) | Range correct but it is scheduling (optimization) time, and 'up to ~1,100–1,730' is incoherent; reader can read it as execution time | moderate | Say 'needed ~1,100–1,730× HEFT's scheduling time' |
| AB8 | Abstract | Selector did not beat the best fixed policy (−0.016%, p = 0.78) | A Numerical | C | D | s03_paired.csv ADAPTIVE/SBS/test_id improvement_mean −0.000157, p 0.777 | Sentence is ungrammatical ('surpass … by (…)') – style only | — | — |
| AB9 | Abstract | RL beat FCFS by 18% | A Numerical | C | D | s02_paired.csv RL/FCFS-EAT/test_id ratio_mean 0.8220 | 17.8% | — | — |
| AB10 | Abstract | RL 1.0% behind HEFT | A Numerical | C | D | s02_paired.csv RL/HEFT/test_id ratio_mean 1.0097 | — | — | — |
| AB11 | Abstract | C++ simulator reproduced makespans for '41,850 accepted jobs' exactly | A Numerical | P | D | cpp_xval manifest accepted_rows_compared 24,300; rederive manifest accepted_rows_compared 17,550, reproduced 10,350/10,350 | Count correct, unit wrong: rows/makespans, not jobs | moderate | Replace 'jobs' with 'accepted result rows' |
| AB12 | Abstract | OpenMP execution 'proved' GA beat HEFT in aggregate by 1.6% (95% CI 1.2–2.0%) | D Statistical | P | D | comparisons.csv M1 geo_mean_ratio 0.9838 [0.9796, 0.9877] | Numbers correct; 'proved' overstates a single-host aggregate result | minor | 'showed' |
| AB13 | Abstract | 'the OpenMP task was 19% slower than a statically scheduled HEFT job' | C Technical | P | D | comparisons.csv M3 1.1879 | 19% correct; compares the OpenMP task runtime with the static HEFT schedule, not a 'task' and a 'job' | moderate | Name the OpenMP task runtime vs the static HEFT schedule |
| AB14 | Abstract | Efficiency dropped to 0.42 at eight threads | A Numerical | C | D | summary_by_method_m_granularity.csv HEFT m=8 us_per_tu=10 efficiency_median 0.423 | (HEFT, 1 ms tasks – not stated) | — | — |
| AB15 | Abstract | 'HEFT is close to the upper limit of affordable scheduling' | G Conclusion | P | D | TRY-ALL vs SBS +0.45% (S03); RL ≥ HEFT cost | Supported for these workloads/simulator only; stated without scope | minor | Add 'on these workloads' |
| M1 | §3.1 | 'a task DAG … will be as efficient as possible based upon its schedule' | J Wording | P | D | Markdown source §3.1 ('runs only as fast as its schedule allows') | Meaning changed by rewording; vague | minor | Restate: performance is bounded by the schedule |
| M2 | §3.1 | Task order and processor assignment determine makespan and utilization | C Technical | C | D | model.py ScheduleBuilder | — | — | — |
| M3 | §3.1 | Optimal scheduling is NP-complete in general [1],[2] | E Citation | C | R | CITATION_VERIFICATION [1] full text §3; [2] partial | — | — | — |
| M4 | §3.1 | Hence list heuristics are used in practice | E Citation | C | R | CITATION_VERIFICATION [1],[2] | — | — | — |
| M5 | §3.1 | On heterogeneous platforms processor allocation is 'as important as' task order | G Conclusion | U | D | — | No evidence or citation given | minor | Cite or soften |
| L1 | §3.2 | Kwok & Ahmad [1] classified 27 static algorithms | E Citation | C | S | Semantic Scholar TL;DR 'classifies 27 scheduling algorithms'; CITATION_VERIFICATION [1] full text | — | — | — |
| L2 | §3.2 | [1] describes task priority, processor selection, idle-slot insertion, random-graph evaluation | E Citation | C | R | CITATION_VERIFICATION [1] (full text §5–6) | 'in this essay' is wrong genre (style) | — | — |
| L3 | §3.2 | Topcuoglu et al. [2] proposed HEFT and CPOP for a bounded number of heterogeneous processors | E Citation | C | S | S2 TL;DR [2] | — | — | — |
| L4 | §3.2 | HEFT/CPOP 'devised for obtaining near-optimal schedules at a low cost' | E Citation | P | S | S2 TL;DR [2]: 'high performance and fast scheduling time'; CITATION_VERIFICATION [2] | 'near-optimal' not supported by the source | moderate | Use 'good schedules at low scheduling cost' |
| L5 | §3.2 | Project HEFT = upward rank, EFT processor selection, idle-slot insertion | C Technical | C | D | schedlab/heuristics.py (insert=True default, list_schedule); ALGORITHM_DESIGN §2 | — | — | — |
| L6 | §3.2 | Braun et al. [3] compared eleven static heuristics for independent tasks on heterogeneous systems | E Citation | C | S | Title / S2 record [3] | — | — | — |
| L7 | §3.2 | In [3] a GA gave the best mapping in all cases; its best solution always came from a Min-min-seeded population | E Citation | C | R | CITATION_VERIFICATION [3] partial text | — | — | — |
| L8 | §3.2 | Min-min 'took less time to generate near optimal solutions' | E Citation | P | R | CITATION_VERIFICATION [3]: Min-min close to the best at very small execution time | 'near optimal' overstates | moderate | 'came close to the best result at very small execution time' |
| L9 | §3.2 | Hou et al. [4] compared a GA with list scheduling and optimal schedules on random task graphs | E Citation | C | S | S2 TL;DR [4]; CITATION_VERIFICATION [4] full text | — | — | — |
| L10 | §3.2 | Bean [5]: GA with random keys for sequencing/optimization incl. multiple-machine scheduling | E Citation | C | S | S2 TL;DR [5] | Close to source wording (attribution, see integrity audit) | — | — |
| L11 | §3.2 | Project GA: keys set priority among ready tasks, so every chromosome decodes to a precedence-feasible schedule | C Technical | C | D | schedlab/ga.py docstring ('decode() always yields a feasible schedule') | — | — | — |
| L12 | §3.2 | Sulaiman et al. [6]: HHG/HTDG hybrid GA/list heuristics with two guided chromosomes | E Citation | C | S | S2 TL;DR [6]; CITATION_VERIFICATION [6] abstract | — | — | — |
| L13 | §3.2 | [6] reported better makespan than two GAs and HEFT/PEFT | E Citation | C | R | CITATION_VERIFICATION [6] (abstract only) | Abstract-level only | — | Read full text |
| L14 | §3.2 | Jiang et al. [7]: real-relative encoding; every chromosome decodes to a precedence-valid schedule | E Citation | C | R | CITATION_VERIFICATION [7] (abstract only) | Abstract-level only | — | Read full text |
| L15 | §3.2 | Reviewed abstracts report no equal-budget random-search / hill-climbing controls | E Citation | N | R | Abstracts of [6],[7] not retrieved in this audit; claim rests on the earlier abstract reading | Not re-verifiable here | — | Check abstracts/full texts |
| L16 | §3.2 | [6]'s approach is 'never worse than the seeds' (attribute of the algorithm) | E Citation | U | R | CITATION_VERIFICATION [6]: abstract says nothing of this | Statement attributed to [6] without support (rewording of the original argument) | moderate | Restore the original reasoning or remove |
| L17 | §3.2 | [6]'s abstract reports better average 'execution time' | E Citation | P | R | CITATION_VERIFICATION [6]: 'average running time' (of the algorithm) | Ambiguous: reads as schedule execution time | minor | 'algorithm running time' |
| L18 | §3.2 | [6] full text unavailable, so not compared with HEFT | F Methodology | C | R | CITATION_VERIFICATION [6] access log | — | — | — |
| L19 | §3.2 | Decima [8] reduced average job 'processing' time by ≥21% vs hand-tuned heuristics | E Citation | P | S | S2 TL;DR [8]: 'average job completion time by at least 21% over hand-tuned scheduling heuristics' | Metric renamed (completion → processing) | minor | Use 'job completion time' |
| L20 | §3.2 | READYS [9]: GCN + actor-critic for dynamic DAG scheduling on CPU/GPU | E Citation | C | R | CITATION_VERIFICATION [9] partial text | — | — | — |
| L21 | §3.2 | READYS comparable to HEFT 'if task execution times were deterministic' | E Citation | P | R | CITATION_VERIFICATION [9]: similar to HEFT at low duration noise | Overstated condition | minor | 'at low duration noise' |
| L22 | §3.2 | READYS beat HEFT as variability grew and transferred to larger graphs | E Citation | C | R | CITATION_VERIFICATION [9] | — | — | — |
| L23 | §3.2 | Zhadan et al. [10]: MARL selects a heuristic rule; 5.32% avg gain over DONF on random DAGs | E Citation | C | R | CITATION_VERIFICATION [10] (abstract); S2 TL;DR ('different heuristic rule at each scheduling step') | Abstract-level only; 'at each step' omitted | — | Read full text |
| L24 | §3.2 | Limitations: gains claimed with stochastic durations, 'clustering' or step-level switching, different baselines/overheads | E Citation | P | R | CITATION_VERIFICATION [8],[9],[10] | 'clustering' should be cluster dynamics | minor | Correct term |
| L25 | §3.2 | '(for [10], cited in its abstract)' | E Citation | P | R | CITATION_VERIFICATION [10] abstract-only | Misstates the evidence level (should be 'based on its abstract only') | minor | Reword |
| L26 | §3.2 | READYS's clear gains over HEFT appear only with stochastic durations [9] | E Citation | C | R | CITATION_VERIFICATION [9] | — | — | — |
| L27 | §3.2 | Rice [11]: choose the algorithm 'expected to solve it optimally' | E Citation | I | R | CITATION_VERIFICATION [11] (metadata only) and [12] full text: choose the algorithm expected to perform best | Definition wrong; [11] itself not read | moderate | 'expected to perform best'; cite [12] for the definition |
| L28 | §3.2 | Kerschke et al. [12] surveyed algorithm selection and relation to configuration, scheduling, portfolios | E Citation | C | S | S2 TL;DR [12] | — | — | — |
| L29 | §3.2 | SBS and VBS called 'two standard metrics' | C Technical | P | R | CITATION_VERIFICATION [12] full text | They are reference solvers; the metric is the gap closed | minor | 'reference points' |
| L30 | §3.2 | Selector judged by fraction of SBS–VBS gap closed | E Citation | C | R | CITATION_VERIFICATION [12] full text | — | — | — |
| L31 | §3.2 | Uzunoglu et al. [13]: learning-to-rank per-instance selection among learning-augmented construction heuristics, serial-batch | E Citation | C | R | CITATION_VERIFICATION [13] full text | — | — | — |
| L32 | §3.2 | [13]: selection beat single best heuristic in every size group (MRIW 6.42% vs 2.23%) | E Citation | C | R | CITATION_VERIFICATION [13] full text | — | — | — |
| L33 | §3.2 | [13]: GA improvement 'resulted in 39.19% mean relative improvement' | E Citation | P | R | CITATION_VERIFICATION [13]: MRIW = vs the worst compared method | Qualifier dropped for 39.19% | minor | Keep 'over the worst compared method' |
| L34 | §3.2 | Algorithm selection pays off only when no algorithm dominates | E Citation | C | R | CITATION_VERIFICATION [12] | — | — | — |
| L35 | §3.2 Eval. methodology | One primary comparison per sub-problem; Wilcoxon [15]; Holm across three [14]; bootstrap CIs | D Statistical | C | D | s0x_paired.csv (p only on primary rows); S02 report Holm table | — | — | — |
| L36 | §3.2 Eval. methodology | 'multiplicity appears since we perform a single pre-specified primary comparison … using Holm' | D Statistical | I | D | — | Causal logic inverted: multiplicity motivates the design, it is not caused by Holm | minor | Rewrite the sentence |
| L37 | §3.2 Eval. methodology | 'bootstrap percentile confidence intervals [16]' | E Citation | P | R | CITATION_VERIFICATION C4: percentile method not confirmed in [16] | Undoes correction C4 | minor | 'bootstrap CIs (percentile method) [16]' |
| G1 | §3.3 | 'In all reviewed literature' AI schedulers are benchmarked in isolation… | G Conclusion | U | R | §3.2 itself reports [3],[13] comparing against heuristics | Over-broad universal claim | moderate | 'Most reviewed work' |
| G2 | §3.3 | Four questions are not answered together in the reviewed work | G Conclusion | U | R | — | Gap claim about the literature, only scoped to 13 papers | minor | Scope to 'the reviewed work' |
| G3 | §3.3 | Controls listed include 'blind search' | C Technical | P | D | ga.py METHODS (GA-UNSEEDED, RANDOM-SEARCH) | 'blind search' is not a method name; meant unseeded/random search | minor | Name the controls |
| G4 | §3.3 | This study addresses all four with stated hypotheses, primary tests and verdicts incl. null/negative | F Methodology | C | D | ARCHITECTURE.md H1–H4; paired CSVs; MD comparisons | — | — | — |
| P1 | §4 | Problem: DAG, cost[t,p], m processors, feasible non-preemptive schedule optimising makespan | C Technical | C | D | model.py | 'optimises' = minimises | — | — |
| P2 | §4 | No communication costs | C Technical | C | D | model.py (no edge costs) | — | — | — |
| P3 | §4 Table 1 | Research questions match the manual | H Compliance | C | D | Case_Study_Manual p.15–16 | — | — | — |
| P4 | §4 Table 1 | Hypotheses H1–H4 predeclared in ARCHITECTURE.md | F Methodology | C | D | docs/ARCHITECTURE.md lines 129–135 | — | — | — |
| P5 | §4 | Role of each part matches manual's baseline / main dimension / adaptation roles | H Compliance | C | D | Manual p.17 Note | — | — | — |
| A1 | §5 | schedlab Python package + two C++ programs (simulator, OpenMP executor); shared core | C Technical | C | D | schedlab/, cpp/schedsim.cpp, cpp/ompexec.cpp | — | — | — |
| A2 | §5 Table 2 | model.py: simulator, validator, LB = max(critical path, min work/m), serial_best | C Technical | C | D | schedlab/model.py bounds() | — | — | — |
| A3 | §5 Table 2 | workloads.py: seeded generator, hashing, split separation | C Technical | C | D | schedlab/workloads.py | — | — | — |
| A4 | §5 Table 2 | heuristics.py: six baselines, all insertion-based | C Technical | C | D | schedlab/heuristics.py (insert=True default) | — | — | — |
| A5 | §5 Table 2 | ga.py: GA + four controls/ablations | C Technical | C | D | ga.py METHODS | — | — | — |
| A6 | §5 Table 2 | rl.py: 12 features, REINFORCE, greedy policy | C Technical | C | D | rl.FEATURES (12); docstring | — | — | — |
| A7 | §5 Table 2 | adaptive.py: 9 features, tree + novelty guard, GA-1000 extension | C Technical | C | D | adaptive.FEATURES (9); GUARD_MARGIN | — | — | — |
| A8 | §5 Table 2 | runner/analysis: one raw row per (instance, method, repeat/seed) | C Technical | C | D | runs.csv row counts 14,850/17,550/13,500 | — | — | — |
| A9 | §5 Table 2 | schedsim: bit-exact port (hex-float I/O, numpy summation order, no FMA) | C Technical | C | D | cpp_xval manifest (5,400/5,400 identical); -ffp-contract=off | — | — | — |
| A10 | §5 Table 2 | ompexec: static replay with acquire/release flags, OpenMP tasks, serial, per-task trace | C Technical | C | D | cpp/ompexec.cpp execute(), spawn() | — | — | — |
| A11 | §5 | Every schedule validated before acceptance; derived metrics recomputed from raw | F Methodology | C | D | runner.py validate(); analysis.py | — | — | — |
| A12 | §5 | 19-column master.csv for every campaign; Execution_Time simulated (sim_tu) / replay seconds | F Methodology | C | D | 4 × master.csv headers; Time_Unit sim_tu / s | — | — | — |
| E1 | §6 | Host and software versions (M4 4P+6E, 16 GB, macOS 27.2, Python 3.12.9, NumPy 2.4.4, SciPy 1.17.1, sklearn 1.8.0, PyTorch 2.11.0, pandas 3.0.2, Matplotlib 3.10.8) | F Methodology | C | D | run manifests hardware/software; requirements.txt; M-D host_at_reconstruction | — | — | — |
| E2 | §6 | One worker, one thread; perf_counter_ns around the scheduler call only | F Methodology | C | D | runner.py lines 151–153 | — | — | — |
| E3 | §6 | S01/S03 on battery; S02 training and final campaign on mains | F Methodology | C | D | S02 manifest/model.json power strings; S01/S03 config notes | — | — | — |
| E4 | §6 | No GPU used | F Methodology | C | D | manifests gpu: null | — | — | — |
| E5 | §6 | torch.set_num_threads(1), deterministic algorithms, fixed seeds | F Methodology | C | D | rl.py lines 23–24; configs | — | — | — |
| E6 | §6 | GCC 15.2 flags, libgomp _OPENMP 201511, OMP_DYNAMIC=false, default wait policy, OMP_PROC_BIND unset | F Methodology | C | D | M-D manifest ompexec_version, omp_env, omp_wait_policy | — | — | — |
| E7 | §6 | Static non-preemptive schedules, shared insertion simulator and validator | C Technical | C | D | model.py; heuristics.py | — | — | — |
| E8 | §6 | Single worker 'without distortion of measured times caused by contention' | F Methodology | P | D | — | Design intent stated as a verified fact | minor | 'so that … are not distorted' |
| E9 | §6 | Replay: thread p runs processor p's tasks in order, waits on predecessor flags; OpenMP tasks start when predecessors finish | C Technical | C | D | ompexec.cpp static and tasks branches | — | — | — |
| E10 | §6 | Deterministic methods: 3 timing repeats with identical makespans 'claimed' | B Experimental | P | D | verify_campaign_result.json (determinism checked) | They are asserted/checked, not merely 'claimed' | minor | 'asserted' |
| E11 | §6 | Stochastic methods 'run once per technique with seeds 0, 1 and 2' | B Experimental | P | D | runs.csv algo_seed 0–2 | Run once per seed, not per technique | minor | 'once per seed' |
| E12 | §6 | S02: 3 training seeds + 1 ablation (seed 0); rows 14,850 / 17,550 / 13,500 | B Experimental | C | D | results/models; runs.csv | — | — | — |
| E13 | §6 | Four workload classes with CV 0.1 / 1.5 / 0.5 / 1.5 and platforms; n {50,100,200}, m {2,4,8}; OOD sets | C Technical | C | D | workloads.py CLASSES; configs/full.toml | — | — | — |
| E14 | §6 | Splits: train 1,080, val 180, test_id 360, test_ood 90; S02 48,000-instance stream; content-hash disjoint | F Methodology | C | D | full.toml per-cell counts (30/5/10 × 36 cells); manifests separation_checked=true; model.json episodes | — | — | — |
| E15 | §6 | Metric definitions (Cmax/LB, speedup serial_best/Cmax, efficiency speedup/m, utilization, ρ, regret) | C Technical | C | D | master.csv: Efficiency = Speedup/Resource_Count (max error 2e-16) | — | — | — |
| E16 | §6 | Statistics: paired, seed-mean, 10,000 bootstrap resamples, Wilcoxon, Holm, secondary CIs without p, Q3+3·IQR outlier flag | D Statistical | C | D | paired CSVs (wilcoxon_p NA on secondary rows); Timing_Outlier column | — | — | — |
| E17 | §6 | Replay: 360 × 15 methods × 3 granularities × 10 reps after 2 warm-ups = 194,400 runs, 54 min, mains | B Experimental | C | D | runs.csv (194,400; 162,000 timed); manifest wall_time_s_from_log 3,227 | Mains power: driver check + operator reading; exact string lost | — | — |
| E18 | §6 | Kernel llround(cost·u·813.1); R² 0.9997; randomized order with fixed seed | C Technical | C | D | ompexec.cpp iters_for; calibration manifest r2 0.99967; instance_order_seed | — | — | — |
| E19 | §6 | Accepted schedules re-derived exactly (10,350, 0 differences); C++ reproduced them bit for bit | B Experimental | C | D | rederive manifest summary | Coverage: 13 methods (not RANDOM-SELECT, ADAPTIVE-GA, GA-1000) | — | — |
| E20 | §6 | Median of 10 reps per instance; speedup T1/Tp; design locked before launch | F Methodology | C | D | per_instance.csv; MD_ANALYSIS_PLAN.md hash in MD report | — | — | — |
| E21 | §6 Table 3 | Computation simulated / measured; Scheduling, decision, inference times measured per run | F Methodology | C | D | raw scheduling_time_s, decision_time_s; replay compute_s | — | — | — |
| E22 | §6 Table 3 | Training time of S02 policies AND S03 selectors recorded in model.json 'measured' block | F Methodology | P | D | s02_rl_seed*/model.json measured.train_time_s present; s03_selector_v1/model.json has no measured/timing field | S03 part false | moderate | Remove S03 or state 'not recorded' |
| E23 | §6 Table 3 | Communication, data movement, energy NA (not modelled / unavailable) | F Methodology | C | D | master.csv NA counts = all rows | — | — | — |
| E24 | §6 Table 3 | Synchronization: NA in campaigns; replay static-mode dependency waiting; fork/join 8/14/47 µs | F Methodology | C | D | replay master Synchronization_Time NA on 25,920 tasks+serial rows; calibration_fork_join_and_threads.csv 8.3/13.5/47.3 µs | — | — | — |
| E25 | §6 Table 3 | Memory = process peak RSS in kB, upper bound per run | F Methodology | C | D | runner._peak_rss_kb (bytes//1024 on macOS) | — | — | — |
| E26 | §6 Table 4 | S01 GA settings (pop 60, 6,000 evals, tournament 3, crossover 0.9, σ 0.15, 2 elites, 3 seeds, seeded HEFT/MINMIN/FCFS-EAT) | B Experimental | C | D | ga.py DEFAULTS; configs/s01_final.toml; S01 verify (fitness_evals = 6000) | — | — | — |
| E27 | §6 Table 4 | ADAPTIVE: depth-2 tree, 9 features, trained on train, depth/SBS on val, guard → SBS | B Experimental | C | D | s03_selector_v1/model.json depth 2, sbs HEFT; adaptive.py | — | — | — |
| E28 | §6 Table 4 | RL: MLP 12→64→64→1, REINFORCE HEFT-relative advantage, 3,000 updates × 16 episodes, best val checkpoint | B Experimental | C | D | rl.py SETTINGS (hidden 64, batch 16, max_updates 3000); make_policy; model.json best_update | — | — | — |
| E29 | §6 Table 4 | Final campaigns: rows/times 14,850 & 7,106 s; 17,550 & 237 s; 13,500 & 80 s (+4 × ~16 min); 0 failures | B Experimental | C | D | runs.csv status counts; manifests wall_time_s; model.json train_time_s 930–959 s | — | — | — |
| T5a | §7.1 Table 5 | Heuristic makespans identical across the three campaigns (2,700 pairs) | B Experimental | C | D | raw runs.csv, 2,700/2,700 identical | — | — | — |
| T5b | §7.1 Table 5 | FCFS-EAT 1.581 / 2.859 / 0.682 / 0.852 / 0.0003 | A Numerical | C | D | S01 master.csv test_id | — | — | — |
| T5c | §7.1 Table 5 | HEFT 1.180 / 3.502 / 0.813 / 0.895 / 0.0004 | A Numerical | C | D | master.csv test_id (Cmax/LB 1.18046) | — | — | — |
| T5d | §7.1 Table 5 | MINMIN 1.391 / 2.959 / 0.705 / 0.716 / 0.0010 | A Numerical | C | D | S01 master.csv | — | — | — |
| T5e | §7.1 Table 5 | GA 1.157 / 3.546 / 0.830 / 0.900 / 0.563 | A Numerical | C | D | S01 master.csv (time = median of per-instance medians 0.5627) | — | — | — |
| T5f | §7.1 Table 5 | GA-KEYS-EFT 1.123 / 3.634 / 0.850 / 0.900 / 1.000 | A Numerical | C | D | S01 master.csv | — | — | — |
| T5g | §7.1 Table 5 | HILL-CLIMB 1.162 / 3.541 / 0.825 / 0.904 / 0.592 | A Numerical | C | D | S01 master.csv | — | — | — |
| T5h | §7.1 Table 5 | ADAPTIVE 1.181 / 3.502 / 0.813 / 0.890 / 0.0005 | A Numerical | C | D | S03 master.csv | — | — | — |
| T5i | §7.1 Table 5 | TRY-ALL speedup 3.514 (other cells 1.175 / 0.818 / 0.891 / 0.0025) | A Numerical | P | D | S03 master.csv speedup mean 3.51347 | Speedup rounds to 3.513; other cells correct | minor | 3.513 |
| T5j | §7.1 Table 5 | ADAPTIVE-GA efficiency 0.815 (other cells 1.179 / 3.504 / 0.893 / 0.0005) | A Numerical | P | D | S03 master.csv efficiency 0.81445 | Rounds to 0.814 | minor | 0.814 |
| T5k | §7.1 Table 5 | RL-S0/S1/S2 Cmax/LB, speedup, utilization, time | A Numerical | C | D | S02 master.csv | — | — | — |
| T5l | §7.1 Table 5 | RL-S0 efficiency 0.821 | A Numerical | P | D | S02 master.csv efficiency 0.82048 | Rounds to 0.820 | minor | 0.820 |
| T5m | §7.1 Table 5 | RL-NOHEFTFEAT 1.217 / 3.352 / 0.797 / 0.822 / 0.005 | A Numerical | C | D | S02 master.csv | — | — | — |
| T5n | §7.1 | Heterogeneous efficiency can exceed m-processor bound because baseline is one processor | C Technical | C | D | model.py serial_best definition | — | — | — |
| T6a | §7.2 Table 6 | S01 row: +1.169%, CI +0.96–1.39%, 330/114/6, p 6.2e-52, reject | A Numerical | C | D | s01_paired.csv all/GA/BEST-HEURISTIC | — | — | — |
| T6b | §7.2 Table 6 | S03 row: −0.016%, ratio CI 0.9991–1.0012, 6/342/12, p 0.78, not rejected | A Numerical | C | D | s03_paired.csv ADAPTIVE/SBS/test_id | — | — | — |
| T6c | §7.2 Table 6 | S02 row: ρ 1.0097 (0.97% longer), CI 1.0034–1.0160, 100/34/226, p 6.8e-6, reject | A Numerical | C | D | s02_paired.csv RL/HEFT/test_id | — | — | — |
| T6d | §7.2 footnote | S01 test_id +1.33% (CI 1.07–1.60%, p 3.0e-43); test_ood +0.54% (p 2.2e-10) | A Numerical | C | D | s01_paired.csv | — | — | — |
| T6e | §7.2 footnote | Holm-adjusted p: S01 ≤ 9.1e-43, S02 1.4e-5, S03 0.78; decisions unchanged by S01 population | D Statistical | C | D | 3·3.02e-43; 2·6.80e-6; 0.777 | — | — | — |
| T6f | §7.2 footnote | S03 and S02 populations fixed before their test evaluation | F Methodology | C | R | S02/S03 acceptance reports; S02_IMPLEMENTATION_PLAN | Process claim from records | — | — |
| S1 | §7.3 | GA mean improvement 1.169%, ties on 114/450 | A Numerical | C | D | s01_paired.csv | — | — | — |
| S2 | §7.3 | GA seeded with HEFT, MINMIN, FCFS-EAT and keeps best-so-far, so cannot be worse than them | C Technical | C | D | configs/s01_final.toml; ga.py elitism | — | — | — |
| S3 | §7.3 | Those heuristics were best on 405 of 450 instances | A Numerical | C | R | S01 report §B.1 (HEFT 326 + FCFS-EAT 58 + MINMIN 21) | — | — | — |
| S4 | §7.3 | All six losses where an 'unsampled' heuristic (LPT-EFT / FCFS-EFT) was best | C Technical | P | R | S01 report §B.2 | Should be 'unseeded' | minor | 'unseeded' |
| S5 | §7.3 | Median optimization 0.25 s (n=50) to 3.7 s (n=400); ~1,100–1,730× HEFT | A Numerical | C | D | s01_overhead_quality.csv | — | — | — |
| S6 | §7.3 | 'comparison is done in simulated time, while the GA optimization costs time' | J Wording | P | D | — | Garbled: the cost is measured real time | minor | 'costs measured wall-clock time' |
| S7 | §7.3 | Hill climber 0.90%; GA ahead by 0.27%, better on 190, worse on 162 | A Numerical | C | D | s01_paired.csv GA/HILL-CLIMB all: 0.27%, 190/98/162 | Wording '(a 0.27% lead for GA on 190 but 162 worse)' garbled | — | — |
| S8 | §7.3 | 'for this budget, GA does not need population and crossover' | G Conclusion | I | D | s01_paired.csv GA vs HILL-CLIMB CI 0.13–0.42% (excludes 0) | GA is detectably better; data show population/crossover add little, not nothing | major | 'add little at this budget' |
| S9 | §7.3 | Random sampling never beat its seeds; unseeded GA 17% worse | A Numerical | C | D | s01_paired.csv RANDOM-SEARCH 0/428/22; GA-UNSEEDED −16.96% | — | — | — |
| S10 | §7.3 | GA-KEYS-EFT evolves priorities only, append-mode EFT placement; beat GA 3.38% vs 1.17%; GA worse on 343 | A Numerical | C | D | s01_paired.csv; ga.py | — | — | — |
| S11 | §7.3 | GA-KEYS-EFT seeds are decoded task orders; no never-worse guarantee | C Technical | C | R | S01 report §E.1; ALGORITHM_DESIGN §3.5 | — | — | — |
| S12 | §7.3 | Its advantage is a smaller search space that is easier to search at 6,000 evaluations | G Conclusion | U | D | — | Plausible explanation, not tested | minor | Mark as a hypothesis |
| S13 | §7.3 | Primary method fixed before test and unchanged | F Methodology | C | D | configs/s01_final.toml lock test; S01 execution provenance | — | — | — |
| T7 | §7.3 Table 7 | Five rows: improvements, ratio CIs, better/tie/worse | A Numerical | C | D | s01_paired.csv all/BEST-HEURISTIC | — | — | — |
| S14 | §7.3 | H1 'confirmed' vs FCFS (+19.7%) | D Statistical | C | D | s01_paired.csv GA/FCFS-EAT all 19.68% | 'supported' would be more precise (style) | — | — |
| S15 | §7.3 | H1b: 'superiority of the algorithm' fell from 2.5% (n=50) to 1.0% (n=400) | D Statistical | P | D | s01_overhead_quality.csv paired_impr_vs_HEFT 2.48% → 0.96% | Baseline (HEFT) not named | minor | Name HEFT |
| S16 | §7.3 | Gains concentrated on heterogeneous classes | A Numerical | C | R | S01 report §B.4 (heterogeneous 3.13%) | — | — | — |
| F1 | §7.3 captions | Figures 1, 2a, 2b, 3 captions (content, statistics, sources) | F Methodology | C | D | results/figures/20261017T044734Z-…/g1,g2,g3 files exist; build_docx mapping | Figure images not visually re-inspected | — | — |
| D1 | §7.4 | Primary S03 result is null; H3 not supported | D Statistical | C | D | s03_paired.csv | — | — | — |
| D2 | §7.4 | 'ADAPTIVE outperformed SBS (HEFT) on just 18 out of 360' | A Numerical | I | D | s03_paired.csv: better 6 / tie 342 / worse 12 | It differed on 18 and was better on only 6 | critical | 'chose differently on 18 (better 6, worse 12)' |
| D3 | §7.4 | The 18 were heterogeneous instances where the tree chose MINMIN | A Numerical | C | R | S03 report §D (HEFT 72, MINMIN 18) | — | — | — |
| D4 | §7.4 | 'the gap narrowed by −0.03 (95% CI −0.30, 0.19)' | D Statistical | P | D | s03_paired.csv gap_closed −0.029 [−0.299, 0.185] | Numbers correct; 'narrowed' contradicts a negative value | moderate | 'gap closed −0.03; CI includes 0' |
| D5 | §7.4 | HEFT best on 71% of training instances | A Numerical | C | D | s03_selector_v1/model.json train_label_counts HEFT 763/1080 = 70.6% | — | — | — |
| D6 | §7.4 | HEFT within 0.48% of oracle on test_id; max selector gain 0.45% | A Numerical | C | R | S03 report §B, s03_robustness.csv | — | — | — |
| D7 | §7.4 | 'H3b holds by definition' | D Statistical | P | D | ARCHITECTURE H3b is an empirical cost comparison | Not true by definition; it held empirically | minor | 'H3b held' |
| D8 | §7.4 | Decision time ≈ 0.15 ms; TRY-ALL ≈ 2.5 ms | A Numerical | C | D | s03_robustness.csv decision_time_s_median 0.000147; TRY-ALL 0.0025 | — | — | — |
| D9 | §7.4 | 'total time for SBS is about 0.5 ms' | A Numerical | I | D | S03 master.csv median call: HEFT 0.37 ms, ADAPTIVE 0.54 ms | 0.5 ms is ADAPTIVE's call time | moderate | Attribute 0.5 ms to ADAPTIVE |
| D10 | §7.4 | OOD: guard fell back on 66% (all n=400, 19/20 fork-join); rest chose HEFT; ADAPTIVE = SBS on 90/90 | A Numerical | C | D | s03_paired.csv test_ood 0/90/0; decisions.csv; S03 report §D | — | — | — |
| D11 | §7.4 | 'deficiencies of fixed policies came about through the distribution' (MINMIN ood_cv regret 63%) | J Wording | P | R | S03 report §C.2 (63.4%) | Number correct; sentence meaning lost ('grew out of distribution') | minor | Reword |
| D12 | §7.4 | Contingency rule: val SBS–VBS gap < 2% (observed 0.66%), θ = 2% | B Experimental | C | D | s03_selector_v1/model.json val_sbs_vbs_gap 0.00663, contingency_threshold 0.02 | — | — | — |
| D13 | §7.4 | ADAPTIVE-GA 'beat' SBS by 0.10% (gap-closed CI −0.20–0.66) | D Statistical | P | R | S03 report §C.1 | CI includes 0: not resolved, so 'beat' overstates | minor | 'improved the mean by 0.10% (not resolved)' |
| D14 | §7.4 | No gain on test_ood; 5–28× HEFT time; GA-1000 +0.87% at 155–282× | A Numerical | C | R | S03 report §E; s03_ga_extension_overhead.csv | — | — | — |
| F2 | §7.4 captions | Figures 4, 5, 6 captions | F Methodology | C | D | results/figures/20261017T083329Z-…/g7,g8,g9 files exist | — | — | — |
| R1 | §7.5 | All three seeds learned on val (beat untrained network with CI below 0, beat FCFS-EAT) | B Experimental | C | R | S02_PILOT_REPORT §9 | — | — | — |
| R2 | §7.5 | ~16 min and 48,000 episodes each; no behaviour-cloning fallback | B Experimental | C | D | model.json train_time_s 930–959, episodes 48000, behaviour_cloning false | — | — | — |
| R3 | §7.5 | RL vs FCFS-EAT ρ 0.822 (CI 0.802–0.841); trails HEFT 0.97% | A Numerical | C | D | s02_paired.csv | — | — | — |
| R4 | §7.5 | p 6.8e-6; RL worse on 226/360; verdict 'matches' (CI inside ±2%); 'improves' not met | D Statistical | C | D | s02_paired.csv; ALGORITHM_DESIGN §4.6 band | — | — | — |
| R5 | §7.5 | Seeds 0 and 1 CIs include 1 (0.999, 1.002); seed 2 2.8% worse | A Numerical | C | D | s02_paired.csv RL-S0 [0.9923,1.0058], RL-S1 [0.9949,1.0086], RL-S2 1.0283 | — | — | — |
| R6 | §7.5 | RL beat HEFT at m=2 (0.973) and on heterogeneous (0.984); 'failed' as m grew (1.039 at m=8) | A Numerical | P | D | S02 master.csv recomputed 0.973 / 0.984 / 1.039 | Numbers right; 'failed' overstates a 3.9% shortfall | minor | 'worsened' |
| R7 | §7.5 | Generalised to ood_size (0.983) and ood_cv; not ood_procs (1.034) or ood_struct (1.038) | A Numerical | C | D | s02_generalization.csv | — | — | — |
| R8 | §7.5 | Removing HEFT features cost 3.7 points of ρ; 'the policy is based on HEFT's features' | D Statistical | P | D | s02_paired.csv RL-NOHEFTFEAT 1.0358 vs RL-S0 0.9990 | Number right; 'based on' overstates 'relies substantially on' | minor | 'relies substantially on' |
| R9 | §7.5 | Inference 50–140 µs per decision, 12–18× HEFT's time | A Numerical | C | D | s02_overhead.csv per_decision 47–139 µs; ratio 12.2–17.7 | — | — | — |
| F3 | §7.5 captions | Figures 7, 8, 9 captions | F Methodology | C | D | results/figures/20261017T115054Z-…/g4,g5,g6 files exist | — | — | — |
| Y1 | §7.6 | HEFT simulated speedup 1.91/3.30/5.30, efficiency 0.95/0.82/0.66; GA 1.98/3.34/5.32; FCFS-EAT 1.67/2.79/4.12 | A Numerical | C | D | master.csv recomputed | — | — | — |
| Y2 | §7.6 | Efficiency falls 'because of the restricted parallelism of the DAGs' | G Conclusion | U | D | — | Explanation not tested (no DAG-width analysis cited) | minor | Support or mark as likely explanation |
| Y3 | §7.6 | GA gain vs 'the optimal heuristic' 2.59/1.04/0.35% | C Technical | P | R | S01 report §B.4 | Numbers right; 'optimal' should be 'best' | minor | 'best heuristic' |
| Y4 | §7.6 | TRY-ALL headroom over HEFT 0.96 / 0.31 / 0.09% | A Numerical | P | D | S03 master.csv recomputed 0.963 / 0.310 / 0.0849 | m=8 rounds to 0.08 | minor | 0.08% |
| Y5 | §7.6 | RL/HEFT 0.973 → 1.017 → 1.039; 1.034 at m=16 | A Numerical | C | D | S02 master.csv; s02_generalization.csv | — | — | — |
| Y6 | §7.6 | HEFT Cmax/LB 1.144 / 1.180 / 1.217 by n | A Numerical | C | D | S01 master.csv | — | — | — |
| Y7 | §7.6 | GA gain by n 1.98/1.08/0.91%; optimization 0.25 → 3.7 s | A Numerical | C | R | S01 report §B.4; s01_overhead_quality.csv | — | — | — |
| Y8 | §7.6 | RL/HEFT by n 1.014 / 1.010 / 1.005; 0.983 at n=400 | A Numerical | P | D | S02 master.csv recomputed 1.0135 / 1.0101 / 1.0054; ood_size 0.9827 | n=50 rounds to 1.013 | minor | 1.013 |
| Y9 | §7.6 | S03 decision 0.10 → 0.19 ms (n 50→200); RL 50–140 µs/decision | A Numerical | C | D | S03 master.csv Decision_Time medians 0.10/0.13/0.19 ms | — | — | — |
| Y10 | §7.6 | Larger DAGs raise search cost faster than benefit; more processors leave less room | G Conclusion | C | D | Y6–Y9 | Supported (wording garbled) | — | — |
| Y11 | §7.6 | Measured HEFT efficiency 0.96 / 0.79 / 0.42 (1 ms) | A Numerical | C | D | summary_by_method_m_granularity.csv 0.963 / 0.787 / 0.423 | — | — | — |
| Z1 | §7.7 | HEFT near the ceiling; gains beyond it cost scheduling time | G Conclusion | C | D | Tables 5–8 | Scoped to these workloads | — | — |
| Z2 | §7.7 | 'choice of heuristics could only do 0.45% better than HEFT and lost all of it' | D Statistical | P | D | s03_paired.csv TRY-ALL vs SBS +0.45%; ADAPTIVE −0.016% | Meaning: 0.45% available, none recovered; 'lost' misleading | minor | Reword |
| Z3 | §7.7 | Learned policy within 1% of HEFT at ~16× cost | A Numerical | C | D | s02_paired; s02_overhead | — | — | — |
| Z4 | §7.7 | Only search beat HEFT, ~1–3% at three orders of magnitude more time | A Numerical | C | D | GA 1.56%, GA-KEYS-EFT 3.76% vs HEFT; 1,100–1,730× | — | — | — |
| Z5 | §7.7 | Results 'confirm' literature's explanation of HEFT dominance [2] | G Conclusion | P | R | CITATION_VERIFICATION [2] | Consistent with, not confirmation of | minor | 'consistent with' |
| Z6 | §7.7 | Cited gains [8]–[10],[13] came with stochastic durations, 'dynamic cluster size', 'task rule switching', other problem classes | E Citation | P | R | CITATION_VERIFICATION [8],[9],[10],[13] | Terms altered (dynamic clusters; step-level rule switching) | minor | Restore terms |
| Z7 | §7.7 | 'hill climbing with the same seed values performed equally' | A Numerical | I | D | s01_paired.csv GA vs HILL-CLIMB +0.27% (CI 0.13–0.42), 190/98/162 | Not equal: nearly as well | major | 'nearly as well' |
| Z8 | §7.7 | A smaller representation (GA-KEYS-EFT) did better | A Numerical | C | D | s01_paired.csv | — | — | — |
| Z9 | §7.7 | GA's edge carries to real threads in aggregate | A Numerical | C | D | comparisons.csv M1 | — | — | — |
| Z10 | §7.7 | ADAPTIVE +0.8% end-to-end at 1 ms, +27% at 10 µs; TRY-ALL +10% to ×4.2; supports H4 (3 sizes, 1 host) | A Numerical | C | D | comparisons.csv 1.008 / 1.267; 1.103 / 4.185 | — | — | — |
| X1 | §7.8 | All values measured wall-clock seconds unless marked simulated | F Methodology | C | D | Table 8 columns | — | — | — |
| X2 | §7.8 | Repetition noise CV 1.9% (1 ms) and 3.5% (10 µs) | A Numerical | P | D | per_instance.csv median wall_cv 1.85% / 3.49% | Correct values but they are medians (statistic not named) | minor | 'median CV' |
| X3 | §7.8 | 'the GA scheduling was 1.6% faster than HEFT's scheduling' | C Technical | I | D | comparisons.csv M1 = measured execution of the schedules; GA scheduling time is ~10³× HEFT's (s01_overhead_quality.csv) | Inverts scheduler cost vs schedule execution | critical | 'GA schedules executed 1.6% faster than HEFT schedules' |
| X4 | §7.8 | Simulated 1.8%; tie within noise on 240/360 | A Numerical | C | D | comparisons.csv sim_geo_mean_ratio 0.9818; ties 240 | — | — | — |
| X5 | §7.8 | Matched simulation at m=2 (0.964 vs 0.964) | A Numerical | C | R | MD_ACCEPTANCE_REPORT §5; own recomputation 0.963 (geo-mean of seed means) | Within 0.001; analysis-code value 0.964 | — | — |
| X6 | §7.8 | 'zero at m=8 (0.999)' | A Numerical | P | R | MD report: 0.999 measured vs 0.996 simulated | Advantage vanished; 'zero' imprecise | minor | 'vanished (0.999)' |
| X7 | §7.8 | ADAPTIVE ran HEFT's schedule on 342; 0.8% slower with Python decision time | A Numerical | C | D | comparisons.csv M2 sim_identical 342, 1.0079 | — | — | — |
| X8 | §7.8 | OpenMP tasks 19% slower; faster on about half the instances only at m=8 | A Numerical | C | D | comparisons.csv 1.1879; per_instance.csv TASKS<HEFT share m=8 49.2% (12.5% / 9.2% at m=2/4) | — | — | — |
| X9 | §7.8 | HEFT speedup saturated beyond 4 threads (1.93 / 3.15 / 3.39) | A Numerical | C | D | summary_by_method_m_granularity.csv 1.925 / 3.149 / 3.387 | — | — | — |
| X10 | §7.8 | 39–51% of threads at m=8 (39% at 1 ms) ran '1.3× slower' | A Numerical | P | D | thread_slowdown.csv share_threads_over_1_3 0.388 / 0.490 / 0.510 | 'more than 1.3×' (threshold, not the slowdown) | minor | 'more than 1.3×' |
| X11 | §7.8 | 'consistent with efficiency cores; observed from timing, not placement' | F Methodology | P | D | M-D manifest: no placement recorded; omp_analysis.py note 'no pinning' | Correctly hedged, but 'observed' mislabels an inference | moderate | 'inferred from timings; placement not recorded' |
| X12 | §7.8 | Dependency waiting 19–28% of thread time at m=8 | A Numerical | C | D | summary_by_method_m_granularity.csv HEFT dep_wait_share 0.189–0.277 | — | — | — |
| X13 | §7.8 | After the ≈8% serial offset, simulation within 3% at m≤4, ≥100 µs; underestimates 1.5–2.4× at m=8 | A Numerical | C | D | G_adj 1.016–1.032 (m≤4); 1.54–2.38 (m=8) | — | — | — |
| T8 | §7.8 Table 8 | Six rows (ratios, CIs, simulated, win/tie/loss, Holm p) | A Numerical | C | D | comparisons.csv us_per_tu=10.0 | — | — | — |
| F4 | §7.8 caption | Figure 10 caption | F Methodology | C | D | md1/md2 CSVs; fig10 report view | — | — | — |
| V1 | §8 | Quality results simulated (no communication, exact costs, free dispatch) | F Methodology | C | D | model.py | — | — | — |
| V2 | §8 | Replay: synthetic kernel, no memory traffic, no data on edges, hetero via iteration counts | F Methodology | C | D | ompexec.cpp kernel/iters_for(cost[t][p]) | — | — | — |
| V3 | §8 | 'one unpinned Apple M4, so its m = 8 results reflect this core mix' | F Methodology | P | D | no placement recorded | Inference presented as fact | minor | 'likely reflect' |
| V4 | §8 | Raw gaps include ≈8% serial offset; M2 uses decision times from another process; host records lost, manifest reconstructed | F Methodology | C | D | SERIAL G_raw 1.07–1.09; M-D manifest RECONSTRUCTED, lost_fields | — | — | — |
| V5 | §8 | One generator; HEFT dominance may be generator-specific | G Conclusion | C | D | workloads.py single generator | Appropriately hedged | — | — |
| V6 | §8 | S01/S03 timed on battery (84% → 15% in S01) | F Methodology | C | R | S01 report §A; config notes | — | — | — |
| V7 | §8 | Outliers: S01 130/14,850 (0.9%; 1.35×, 86×); S03 448/17,550 (2.6%; 2.84×, 212×); S02 23/13,500 (0.2%; 1.81×, 2.4×) | A Numerical | C | D | master.csv Timing_Outlier; ratio to group median recomputed | — | — | — |
| V8 | §8 | 83% of ADAPTIVE-GA outliers called GA (5% of its runs); all RANDOM-SELECT outliers drew MINMIN (17%) | A Numerical | C | D | decisions.csv joined to master.csv: 82.7% / 5.3%; 100% / 16.7% | — | — | — |
| V9 | §8 | S02's lower outlier rate coincides with mains power but is not isolated as cause; simulated makespans unaffected by power | G Conclusion | C | D | heuristic re-run reproduction (verify results) | — | — | — |
| V10 | §8 | S01 population not predeclared; S02 fixed in plan; 3 seeds rough; OOD cells 10–40 (ood_cv 10) | D Statistical | C | D | s02_generalization.csv instances 10–40 | — | — | — |
| V11 | §8 | 'Seeded approaches will never beat their seeds' | C Technical | I | D | s01_paired.csv GA vs HEFT 338/112/0 (GA beats its seed HEFT on 338) | Inverted: they cannot LOSE to their seeds | critical | 'cannot be worse than their seeds' |
| V12 | §8 | RL training ended at budget with return still rising; no hyperparameter search | B Experimental | C | D | model.json stop_reason max_updates; rl.py SETTINGS 'predeclared; no tuning' | — | — | — |
| V13 | §8 | One student — pending approval; Batches 1–3/7 objective not met; none invented | H Compliance | C | D | no approval/findings in repository | — | — | — |
| V14 | §8 | Literature verification levels per reference | F Methodology | C | D | CITATION_VERIFICATION.md status line | — | — | — |
| W1 | §9 | GA 1.17% below best heuristic at ~10³× time; hill climber nearly as good; keys-only GA better | A Numerical | C | D | s01_paired; s01_overhead_quality | Contradicts §7.7's 'performed equally' (internal inconsistency) | — | — |
| W2 | §9 | Adaptive selection no improvement (−0.016%, p 0.78) | A Numerical | C | D | s03_paired.csv | — | — | — |
| W3 | §9 | RL ~18% better than FCFS; matched HEFT within ±2%; trailed by a significant 1% | A Numerical | C | D | s02_paired.csv | — | — | — |
| W4 | §9 | AI scheduling improves over conventional policy but not over a strong one without more scheduling time | G Conclusion | C | D | Tables 5–8 | Scoped by 'these' earlier in the paragraph | — | — |
| W5 | §9 | OpenMP: GA gain held in aggregate (1.6%), not per instance or at 8 threads; adaptive slower end-to-end | A Numerical | C | D | comparisons.csv | — | — | — |
| W6 | §9 Future work | Reviewed RL work reports advantages under duration noise [9] | E Citation | C | R | CITATION_VERIFICATION [9] | — | — | — |
| REF1 | §10 References | Bibliographic entry [1] (authors, title, venue, year, DOI) | E Citation | C | S | S2 record: CSUR 1999, Kwok & Ahmad | — | — | — |
| REF2 | §10 References | Bibliographic entry [2] (authors, title, venue, year, DOI) | E Citation | C | S | S2: IEEE TPDS 2002 | — | — | — |
| REF3 | §10 References | Bibliographic entry [3] (authors, title, venue, year, DOI) | E Citation | C | S | S2: JPDC 2001 | — | — | — |
| REF4 | §10 References | Bibliographic entry [4] (authors, title, venue, year, DOI) | E Citation | C | S | S2: IEEE TPDS 1994 | — | — | — |
| REF5 | §10 References | Bibliographic entry [5] (authors, title, venue, year, DOI) | E Citation | C | S | S2: INFORMS J. Comput. (ORSA J. Comput.) 1994 | — | — | — |
| REF6 | §10 References | Bibliographic entry [6] (authors, title, venue, year, DOI) | E Citation | C | S | S2: J. Grid Comput. 2021 | — | — | — |
| REF7 | §10 References | Bibliographic entry [7] (authors, title, venue, year, DOI) | E Citation | C | S | S2: IEEE TPDS 2025, author 'Rui Lu' | — | — | — |
| REF8 | §10 References | Bibliographic entry [8] (authors, title, venue, year, DOI) | E Citation | C | S | S2 year 2018 (arXiv); Crossref 2019 per ERRATA | Year 2019 rests on Crossref record (R) | — | — |
| REF9 | §10 References | Bibliographic entry [9] (authors, title, venue, year, DOI) | E Citation | C | S | S2: IEEE CLUSTER 2021 | — | — | — |
| REF10 | §10 References | Bibliographic entry [10] (authors, title, venue, year, DOI) | E Citation | C | S | S2: ACM TIST 2023 | — | — | — |
| REF11 | §10 References | Bibliographic entry [11] (authors, title, venue, year, DOI) | E Citation | C | S | S2: Advances in Computers 1976 | — | — | — |
| REF12 | §10 References | Bibliographic entry [12] (authors, title, venue, year, DOI) | E Citation | C | S | S2 year 2018; Crossref 2019 per ERRATA | Year rests on Crossref (R) | — | — |
| REF13 | §10 References | Bibliographic entry [13] (authors, title, venue, year, DOI) | E Citation | C | S | S2 year 2024; Crossref vol. 173 Jan 2025 per ERRATA | Year rests on Crossref (R) | — | — |
| REF14 | §10 References | Bibliographic entry [14] (authors, title, venue, year, DOI) | E Citation | C | S | S2: Holm 1979 | — | — | — |
| REF15 | §10 References | Bibliographic entry [15] (authors, title, venue, year, DOI) | E Citation | C | R | Not found in Semantic Scholar; CITATION_VERIFICATION Crossref/OpenAlex record | Not re-verified | — | — |
| REF16 | §10 References | Bibliographic entry [16] (authors, title, venue, year, DOI) | E Citation | C | S | S2: Statistical Science 1986 | — | — | — |
