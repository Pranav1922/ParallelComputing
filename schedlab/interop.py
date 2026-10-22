"""Bridge to the C++ workload simulator (cpp/schedsim) and cross-language validation.

Instances and schedules cross the boundary as text files with every double written as a hex float
(float.hex / C99 %a), so values are compared exactly. File formats: cpp/README.md.

    python -m schedlab.interop xval-heuristics --config configs/s01_final.toml \\
        --campaign results/raw/<s01> --campaign results/raw/<s03> --campaign results/raw/<s02>

writes a new results/raw/<UTC>-cpp_xval_heuristics-<hash>/ directory and never touches the campaigns it reads.
This module does not change any existing schedlab module; accepted campaigns are read-only inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .heuristics import HEURISTICS
from .model import Instance, Schedule, bounds
from .workloads import experiment_matrix

ROOT = Path(__file__).resolve().parent.parent
BIN = Path(os.environ.get("SCHEDSIM", ROOT / "cpp" / "build" / "schedsim"))


# ---- file formats ---------------------------------------------------------------------------

def instance_text(inst: Instance) -> str:
    edges = [(u, v) for u in range(inst.n) for v in inst.succs[u]]
    lines = ["schedsim-instance 1", f"id {inst.id}", f"size {inst.n} {inst.m} {len(edges)}"]
    lines += [f"{u} {v}" for u, v in edges]
    lines += [" ".join(float(c).hex() for c in row) for row in inst.cost_rows]
    return "\n".join(lines + ["end", ""])


def parse_instance_text(text: str) -> tuple[str, int, int, list, list]:
    """(id, n, m, edges, cost rows) from the instance format; used to check the C++ round trip."""
    tok = text.split()
    assert tok[:2] == ["schedsim-instance", "1"] and tok[2] == "id" and tok[4] == "size", "not an instance file"
    iid, n, m, e = tok[3], int(tok[5]), int(tok[6]), int(tok[7])
    i = 8
    edges = [(int(tok[i + 2 * k]), int(tok[i + 2 * k + 1])) for k in range(e)]
    i += 2 * e
    cost = [[float.fromhex(tok[i + t * m + p]) for p in range(m)] for t in range(n)]
    assert tok[i + n * m] == "end"
    return iid, n, m, edges, cost


def _ints(xs) -> str:
    return " ".join(str(int(x)) for x in xs)


def _hexes(xs) -> str:
    return " ".join(float(x).hex() for x in xs)


def job_text(label: str, mode: str, order, proc) -> str:
    return f"job {label} {mode}\norder {_ints(order)}\nproc {_ints(proc)}\nend\n"


def keys_text(label: str, keys, proc=None) -> str:
    p = "proc -" if proc is None else f"proc {_ints(proc)}"
    return f"keys {label}\nkey {_hexes(keys)}\n{p}\nend\n"


def check_text(label: str, s: Schedule) -> str:
    return (f"check {label}\nproc {_ints(s.proc)}\nstart {_hexes(s.start)}\n"
            f"finish {_hexes(s.finish)}\nend\n")


def parse_results(text: str) -> dict:
    """label -> Schedule, or label -> error message (str)."""
    out, lines, i = {}, text.splitlines(), 0
    while i < len(lines):
        head = lines[i].split(" ", 2)
        if head[0] == "error":
            out[head[1]] = head[2] if len(head) > 2 else ""
            i += 2
            continue
        assert head[0] == "result", f"unexpected line {lines[i]!r}"
        label = head[1]
        rows = []
        i += 2  # skip the makespan line; it is recomputed from finish
        while lines[i] != "end":
            p, s, f = lines[i].split()
            rows.append((int(p), float.fromhex(s), float.fromhex(f)))
            i += 1
        i += 1
        proc, start, finish = (zip(*rows) if rows else ((), (), ()))
        out[label] = Schedule(np.array(proc, dtype=np.int64), np.array(start, dtype=np.float64),
                              np.array(finish, dtype=np.float64))
    return out


def parse_verdicts(text: str) -> dict:
    out, label = {}, None
    for line in text.splitlines():
        if line.startswith("verdict "):
            label = line.split()[1]
            out[label] = []
        elif line.startswith("violation "):
            out[label].append(line[len("violation "):])
    return out


# ---- running the binary -----------------------------------------------------------------------

def _run(*args: str) -> str:
    if not BIN.exists():
        raise FileNotFoundError(f"{BIN} not built; run `make -C cpp`")
    r = subprocess.run([str(BIN), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"schedsim {args[0]} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


class Session:
    """One instance written once to a temporary directory; every call reuses that file."""

    def __init__(self, inst: Instance, workdir: str | Path):
        self.inst = inst
        self.dir = Path(workdir)
        self.path = self.dir / "instance.txt"
        self.path.write_text(instance_text(inst))

    def _with(self, cmd: str, name: str, body: str) -> str:
        f = self.dir / name
        f.write_text(body)
        return _run(cmd, str(self.path), str(f))

    def dump(self) -> str:
        return _run("dump", str(self.path))

    def bounds(self) -> dict:
        vals = _run("bounds", str(self.path)).split()[1:]
        return dict(zip(("serial_best", "cp_min", "work_lb", "lower_bound"), map(float.fromhex, vals)))

    def ranks(self) -> tuple[np.ndarray, np.ndarray]:
        """(mean cost, upward rank) per task, as computed in C++."""
        rows = [line.split() for line in _run("ranks", str(self.path)).splitlines()]
        return (np.array([float.fromhex(r[0]) for r in rows]), np.array([float.fromhex(r[1]) for r in rows]))

    def heuristics(self) -> dict:
        return parse_results(_run("heuristics", str(self.path)))

    def eval(self, blocks: list[str]) -> dict:
        return parse_results(self._with("eval", "jobs.txt", "".join(blocks)))

    def validate(self, checks: list[str]) -> dict:
        return parse_verdicts(self._with("validate", "checks.txt", "".join(checks)))


def placement_order(s: Schedule) -> list[int]:
    """Start-time order (ties by id): replaying it in append mode reproduces a semi-active schedule exactly."""
    return sorted(range(len(s.start)), key=lambda t: (s.start[t], t))


def identical(a: Schedule, b: Schedule) -> bool:
    return (np.array_equal(a.proc, b.proc) and np.array_equal(a.start, b.start)
            and np.array_equal(a.finish, b.finish))


# ---- V4: the six heuristics on every campaign instance ------------------------------------------

def _accepted_rows(campaigns: list[Path]) -> dict:
    """(instance_id, algorithm) -> list of (campaign, makespan, serial_best, lower_bound, instance_hash)."""
    out: dict = {}
    names = set(HEURISTICS)
    for camp in campaigns:
        with open(camp / "runs.csv", newline="") as f:
            for r in csv.DictReader(f):
                if r["algorithm"] in names and r["status"] == "ok":
                    out.setdefault((r["instance_id"], r["algorithm"]), []).append(
                        (camp.name, float(r["makespan_sim"]), float(r["serial_best_sim"]), float(r["lower_bound_sim"]),
                         r["instance_hash"]))
    return out


def xval_heuristics(config: Path, campaigns: list[Path], out_root: Path) -> Path:
    cfg = tomllib.loads(config.read_text())
    splits = cfg["run"]["splits"]
    matrix = experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])
    insts = [i for s in splits for i in matrix[s]]
    accepted = _accepted_rows(campaigns)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = hashlib.sha1(json.dumps([str(config), [c.name for c in campaigns]]).encode()).hexdigest()[:8]
    out = out_root / f"{stamp}-cpp_xval_heuristics-{tag}"
    out.mkdir(parents=True)
    rows, t0 = [], time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        for inst in insts:
            ses = Session(inst, tmp)
            cpp, py_b, cpp_b = ses.heuristics(), bounds(inst), ses.bounds()
            for name, fn in HEURISTICS.items():
                for mode in ("insert", "append"):
                    py = fn(inst, None, insert=mode == "insert")[0]
                    c = cpp[f"{name}:{mode}"]
                    acc = accepted.get((inst.id, name), []) if mode == "insert" else []
                    rows.append(dict(
                        instance_id=inst.id, split=inst.meta["split"], n=inst.n, m=inst.m, algorithm=name, mode=mode,
                        makespan_py=py.makespan.hex(), makespan_cpp=c.makespan.hex(),
                        arrays_identical=identical(py, c),
                        accepted_rows=len(acc),
                        accepted_hash_equal=all(a[4] == inst.meta["hash"] for a in acc) if acc else "",
                        accepted_makespan_equal=all(a[1] == c.makespan for a in acc) if acc else "",
                        bounds_equal=all(py_b[k] == cpp_b[k] for k in py_b),
                        accepted_bounds_equal=all(a[2] == cpp_b["serial_best"] and a[3] == cpp_b["lower_bound"]
                                                  for a in acc) if acc else ""))
    with open(out / "comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ins = [r for r in rows if r["mode"] == "insert"]
    summary = dict(
        instances=len(insts), comparisons=len(rows),
        arrays_identical=sum(r["arrays_identical"] for r in rows),
        bounds_equal=sum(r["bounds_equal"] for r in rows),
        accepted_rows_compared=sum(r["accepted_rows"] for r in ins),
        insert_comparisons_with_accepted_rows=sum(1 for r in ins if r["accepted_rows"]),
        accepted_makespan_equal=sum(1 for r in ins if r["accepted_makespan_equal"] is True),
        accepted_bounds_equal=sum(1 for r in ins if r["accepted_bounds_equal"] is True),
        mismatches=[{k: r[k] for k in ("instance_id", "algorithm", "mode")} for r in rows
                    if not r["arrays_identical"] or not r["bounds_equal"] or r["accepted_makespan_equal"] is False
                    or r["accepted_hash_equal"] is False
                    or r["accepted_bounds_equal"] is False],
        elapsed_s=round(time.perf_counter() - t0, 1))
    manifest = dict(
        kind="cpp_xval_heuristics", created_utc=stamp, config=str(config),
        config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(), splits=splits,
        campaigns_read=[str(c) for c in campaigns],
        campaign_runs_sha256={c.name: hashlib.sha256((c / "runs.csv").read_bytes()).hexdigest() for c in campaigns},
        schedsim_binary=str(BIN.relative_to(ROOT)) if BIN.is_relative_to(ROOT) else str(BIN),
        schedsim_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), schedsim_version=_run("version").strip(),
        interop_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        note="Read-only comparison; accepted campaigns are inputs and are not modified. Times are sim_tu.",
        summary=summary)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schedlab.interop")
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("xval-heuristics", help="V4: six heuristics, Python vs C++, against accepted campaign rows")
    x.add_argument("--config", type=Path, required=True)
    x.add_argument("--campaign", type=Path, action="append", default=[])
    x.add_argument("--out", type=Path, default=ROOT / "results" / "raw")
    a = ap.parse_args(argv)
    out = xval_heuristics(a.config, a.campaign, a.out)
    s = json.loads((out / "manifest.json").read_text())["summary"]
    print(out)
    print(json.dumps({k: v for k, v in s.items() if k != "mismatches"}), "mismatches:", len(s["mismatches"]))
    return 0 if not s["mismatches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
