# Citation verification table (updated 2026-10-17, literature-verification milestone)

**Two kinds of verification are recorded separately.**
- *Bibliographic*: existence, title, authors, year, venue and DOI checked against at least one database record
  (Semantic Scholar (S2), Crossref or OpenAlex). Done for all 16 references.
- *Content*: what was actually read to check the claim the report attributes to the source, at one of four levels.
  **Full-text verified** = a complete copy of the paper (published version or author/repository copy) was obtained
  and every claim the report attributes to it was checked against the text. **Partially verified** = only part of
  the text could be read (some sections or pages, or a preprint version). **Abstract only** = abstract or publisher
  summary only. **Metadata only** = title and bibliographic record only. Nothing is marked full-text verified
  unless its text was read.

| # | Reference (IEEE style) | DOI | Bibliographic check | Content check (what was read) | Recent (≥ 2021) | Claim(s) supported in the report | Notes / discrepancies |
|---|---|---|---|---|---|---|---|
| [1] | Y.-K. Kwok, I. Ahmad, "Static scheduling algorithms for allocating directed task graphs to multiprocessors," *ACM Comput. Surv.*, vol. 31, pp. 406–471, 1999 | 10.1145/344588.344618 | S2, ACM record, OpenAlex | **Full-text verified** (published version, 66 pp., from the second author's university page; read: abstract, §3 NP-completeness, §5 list-scheduling techniques, insertion vs non-insertion passages, §9 summary; rest searched) | no (seminal) | DAG scheduling "in general an NP-complete problem" (§3); 27 algorithms classified in a taxonomy; list scheduling = node priorities + processor allowing the earliest start; insertion into idle time slots; surveyed studies use randomly generated DAGs | ACM copy blocked (HTTP 403 / bot check) |
| [2] | H. Topcuoglu, S. Hariri, M.-Y. Wu, "Performance-effective and low-complexity task scheduling for heterogeneous computing," *IEEE TPDS*, vol. 13, pp. 260–274, 2002 | 10.1109/71.993206 | S2 | **Partially verified** (copy of the published article on a third-party document site: abstract, introduction, algorithm description) | no (seminal) | HEFT: highest upward rank first, processor minimising earliest finish time with an insertion-based approach; NP-complete in the general case; low scheduling cost | — |
| [3] | T. D. Braun *et al.*, "A comparison of eleven static heuristics for mapping a class of independent tasks onto heterogeneous distributed computing systems," *J. Parallel Distrib. Comput.*, vol. 61, pp. 810–837, 2001 | 10.1006/jpdc.2000.1714 | S2 | **Partially verified** (author-institution copies, Colorado State and NPS repositories: abstract, results, summary) | no (seminal) | Independent tasks; GA best in all cases, best GA solution always from a Min-min-seeded population; Min-min close to the best at a very small execution time | Earlier report wording corrected after this check |
| [4] | E. Hou, N. Ansari, H. Ren, "A genetic algorithm for multiprocessor scheduling," *IEEE TPDS*, vol. 5, pp. 113–120, 1994 | 10.1109/71.265940 | S2 | **Full-text verified** (scan of the published article, 8 pp., from the second author's NJIT page; read in full via OCR) | no (seminal) | GA (per-processor task lists, height-ordered so offspring stay legal) compared with a list-scheduling algorithm and known optimal schedules on random task graphs (2–5 identical processors) and two robot-dynamics task graphs; within 10% of optimal and consistently better than list scheduling | Deterministic model, identical processors, no communication costs |
| [5] | J. C. Bean, "Genetic algorithms and random keys for sequencing and optimization," *ORSA J. Comput.*, vol. 6, pp. 154–160, 1994 | 10.1287/ijoc.6.2.154 | S2 | **Partially verified** (University of Michigan Technical Report 92-43, revised December 1993, from Deep Blue: abstract, introduction and start of §1 only; rest of the PDF not retrievable; published version not read) | no (seminal) | Random keys: solutions encoded as random numbers used as sort keys, so all offspring are feasible; applied to multiple-machine scheduling, resource allocation and quadratic assignment | Preprint version; indexed under successor title *INFORMS J. Comput.* |
| [6] | M. Sulaiman, Z. Halim, M. Lebbah, M. Waqas, S. Tu, "An evolutionary computing-based efficient hybrid task scheduling approach for heterogeneous computing environment," *J. Grid Comput.*, vol. 19, no. 1, Art. 11, 2021 | 10.1007/s10723-021-09552-4 | S2, Crossref | **Abstract only** (Springer article page; paywalled; HAL record hal-04456319 is a notice without a file; no open copy found) | **yes** | HHG and HTDG (GA + list heuristic; HTDG adds task duplication); initial population improved by two guided chromosomes; compared with NGA, EGA-TS, HEFT, PEFT on best-result count, average makespan, SLR, speedup and running time | Abstract claims better "average running time" than the counterparts; see recommendation C2 |
| [7] | J. Jiang, Z. Sun, R. Lu, L. Pan, Z. Peng, "Real relative encoding genetic algorithm for workflow scheduling in heterogeneous distributed computing systems," *IEEE TPDS*, vol. 36, no. 1, pp. 1–14, 2025 | 10.1109/TPDS.2024.3492210 | S2, Crossref | **Abstract only** (OpenAlex abstract; closed access, no repository copy found) | **yes** | Real numbers encode relative task positions in the schedulable set; any crossover/mutation result decodes to a valid (precedence-respecting) schedule; simplifies genetic operations | "Ruiqi Lu" (Crossref) vs "Rui Lu" (S2) |
| [8] | H. Mao, M. Schwarzkopf, S. B. Venkatakrishnan, Z. Meng, M. Alizadeh, "Learning scheduling algorithms for data processing clusters," in *Proc. ACM SIGCOMM*, 2019, pp. 270–288 | 10.1145/3341302.3342080 | S2, Crossref | **Full-text verified** (arXiv 1810.01963 version, 19 pp.; not compared line by line with the published version) | no | Jobs as DAGs; RL with graph neural networks; average job completion time improved "by at least 21%" over hand-tuned heuristics | S2 year 2018 (arXiv) vs Crossref 2019 → 2019 |
| [9] | N. Grinsztajn, O. Beaumont, E. Jeannot, P. Preux, "READYS: A reinforcement learning based strategy for heterogeneous dynamic scheduling," in *Proc. IEEE CLUSTER*, 2021, pp. 70–81 | 10.1109/Cluster48925.2021.00031 | S2 | **Partially verified** (author-hosted PDF: abstract, experimental results, conclusion) | **yes** | GCN + A2C; similar to HEFT at low duration noise, better than HEFT as noise grows; transfer from small to larger graphs | — |
| [10] | A. Zhadan *et al.*, "Multi-agent reinforcement learning-based adaptive heterogeneous DAG scheduling," *ACM Trans. Intell. Syst. Technol.*, vol. 14, no. 5, pp. 1–26, 2023 | 10.1145/3610300 | S2, Crossref, OpenAlex | **Abstract only** (ACM lists a free PDF, but every route tried hit HTTP 403 or a bot check; not bypassed) | **yes** | Different heuristic rule chosen at each scheduling step via multi-agent RL; compared with DONF, CPOP, HCPT, HPS, PETS; average 5.32% gain over DONF on random DAGs, up to 30% on specific topologies | Free PDF should open in a normal browser: https://dl.acm.org/doi/pdf/10.1145/3610300 |
| [11] | J. R. Rice, "The algorithm selection problem," *Advances in Computers*, vol. 15, pp. 65–118, 1976 | 10.1016/S0065-2458(08)60520-3 | Crossref | **Metadata only** (definition also stated in [12] and [13], both read in full) | no (seminal) | Algorithm selection problem: problem space, algorithm space, performance measure, features, selection mapping | — |
| [12] | P. Kerschke, H. H. Hoos, F. Neumann, H. Trautmann, "Automated algorithm selection: Survey and perspectives," *Evol. Comput.*, vol. 27, no. 1, pp. 3–45, 2019 | 10.1162/evco_a_00242 | S2, Crossref | **Full-text verified** (arXiv 1811.11597 version, 47 pp.) | no | SBS and VBS (oracle) definitions; closing the SBS–VBS gap as an evaluation measure; Rice's framework | S2 year 2018 vs Crossref 2019 → 2019 |
| [13] | A. Uzunoglu, C. Gahm, A. Tuma, "Machine learning based algorithm selection and genetic algorithms for serial-batch scheduling," *Comput. Oper. Res.*, vol. 173, Art. 106827, 2025 | 10.1016/j.cor.2024.106827 | S2, Crossref, OpenAlex | **Full-text verified** (open-access copy, CC BY-NC-ND, from the University of Augsburg OPUS repository; read: abstract, introduction, related work, ASP method, experimental setup, performance metric, results, conclusions) | **yes** | Learning-to-rank selection (best: gradient-boosted trees) among 17 learning-augmented construction heuristics, per instance; two GAs improve the selected heuristic's solutions; selection beats the single best heuristic in every (n, m) group (MRIW 6.42% vs 2.23%); best GA MRIW 39.19% | 39.19% is a mean relative improvement over the *worst* of six compared methods (MRIW), not over a baseline; see recommendation C1. ScienceDirect blocked |
| [14] | S. Holm, "A simple sequentially rejective multiple test procedure," *Scand. J. Statist.*, vol. 6, pp. 65–70, 1979 | 10.2307/4615733 | S2, OpenAlex | **Metadata only** (method reference; JSTOR, not read) | no (methods) | Holm correction (claim is the method's name) | Crossref returns 404 for this JSTOR DOI |
| [15] | F. Wilcoxon, "Individual comparisons by ranking methods," *Biometrics Bulletin*, vol. 1, no. 6, p. 80, 1945 | 10.2307/3001968 | Crossref, OpenAlex | **Metadata only** (method reference; closed access) | no (methods) | Wilcoxon signed-rank test (claim is the method's origin) | Records give only the first page (80), so no page range is cited |
| [16] | B. Efron, R. Tibshirani, "Bootstrap methods for standard errors, confidence intervals, and other measures of statistical accuracy," *Statist. Sci.*, vol. 1, no. 1, pp. 54–75, 1986 | 10.1214/ss/1177013815 | S2, OpenAlex, Project Euclid record | **Abstract only** (states the last third "deals mainly with bootstrap confidence intervals"; Project Euclid lists a free PDF, but it is behind a security check, not bypassed; no other open copy found) | no (methods) | Bootstrap confidence intervals (general) | Percentile method not confirmed in this paper's text; see recommendation C4 |

**Manual requirement:** at least 5 scholarly papers, at least 3 recent → **met**: 16 references (13 scholarly works on
the topic plus three statistics method references); **5** published 2021 or later: [6], [7], [9], [10], [13].

**Content-verification status:** full-text verified — [1], [4], [8], [12], [13]; partially verified — [2], [3], [5],
[9]; abstract only — [6], [7], [10], [16]; metadata only — [11], [14], [15]. Of the five recent works, [9] and [13]
have been read (partly and fully); [6], [7] and [10] are still checked against their abstracts only.

**Author names** are given as in the record used (initials where the record gives initials).

**Considered and not cited:** Y.-T. Song *et al.*, *Comput. Electr. Eng.* 107 (2023), DOI
10.1016/j.compeleceng.2023.108653 — metadata verified, but no abstract was retrievable.

## Claim check against the integrated report (2026-10-17)

Every sentence in `CS15_Integrated_Report_DRAFT.md` that cites [1], [4]–[7], [10], [13] or [16] was checked against
what was read. Corrections C1–C5 below were **applied** to the report on 2026-10-17 (C4 as option (b); the same C4
wording was applied to the technical note). The sentences quoted are the earlier wording.

**Supported as written**
- §3.1 "Finding an optimal schedule is NP-complete in the general case [1], [2]" — [1] §3: "The DAG scheduling
  problem is in general an NP-complete problem".
- §3.2 "Kwok and Ahmad [1] surveyed and classified 27 static algorithms …" — abstract and §4 taxonomy. The listed
  vocabulary (task priority, processor selection, insertion into idle slots, random-graph evaluation) all appears in
  §5–§6 and in the studies the survey reports.
- §3.2 "Hou, Ansari and Ren [4] applied a genetic algorithm … compared it with list scheduling and optimal schedules
  on random task graphs" — §VIII and Tables I–IV of [4].
- §3.2 "Bean [5] presented a genetic algorithm with random keys … including multiple-machine scheduling" — abstract
  and §1 of the technical-report version.
- §3.2 [6]: guided chromosomes; better average makespan than two GAs and HEFT/PEFT — abstract.
- §3.2 [7]: "every chromosome decodes to a precedence-valid schedule, simplifying the genetic operators" — abstract.
- §3.2 [10]: rule chosen per step by multi-agent RL; average 5.32% over DONF on random DAGs — abstract.
- §3.2 [13]: ML selection among construction heuristics, then GA improvement — full text (§§2, 4, 5, 8).
- §3.3 research gap: [13]'s gains come from a different problem class (serial-batch scheduling with weighted
  tardiness) — full text; [10]'s from step-level rule switching — abstract.

**Corrections (applied 2026-10-17)**
- **C1 ([13], §3.2, needed).** Sentence: "Uzunoglu *et al.* [13] used machine-learning selection among construction
  heuristics for a serial-batch scheduling problem, followed by GA improvement, and reported a 39.19% average
  increase in solution quality." The full text defines 39.19% as the MRIW of the best GA (GA-J2P): the mean relative
  improvement over the worst final objective value among the six methods compared (§6.3, Table 9). It is not an
  improvement over a baseline. Suggested replacement: "Uzunoglu *et al.* [13] used learning-to-rank models to
  select, per instance, among learning-augmented construction heuristics for a serial-batch scheduling problem.
  Selection beat the single best heuristic in every size group (mean relative improvement over the worst compared
  method, 6.42% vs 2.23%), and GA improvement of the selected solutions raised it to 39.19%." This also strengthens
  the S03 discussion, since [13] is a case where per-instance selection did beat the single best solver. Applied; the report
  remains 12 pages in Microsoft Word.
- **C2 ([6], §3.2, recommended).** Sentence: "Optimization time is reported in [6] but the quality–time trade-off
  against a microsecond-scale heuristic is not the focus." The abstract states that the method also performs better
  on "average running time" than its counterparts. Without the full text, "not the focus" cannot be checked.
  Suggested replacement: "[6]'s abstract reports better average running time than its counterparts; how that time
  compares with HEFT's could not be checked, as the full text was not accessible."
- **C3 ([10], §3.2, recommended).** Sentence: "*Limitations relative to our question:* gains are reported in
  settings with stochastic durations, cluster dynamics or step-level rule switching, against baselines whose
  placement rules and overheads differ; the RL policy's own inference overhead and training cost are not the
  headline metric." For [8] and [9] this rests on text that was read; for [10] only on its abstract. Suggested
  change: insert "(for [10], from its abstract)" after "headline metric", matching the "(from the abstracts)" scoping
  already used in the evolutionary paragraph.
- **C4 ([16], §3.2 and §6, conditional).** Sentences: "effect sizes carry percentile bootstrap confidence intervals
  [16]" and "95% percentile-bootstrap CIs [16]". [16]'s abstract confirms that it covers bootstrap confidence
  intervals, but its description of the percentile interval was not read. Options: (a) open the free Project Euclid
  PDF in a normal browser and confirm the percentile interval in its confidence-interval part; or (b) change the
  wording to "bootstrap confidence intervals (percentile method) [16]", keeping the citation for bootstrap intervals
  in general. A candidate primary source for the percentile method itself is B. Efron, "Nonparametric standard errors
  and confidence intervals," *Canadian Journal of Statistics*, vol. 9, no. 2, 1981, §4 "The percentile method". It
  was seen only in a search excerpt; its record and DOI have not been verified, so it is **not** added. Applied as
  option (b): §3.2 "bootstrap confidence intervals (percentile method) [16]"; §6 "95% bootstrap CIs (percentile
  method) [16]"; note §2 the same wording with [7].
- **C5 ([1], §3.2, optional wording).** "established the vocabulary used here" → "describe the vocabulary used
  here" (subject: Kwok and Ahmad). The survey collects terms that predate it; the content is supported either way.

**Access log (legitimate routes only; no bot check, CAPTCHA or login was bypassed).**
- **[1]:** ACM blocked (403 / bot check). Author page copy at ranger.uta.edu obtained.
- **[4]:** IEEE closed. Author page copy at web.njit.edu (scanned) obtained.
- **[5]:** INFORMS closed. Deep Blue technical report: only the first pages were readable; the PDF itself is gated
  by a browser script.
- **[6]:** Springer paywall. HAL record has no file; Unpaywall and OpenAlex show no open copy.
- **[7]:** IEEE closed; OpenAlex and Unpaywall show no open copy.
- **[10]:** ACM free PDF blocked (403 / bot check); no preprint found.
- **[13]:** ScienceDirect blocked. University of Augsburg OPUS repository copy obtained.
- **[16]:** Project Euclid free PDF behind a security check; no other open copy found.

**Still to verify (you, in a normal browser or with library access):**
- [10] via the free ACM PDF;
- [16]'s percentile interval via the free Project Euclid PDF;
- full texts of [6] and [7] (paywalled);
- the published version of [5];
- optionally [14] and [15], if the method references should be read rather than cited by name.
