# C++ components

`schedsim` is the C++ workload simulator: an independent port of the Python scheduling core
(`schedlab/model.py`: instance checks, `ScheduleBuilder` in append and insertion mode, `validate`, `bounds`,
`upward_rank`; `schedlab/heuristics.py`: the six baselines; `schedlab/ga.py`: `decode`). Times are simulated time
units (`sim_tu`), not seconds. `ompexec` is the OpenMP executor: it runs schedules on real threads and measures
wall-clock seconds (section at the end).

## Build

```bash
make -C cpp
```

Defaults: Homebrew GCC 15.2 (`g++-15`), `-O2 -std=c++17 -Wall -Wextra -Wno-psabi -ffp-contract=off -fno-fast-math`.
`-ffp-contract=off` is required: without it GCC on arm64 may fuse `a*b+c` into FMA, and the cross-language checks
are bit-exact. `cpp/build/schedsim version` prints the compiler and flags it was built with.

## Commands

| Command | Output |
|---|---|
| `schedsim version` | build identification |
| `schedsim dump INSTANCE` | the parsed instance, re-emitted (edges sorted) |
| `schedsim bounds INSTANCE` | `bounds serial_best cp_min work_lb lower_bound` |
| `schedsim ranks INSTANCE` | per task: mean cost, upward rank |
| `schedsim heuristics INSTANCE` | result blocks `NAME:insert` and `NAME:append` for the six heuristics |
| `schedsim eval INSTANCE JOBS` | one result (or `error`) block per job |
| `schedsim validate INSTANCE CHECKS` | one `verdict LABEL COUNT` block per check, with `violation` lines |

Exit code 1 means the input was malformed: the same conditions `make_instance` rejects (edge not `u < v`, duplicate
edge, non-positive or non-finite cost), or a malformed job file. An infeasible placement order (a task placed
before its predecessors, or an out-of-range processor) is not fatal: it gives an `error LABEL message` block.

## File formats

Every double is a C99 hex float (`%a`; Python `float.hex()` / `float.fromhex()`), so no decimal rounding happens.

Instance:
```
schedsim-instance 1
id <instance id>
size <n> <m> <edges>
<u> <v>                 one line per edge, 0 <= u < v < n
<cost[t][0]> ... <cost[t][m-1]>     one line per task
end
```

Jobs (for `eval`):
```
job <label> append|insert
order <t ...>           placement order, n task ids
proc <p ...>            processor per task id
end
keys <label>            GA decode: highest key among ready tasks, ties to the lowest id, append mode
key <hex ...>
proc <p ...>            or `proc -` for the GA-KEYS-EFT decoder (earliest-finish processor)
end
```

Checks (for `validate`): `check <label>`, then `proc`, `start` and `finish` lines, then `end`.

Result: `result <label>`, `makespan <hex>`, n lines `<proc> <start> <finish>`, `end`.

## Matched semantics (verified by `tests/test_cpp_interop.py`)

- Same placement rules, tolerance (`1e-9·max(1, |x|)`) and tie rules (lowest task id, then lowest processor id)
  as the Python code.
- Mean cost uses numpy's pairwise summation (`numpy.mean(axis=1)`). Column sums are sequential, except for m = 1,
  where numpy sums the contiguous column pairwise. These orders were determined empirically on numpy 2.4.4 and are
  checked bit for bit.
- The tests include integer-cost instances, so exact-fit gaps and ties occur. Five deliberately broken builds
  (summation order, gap-fit boundary, priority tie, key tie, single-column sum) were each caught by the tests.

Campaign-scale check (V4) against the accepted campaigns, which are read and not modified:

```bash
python -m schedlab.interop xval-heuristics --config configs/s01_final.toml \
  --campaign results/raw/20261017T044734Z-s01_final-430d8a10 \
  --campaign results/raw/20261017T083329Z-s03_final-b8e5be9a \
  --campaign results/raw/20261017T115054Z-s02_final-898ee9e1
```

Re-derivation of the accepted search, learned and adaptive schedules (V6): S01 `GA`, `GA-UNSEEDED`,
`GA-KEYS-EFT`, `RANDOM-SEARCH`, `HILL-CLIMB` (seeds 0–2); S02 `RL-S0`–`RL-S2`, `RL-NOHEFTFEAT`; S03 `ADAPTIVE`,
`ADAPTIVE-TOP2`, `ADAPTIVE-NOGUARD`, `TRY-ALL`. Each is rebuilt from its locked config and the runner's per-run seed.
Every schedule must reproduce the accepted `makespan_sim` exactly, S03 decisions must equal `decisions.csv`, and
`schedsim` must replay each schedule bit for bit. The schedules are saved as job files for the OpenMP executor:

```bash
python -m schedlab.rederive --workers 8            # all instances; --limit K for a pilot
```

## ompexec — OpenMP executor (measured seconds)

Built by the same `make -C cpp` with `-fopenmp` (GCC 15 libgomp, `_OPENMP` = 201511). Each task runs a dependent
floating-point chain of `llround(cost[t][p] · K)` iterations; `K` (iterations per `sim_tu`) is fixed per granularity
from calibration. The kernel is `noipa` with an empty-asm barrier: without that, GCC deleted the call or could
move it outside the timestamps. Timer: `clock_gettime_nsec_np(CLOCK_UPTIME_RAW)` (41.7 ns ticks; libstdc++'s
`steady_clock` on macOS ticks in 1 µs).

| Mode | Execution |
|---|---|
| `serial` | all tasks in id order on one thread, on the cheapest processor: the speedup baseline T₁ |
| `static` | `omp parallel num_threads(m)`; thread p runs processor p's tasks of a schedule in start order, waiting on per-task acquire/release flags |
| `tasks` | OpenMP tasks, created when the last predecessor finishes; work `cost[t][thread]` (heterogeneity-blind dynamic baseline) |

`ompexec run INSTANCE JOBS PLAN K [TRACE]` — PLAN lines `<mode> <label> <rep> <warmup> <verify> <trace>`;
one CSV row per line (wall, compute, dependency wait, ready-queue time, idle, imbalance, checks); TRACE gets
per-task thread/start/end. `ompexec calibrate ITERS THREADS REPS` — kernel time per concurrent thread and the
cost of a near-empty parallel region. Driver and tests:

```bash
python -m schedlab.ompexec calibrate                                  # X2
python -m schedlab.ompexec execute --calibration results/raw/<X2 dir> --pilot   # X3 pilot, 24 instances
python -m pytest tests/test_ompexec.py                                # V7-V9 from the per-task trace
```

No thread pinning is used (`OMP_PROC_BIND` is not set) and core placement is not recorded, so threads may land on
performance or efficiency cores. Whether pinning is possible on macOS was not tested in this project.
