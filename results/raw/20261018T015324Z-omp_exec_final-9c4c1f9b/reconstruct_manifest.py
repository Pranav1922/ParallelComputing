"""Reconstruct manifest.json for the M-D campaign after the driver crashed while writing it.

Only recomputable values are written; every value states where it comes from. Fields that existed only in the
crashed process are listed under lost_fields. Measurement files are not modified. A copy of this script and of
the driver's stdout are stored next to the data.
"""
import csv
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/pranavkumar/parallelComputing/cs15")
sys.path.insert(0, str(ROOT))
from schedlab import ompexec as ox  # noqa: E402
from schedlab.workloads import experiment_matrix  # noqa: E402

OUT = ROOT / "results/raw/20261018T015324Z-omp_exec_final-9c4c1f9b"
LOG = Path(__file__).with_name("md_final.log")
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

cfg_path = ROOT / "configs/omp_exec_final.toml"
cfg_text = cfg_path.read_text()
cfg = tomllib.loads(cfg_text)
ex, inp = cfg["execution"], cfg["inputs"]

# the locked files must still be byte-identical to the lock and to the run's own execution_snapshot
lock_ok = {f: sha(ROOT / f) == h for f, h in cfg["lock"]["sha256"].items()}
snap = OUT / "execution_snapshot"
snap_ok = {f: sha(snap / f) == cfg["lock"]["sha256"][f] for f in ox.LOCKED_FILES}
assert all(lock_ok.values()) and all(snap_ok.values()), (lock_ok, snap_ok)
assert sha(snap / "configs/omp_exec_final.toml") == sha(cfg_path)

wcfg = tomllib.loads((ROOT / inp["instances_config"]).read_text())
insts = experiment_matrix(wcfg["workload"], wcfg["campaign"]["seed"])["test_id"]

rows = list(csv.DictReader(open(OUT / "runs.csv")))
keys = [(r["instance_id"], r["us_per_tu"], r["mode"], r["label"], r["rep"], r["warmup"]) for r in rows]
checks = dict(
    runs=len(rows), timed_runs=sum(r["warmup"] == "0" for r in rows),
    order_ok=all(r["order_ok"] == "1" for r in rows), thread_ok=all(r["thread_ok"] == "1" for r in rows),
    once_ok=all(r["once_ok"] == "1" for r in rows), threads_seen_ok=all(r["threads_seen"] == r["threads"] for r in rows),
    verified_runs=sum(r["verified"] == "1" for r in rows),
    verify_ok=all(r["verify_ok"] == "1" for r in rows if r["verified"] == "1"))
with gzip.open(OUT / "task_trace.csv.gz", "rt") as f:
    trace_rows = sum(1 for _ in f) - 1
exp = cfg["expected"]
ids = {r["instance_id"] for r in rows}
log_lines = LOG.read_text().splitlines()
progress = [l for l in log_lines if l.endswith(" s") and "instances," in l]

shutil.copyfile(LOG, OUT / "driver_stdout.log")            # the run's own stdout, verbatim (ends in the traceback)
shutil.copyfile(Path(__file__), OUT / "reconstruct_manifest.py")

host_now = ox._host()
manifest = dict(
    kind=cfg["campaign"]["name"],
    RECONSTRUCTED=True,
    reconstruction=dict(
        reconstructed_utc=datetime.now(timezone.utc).isoformat(),
        reason=("The driver (schedlab/ompexec.py as locked) finished every measurement and closed runs.csv and "
                "task_trace.csv.gz, then raised TypeError while building manifest.json: execute() sets "
                "config_sha256 (instance config) and run_final() passed config_sha256 (locked config) again in "
                "extra_manifest. No manifest was written, post-run checks did not run, files were not sealed. "
                "Measurement files are unchanged; this manifest is written afterwards from recomputable values only."),
        method="reconstruct_manifest.py (copy in this directory); driver stdout: driver_stdout.log",
        deviation="Driver bug fixed after the run (extra keys renamed locked_config_*); the run used the locked "
                  "driver, preserved byte-identically in execution_snapshot/."),
    lost_fields=dict(
        host_start="host dict at start (cpu, cores, RAM, OS, pmset power string): held only in the crashed process",
        host_end="host dict at end, including the power state at the end of the run",
        power_at_launch_exact="exact pmset string seen by the driver; only the fact that its AC check passed is known",
        wall_time_s_exact="perf_counter total; the last progress line gives the time after the last instance",
        manifest_written_utc="time the original manifest would have been written"),
    instances=[i.id for i in insts], reps=ex["reps"], warmup=ex["warmup"],
    granularities_us_per_tu=ex["granularities_us_per_tu"], static_methods=ex["static_methods"],
    calibration=inp["calibration_dir"], iters_per_tu=ex["iters_per_tu"], rederive=inp["rederive_dir"],
    schedules_sha256={i.id: sha(ROOT / inp["rederive_dir"] / "schedules" / f"{i.id}.jobs") for i in insts},
    config=inp["instances_config"], config_sha256=sha(ROOT / inp["instances_config"]),
    locked_config_file=str(cfg_path.relative_to(ROOT)), locked_config_sha256=hashlib.sha256(cfg_text.encode()).hexdigest(),
    ompexec_version=subprocess.run([str(snap / "cpp/build/ompexec"), "version"], capture_output=True, text=True).stdout.strip(),
    ompexec_sha256=cfg["lock"]["sha256"]["cpp/build/ompexec"], omp_env=cfg["omp"]["env"],
    omp_wait_policy=cfg["omp"]["wait_policy"], instance_order_seed=ex["instance_order_seed"],
    code_sha256={f: cfg["lock"]["sha256"][f] for f in ox.LOCKED_FILES},
    lock_verified_at_reconstruction=lock_ok, execution_snapshot_verified=snap_ok,
    power_at_launch=("AC Power: the driver refuses to start otherwise (run_final checks pmset); the operator's "
                     "pmset reading immediately before launch was \"Now drawing from 'AC Power'\""),
    wall_time_s_from_log=float(progress[-1].split(",")[1].strip().rstrip(" s")) if progress else None,
    progress_lines=len(progress),
    file_times_utc=dict(directory_created=datetime.fromtimestamp((OUT).stat().st_birthtime, timezone.utc).isoformat(),
                        runs_csv_last_modified=datetime.fromtimestamp((OUT / "runs.csv").stat().st_mtime, timezone.utc).isoformat()),
    host_at_reconstruction=dict(host_now, note="measured now, not at the run; same machine"),
    checks=checks,
    post_run=dict(
        rows=len(rows), rows_expected=exp["rows"], timed=checks["timed_runs"], timed_expected=exp["timed_rows"],
        verified=checks["verified_runs"], verified_expected=exp["verified_rows"], trace_rows=trace_rows,
        trace_rows_expected=exp["trace_rows"], instances=len(ids), instances_expected=exp["instances"],
        instances_match_config=ids == {i.id for i in insts}, duplicates=len(keys) - len(set(keys)),
        complete=(len(rows) == exp["rows"] and ids == {i.id for i in insts} and len(keys) == len(set(keys))
                  and trace_rows == exp["trace_rows"]),
        output_sha256={str(f.relative_to(OUT)): sha(f) for f in sorted(OUT.rglob("*"))
                       if f.is_file() and f.name != "manifest.json"}),
    note="Measured seconds on the host. sim_makespan_tu is simulated (sim_tu) and only echoed for later "
         "comparison. Raw rows; derived metrics are computed separately.")
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
print(json.dumps(dict(checks=checks, post_run={k: v for k, v in manifest["post_run"].items() if k != "output_sha256"},
                      wall_from_log=manifest["wall_time_s_from_log"])))
