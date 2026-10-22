# Academic-integrity and originality audit (2026-10-18) — for the student's review

Scope: `CS15_Integrated_Report_DRAFT.md`, `CS15_Individual_Technical_Note_DRAFT.md`, and the literature-review
companion (`CS15_Literature_Review_DRAFT.docx`, built from report §3.2–3.3, §10 and `CITATION_VERIFICATION.md`).
Nothing was rewritten. No data, model, configuration, provenance or result was changed.

## 0. What this audit cannot establish

- **The Turnitin scores cannot be determined here.** The faculty's thresholds are an AI-writing score ≤ 10 % and a
  similarity score ≤ 8 %. Neither can be measured or predicted without the actual Turnitin report:
  - Turnitin compares against web pages, publications and earlier student submissions, which are not available here;
  - its AI-writing indicator is a proprietary model.
- **What was done instead** is a local check:
  - word-sequence overlap against the reference abstracts available from OpenAlex, plus four saved full texts
    ([1], [4], [8], [12]);
  - a sentence-by-sentence comparison for the abstract-based summaries;
  - overlap between the three documents themselves.
  Abstracts were not retrievable for [3], [6], [11] and [15].
- **No changes to dodge detectors.** This audit does not recommend wording changes designed to get past AI detectors
  or similarity matching. The recommendations below concern attribution, accuracy and authorship only.

## 1. The central issue: AI assistance and authorship

What happened, as far as I can see (the sessions visible to me):
- **Prose.** The report, the technical note, the literature review and `CITATION_VERIFICATION.md` were drafted by an
  AI assistant (Claude, in Claude Code).
- **Code.** Most of the code (`schedlab/`, `cpp/`) and the analysis and verification scripts were written by the same
  assistant.
- **Your role.** You directed the work and made the decisions recorded in the milestone requests: scope, the S01
  settings, the S03 contingency choice, the S02 plan, the C++/OpenMP plan and its defaults, and the handling of the
  M-D defect.
- **Earlier sessions.** Work done in sessions not visible to me (the 2026-10-11 milestones under another account) is
  not characterised here.

Consequences:
- **No AI-use policy is available here.** No integrity or AI-use policy exists in the repository, and the course
  manual (`Case_Study_Manual (1).pdf`) says nothing about generative AI, plagiarism or similarity scores. Before
  submission, obtain the applicable VIT / faculty policy on generative-AI use.
- **The AI-writing score.** Text drafted by an AI assistant is likely to be flagged by an AI-writing indicator. The
  ethical ways to meet a 10 % limit are:
  - write the sections yourself, from your own understanding, in your own words;
  - disclose the assistance as the policy requires;
  - ask the faculty how AI-assisted code and text are treated.
  Running the drafts through paraphrasing or "humanizer" tools to lower the score would misrepresent authorship.
  This audit does not support that.
- **Disclosure.** None of the documents discloses AI assistance at present. Whether a disclosure is *required*
  depends on the policy you obtain. A factual template for you to correct and complete:

  > *AI assistance.* An AI coding assistant (Claude, via Claude Code) was used to implement parts of the software
  > (`schedlab/`, `cpp/`), to run and check the experiments, and to draft parts of this document. The research
  > questions, design decisions and acceptance of each milestone were mine; all reported numbers come from the saved
  > data and scripts in the repository. [State precisely which sections you wrote yourself.]

## 2. Audit table

Priority:
- **H**: necessary for integrity or accuracy before submission;
- **M**: should be fixed;
- **L**: optional improvement.

Locations are Markdown sources; the Word files are rebuilt from them.

| # | Location | Passage (start) | Concern | Evidence | Recommended correction | Priority |
|---|---|---|---|---|---|---|
| 1 | Note §1, first sentence | "I designed and implemented the shared scheduling core and all three sub-problems" | Authorship claim in your voice, drafted by the AI assistant; the code was largely written with AI assistance | §1 above | Rewrite yourself so it states what you did and what the assistant did; add the disclosure the policy requires | **H** |
| 2 | Note §4 "What I learned" (all five items) | "A strong cheap heuristic sets a high bar…" | First-person reflections drafted by the AI assistant: not your own experience | Drafted in these sessions | Replace with what *you* learned, in your words, or remove the section | **H** |
| 3 | All three documents, interpretive prose | Abstract; §3.1–3.3; §7.7; §9 (report); note §2 | AI-drafted text, undisclosed; the parts most likely to be judged as your own writing | §1 above | Rewrite these sections yourself from your understanding (the data and tables can stay); disclose per policy | **H** |
| 4 | Report §3.2, RL paragraph, sentence 1 | "…improved average job completion time by at least 21% over hand-tuned heuristics…" | 10 consecutive words copied from the source without quotation marks | Matches [8]'s abstract and full text: "improve average job completion time by at least 21% over hand-tuned scheduling heuristics" | Either quote it exactly with the citation, or restate in your own words (e.g. that Decima reported a ≥ 21 % lower average job completion time than tuned heuristics in its cluster experiments [8]) | **H** |
| 5 | Report §3.2, evolutionary paragraph, Bean sentence | "Bean [5] presented a genetic algorithm with random keys for sequencing and optimization problems, including multiple-machine scheduling…" | Patchwriting: same sequence and phrasing as the abstract | [5] abstract: "a general genetic algorithm to address a wide variety of sequencing and optimization problems including multiple machine scheduling…" | Rephrase in your own words, keeping the citation and the content (random keys as sort keys, so offspring stay feasible) | M |
| 6 | Report §3.2, first paragraph, HEFT sentence | "…HEFT … and CPOP for a bounded number of heterogeneous processors…" | 7-word phrase from the abstract | [2] abstract, same phrase | Put the phrase in quotation marks or reword it ("for a fixed set of heterogeneous processors") | L |
| 7 | Report §3.2, RL paragraph, Zhadan sentence | "…reported an average 5.32% gain over the best baseline (DONF) on random DAGs" | Close paraphrase of the abstract; full text not read | [10] abstract: "an average performance gain of 5.32%, compared to the best scheduling algorithm, DONF … on a large number of random DAGs" | Keep the citation; say it is the abstract's figure, and reword | L |
| 8 | Report §3.2, Jiang [7] and READYS [9] sentences | "…real-relative encoding whose every chromosome decodes…", "…combined graph convolutional networks with an actor-critic method…" | Close to the abstracts' structure (both cited) | [7] and [9] abstracts | Light rewording in your own words | L |
| 9 | Literature-review companion (`.docx`) | Entire document | 61.5 % of its words are verbatim runs (≥ 8 words) from the report, since it is built from §3.2–3.3 and §10. If both are submitted, a similarity check can match one against the other | Local overlap check | Submit it only if the faculty ask for it. Otherwise ask for own-submission matches to be excluded, or write a distinct literature review | M |
| 10 | Report §7.8 | "about half of the threads at m = 8 ran more than 1.3× slower than calibrated" | Overstated for the primary task size | `thread_slowdown.csv`: 38.8 % (1 ms), 49.0 % (100 µs), 51.0 % (10 µs) | "39–51 % of the threads (39 % at 1 ms tasks)" | M |
| 11 | Report §7.8; note §3 and §4 | "(efficiency cores, no pinning)", "efficiency cores at 8 threads" | Stated as the cause; it is an inference from timing, since core placement was not observed | `docs/MD_ACCEPTANCE_REPORT.md` §6 says "almost certainly" | "consistent with threads running on efficiency cores (inferred from task timings; core placement was not recorded)" | M |
| 12 | Report §6, environment paragraph | "no thread pinning (not supported on macOS)" (also "macOS ignores OMP_PROC_BIND" in `cpp/README.md` and the M-D config) | Not tested in this project, and no source given | No test or citation | "No thread pinning was used" (fact); add a source for the macOS statement or drop it | M |
| 13 | Note §1, C++/OpenMP bullet | "exact re-derivation of every accepted search, learned and adaptive schedule" | Overclaim: RANDOM-SELECT, ADAPTIVE-GA and GA-1000 were not re-derived | `results/raw/20261017T162329Z-rederive-21e353a7/manifest.json` (13 methods) | "of the accepted schedules of 13 search, learned and adaptive methods" | M |
| 14 | Report §6, measured-execution paragraph | "A task runs a compute kernel of cost × 813 iterations per µs-of-work" | Imprecise formula | `cpp/ompexec.cpp`: iterations = llround(cost · K), K = 813.1 × (µs per `sim_tu`) | "a task of cost c runs llround(c · u · 813.1) kernel iterations, u = µs per sim_tu (813.1 iterations/µs, calibrated)" | L |
| 15 | Report abstract vs §3.1 | Abstract: "NP-hard"; §3.1: "NP-complete in the general case [1], [2]" | Inconsistent terms | [1] and [2] both say NP-complete (decision version) | Use one formulation, e.g. "NP-hard (its decision version is NP-complete [1], [2])", or "NP-complete" in both | L |
| 16 | Report §6 and §8; `docs/MD_ANALYSIS_PLAN.md` | OpenMP task semantics; libgomp wait policy "spin, then sleep" | Technical claims without a source | No citation | Cite the OpenMP API specification (version 4.5) and the GCC libgomp manual, after checking both records | L |
| 17 | Abstract, §7.7, §9 | "HEFT … near the ceiling…" stated three times | Repetition | — | Keep it once in the conclusion; vary the others in your own words | L |
| 18 | Report §3.2 claims for [6], [7], [10], [16]; [5] | Abstract-level summaries | Full texts not read | `CITATION_VERIFICATION.md`; retried 2026-10-18: ACM ([10]) Cloudflare check and Project Euclid ([16]) security check, neither bypassed; [5], [6], [7] paywalled | Open [10] and [16] in your own browser and [5], [6], [7] via the library; confirm or correct the four claims; update `CITATION_VERIFICATION.md` | M |
| 19 | Bibliography | All 16 entries | — | All 16 DOIs agree between the report list and `references.bib`; years, volumes and pages agree with OpenAlex; the [7] "Ruiqi/Rui Lu" difference is recorded | None | — |

No passage was found that cites a source for something the source does not say (claim check of 2026-10-17, still
valid). No numerical result needs changing; items 10–15 are wording accuracy only. All negative and null results stay.

## 3. Original to the project vs taken from the literature

"Original to the project" means *not taken from the cited works*. It does **not** settle who wrote it (see §1).

| Taken from the literature (cited) | Original to this project |
|---|---|
| List scheduling, upward rank, HEFT and its insertion policy [2]; Min-min [3]; DAG-scheduling terminology [1] | The shared simulator with append and insertion modes, and the proofs relating them (`docs/ARCHITECTURE.md` §3.1); the cost model and workload generator |
| Random-key encoding idea [5]; GA scheduling in general [4], [6], [7] | The GA design actually used (keys + assignment, heuristic seeding), its equal-budget controls (random search, hill climbing, unseeded GA) and the keys-only ablation |
| Policy-gradient RL in general; RL for DAG scheduling [8]–[10] | The candidate-scoring policy, its features, the HEFT-relative advantage, and the training and evaluation protocol |
| Algorithm selection, SBS/VBS and gap-closed evaluation [11], [12]; ML selection for scheduling [13] | The nine workload features, the selector with a novelty guard, and the GA contingency extension |
| Holm [14], Wilcoxon [15], percentile bootstrap [16] | The predeclared hypotheses, primary comparisons and verdict bands; every experimental result in Tables 5–8 and Figures 1–10 |
| — | The C++ port with bit-exact cross-validation; the OpenMP executor; the measured replay and its findings |

## 4. Passages you should personally review and rewrite from your own understanding

1. **Technical note:** §1 (individual contribution), §4 (what I learned), §5 (limitations) — items 1–3.
2. **Report abstract and §9 conclusion:** these are where your own synthesis is expected.
3. **Report §3 (introduction, literature review, research gap):** fix items 4–8 while rewriting.
4. **Report §7.7** (comparative discussion) and the interpretive sentences of §7.3–7.5 and §7.8.
5. **Accuracy items 10–15:** short factual edits; each can be checked against the cited file.
6. **A disclosure statement** (§1), once you have the policy.

## 5. Changes that are genuinely necessary for academic integrity

1. **Authorship.** Correct the note's authorship statement and replace the AI-drafted "What I learned" (items 1, 2).
2. **Disclosure.** Obtain the AI-use policy and add the disclosure it requires (§1).
3. **Quotation.** Quote or restate the copied Decima phrase (item 4); rephrase the Bean sentence (item 5).
4. **Unsupported wording.** Fix the overstated or untested statements (items 10–13).
5. **Self-overlap.** Decide with the faculty how the literature-review companion is submitted (item 9).
6. **Full texts.** Read [10] and [16] (free) and [5], [6], [7] (library), and confirm the four abstract-level
   claims (item 18).

Everything else (items 6–8 and 14–17) is optional improvement.
