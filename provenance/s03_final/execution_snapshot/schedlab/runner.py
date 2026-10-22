"""Campaign runner: identical instances for every algorithm, repeats, timing, append-only raw CSV, manifest.

Raw output only. Nothing derived (speedup, efficiency, ...) is computed here; see analysis.py.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import platform
import resource
import signal
import subprocess
import sys
import time
import tomllib
import zlib
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import numpy as np

from functools import partial

from . import adaptive, ga
from .heuristics import HEURISTICS
from .model import bounds, validate
from .workloads import assert_separated, experiment_matrix

NA = "NA"  # unavailable or inapplicable; never 0, never blank

RAW_COLUMNS = [
    "run_uid", "campaign_id", "sub_problem", "workload_class", "family", "split", "instance_id", "instance_hash",
    "instance_seed", "problem_size", "n_edges", "platform", "resource_count", "algorithm", "algo_config_hash",
    "algo_seed", "model_id", "run_id", "makespan_sim", "busy_time_sim", "scheduling_time_s", "decision_time_s",
    "decision_count", "fitness_evals", "peak_rss_kb", "serial_best_sim", "lower_bound_sim", "valid", "status",
    "error_msg", "threads", "workers", "hardware_id", "time_unit", "timestamp_utc",
]

TRACE_COLUMNS = ["run_uid", "generation", "fitness_evals", "elapsed_s", "best_makespan_sim", "mean_makespan_sim"]
DECISION_COLUMNS = ["run_uid", "selected", "candidates", "fallback", "novel"] + adaptive.FEATURES

# name -> (owning sub-problem, scheduler(inst, rng) -> (Schedule, info), parameters that define it[, algorithm seeds])
# Without seeds an algorithm is deterministic and is repeated run.timing_repeats times for timing only.
SCHEDULERS = {name: ("BASE", fn, {"insert": True}) for name, fn in HEURISTICS.items()}


def _pinned(section: dict, key: str, actual: str) -> None:
    """A config may pin a model id; a different model on disk stops the campaign before anything runs."""
    if key in section and section[key] != actual:
        raise ValueError(f"{key} pinned to {section[key]} but the model on disk is {actual}")


def build_schedulers(cfg: dict) -> dict:
    """The heuristics, plus the S01 search methods with a [ga] section and the S03 methods with an [s03] section."""
    out = dict(SCHEDULERS)
    if "ga" in cfg:
        settings = {k: (tuple(v) if isinstance(v, list) else v) for k, v in cfg["ga"].items() if k != "seeds"}
        for method in ga.METHODS:
            out[method] = ("S01", partial(ga.optimize, method=method, **settings),
                           {"method": method, **settings}, cfg["ga"]["seeds"])
    if "s03" in cfg:
        bundle, model_id = adaptive.load(cfg["s03"]["model"])
        _pinned(cfg["s03"], "model_id", model_id)
        for method in adaptive.METHODS:
            entry = ("S03", partial(adaptive.schedule, method=method, bundle=bundle),
                     {"method": method, "model_id": model_id})
            out[method] = entry + ((cfg["s03"]["seeds"],) if method == "RANDOM-SELECT" else ())
        if "model_ga" in cfg["s03"]:  # contingency extension, separately labelled; seeded because GA is stochastic
            bundle, model_id = adaptive.load(cfg["s03"]["model_ga"])
            _pinned(cfg["s03"], "model_ga_id", model_id)
            for method in adaptive.GA_METHODS:
                out[method] = ("S03", partial(adaptive.schedule, method=method, bundle=bundle),
                               {"method": method, "model_id": model_id}, cfg["s03"]["seeds"])
    return out


def _sysctl(key: str) -> str:
    try:
        return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def hardware() -> dict:
    cpu = _sysctl("machdep.cpu.brand_string") or platform.processor() or platform.machine()
    return dict(cpu=cpu, physical_cores=int(_sysctl("hw.physicalcpu") or os.cpu_count()),
                ram_bytes=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"), gpu=None,
                os=platform.platform(), machine=platform.machine())


def _software() -> dict:
    out = {"python": sys.version}
    for pkg in ("numpy", "scipy", "scikit-learn", "torch", "matplotlib", "pandas", "pytest"):
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = NA
    return out


def _git(*args: str):
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def code_hash() -> str:
    """sha256 over schedlab's source files: identifies the code that produced a campaign (no git here)."""
    h = hashlib.sha256()
    for f in sorted(Path(__file__).parent.glob("*.py")):
        h.update(f.name.encode() + b"\0" + f.read_bytes())
    return h.hexdigest()[:16]


def _peak_rss_kb() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss // 1024 if sys.platform == "darwin" else rss  # macOS reports bytes, Linux kB


def _short_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:8]


def _timed_call(fn, inst, rng, timeout_s: float):
    """Run one scheduler call. Only the call itself is inside the timed region."""
    def on_alarm(*_):
        raise TimeoutError(f"exceeded {timeout_s} s")
    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    try:
        t0 = time.perf_counter_ns()
        sched, info = fn(inst, rng)
        elapsed = (time.perf_counter_ns() - t0) / 1e9
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    return sched, info, elapsed


def run_campaign(config_path, out_root="results/raw", schedulers=None) -> Path:
    """Run one campaign and return its raw directory. Never overwrites an existing campaign."""
    config_path = Path(config_path)
    cfg = tomllib.loads(config_path.read_text())
    schedulers = schedulers or build_schedulers(cfg)
    camp, run = cfg["campaign"], cfg["run"]
    started = datetime.now(timezone.utc)
    campaign_id = f"{started:%Y%m%dT%H%M%SZ}-{camp['name']}-{_short_hash(cfg)}"
    out = Path(out_root) / campaign_id
    out.mkdir(parents=True)  # raises if it exists

    log = logging.getLogger(f"schedlab.{campaign_id}")
    log.setLevel(logging.INFO)
    handler = logging.FileHandler(out / "run.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)

    # All declared splits are generated and checked for separation, even those not run.
    matrix = experiment_matrix(cfg["workload"], camp["seed"])
    split_counts = assert_separated(matrix)
    log.info("split separation verified: %s", split_counts)

    hw = hardware()
    hardware_id = f"{hw['cpu']}-{hw['physical_cores']}c-{hw['ram_bytes'] >> 30}GB".replace(" ", "_")
    manifest = dict(
        campaign_id=campaign_id, config_file=str(config_path), config=cfg, config_hash=_short_hash(cfg), code_hash=code_hash(),
        git_commit=_git("rev-parse", "HEAD"), git_dirty=bool(_git("status", "--porcelain")) if _git("rev-parse", "HEAD") else None,
        started_utc=started.isoformat(), finished_utc=None, hardware={hardware_id: hw}, software=_software(),
        runtime=dict(workers=camp["workers"], threads=1, PYTHONHASHSEED=os.environ.get("PYTHONHASHSEED", "unset")),
        models=[], notes=camp.get("notes", ""), split_counts=split_counts, separation_checked=True,
        row_count=0, failed_count=0, wall_time_s=None,
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    if "s03" in cfg:
        manifest["models"] = [dict(model_id=adaptive.load(cfg["s03"][key])[1], path=cfg["s03"][key], role=key,
                                   report=json.loads((Path(cfg["s03"][key]) / "model.json").read_text()))
                              for key in ("model", "model_ga") if key in cfg["s03"]]
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    instances = [i for s in run["splits"] for i in matrix[s]]
    for name in run["algorithms"]:  # one untimed warm-up call per deterministic algorithm
        if len(schedulers[name]) > 3:
            continue  # search methods run for seconds; warm-up only matters for microsecond timings
        try:
            _timed_call(schedulers[name][1], instances[0], np.random.default_rng(0), run["timeout_s"])
        except Exception:
            pass  # a broken or hanging scheduler is recorded per run below, not here

    rows = failed = 0
    t_start = time.perf_counter()
    with open(out / "runs.csv", "w", newline="") as fh, open(out / "ga_trace.csv", "w", newline="") as trace_fh, \
            open(out / "decisions.csv", "w", newline="") as dec_fh:
        writer = csv.DictWriter(fh, fieldnames=RAW_COLUMNS)
        writer.writeheader()
        trace_writer = csv.writer(trace_fh)
        trace_writer.writerow(TRACE_COLUMNS)
        dec_writer = csv.writer(dec_fh)
        dec_writer.writerow(DECISION_COLUMNS)
        for inst in instances:
            meta, b = inst.meta, bounds(inst)
            for name in run["algorithms"]:
                sub_problem, fn, params, *rest = schedulers[name]
                algo_seeds = rest[0] if rest else [None] * run["timing_repeats"]
                for rep, algo_seed in enumerate(algo_seeds):
                    rows += 1
                    row = dict.fromkeys(RAW_COLUMNS, NA)
                    row.update(
                        run_uid=f"{campaign_id}-{rows:06d}", campaign_id=campaign_id, sub_problem=sub_problem,
                        workload_class=meta["label"], family=meta["family"], split=meta["split"],
                        instance_id=inst.id, instance_hash=meta["hash"],
                        instance_seed="-".join(map(str, meta["seed"])), problem_size=inst.n,
                        n_edges=sum(map(len, inst.preds)), platform=meta["platform"], resource_count=inst.m,
                        algorithm=name, algo_config_hash=_short_hash(params), run_id=rep,
                        model_id=params.get("model_id", NA),
                        algo_seed=NA if algo_seed is None else algo_seed,
                        serial_best_sim=b["serial_best"], lower_bound_sim=b["lower_bound"], threads=1,
                        workers=camp["workers"], hardware_id=hardware_id, time_unit="sim_tu",
                    )
                    rng = np.random.default_rng(np.random.SeedSequence(
                        [camp["seed"], 99, zlib.crc32(name.encode()), int(meta["hash"][:8], 16),
                         rep if algo_seed is None else algo_seed]))
                    try:
                        sched, info, elapsed = _timed_call(fn, inst, rng, run["timeout_s"])
                        problems = validate(inst, sched)  # outside the timed region
                        if problems:  # an infeasible schedule has no trustworthy measurements
                            row.update(valid=0, status="invalid", error_msg=problems[0])
                        else:
                            row.update(
                                makespan_sim=sched.makespan,
                                busy_time_sim=float(inst.cost[np.arange(inst.n), sched.proc].sum()),
                                scheduling_time_s=elapsed, decision_time_s=info.get("decision_time_s", NA),
                                decision_count=info.get("decision_count", NA),
                                fitness_evals=info.get("fitness_evals", 1), valid=1, status="ok",
                            )
                            trace_writer.writerows((row["run_uid"], *t) for t in info.get("trace", ()))
                            if "decision" in info:
                                d = info["decision"]
                                x = NA if d["x"] is None else d["x"]
                                dec_writer.writerow([row["run_uid"], d["selected"], "|".join(d["candidates"]),
                                                     int(d["fallback"]), int(d["novel"]),
                                                     *([NA] * len(adaptive.FEATURES) if x is NA else (repr(float(v)) for v in x))])
                    except TimeoutError as e:
                        row.update(status="timeout", error_msg=str(e))
                    except Exception as e:  # keep the campaign going; the failure is a row, not a crash
                        row.update(status="error", error_msg=f"{type(e).__name__}: {e}".splitlines()[0])
                        log.exception("%s failed on %s", name, inst.id)
                    if row["status"] != "ok":
                        failed += 1
                        log.warning("%s on %s: %s (%s)", name, inst.id, row["status"], row["error_msg"])
                    row.update(peak_rss_kb=_peak_rss_kb(), timestamp_utc=datetime.now(timezone.utc).isoformat())
                    writer.writerow(row)
                    fh.flush()
                    trace_fh.flush()
                    dec_fh.flush()

    manifest.update(finished_utc=datetime.now(timezone.utc).isoformat(), row_count=rows, failed_count=failed,
                    wall_time_s=time.perf_counter() - t_start)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    log.info("finished: %d rows, %d not ok", rows, failed)
    log.removeHandler(handler)
    handler.close()
    for f in out.iterdir():  # raw data is immutable from here on
        f.chmod(0o444)
    return out
