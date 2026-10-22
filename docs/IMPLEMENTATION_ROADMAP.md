# Implementation Roadmap

Nothing below has been started. Implementation begins only after your approval.

Today is 2026-10-11; the manual's deadline is 2026-10-19. The dates are a suggestion that fits that window.

---

## Target repository layout

```
cs15/
├── README.md                 exact commands to reproduce (manual requirement)
├── requirements.txt          pinned: numpy, scipy, scikit-learn, torch, matplotlib, pandas, pytest
├── pytest.ini                puts the repo root on the import path for tests
├── configs/
│   ├── pilot.toml
│   ├── cost_probe.toml       heuristic timing at campaign sizes
│   ├── full.toml
│   ├── identity.toml         Student_ID / Batch_ID placeholders
│   └── ablation_*.toml
├── schedlab/
│   ├── __init__.py           empty
│   ├── __main__.py           CLI: train-rl | train-selector | run | analyze
│   ├── model.py              Instance, Schedule, ScheduleBuilder, validate, bounds, upward_rank
│   ├── workloads.py          generators, class presets, seeds, splits, hashing
│   ├── heuristics.py         six heuristics + registry
│   ├── ga.py                 S01
│   ├── rl.py                 S02
│   ├── adaptive.py           S03
│   ├── runner.py             campaign loop, timing, CSV, manifest
│   └── analysis.py           derived metrics, statistics, tables, figures
├── tests/
│   ├── test_model.py  test_workloads.py  test_heuristics.py
│   ├── test_ga.py  test_rl.py  test_adaptive.py
│   ├── test_pipeline.py      integration
│   └── test_results.py       campaign validation
├── models/                   trained RL and selector files + metadata
├── results/
│   ├── raw/<campaign_id>/    runs.csv, traces, manifest.json, run.log   (read-only once finished)
│   ├── derived/              master.csv, summary tables                 (regenerable)
│   └── figures/              pdf, svg, source csv                       (regenerable)
└── docs/                     these documents
```

Nine source modules. Each sub-problem lives in exactly one file, so the individual contribution of each is easy to
point to in the report.

Setup: all packages are already installed on this machine. `requirements.txt` pins the installed versions for anyone
else reproducing the work. Nothing new needs installing.

---

## Phases (dependency order)

| # | Phase | Depends on | Deliverables | Acceptance criteria | Suggested day |
|---|---|---|---|---|---|
| 0 | Approvals | — | Your approval of the audit and milestone 1. Separately, **faculty** approval of the scope and tool deviations (`ARCHITECTURE.md` §1.1, §1.2) | Your approval gates phase 1. Faculty approval gates submission, not coding; it is not assumed | Oct 11–12 |
| L | Literature review (separate task, runs in parallel) | — | ≥ 5 scholarly papers, ≥ 3 recent, each verified against a bibliographic source before it is cited | Status: **not started.** Done only when every reference has been checked to exist with matching authors, title, venue and year | by Oct 17 |
| 1 | Core model and simulator | 0 | `model.py`, `test_model.py` | All `test_model` tests pass, including the four broken-schedule tests, hand-computed cases and the insertion tests | Oct 12 |
| 2 | Workload generator | 1 | `workloads.py`, `test_workloads.py` | Tests pass; split hash sets disjoint; class CV within tolerance | Oct 12 |
| 3 | Baseline heuristics | 1 | `heuristics.py`, `test_heuristics.py` | Tests pass; all six valid and deterministic on 500 random instances | Oct 12 |
| 4 | Runner and analysis skeleton | 2, 3 | `runner.py`, `analysis.py` (derive `master.csv` + one figure), `__main__.py`, `test_pipeline.py` | Heuristics-only pilot produces `runs.csv` → `master.csv` with the manual's 19 columns; integration test passes | Oct 13 |
| 5 | S01 genetic algorithm | 3, 4 | `ga.py` with controls, `test_ga.py` | Tests pass; no result below the brute-force optimum on tiny instances (optimum hit rate recorded as a diagnostic); budgets match across GA, random search and hill climb; evaluations/second measured | Oct 13–14 |
| 6 | S03 adaptive selector | 3, 4 | `adaptive.py`, `test_adaptive.py`, `train-selector` | Tests pass; `SBS`–`VBS` gap on `val` measured; contingency decision recorded | Oct 14 |
| 7 | S02 reinforcement learning | 3, 4 | `rl.py`, `test_rl.py`, `train-rl` | Tests pass; pilot training shows validation improvement over update 0; leakage guard active | Oct 15–16 (time box: 2 days) |
| 8 | Pilot gate | 5, 6, 7 | Pilot campaign + gate checklist (methodology §6) | Core criteria P1–P7 pass; P8–P10 pass for each sub-problem that proceeds; runtime projected from measured costs | Oct 16 |
| 9 | *(Optional, off by default)* Real-execution replay | 8 | Replay a few schedules with real threads running calibrated busy loops; compare measured wall time with simulated makespan × `τ` | Reported as a simulator-gap measurement on a handful of instances; clearly separate from all other results | only if time remains |
| 10 | Freeze and full campaign | 8 | Tuned configs; trained models with hashes; `results/raw/<campaign>/` | `test_results.py` passes on the campaign; raw directory read-only | Oct 16–17 (overnight) |
| 11 | Analysis | 10 | `master.csv`, T1, T2, G1–G10 with source CSVs | Every figure regenerates from `master.csv` with one command; statistics for the three primary comparisons | Oct 17 |
| 12 | Report and README | 11 | Individual technical notes, batch report (Word), README with exact commands | Report sections follow the manual's format; every speedup names its baseline; limitations and ≥ 3 future directions present; ≥ 5 verified references | Oct 18 |
| — | Buffer | | | | Oct 19 |

S03 (phase 6) comes before S02 (phase 7) on purpose: it is cheap once the heuristics exist, and RL carries the most
risk, so it goes last where an overrun cannot block the other two.

---

## First implementation milestone (M1) — implemented 2026-10-11, awaiting review

Phases 1–3 only: the shared core that every sub-problem needs, whatever faculty decide about scope.

| | |
|---|---|
| Files | `schedlab/model.py`, `schedlab/workloads.py`, `schedlab/heuristics.py`, `tests/test_model.py`, `tests/test_workloads.py`, `tests/test_heuristics.py`, `requirements.txt` |
| Not included | runner, CSV output, analysis, GA, RL, selector, any experiment |
| Done when | `pytest` passes every test listed for those three files in `VALIDATION_PLAN.md` §1; all six heuristics produce valid, deterministic schedules on 500 seeded random instances; split hash sets are disjoint |
| Cost | Seconds of compute. No packages installed. |

---

## Milestone M2 — implemented 2026-10-11, awaiting review

Roadmap phase 4: `runner.py`, `analysis.py`, `__main__.py`, configs, `tests/test_pipeline.py`, heuristics-only pilot.
Deferred from the runner to the GA milestone, where they first matter: resuming an interrupted campaign and
multi-worker execution. `tests/test_results.py` does not exist yet; its checks currently live in `analysis.check()`,
which `analyze` runs on every campaign.

---

## Milestone S01 — implemented 2026-10-11

Roadmap phase 5: `schedlab/ga.py`, `tests/test_ga.py`, `configs/ga_pilot.toml`, runner and analysis integration.
Pilot on the `val` split only (`results/raw/20261011T165803Z-ga_pilot-3955b13e`); the full campaign has not been run.

Decisions on the pilot's open questions (user, 2026-10-17, on `val` evidence only, before any test evaluation):

1. **Primary variant:** the full `GA` (keys + assignment), as predeclared. `GA-KEYS-EFT` stays as a prominent ablation
   and its results are reported as they are.
2. **Seed set:** the predeclared three heuristic seeds (`HEFT`, `MINMIN`, `FCFS-EAT`).
3. **Budget:** 6,000 evaluations.

## Milestone S01 closeout — 2026-10-17

- Audit of the improvement formulas and of `GA-KEYS-EFT` (`DATA_SCHEMA.md` §4.1, `ALGORITHM_DESIGN.md` §3.5).
- G2a, G2b, G3, the paired table and the overhead–quality table, with tests (`tests/test_analysis_s01.py`, new
  tests in `tests/test_ga.py`).
- Final campaign with the locked `configs/s01_final.toml` (methodology §7.2). Provenance in `provenance/s01_final/`.
- Outcome and acceptance status: `docs/S01_ACCEPTANCE_REPORT.md`. Campaign complete and verified (14,850 rows,
  0 failures, all checks passed, 201 tests passed).
- **Accepted by the user on 2026-10-17 as technically complete** (campaign integrity, tests, validated outputs,
  provenance). Acceptance is technical; the scientific conclusions are the scope-limited observations in the report's
  §F. Report wording amended the same day (`provenance/s01_final/REPORT_AMENDMENTS.md`); no data changed.

## Milestone S03 — pilot implemented 2026-10-17, awaiting review

Roadmap phase 6: `schedlab/adaptive.py`, `tests/test_adaptive.py`, `train-selector`, `configs/s03_pilot.toml`,
runner and analysis integration. Selector `results/models/s03_selector_v1` (`820ba281844c513e`), pilot
`results/raw/20261017T075602Z-s03_pilot-eeb28bc3` on `val` only. Pilot criteria S03-P1 to P5 pass; **S03-P6: the §5.7
contingency triggered** (`SBS`–`VBS` gap 0.663% on `val`), which blocks the full S03 campaign until you decide how (or
whether) to add the GA member. Report: `docs/S03_PILOT_REPORT.md`. Full S03 campaign and S02 not started.

Update 2026-10-17: you chose option 2 (GA-1000 member, threshold label). Implemented as a separately labelled
contingency extension (`s03_selector_ga_v2`, `6d83fac40cb5c6ed`, θ = 2% chosen on `val`); the six-heuristic selector
stays primary. Extension pilot `20261017T082349Z-s03_pilot_ga-8d8bac5a` passes its checks and is reproducible
(report §8).

Full S03 campaign run once on 2026-10-17 with the locked `configs/s03_final.toml`
(`results/raw/20261017T083329Z-s03_final-b8e5be9a`): 17,550 / 17,550 rows, 0 failures, all checks and 223 tests pass,
figures reproduce, provenance in `provenance/s03_final/`. Primary result (`ADAPTIVE` vs `SBS`, `test_id`): −0.016%,
p = 0.78, gap closed −0.03 (CI −0.30–0.19), i.e. no detectable improvement. Report: `docs/S03_ACCEPTANCE_REPORT.md`.
- **Accepted by the user on 2026-10-17 as technically complete** (integrity, tests, reproducible figures,
  provenance). Technical acceptance only: the primary hypothesis was not supported. `ADAPTIVE` stays primary,
  `ADAPTIVE-GA` a separate extension. Raw data, pilots, models and provenance preserved; no rerun.
- S02: implementation plan drafted for review (`docs/S02_IMPLEMENTATION_PLAN.md`); nothing implemented or trained.

## Milestone S02 — pilot implemented 2026-10-17, awaiting review

Plan approved with its three decisions. `schedlab/rl.py`, `tests/test_rl.py`, `train-rl`, `configs/s02_pilot.toml`,
runner and analysis integration; 236 tests pass. Pilot policy `s02_pilot_seed0` (`580faad134361f1a`, 300 updates,
97 s, mains power); pilot campaign `20261017T090051Z-s02_pilot-04ee0d92` on `val` only. Criteria S02-P1 to P6 pass;
BC fallback not triggered. Report: `docs/S02_PILOT_REPORT.md`.

Full training done 2026-10-17 (approved; AC power; predeclared settings, no overrides): `RL-S0` `c827a9f51c512ac4`,
`RL-S1` `e83496e27b9d4ef1`, `RL-S2` `1765acd48d43dfde`, `RL-NOHEFTFEAT` `a7781d888bca8550`; 3,000 updates each,
63 min total; no fallback; §4.6 "learned" on `val` for 3 of 3 seeds (report §9).

Final S02 campaign run once 2026-10-17 on AC power with the locked `configs/s02_final.toml`
(`results/raw/20261017T115054Z-s02_final-898ee9e1`): 13,500 / 13,500 rows, 0 failures, all checks and 238 tests
pass, figures reproduce, provenance in `provenance/s02_final/`. Primary (`RL` vs `HEFT`, `test_id`): mean ρ 1.0097
(CI 1.0034–1.0160 [corrected 2026-10-17, see docs/report/ERRATA.md]), p = 6.8e-6 → predeclared verdict "matches" (within ±2%) with a significant ~1% shortfall;
improves over `FCFS-EAT` (ρ 0.822); seed-dependent. Holm family complete. Report: `docs/S02_ACCEPTANCE_REPORT.md`.
- **Accepted by the user on 2026-10-17 as technically complete** (integrity, tests, reproducible figures,
  provenance). Technical acceptance only: RL improves over `FCFS-EAT` but not over `HEFT` (small significant
  shortfall, seed-dependent). Raw data, models, pilots and provenance preserved; no rerun.

---

## Priorities if time runs short

Cut from the bottom:

1. Core, heuristics, runner, analysis (phases 1–4) — without these there is no result at all.
2. S01 GA with `RANDOM-SEARCH` and `GA-UNSEEDED` controls.
3. S03 `ADAPTIVE` with `SBS`, `VBS`, `TRY-ALL`.
4. S02 RL with one OOD set (`ood_size`).
5. Remaining OOD sets; remaining ablations; `ADAPTIVE-TOP2`.
6. Phase 9 replay.

Never cut: validation tests, the leakage guard, the strong baseline, overhead reporting.

---

## Reproduction commands (to go in README once implemented)

```
pip install -r requirements.txt
pytest
python -m schedlab run --config configs/pilot.toml
python -m schedlab train-selector --config configs/full.toml
python -m schedlab train-rl --config configs/full.toml
python -m schedlab run --config configs/full.toml
pytest tests/test_results.py --campaign results/raw/<campaign_id>
python -m schedlab analyze results/raw/<campaign_id>
```
