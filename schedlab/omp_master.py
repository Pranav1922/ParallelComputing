"""The manual's 19-column master.csv for a measured OpenMP campaign (one row per run, raw rows unchanged).

    python -m schedlab.omp_master results/raw/<omp campaign> [--out-root results]

Derived values are computed from the raw rows here: Speedup = median SERIAL wall time on the same instance and
granularity / this run's wall time; Efficiency = Speedup / Threads. Student_ID / Batch_ID come from
configs/identity.toml (placeholders until confirmed; this is not the identity-dependent final export).
Execution_Time is measured seconds (Time_Unit = s); the simulated makespan is kept separately in sim_tu.
"""
from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import MANUAL_COLUMNS

ROOT = Path(__file__).resolve().parent.parent
SUB = {"GA": "S01", "GA-KEYS-EFT": "S01", "RL": "S02", "ADAPTIVE": "S03", "TRY-ALL": "S03"}
NA = "NA"


def _sub(label: str) -> str:
    base = label.split("#")[0]
    return SUB.get(base, "S02" if base.startswith("RL-") else "BASE")


def derive(raw_dir: Path, identity: dict) -> pd.DataFrame:
    r = pd.read_csv(raw_dir / "runs.csv", float_precision="round_trip")
    algo = np.where(r["mode"] == "static", r["label"], np.where(r["mode"] == "tasks", "OMP-TASKS", "SERIAL"))
    timed_serial = r[(r["mode"] == "serial") & (r.warmup == 0)]
    t1 = timed_serial.groupby(["instance_id", "us_per_tu"]).wall_s.median().rename("T1")
    r = r.join(t1, on=["instance_id", "us_per_tu"])
    speed = r.T1 / r.wall_s
    sub = pd.Series(algo).map(_sub)
    m = pd.DataFrame({
        "Student_ID": sub.map(identity["student_id"]), "Batch_ID": identity["batch_id"],
        "Workload": r.workload_class, "Dataset": r.instance_id, "Problem_Size": r.n, "Algorithm": algo,
        "Parallel_Model": r["mode"].map({"serial": "SERIAL", "static": "OMP-STATIC", "tasks": "OMP-TASKS"}),
        "Hardware": "Apple M4 (4P+6E cores), GCC 15.2 libgomp", "Resource_Count": r.threads, "Threads": r.threads,
        "Execution_Time": r.wall_s, "Speedup": speed, "Efficiency": speed / r.threads,
        "Communication_Time": NA,                                     # no data moves along edges in the kernel
        "Synchronization_Time": r.dep_wait_s.where(r["mode"] == "static", other=np.nan),  # thread-seconds waiting
        "Scheduling_Time": NA,                                        # schedules were computed earlier, in Python
        "Memory_Use": NA, "Energy_if_available": NA,
        "Run_ID": [f"{raw_dir.name}-{i + 1:06d}" for i in range(len(r))],
    })
    m["Synchronization_Time"] = m.Synchronization_Time.astype(object).where(m.Synchronization_Time.notna(), NA)
    extra = pd.DataFrame({
        "Time_Unit": "s", "Speedup_Baseline": "SERIAL: all tasks on one thread, cheapest processor, same instance "
                                              "and granularity (median of 10 timed reps)",
        "Sub_Problem": sub, "Granularity_us_per_tu": r.us_per_tu, "Rep": r.rep, "Warmup": r.warmup,
        "Sim_Makespan_tu": r.sim_makespan_tu, "Compute_Time": r.compute_s,
        "Ready_Queue_Time_incl_contention": r.ready_queue_s, "Idle_Time": r.idle_s, "Imbalance": r.imbalance,
        "Verified": r.verified, "Integrity_OK": ((r.order_ok == 1) & (r.thread_ok == 1) & (r.once_ok == 1)).astype(int),
    })
    out = pd.concat([m, extra], axis=1)
    assert list(out.columns[:len(MANUAL_COLUMNS)]) == MANUAL_COLUMNS
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schedlab.omp_master")
    ap.add_argument("raw", type=Path)
    ap.add_argument("--out-root", type=Path, default=ROOT / "results")
    ap.add_argument("--identity", type=Path, default=ROOT / "configs" / "identity.toml")
    a = ap.parse_args(argv)
    out = a.out_root / "derived" / a.raw.name
    out.mkdir(parents=True, exist_ok=True)
    df = derive(a.raw, tomllib.loads(a.identity.read_text()))
    df.to_csv(out / "master.csv", index=False, na_rep="NA")
    print(out / "master.csv", len(df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
