"""V6: re-derive the accepted campaigns' search, learned and adaptive schedules, and check them.

For every instance of the three accepted final campaigns, the scheduler of each listed method is rebuilt
from the campaign's locked config (runner.build_schedulers, pinned models) and called with the same
per-run random stream the runner used. The resulting schedule must reproduce the accepted makespan_sim
exactly; S03 decisions must equal decisions.csv; the C++ simulator must reproduce the schedule bit for bit.

    python -m schedlab.rederive [--workers 8] [--limit K] [--out results/raw]

Accepted campaigns are read-only inputs. Output goes to a new <UTC>-rederive-<hash>/ directory:
  rederived.csv          one row per re-derived run (exact values as hex floats)
  decisions_check.csv    S03 decision comparison per accepted run
  schedules/<id>.jobs    every re-derived schedule as a schedsim job block (append mode, start-time order),
                         the input of the OpenMP executor in milestone M-C
  manifest.json          inputs, their sha256, code and binary hashes, summary
Nothing is timed: re-derivation reproduces schedules, not scheduling times. Workers only parallelize this
offline check; they do not affect any value (every run has its own seeded stream).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
import time
import tomllib
import zlib
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import interop
from .model import Schedule, validate
from .workloads import experiment_matrix

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGNS = {
    "S01": ("configs/s01_final.toml", "results/raw/20261017T044734Z-s01_final-430d8a10",
            ["GA", "GA-UNSEEDED", "GA-KEYS-EFT", "RANDOM-SEARCH", "HILL-CLIMB"]),
    "S02": ("configs/s02_final.toml", "results/raw/20261017T115054Z-s02_final-898ee9e1",
            ["RL-S0", "RL-S1", "RL-S2", "RL-NOHEFTFEAT"]),
    "S03": ("configs/s03_final.toml", "results/raw/20261017T083329Z-s03_final-b8e5be9a",
            ["ADAPTIVE", "ADAPTIVE-TOP2", "ADAPTIVE-NOGUARD", "TRY-ALL"]),
}

_SCHED: dict = {}  # per worker process: sub-problem -> (campaign seed, schedulers)


def _init_worker() -> None:
    from .runner import build_schedulers
    os.chdir(ROOT)  # model paths in the configs are relative to the repository root
    for sub, (cfg_path, _, _) in CAMPAIGNS.items():
        cfg = tomllib.loads(Path(cfg_path).read_text())
        _SCHED[sub] = (cfg["campaign"]["seed"], build_schedulers(cfg))


def _rng(camp_seed: int, name: str, inst_hash: str, rep_or_seed: int):
    """The runner's per-run stream (runner.run_campaign, identical in all three execution snapshots)."""
    return np.random.default_rng(np.random.SeedSequence(
        [camp_seed, 99, zlib.crc32(name.encode()), int(inst_hash[:8], 16), rep_or_seed]))


def _work(task):
    """Re-derive every listed method on one instance. Deterministic methods are called once (stream of
    repeat 0); every repeat of a deterministic method gets the same schedule, which the check confirms."""
    sub, inst = task
    camp_seed, schedulers = _SCHED[sub]
    out = []
    for name in CAMPAIGNS[sub][2]:
        _, fn, _, *rest = schedulers[name]
        for seed in (rest[0] if rest else [None]):
            sched, info = fn(inst, _rng(camp_seed, name, inst.meta["hash"], 0 if seed is None else seed))
            d = info.get("decision")
            out.append(dict(algorithm=name, algo_seed=seed, proc=sched.proc, start=sched.start, finish=sched.finish,
                            decision=None if d is None else dict(
                                selected=d["selected"], candidates="|".join(d["candidates"]),
                                fallback=int(d["fallback"]), novel=int(d["novel"]),
                                x=None if d["x"] is None else [repr(float(v)) for v in d["x"]])))
    return sub, inst.id, out


def _accepted(raw: Path, names: set) -> tuple[dict, dict]:
    runs: dict = {}
    with open(raw / "runs.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["algorithm"] in names:
                runs.setdefault((r["instance_id"], r["algorithm"]), []).append(r)
    dec = {}
    if (raw / "decisions.csv").exists():
        with open(raw / "decisions.csv", newline="") as f:
            rd = csv.reader(f)
            next(rd)
            for row in rd:
                dec[row[0]] = row[1:]
    return runs, dec


def _label(name: str, seed) -> str:
    return name if seed is None else f"{name}#s{seed}"


def rederive(out_root: Path, workers: int, limit: int | None) -> Path:
    os.chdir(ROOT)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = hashlib.sha1(json.dumps({k: v[2] for k, v in CAMPAIGNS.items()}).encode()).hexdigest()[:8]
    out = Path(out_root) / f"{stamp}-rederive-{tag}"
    (out / "schedules").mkdir(parents=True)

    tasks, insts, accepted = [], {}, {}
    for sub, (cfg_path, raw, names) in CAMPAIGNS.items():
        cfg = tomllib.loads(Path(cfg_path).read_text())
        matrix = experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])
        chosen = [i for s in cfg["run"]["splits"] for i in matrix[s]]
        if limit:
            chosen = chosen[::max(1, len(chosen) // limit)][:limit]
        for i in chosen:
            insts[i.id] = i
        tasks += [(sub, i) for i in chosen]
        accepted[sub] = _accepted(Path(raw), set(names))
    tasks.sort(key=lambda t: -t[1].n)  # long GA runs first, for load balance

    rows, dec_rows, jobs = [], [], {}
    t0 = time.perf_counter()
    done = 0
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as pool:
        for sub, iid, results in pool.map(_work, tasks, chunksize=1):
            inst = insts[iid]
            runs, dec = accepted[sub]
            for r in results:
                name, seed = r["algorithm"], r["algo_seed"]
                acc = [a for a in runs.get((iid, name), [])
                       if seed is None or a["algo_seed"] == str(seed)]
                mk = float(r["finish"].max()) if inst.n else 0.0
                s = Schedule(r["proc"], r["start"], r["finish"])
                label = _label(name, seed)
                jobs.setdefault(iid, []).append((label, s))
                rows.append(dict(
                    sub_problem=sub, instance_id=iid, instance_hash=inst.meta["hash"], split=inst.meta["split"],
                    n=inst.n, m=inst.m, algorithm=name, algo_seed="NA" if seed is None else seed, label=label,
                    makespan_rederived=repr(mk), makespan_rederived_hex=mk.hex(),
                    accepted_rows=len(acc),
                    accepted_hash_equal=all(a["instance_hash"] == inst.meta["hash"] for a in acc),
                    accepted_status_ok=all(a["status"] == "ok" for a in acc),
                    accepted_makespan_equal=bool(acc) and all(float(a["makespan_sim"]) == mk for a in acc),
                    valid=not validate(inst, s), cpp_identical="", cpp_makespan_equal=""))
                if r["decision"] is not None or any(a["run_uid"] in dec for a in acc):
                    for a in acc:
                        got = dec.get(a["run_uid"])
                        d = r["decision"]
                        want = None if d is None else [d["selected"], d["candidates"], str(d["fallback"]),
                                                       str(d["novel"])] + (d["x"] or ["NA"] * (len(got) - 4 if got else 0))
                        dec_rows.append(dict(instance_id=iid, algorithm=name, run_uid=a["run_uid"],
                                             accepted="|".join(got) if got else "MISSING",
                                             rederived="|".join(want) if want else "NONE",
                                             equal=got is not None and want is not None and got == want))
            done += 1
            if done % 50 == 0 or done == len(tasks):
                print(f"{done}/{len(tasks)} instance-campaign tasks, {time.perf_counter() - t0:.0f} s", flush=True)

    # C++ check: each schedule replayed by schedsim in append mode, start-time order (exact for semi-active
    # schedules; every method here builds semi-active schedules, see ARCHITECTURE.md §3.1)
    by_key = {(r["instance_id"], r["label"]): r for r in rows}
    with tempfile.TemporaryDirectory() as tmp:
        for iid, js in jobs.items():
            blocks = [interop.job_text(label, "append", interop.placement_order(s), s.proc) for label, s in js]
            (out / "schedules" / f"{iid}.jobs").write_text("".join(blocks))
            got = interop.Session(insts[iid], tmp).eval(blocks)
            for label, s in js:
                c, r = got[label], by_key[(iid, label)]
                ok = not isinstance(c, str)
                r["cpp_identical"] = ok and interop.identical(c, s)
                r["cpp_makespan_equal"] = ok and c.makespan == float(r["makespan_rederived"])

    for name, data in (("rederived.csv", rows), ("decisions_check.csv", dec_rows)):
        with open(out / name, "w", newline="") as f:
            if data:
                w = csv.DictWriter(f, fieldnames=list(data[0]))
                w.writeheader()
                w.writerows(data)

    def bad(r):
        return not (r["accepted_rows"] and r["accepted_hash_equal"] and r["accepted_status_ok"]
                    and r["accepted_makespan_equal"] and r["valid"] and r["cpp_identical"] and r["cpp_makespan_equal"])
    per_method = {}
    for r in rows:
        k = f'{r["sub_problem"]}/{r["algorithm"]}'
        pm = per_method.setdefault(k, dict(rederived=0, accepted_rows=0, reproduced=0, cpp_identical=0))
        pm["rederived"] += 1
        pm["accepted_rows"] += r["accepted_rows"]
        pm["reproduced"] += bool(r["accepted_makespan_equal"])
        pm["cpp_identical"] += bool(r["cpp_identical"])
    summary = dict(
        instances=len(insts), tasks=len(tasks), rederived_runs=len(rows),
        accepted_rows_compared=sum(r["accepted_rows"] for r in rows),
        reproduced_exactly=sum(bool(r["accepted_makespan_equal"]) for r in rows),
        valid=sum(r["valid"] for r in rows), cpp_identical=sum(bool(r["cpp_identical"]) for r in rows),
        decisions_compared=len(dec_rows), decisions_equal=sum(d["equal"] for d in dec_rows),
        per_method=per_method,
        not_reproduced=[{k: r[k] for k in ("sub_problem", "instance_id", "label")} for r in rows if bad(r)],
        decision_mismatches=[{k: d[k] for k in ("instance_id", "algorithm", "run_uid")} for d in dec_rows if not d["equal"]],
        elapsed_s=round(time.perf_counter() - t0, 1), workers=workers, limit=limit)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    manifest = dict(
        kind="rederive", created_utc=stamp, campaigns={sub: dict(config=c, config_sha256=sha(c), raw=r,
                                                                 runs_sha256=sha(Path(r) / "runs.csv"), methods=n)
                                                        for sub, (c, r, n) in CAMPAIGNS.items()},
        code_sha256={f: sha(ROOT / "schedlab" / f) for f in
                     ("rederive.py", "interop.py", "runner.py", "ga.py", "rl.py", "adaptive.py", "model.py",
                      "heuristics.py", "workloads.py")},
        schedsim_sha256=sha(interop.BIN), schedsim_version=interop._run("version").strip(),
        note="Read-only re-derivation of accepted schedules; accepted campaigns are not modified. sim_tu, not seconds.",
        summary=summary)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    for f in out.rglob("*"):
        if f.is_file():
            f.chmod(0o444)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schedlab.rederive")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="instances per campaign (pilot); default all")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "raw")
    a = ap.parse_args(argv)
    out = rederive(a.out, a.workers, a.limit)
    s = json.loads((out / "manifest.json").read_text())["summary"]
    print(out)
    print(json.dumps({k: v for k, v in s.items() if k not in ("per_method", "not_reproduced", "decision_mismatches")}))
    print("not reproduced:", len(s["not_reproduced"]), "decision mismatches:", len(s["decision_mismatches"]))
    return 0 if not s["not_reproduced"] and not s["decision_mismatches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
