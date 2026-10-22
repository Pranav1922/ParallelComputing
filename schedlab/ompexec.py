"""Driver for the OpenMP executor (cpp/build/ompexec): X2 calibration and X3 measured execution.

    python -m schedlab.ompexec calibrate                          # X2 -> results/raw/<UTC>-omp_calibration-<h>/
    python -m schedlab.ompexec execute --calibration DIR --pilot  # X3 pilot (24 instances)
    python -m schedlab.ompexec execute --calibration DIR          # X3 full (360 test_id instances)

Measured wall-clock seconds only. Simulated makespans (sim_tu) are echoed in their own column, never mixed
with seconds. Schedules come from the M-B re-derivation (results/raw/*-rederive-*/schedules) plus the two
heuristics FCFS-EAT and HEFT computed here; nothing is re-optimized. Runs are strictly sequential.
Raw rows only; derived metrics (speedup, efficiency, simulator gap) are computed later from these files.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import platform
import shutil
import statistics
import subprocess
import tempfile
import time
import tomllib
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import interop
from .heuristics import HEURISTICS
from .workloads import CLASSES, experiment_matrix

ROOT = Path(__file__).resolve().parent.parent
BIN = Path(os.environ.get("OMPEXEC", ROOT / "cpp" / "build" / "ompexec"))
REDERIVE = ROOT / "results" / "raw" / "20261017T162329Z-rederive-21e353a7"
CONFIG = ROOT / "configs" / "s01_final.toml"   # same [workload] and seed in all three final campaigns
GRANULARITIES_US_PER_TU = (10.0, 1.0, 0.1)      # mean task (100 sim_tu): 1 ms, 100 us, 10 us
STATIC_METHODS = ["FCFS-EAT", "HEFT", "GA#s0", "GA#s1", "GA#s2", "GA-KEYS-EFT#s0", "GA-KEYS-EFT#s1",
                  "GA-KEYS-EFT#s2", "RL-S0", "RL-S1", "RL-S2", "ADAPTIVE", "TRY-ALL"]
# Fixed OpenMP runtime settings for every run (recorded in the manifest). No pinning: macOS ignores OMP_PROC_BIND.
OMP_ENV = {"OMP_DYNAMIC": "false", "OMP_MAX_ACTIVE_LEVELS": "1"}


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OMP_", "GOMP_"))}
    return {**env, **OMP_ENV}


def _run(*args: str) -> str:
    if not BIN.exists():
        raise FileNotFoundError(f"{BIN} not built; run `make -C cpp`")
    r = subprocess.run([str(BIN), *args], capture_output=True, text=True, env=_env())
    if r.returncode != 0:
        raise RuntimeError(f"ompexec {args[0]} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _host() -> dict:
    def sysctl(k):
        try:
            return subprocess.run(["sysctl", "-n", k], capture_output=True, text=True).stdout.strip()
        except OSError:
            return "unknown"
    def pmset():
        try:
            return " ".join(subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout.split())
        except OSError:
            return "unknown"
    return dict(cpu=sysctl("machdep.cpu.brand_string"), physical_cores=sysctl("hw.physicalcpu"),
                perf_cores=sysctl("hw.perflevel0.physicalcpu"), efficiency_cores=sysctl("hw.perflevel1.physicalcpu"),
                ram_bytes=sysctl("hw.memsize"), os=platform.platform(), power=pmset())


def _new_dir(out_root: Path, kind: str, payload) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(out_root) / f"{stamp}-{kind}-{hashlib.sha1(json.dumps(payload).encode()).hexdigest()[:8]}"
    out.mkdir(parents=True)
    return out


def _seal(out: Path) -> None:
    for f in out.rglob("*"):
        if f.is_file():
            f.chmod(0o444)


# ---- X2: calibration ---------------------------------------------------------------------------

LIN_ITERS = (1_000, 3_000, 10_000, 30_000, 100_000, 300_000, 1_000_000, 3_000_000)
SPEED_ITERS = 1_000_000


def calibrate(out_root: Path, reps: int = 30) -> Path:
    out = _new_dir(out_root, "omp_calibration", dict(lin=LIN_ITERS, speed=SPEED_ITERS, reps=reps))
    host_start = _host()
    _run("calibrate", "200000000", "1", "1")            # ~0.3 s warm-up: lets the core reach its clock
    rows = []
    for iters in LIN_ITERS:                              # linearity, one thread
        rows += _rows(_run("calibrate", str(iters), "1", str(reps)), "linearity")
    for threads in (1, 2, 4, 8):                         # concurrent speed per thread; fork/join cost
        rows += _rows(_run("calibrate", str(SPEED_ITERS), str(threads), str(reps)), "threads")
    for threads in (1, 2, 4, 8):                         # fork/join of a near-empty region, back to back
        rows += _rows(_run("calibrate", "0", str(threads), str(reps)), "empty")
    with open(out / "calibration.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    lin = [r for r in rows if r["experiment"] == "linearity" and r["kind"] == "kernel"]
    x = np.array([float(r["iters"]) for r in lin])
    y = np.array([float(r["seconds"]) for r in lin])
    slope, intercept = np.polyfit(x, y, 1)
    r2 = 1 - ((y - (slope * x + intercept)) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    big = [float(r["seconds"]) for r in lin if int(r["iters"]) == max(LIN_ITERS)]
    iters_per_us = max(LIN_ITERS) / statistics.median(big) / 1e6
    per_threads = {}
    for threads in (1, 2, 4, 8):
        k = [r for r in rows if r["experiment"] == "threads" and r["kind"] == "kernel" and int(r["threads"]) == threads]
        by_thread = {}
        for r in k:
            by_thread.setdefault(int(r["thread"]), []).append(float(r["seconds"]))
        med = {t: statistics.median(v) for t, v in by_thread.items()}
        e = [float(r["seconds"]) for r in rows if r["experiment"] == "empty" and r["kind"] == "empty_region"
             and int(r["threads"]) == threads]
        per_threads[threads] = dict(
            kernel_median_s_by_thread=med, slowest_over_fastest=max(med.values()) / min(med.values()),
            kernel_cv=statistics.pstdev([float(r["seconds"]) for r in k]) / statistics.mean([float(r["seconds"]) for r in k]),
            empty_region_median_s=statistics.median(e), empty_region_max_s=max(e))
    derived = dict(
        iters_per_us=iters_per_us, linear_fit=dict(slope_s_per_iter=slope, intercept_s=intercept, r2=r2),
        cv_by_iters={i: statistics.pstdev(v) / statistics.mean(v) for i in LIN_ITERS
                     for v in [[float(r["seconds"]) for r in lin if int(r["iters"]) == i]]},
        iters_per_tu={str(g): g * iters_per_us for g in GRANULARITIES_US_PER_TU},
        threads=per_threads)
    manifest = dict(kind="omp_calibration", host_start=host_start, host_end=_host(), ompexec_version=_run("version").strip(),
                    ompexec_sha256=_sha(BIN), omp_env=OMP_ENV, reps=reps, derived=derived,
                    note="Raw kernel timings in calibration.csv; derived values (computed from it) here. Seconds.")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    _seal(out)
    return out


def _rows(text: str, experiment: str) -> list[dict]:
    return [dict(experiment=experiment, **r) for r in csv.DictReader(io.StringIO(text))]


# ---- X3: measured execution ----------------------------------------------------------------------

def pilot_instances(insts):
    """24 of the 36 test_id cells (class x n x m), index 0, balanced: cell indices with (c + s + p) % 3 != 0."""
    classes, sizes, procs = list(CLASSES), [50, 100, 200], [2, 4, 8]
    keep = {(c, n, m) for ci, c in enumerate(classes) for si, n in enumerate(sizes) for pi, m in enumerate(procs)
            if (ci + si + pi) % 3}
    return [i for i in insts if i.meta["index"] == 0 and (i.meta["workload_class"], i.n, i.m) in keep]


def _jobs_text(inst) -> str:
    text = (REDERIVE / "schedules" / f"{inst.id}.jobs").read_text()
    blocks = {}
    for blk in ("\n" + text).split("\nend\n"):   # whole-line "end" ("append" also ends in "end")
        if blk.strip():
            blocks[blk.split()[1]] = blk.lstrip("\n") + "\nend\n"
    for name in ("FCFS-EAT", "HEFT"):
        s = HEURISTICS[name](inst, None)[0]
        blocks[name] = interop.job_text(name, "append", interop.placement_order(s), s.proc)
    return "".join(blocks[k] for k in STATIC_METHODS)


def _plan(inst, g: float, reps: int, warmup: int) -> str:
    """Warm-up passes, then reps passes; method order shuffled per pass (seeded by instance and granularity).
    Rep 0 is verified (kernel results recomputed) and traced per task."""
    methods = [("serial", "-")] + [("static", m) for m in STATIC_METHODS] + [("tasks", "-")]
    rng = np.random.default_rng([int(inst.meta["hash"][:8], 16), int(round(g * 1000))])
    lines = []
    for w in range(warmup):
        lines += [f"{mo} {la} {w} 1 0 0" for mo, la in (methods[i] for i in rng.permutation(len(methods)))]
    for rep in range(reps):
        lines += [f"{mo} {la} {rep} 0 {int(rep == 0)} {int(rep == 0)}"
                  for mo, la in (methods[i] for i in rng.permutation(len(methods)))]
    return "\n".join(lines) + "\n"


MANIFEST_KEYS = {"kind", "instances", "reps", "warmup", "granularities_us_per_tu", "static_methods", "calibration",
                 "iters_per_tu", "rederive", "schedules_sha256", "config", "config_sha256", "ompexec_version",
                 "ompexec_sha256", "omp_env", "code_sha256", "host_start", "host_end", "wall_time_s", "checks",
                 "instance_order_seed", "note"}


def execute(calibration: Path, out_root: Path, pilot: bool, reps: int = 10, warmup: int = 2,
            kind: str | None = None, trace_gzip: bool = False, extra_manifest: dict | None = None,
            instance_order_seed: int = 20261017, before_run=None) -> Path:
    clash = MANIFEST_KEYS & set(extra_manifest or {})
    if clash:  # checked before anything runs (the M-D run crashed on such a clash after measuring)
        raise ValueError(f"extra_manifest would overwrite {sorted(clash)}")
    cal = json.loads((calibration / "manifest.json").read_text())
    if cal["ompexec_sha256"] != _sha(BIN):
        raise ValueError("ompexec binary differs from the one calibrated; recalibrate")
    ipt = cal["derived"]["iters_per_tu"]
    cfg = tomllib.loads(CONFIG.read_text())
    insts = experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])["test_id"]
    if pilot:
        insts = pilot_instances(insts)
    kind = kind or ("omp_pilot" if pilot else "omp_exec")
    out = _new_dir(out_root, kind, dict(n=len(insts), reps=reps, warmup=warmup, cal=calibration.name))
    if before_run:
        before_run(out)
    host_start = _host()
    order = np.random.default_rng(instance_order_seed).permutation(len(insts))
    t0 = time.perf_counter()
    header_done = trace_header = False
    with open(out / "runs.csv", "w", newline="") as runs_f, (gzip.open(out / "task_trace.csv.gz", "wt", newline="") if trace_gzip
                                                     else open(out / "task_trace.csv", "w", newline="")) as tr_f, \
            tempfile.TemporaryDirectory() as tmp:
        for k, idx in enumerate(order):
            inst = insts[idx]
            ses = interop.Session(inst, tmp)                 # writes instance.txt
            (Path(tmp) / "jobs.txt").write_text(_jobs_text(inst))
            for g in np.random.default_rng([k, 7]).permutation(GRANULARITIES_US_PER_TU):
                g = float(g)
                (Path(tmp) / "plan.txt").write_text(_plan(inst, g, reps, warmup))
                trace = Path(tmp) / "trace.csv"
                text = _run("run", str(ses.path), str(Path(tmp) / "jobs.txt"), str(Path(tmp) / "plan.txt"),
                            repr(ipt[str(g)]), str(trace))
                lines = text.splitlines()
                if not header_done:
                    runs_f.write("us_per_tu,workload_class," + lines[0] + "\n")
                    header_done = True
                for line in lines[1:]:
                    runs_f.write(f"{g!r},{inst.meta['workload_class']},{line}\n")
                tl = trace.read_text().splitlines()
                if not trace_header:
                    tr_f.write("instance_id,us_per_tu," + tl[0] + "\n")
                    trace_header = True
                for line in tl[1:]:
                    tr_f.write(f"{inst.id},{g!r},{line}\n")
            runs_f.flush()
            print(f"{k + 1}/{len(insts)} instances, {time.perf_counter() - t0:.0f} s", flush=True)

    rows = list(csv.DictReader(open(out / "runs.csv")))
    checks = dict(
        runs=len(rows), timed_runs=sum(r["warmup"] == "0" for r in rows),
        order_ok=all(r["order_ok"] == "1" for r in rows), thread_ok=all(r["thread_ok"] == "1" for r in rows),
        once_ok=all(r["once_ok"] == "1" for r in rows),
        threads_seen_ok=all(r["threads_seen"] == r["threads"] for r in rows),
        verified_runs=sum(r["verified"] == "1" for r in rows),
        verify_ok=all(r["verify_ok"] == "1" for r in rows if r["verified"] == "1"))
    manifest = dict(
        kind=kind, instances=[i.id for i in insts], reps=reps, warmup=warmup, granularities_us_per_tu=GRANULARITIES_US_PER_TU,
        static_methods=STATIC_METHODS, calibration=str(calibration.relative_to(ROOT)), iters_per_tu=ipt,
        rederive=str(REDERIVE.relative_to(ROOT)),
        schedules_sha256={i.id: _sha(REDERIVE / "schedules" / f"{i.id}.jobs") for i in insts},
        config=str(CONFIG.relative_to(ROOT)), config_sha256=_sha(CONFIG),
        ompexec_version=_run("version").strip(), ompexec_sha256=_sha(BIN), omp_env=OMP_ENV,
        code_sha256={f: _sha(ROOT / "schedlab" / f) for f in ("ompexec.py", "interop.py", "heuristics.py")},
        host_start=host_start, host_end=_host(), wall_time_s=round(time.perf_counter() - t0, 1), checks=checks,
        instance_order_seed=instance_order_seed)
    assert set(manifest) | {"note"} == MANIFEST_KEYS, "keep MANIFEST_KEYS in sync with the manifest"
    manifest.update(extra_manifest or {})
    manifest = dict(manifest,
        note="Measured seconds on the host. sim_makespan_tu is simulated (sim_tu) and only echoed for later "
             "comparison. Raw rows; derived metrics are computed separately.")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    _seal(out)
    return out


# ---- M-D: the locked full campaign ----------------------------------------------------------------

LOCKED_FILES = ("cpp/ompexec.cpp", "cpp/schedsim.hpp", "cpp/Makefile", "cpp/build/ompexec", "schedlab/ompexec.py",
                "schedlab/interop.py", "schedlab/heuristics.py", "schedlab/model.py", "schedlab/workloads.py")


def run_final(config_path: Path, out_root: Path) -> Path:
    """Run the locked M-D campaign once. Refuses to start unless every locked hash matches, the settings equal
    this module's, and the host is on AC power. Never reruns; integrity failures are reported, not repaired."""
    cfg_text = config_path.read_text()
    cfg = tomllib.loads(cfg_text)
    lock, ex = cfg["lock"], cfg["execution"]
    bad = [f for f in LOCKED_FILES if _sha(ROOT / f) != lock["sha256"].get(f)]
    for key in ("calibration_manifest", "rederive_manifest", "instances_config"):
        if _sha(ROOT / cfg["inputs"][key]) != lock["sha256"].get(cfg["inputs"][key]):
            bad.append(cfg["inputs"][key])
    if bad:
        raise SystemExit(f"lock mismatch, not starting: {bad}")
    if (list(ex["static_methods"]) != STATIC_METHODS or tuple(ex["granularities_us_per_tu"]) != GRANULARITIES_US_PER_TU
            or cfg["omp"]["env"] != OMP_ENV or ROOT / cfg["inputs"]["rederive_dir"] != REDERIVE
            or ROOT / cfg["inputs"]["instances_config"] != CONFIG):
        raise SystemExit("config settings differ from the locked driver constants, not starting")
    cal = json.loads((ROOT / cfg["inputs"]["calibration_manifest"]).read_text())["derived"]["iters_per_tu"]
    if cal != ex["iters_per_tu"]:
        raise SystemExit("iters_per_tu in the config differs from the calibration, not starting")
    power = _host()["power"]
    if "AC Power" not in power:
        raise SystemExit(f"not on mains power ({power}), not starting")

    def snapshot(out: Path):
        snap = out / "execution_snapshot"
        for f in LOCKED_FILES + (str(config_path.relative_to(ROOT)),):
            (snap / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / f, snap / f)

    out = execute(ROOT / cfg["inputs"]["calibration_dir"], out_root, pilot=False, reps=ex["reps"], warmup=ex["warmup"],
                  kind=cfg["campaign"]["name"], trace_gzip=True, instance_order_seed=ex["instance_order_seed"],
                  before_run=snapshot,
                  # locked_config_*: execute() already records config / config_sha256 (the instance config).
                  # Fixed 2026-10-18 after the M-D run crashed on the duplicate keyword (see docs/MD_ACCEPTANCE_REPORT.md).
                  extra_manifest=dict(locked_config_file=str(config_path.relative_to(ROOT)),
                                      locked_config_sha256=hashlib.sha256(cfg_text.encode()).hexdigest(),
                                      power_at_launch=power, omp_wait_policy=cfg["omp"]["wait_policy"]))
    for f in out.rglob("*"):
        if f.is_file():
            f.chmod(0o644)  # unseal briefly to add the post-run checks
    m = json.loads((out / "manifest.json").read_text())
    rows = list(csv.DictReader(open(out / "runs.csv")))
    exp = cfg["expected"]
    keys = [(r["instance_id"], r["us_per_tu"], r["mode"], r["label"], r["rep"], r["warmup"]) for r in rows]
    insts = {r["instance_id"] for r in rows}
    m["post_run"] = dict(
        rows=len(rows), rows_expected=exp["rows"], timed=m["checks"]["timed_runs"], timed_expected=exp["timed_rows"],
        verified=m["checks"]["verified_runs"], verified_expected=exp["verified_rows"],
        instances=len(insts), instances_expected=exp["instances"], duplicates=len(keys) - len(set(keys)),
        complete=len(rows) == exp["rows"] and len(insts) == exp["instances"] and len(keys) == len(set(keys)),
        output_sha256={str(f.relative_to(out)): _sha(f) for f in sorted(out.rglob("*"))
                       if f.is_file() and f.name != "manifest.json"})
    (out / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
    _seal(out)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schedlab.ompexec")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calibrate")
    c.add_argument("--reps", type=int, default=30)
    c.add_argument("--out", type=Path, default=ROOT / "results" / "raw")
    e = sub.add_parser("execute")
    e.add_argument("--calibration", type=Path, required=True)
    e.add_argument("--pilot", action="store_true")
    e.add_argument("--reps", type=int, default=10)
    e.add_argument("--warmup", type=int, default=2)
    e.add_argument("--out", type=Path, default=ROOT / "results" / "raw")
    f = sub.add_parser("final", help="M-D: the locked full campaign (configs/omp_exec_final.toml)")
    f.add_argument("--config", type=Path, default=ROOT / "configs" / "omp_exec_final.toml")
    f.add_argument("--out", type=Path, default=ROOT / "results" / "raw")
    a = ap.parse_args(argv)
    if a.cmd == "final":
        out = run_final(a.config.resolve(), a.out)
        m = json.loads((out / "manifest.json").read_text())
        print(out)
        print(json.dumps(m["checks"]), json.dumps({k: v for k, v in m["post_run"].items() if k != "output_sha256"}))
        ok = all(v for k, v in m["checks"].items() if k.endswith("_ok")) and m["post_run"]["complete"]
        return 0 if ok else 1
    if a.cmd == "calibrate":
        out = calibrate(a.out, a.reps)
        print(out)
        print(json.dumps(json.loads((out / "manifest.json").read_text())["derived"], indent=1))
        return 0
    out = execute(a.calibration.resolve(), a.out, a.pilot, a.reps, a.warmup)
    ch = json.loads((out / "manifest.json").read_text())["checks"]
    print(out)
    print(json.dumps(ch))
    return 0 if all(v for k, v in ch.items() if k.endswith("_ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
